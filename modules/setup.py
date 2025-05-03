from setuptools import setup, Extension

module = Extension(
    'fcache_cpp',
    sources=['modules/fcache.cpp'],
    extra_compile_args=['-std=c++17', '-O3'],  # High optimization level
)

setup(
    name='fcache_cpp',
    version='0.1',
    description='C++ implementation of FileCacheManager',
    ext_modules=[module],
)
