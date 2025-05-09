#!/usr/bin/env python
import os
import sys
import errno
from threading import Thread
from fuse import FUSE, Operations, FuseOSError
from modules.OPT_base import Base_Opt
from modules.fcache import FileCacheManager
from modules.OPT_swg import SWG_Opt
from modules.OPT_markov import Markov_Opt
from modules.OPT_markovadaptive import AdaptiveMarkov_Opt

class QuarkFS(Operations):
    OPTM: Base_Opt
    CACHE: FileCacheManager
    enable_opt: bool

    def __init__(self, root: str, optimizer: Base_Opt, fcache: FileCacheManager):
        print(f'Optimizer: {optimizer.name}')
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
                self.OPTM.status_fmt()
                self.CACHE.cache_status()
            elif ui == 'enable':
                self.enable_opt = not self.enable_opt
                print(f'{'enabled' if self.enable_opt else 'disabled'} optimizations')
            elif ui.startswith('cache'):
                fn = ui.split('cache')[1].strip()
                self.CACHE.request_file(fn)
                print(f'requested {fn}')
            elif ui.startswith('pred'):
                box = ui.split(' ')
                fn = box[1].strip()
                times = int(box[2].strip()) if len(box) > 2 else 1
                prediction = self.OPTM.predict_nexts(fn, times)
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
                #print(f"{p_header}: {path} @ offset {offset} size {size}")
                if self.enable_opt:
                    predictions = self.OPTM.predict_nexts(path, num_predictions=2)
                    if predictions:
                        #print(f'Predicted: {predictions}')
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
        #print(f"Write: {path} @ offset {offset} size {len(data)}")
        return written

    def create(self, path, mode, fi=None):
        full_path = self.full_path(path)
        print(f"Creating file: {path} with mode {oct(mode)}")
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def chmod(self, path, mode):
        full_path = self.full_path(path)
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

    def access(self, path, amode):
        full_path = self.full_path(path)
        if not os.access(full_path, amode):
            raise FuseOSError(errno.EACCES)
        return 0

    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        return os.fsync(fh)

    def fsyncdir(self, path, datasync, fh):
        return 0

    def chown(self, path, uid, gid):
        full_path = self.full_path(path)
        return os.chown(full_path, uid, gid)

    def utimens(self, path, times=None):
        full_path = self.full_path(path)
        return os.utime(full_path, times)

    def truncate(self, path, length, fh=None):
        full_path = self.full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)
        return 0

    def readlink(self, path):
        full_path = self.full_path(path)
        return os.readlink(full_path)

    def mknod(self, path, mode, dev):
        full_path = self.full_path(path)
        return os.mknod(full_path, mode, dev)

    def symlink(self, target, source):
        target_full = self.full_path(target)
        return os.symlink(source, target_full)

    def link(self, target, source):
        target_full = self.full_path(target)
        source_full = self.full_path(source)
        return os.link(source_full, target_full)

    def rename(self, old, new):
        old_full = self.full_path(old)
        new_full = self.full_path(new)
        return os.rename(old_full, new_full)

    def statfs(self, path):
        full_path = self.full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def opendir(self, path):
        full_path = self.full_path(path)
        return os.open(full_path, os.O_RDONLY)

    def releasedir(self, path, fh):
        return os.close(fh)

    def destroy(self, path):
        pass

    def getxattr(self, path, name, position=0):
        full_path = self.full_path(path)
        try:
            return os.getxattr(full_path, name)
        except OSError as e:
            # Proper error handling
            if e.errno == errno.ENOTSUP:
                raise FuseOSError(errno.ENOTSUP)
            if e.errno == errno.ENODATA:
                raise FuseOSError(errno.ENODATA)
            # General case
            raise FuseOSError(errno.ENOTSUP)

    def listxattr(self, path):
        full_path = self.full_path(path)
        try:
            return os.listxattr(full_path)
        except OSError:
            # If not supported, return empty list
            return []

    def removexattr(self, path, name):
        full_path = self.full_path(path)
        try:
            return os.removexattr(full_path, name)
        except OSError as e:
            if e.errno == errno.ENOTSUP:
                raise FuseOSError(errno.ENOTSUP)
            if e.errno == errno.ENODATA:
                raise FuseOSError(errno.ENODATA)
            # General case
            raise FuseOSError(errno.ENOTSUP)

    def setxattr(self, path, name, value, options, position=0):
        full_path = self.full_path(path)
        try:
            return os.setxattr(full_path, name, value, options)
        except OSError:
            raise FuseOSError(errno.ENOTSUP)

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
