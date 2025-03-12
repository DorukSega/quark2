#!/usr/bin/env python
import os
import sys
from threading import Thread
from time import sleep
from fuse import FUSE, Operations
from modules.base import Base_Opt
from modules.fcache import FileCacheManager
from modules.swg import SWG_Opt

class QuarkFS(Operations):
    OPTM: Base_Opt
    CACHE: FileCacheManager
    def __init__(self, root: str, optimizer:Base_Opt, fcache:FileCacheManager):
        self.root = os.path.realpath(root)
        self.OPTM = optimizer
        self.CACHE = fcache
        self.CACHE.root = self.root
        Thread(target=self._log_cache, daemon=True).start()

    def _log_cache(self):
        while True: 
            self.CACHE.cache_status()
            sleep(5)

    # Helper to map paths
    def full_path(self, partial):
        return os.path.join(self.root, partial.lstrip('/'))

    def read(self, path, size, offset, fh):
        def log_predict(p_header='Read'): # logs the read and predicts next
            if self.OPTM.last_file_read() != path:
                self.OPTM.log_read(path)
                print(f"{p_header}: {path} @ offset {offset} size {size}")
                predictions = self.OPTM.predict_nexts(path)
                if predictions:
                    print(f'Predicted: {predictions}')
                    if isinstance(predictions, str):
                        # single file instead of multiple
                        self.CACHE.request_file(predictions)
                    elif isinstance(predictions, list): # TODO: confirm order works
                        for file in predictions:
                            self.CACHE.request_file(file)

        # Check if the file is already in cache
        #buff_cached, len_cached = self.CACHE.is_in_cache(path)
        buff_cached = self.CACHE.read_cache(path, size, offset)
        #if len_cached: print(f'{len(buff_cached)} == {len_cached}')
        if buff_cached:
            log_predict('Cache hit')
            return buff_cached
        os.lseek(fh, offset, os.SEEK_SET)
        buf = os.read(fh, size)
        log_predict()
        return buf

    def write(self, path, data, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        written = os.write(fh, data)
        print(f"Write: {path} @ offset {offset} size {len(data)}")
        return written

    def create(self, path, mode, fi=None):
        full_path = self.full_path(path)
        print(f"Creating file: {path} with mode {oct(mode)}")
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def chmod(self, path, mode):
        full_path = self.full_path(path)
        print(f"Changing mode for: {path} to {oct(mode)}")
        return os.chmod(full_path, mode)

    def getattr(self, path, fh=None):
        full_path = self.full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                    'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self.full_path(path)
        dirents = ['.', '..'] + os.listdir(full_path)
        for r in dirents:
            yield r

    def open(self, path, flags):
        full_path = self.full_path(path)
        return os.open(full_path, flags)

    def release(self, path, fh):
        return os.close(fh)

    def mkdir(self, path, mode):
        full_path = self.full_path(path)
        print(f"Creating directory: {path}")
        return os.mkdir(full_path, mode)

    def unlink(self, path):
        full_path = self.full_path(path)
        print(f"Deleting file: {path}")
        return os.unlink(full_path)

    def rmdir(self, path):
        full_path = self.full_path(path)
        print(f"Removing directory: {path}")
        return os.rmdir(full_path)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} <source-dir> <mount-point>')
        exit(1)
    # TODO: make the source_dir a temporary folder? or write a seperate benchmark program that reads and writes
    source_dir = sys.argv[1]
    mount_point = sys.argv[2]

    test_OPT = SWG_Opt()
    file_cache = FileCacheManager()

    while False: # for debugging cacher
        # cmp --silent ./data/a ./test || echo "files are different"
        user_input = input("Enter file to request or 's' for status: ")
        if user_input.lower() == 's':
            file_cache.cache_status()
        if user_input.lower() == 'x':
            break
        else:
            file_cache.request_file(user_input)

    fuse = FUSE(QuarkFS(source_dir, test_OPT, file_cache), mount_point, foreground=True)
