#!/usr/bin/env python
import os
import sys
from fuse import FUSE, Operations
from opts.base import Base_Opt

class QuarkFS(Operations):
    def __init__(self, root, optimizer:Base_Opt):
        self.root = os.path.realpath(root)
        self.OPTM = optimizer

    # Helper to map paths
    def full_path(self, partial):
        return os.path.join(self.root, partial.lstrip('/'))

    def read(self, path, size, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        buf = os.read(fh, size)
        # logs the read
        self.OPTM.log_read(path)
        print(f"Intercepted read: {path} @ offset {offset} size {size}")
        self.OPTM.status_fmt()
        return buf

    def write(self, path, data, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        written = os.write(fh, data)
        print(f"Intercepted write: {path} @ offset {offset} size {len(data)}")
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

    source_dir = sys.argv[1]
    mount_point = sys.argv[2]

    test_OPT = Base_Opt()

    fuse = FUSE(QuarkFS(source_dir, test_OPT), mount_point, foreground=True)

