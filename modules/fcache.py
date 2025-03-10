import threading
import os
import gc
import queue
from collections import OrderedDict


class FileCacheManager:
    def __init__(self, memory_limit=4 * 1024 ** 3, chunk_size=1024 * 1024):
        self.memory_limit = memory_limit
        self.chunk_size = chunk_size
        self.cache = OrderedDict()
        self.cache_lock = threading.Lock()
        self.read_queue = queue.Queue()
        self.current_cache_size = 0
        threading.Thread(target=self._file_reader_thread, daemon=True).start()

    def request_file(self, filepath):
        if os.path.getsize(filepath) > self.memory_limit:
            print(f'{filepath} is larger than cache limit, {os.path.getsize(filepath)} > {self.memory_limit}\n')
            return

        with self.cache_lock:
            if filepath in self.cache:
                self.cache.move_to_end(filepath)
                return
        self.read_queue.put(filepath)

    def is_in_cache(self, filepath):
        with self.cache_lock:
            if filepath in self.cache:
                return self.cache[filepath]['data'], self.cache[filepath]['size']
        return None, 0

    def cache_status(self):
        with self.cache_lock:
            print(f"Cache: {self.current_cache_size / (1024 ** 2):.2f} MB | Files:", end=" ")
            print(", ".join(f"{file}({data['size'] / (1024 ** 2):.2f}MB)" for file, data in self.cache.items()))
        queue_items = list(self.read_queue.queue)
        print(f"Queue: {', '.join(map(str, queue_items))}")

    def _file_reader_thread(self):
        while True:
            filepath = self.read_queue.get()
            
            if not os.path.exists(filepath):
                continue

            with self.cache_lock:
                if filepath in self.cache and os.path.getsize(filepath) == self.cache[filepath]['size']:
                    self.cache.move_to_end(filepath)
                    continue

            with open(filepath, 'rb') as f:
                file_data = bytearray()
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break

                    file_data.extend(chunk)
                    chunk_len = len(chunk)

                    with self.cache_lock:
                        if filepath not in self.cache:
                            self.cache[filepath] = {'data': file_data, 'size': chunk_len}
                            self.current_cache_size += chunk_len
                        else:
                            self.cache[filepath]['size'] += chunk_len
                            self.current_cache_size += chunk_len

                        self.cache.move_to_end(filepath)

                        while self.current_cache_size > self.memory_limit:
                            _, removed_info = self.cache.popitem(last=False)
                            self.current_cache_size -= removed_info['size']
                            del removed_info
                            gc.collect()
