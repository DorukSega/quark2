#!/usr/bin/env python
import os
import sys
from threading import Thread
from fuse import FUSE, Operations
from modules.OPT_base import Base_Opt
from modules.fcache import FileCacheManager
from modules.OPT_swg import SWG_Opt
from modules.OPT_markov import Markov_Opt
from modules.OPT_LSTM import LSTM_Opt

class QuarkFS(Operations):
    OPTM: Base_Opt
    CACHE: FileCacheManager
    enable_opt: bool

    def __init__(self, root: str, optimizer: Base_Opt, fcache: FileCacheManager):
        self.root = os.path.realpath(root)
        self.OPTM = optimizer
        self.CACHE = fcache
        self.CACHE.root = self.root
        self.enable_opt = False
        Thread(target=self._log_cache, daemon=True).start()
        self.prediction_count = 0 #TODO:make it so it only predicts every x runs

    def _log_cache(self):
        while True:
            ui = input().lower()
            if ui == 's':
                self.CACHE.cache_status()
                self.OPTM.status_fmt()
            elif ui == 'enable':
                self.enable_opt = not self.enable_opt
                print(f'{'enabled' if self.enable_opt else 'disabled'} optimizations')
            elif ui.startswith('cache'):
                fn = ui.split('cache')[1].strip()
                self.CACHE.request_file(fn)
                print(f'requested {fn}')
            elif ui.startswith('pred'):
                fn = ui.split('pred')[1].strip()
                prediction = self.OPTM.predict_nexts(fn)
                if prediction:
                    print(f'predicted {prediction}')
            elif ui == 'exit':
                break

    # Helper to map paths
    def full_path(self, partial):
        return os.path.join(self.root, partial.lstrip('/'))

    def read(self, path, size, offset, fh):
        def log_predict(p_header='Read'):  # logs the read and predicts next
            if self.OPTM.last_file_read() != path:
                self.OPTM.log_read(path)
                print(f"{p_header}: {path} @ offset {offset} size {size}")
                if self.enable_opt:
                    predictions = self.OPTM.predict_nexts(path)
                    if predictions:
                        print(f'Predicted: {predictions}')
                        if isinstance(predictions, str):
                            self.CACHE.request_file(predictions)
                        elif isinstance(predictions, list):  # TODO: confirm order works
                            for file in predictions:
                                self.CACHE.request_file(file)

        # Check if the file is already in cache
        # buff_cached, len_cached = self.CACHE.is_in_cache(path)
        buff_cached = self.CACHE.read_cache(path, size, offset)
        # if len_cached: print(f'{len(buff_cached)} == {len_cached}')
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

    test_OPT = Markov_Opt()
    file_cache = FileCacheManager()

    # cmp --silent ./data/a ./test || echo "files are different"
    try:
        fuse = FUSE(QuarkFS(source_dir, test_OPT, file_cache),
                mount_point, foreground=True)
    except RuntimeError:
        print(f'run umount {mount_point}')
