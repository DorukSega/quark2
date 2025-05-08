# Try to import the C++ implementation
from fcache_cpp import FileCacheManager as CppFileCacheManager

class FileCacheManager:
    '''
    Python wrapper for the C++ FileCacheManager implementation.
    Maintains the same API as the original Python version.
    '''
    def __init__(self, memory_limit=8 * 1024 ** 3, chunk_size=1024 * 1024):
        self._cpp_manager = CppFileCacheManager(memory_limit, chunk_size)
        self._root = '.'
    
    def request_file(self, filepath):
        self._cpp_manager.request_file(filepath)
    
    def is_in_cache(self, filepath):
        return self._cpp_manager.is_in_cache(filepath)
    
    def read_cache(self, filepath, size, offset):
        return self._cpp_manager.read_cache(filepath, size, offset)
    
    def cache_status(self):
        self._cpp_manager.cache_status()
    
    @property
    def root(self):
        return self._root
    
    @root.setter
    def root(self, value):
        self._root = value
        self._cpp_manager.set_root(value)

print("Using high-performance C++ FileCacheManager implementation")
