import threading
import os
import gc
import queue
from collections import OrderedDict

def normalize_path(path):
    normalized = os.path.normpath(path).lstrip('/')
    return normalized

class FileCacheManager:
    def __init__(self, memory_limit=4 * 1024 ** 3, chunk_size=1024 * 1024):
        self.memory_limit = memory_limit
        self.chunk_size = chunk_size
        self.cache = OrderedDict()
        self.cache_lock = threading.Lock()
        self.read_queue = queue.Queue()
        self.current_cache_size = 0
        self.root = '.'
        threading.Thread(target=self._file_reader_thread, daemon=True).start()

    def request_file(self, filepath):
        filepath = normalize_path(filepath)
        self.read_queue.put(filepath)

    def is_in_cache(self, filepath):
        filepath = normalize_path(filepath)
        with self.cache_lock:
            if filepath in self.cache:
                return self.cache[filepath], 1
        return None, 0

    def cache_status(self):
        with self.cache_lock:
            print(f"Cache: {self.current_cache_size / (1024 ** 2):.2f} MB | Files:", end=" ")
            print(", ".join(f"{file}" for file, _ in self.cache.items()))
        queue_items = list(self.read_queue.queue)
        print(f"Queue: {', '.join(map(str, queue_items))}")

    def _file_reader_thread(self):
        while True:
            filepath_virt = self.read_queue.get()
            filepath_virt = normalize_path(filepath_virt)
            filepath_real = os.path.join(self.root, filepath_virt)

            if not os.path.exists(filepath_real):
                print(f'File {filepath_real} does not exist')
                continue
            file_size = os.path.getsize(filepath_real) 
            if file_size > self.memory_limit:
                continue

            with self.cache_lock:
                if filepath_virt in self.cache:
                    self.cache.move_to_end(filepath_virt)
                    continue
                while self.current_cache_size+file_size > self.memory_limit:
                    _, removed_info = self.cache.popitem(last=False)
                    self.current_cache_size -= removed_info['size']
                    del removed_info
                    gc.collect()

            file_data = b''
            with open(filepath_real, 'rb') as f:
                file_data= f.read()
            assert file_size == len(file_data)

            with self.cache_lock:
                self.cache[filepath_virt] = file_data
                self.current_cache_size += file_size
                self.cache.move_to_end(filepath_virt)
