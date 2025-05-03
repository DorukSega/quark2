// fcache.cpp - C++ implementation of FileCacheManager
#include <Python.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <list>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <fstream>
#include <iostream>
#include <filesystem>

namespace fs = std::filesystem;

// Helper function to normalize paths
std::string normalize_path(const std::string& path) {
    std::string result = path;
    // Replace backslashes with forward slashes
    for (auto& c : result) {
        if (c == '\\') c = '/';
    }
    // Remove leading slash if present
    if (!result.empty() && result[0] == '/') {
        result = result.substr(1);
    }
    return result;
}

// LRU cache implementation
class FileCache {
private:
    struct CacheEntry {
        std::vector<char> data;
        size_t size;
    };
    
    std::list<std::string> lru_order;
    std::unordered_map<std::string, std::pair<std::list<std::string>::iterator, CacheEntry>> cache;
    size_t current_size;
    size_t max_size;
    std::mutex mutex;
    
public:
    FileCache(size_t max_size) : current_size(0), max_size(max_size) {}
    
    bool contains(const std::string& path) {
        std::lock_guard<std::mutex> lock(mutex);
        return cache.find(path) != cache.end();
    }
    
    std::vector<char>* get(const std::string& path) {
        std::lock_guard<std::mutex> lock(mutex);
        auto it = cache.find(path);
        if (it == cache.end()) {
            return nullptr;
        }
        
        // Move to front of LRU
        lru_order.erase(it->second.first);
        lru_order.push_front(path);
        it->second.first = lru_order.begin();
        
        return &it->second.second.data;
    }
    
    void insert(const std::string& path, std::vector<char>&& data) {
        std::lock_guard<std::mutex> lock(mutex);
        size_t size = data.size();
        
        // Check if already exists
        auto it = cache.find(path);
        if (it != cache.end()) {
            // Update existing entry
            current_size -= it->second.second.size;
            current_size += size;
            
            // Update LRU position
            lru_order.erase(it->second.first);
            lru_order.push_front(path);
            
            // Update entry
            it->second.first = lru_order.begin();
            it->second.second.data = std::move(data);
            it->second.second.size = size;
            return;
        }
        
        // Make room if needed
        while (!lru_order.empty() && current_size + size > max_size) {
            // Remove least recently used item
            std::string oldest = lru_order.back();
            lru_order.pop_back();
            
            size_t removed_size = cache[oldest].second.size;
            current_size -= removed_size;
            cache.erase(oldest);
        }
        
        // Add new entry
        lru_order.push_front(path);
        CacheEntry entry{std::move(data), size};
        cache[path] = {lru_order.begin(), std::move(entry)};
        current_size += size;
    }
    
    size_t get_current_size() const {
        return current_size;
    }
    
    std::vector<std::string> get_cached_files() {
        std::lock_guard<std::mutex> lock(mutex);
        return std::vector<std::string>(lru_order.begin(), lru_order.end());
    }
};

// File reader thread
class FileReader {
private:
    std::string root_dir;
    std::shared_ptr<FileCache> cache;
    std::queue<std::string> file_queue;
    std::mutex queue_mutex;
    std::condition_variable queue_cv;
    bool running;
    std::thread worker;
    
    void worker_function() {
        while (running) {
            std::string filepath;
            
            {
                std::unique_lock<std::mutex> lock(queue_mutex);
                queue_cv.wait(lock, [this]() { return !file_queue.empty() || !running; });
                
                if (!running) break;
                
                filepath = file_queue.front();
                file_queue.pop();
            }
            
            process_file(filepath);
        }
    }
    
    void process_file(const std::string& filepath_virt) {
        std::string normalized_path = normalize_path(filepath_virt);
        fs::path filepath_real = fs::path(root_dir) / normalized_path;
        
        if (!fs::exists(filepath_real)) {
            std::cerr << "File " << filepath_real << " does not exist" << std::endl;
            return;
        }
        
        try {
            size_t file_size = fs::file_size(filepath_real);
            
            // Check if already in cache
            if (cache->contains(normalized_path)) {
                return;
            }
            
            // Read file
            std::ifstream file(filepath_real, std::ios::binary);
            if (!file) {
                std::cerr << "Failed to open file: " << filepath_real << std::endl;
                return;
            }
            
            std::vector<char> file_data(file_size);
            file.read(file_data.data(), file_size);
            
            if (file.gcount() != static_cast<std::streamsize>(file_size)) {
                std::cerr << "Read size mismatch: expected " << file_size 
                          << ", got " << file.gcount() << std::endl;
                return;
            }
            
            // Add to cache
            cache->insert(normalized_path, std::move(file_data));
            
        } catch (const std::exception& e) {
            std::cerr << "Error processing file " << filepath_real << ": " << e.what() << std::endl;
        }
    }
    
public:
    FileReader(const std::string& root, std::shared_ptr<FileCache> cache)
        : root_dir(root), cache(cache), running(true) {
        worker = std::thread(&FileReader::worker_function, this);
    }
    
    ~FileReader() {
        {
            std::lock_guard<std::mutex> lock(queue_mutex);
            running = false;
        }
        queue_cv.notify_all();
        if (worker.joinable()) {
            worker.join();
        }
    }
    
    void request_file(const std::string& filepath) {
        {
            std::lock_guard<std::mutex> lock(queue_mutex);
            file_queue.push(filepath);
        }
        queue_cv.notify_one();
    }
    
    void set_root(const std::string& root) {
        root_dir = root;
    }
    
    std::vector<std::string> get_queue_items() {
        std::lock_guard<std::mutex> lock(queue_mutex);
        std::vector<std::string> items;
        std::queue<std::string> queue_copy = file_queue;
        while (!queue_copy.empty()) {
            items.push_back(queue_copy.front());
            queue_copy.pop();
        }
        return items;
    }
};

// FileCacheManager implementation
class FileCacheManagerImpl {
private:
    std::shared_ptr<FileCache> cache;
    std::unique_ptr<FileReader> reader;
    size_t memory_limit;
    size_t chunk_size;
    
public:
    FileCacheManagerImpl(size_t memory_limit, size_t chunk_size)
        : memory_limit(memory_limit), chunk_size(chunk_size) {
        cache = std::make_shared<FileCache>(memory_limit);
        reader = std::make_unique<FileReader>(".", cache);
    }
    
    void request_file(const std::string& filepath) {
        reader->request_file(filepath);
    }
    
    bool is_in_cache(const std::string& filepath, std::vector<char>** data_ptr) {
        std::string normalized = normalize_path(filepath);
        *data_ptr = cache->get(normalized);
        return *data_ptr != nullptr;
    }
    
    std::vector<char>* read_cache(const std::string& filepath, size_t size, size_t offset) {
        std::string normalized = normalize_path(filepath);
        return cache->get(normalized);
    }
    
    void cache_status() {
        double mb_size = cache->get_current_size() / (1024.0 * 1024.0);
        std::cout << "Cache: " << mb_size << " MB | Files: ";
        
        auto files = cache->get_cached_files();
        for (size_t i = 0; i < files.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << files[i];
        }
        std::cout << std::endl;
        
        std::cout << "Queue: ";
        auto queue_items = reader->get_queue_items();
        for (size_t i = 0; i < queue_items.size(); ++i) {
            if (i > 0) std::cout << ", ";
            std::cout << queue_items[i];
        }
        std::cout << std::endl;
    }
    
    void set_root(const std::string& root) {
        reader->set_root(root);
    }
};

// Python module implementation
extern "C" {
    // Define the Python object structure
    typedef struct {
        PyObject_HEAD
        FileCacheManagerImpl* impl;
    } FCMObject;

    static void FCM_dealloc(FCMObject* self) {
        delete self->impl;
        Py_TYPE(self)->tp_free((PyObject*)self);
    }
    
    static PyObject* FCM_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
        static char* kwlist[] = {(char*)"memory_limit", (char*)"chunk_size", nullptr};
        size_t memory_limit = 4ULL * 1024 * 1024 * 1024; // 4 GB default
        size_t chunk_size = 1024 * 1024; // 1 MB default
        
        if (!PyArg_ParseTupleAndKeywords(args, kwds, "|KK", kwlist, &memory_limit, &chunk_size)) {
            return nullptr;
        }
        
        FCMObject* self = (FCMObject*)type->tp_alloc(type, 0);
        if (self != nullptr) {
            // Create the C++ implementation
            self->impl = new FileCacheManagerImpl(memory_limit, chunk_size);
        }
        return (PyObject*)self;
    }
    
    static PyObject* FCM_request_file(PyObject* self, PyObject* args) {
        const char* filepath;
        if (!PyArg_ParseTuple(args, "s", &filepath)) {
            return nullptr;
        }
        
        FCMObject* fcm = (FCMObject*)self;
        fcm->impl->request_file(filepath);
        Py_RETURN_NONE;
    }
    
    static PyObject* FCM_is_in_cache(PyObject* self, PyObject* args) {
        const char* filepath;
        if (!PyArg_ParseTuple(args, "s", &filepath)) {
            return nullptr;
        }
        
        FCMObject* fcm = (FCMObject*)self;
        std::vector<char>* data = nullptr;
        bool in_cache = fcm->impl->is_in_cache(filepath, &data);
        
        if (in_cache) {
            // Return (bytes, 1) - bytes is just a placeholder for compatibility
            PyObject* bytes = PyBytes_FromStringAndSize("", 0);
            PyObject* result = Py_BuildValue("Oi", bytes, 1);
            Py_DECREF(bytes);
            return result;
        } else {
            // Return (None, 0)
            Py_INCREF(Py_None);
            return Py_BuildValue("Oi", Py_None, 0);
        }
    }
    
    static PyObject* FCM_read_cache(PyObject* self, PyObject* args) {
        const char* filepath;
        size_t size, offset;
        if (!PyArg_ParseTuple(args, "snn", &filepath, &size, &offset)) {
            return nullptr;
        }
        
        FCMObject* fcm = (FCMObject*)self;
        std::vector<char>* data = fcm->impl->read_cache(filepath, size, offset);
        if (!data) {
            Py_RETURN_NONE;
        }
        
        if (offset >= data->size()) {
            Py_RETURN_NONE;
        }
        
        size_t end = std::min(offset + size, data->size());
        return PyBytes_FromStringAndSize(data->data() + offset, end - offset);
    }
    
    static PyObject* FCM_cache_status(PyObject* self, PyObject* Py_UNUSED(ignored)) {
        FCMObject* fcm = (FCMObject*)self;
        fcm->impl->cache_status();
        Py_RETURN_NONE;
    }
    
    static PyObject* FCM_set_root(PyObject* self, PyObject* args) {
        const char* root;
        if (!PyArg_ParseTuple(args, "s", &root)) {
            return nullptr;
        }
        
        FCMObject* fcm = (FCMObject*)self;
        fcm->impl->set_root(root);
        Py_RETURN_NONE;
    }
    
    static PyMethodDef FCM_methods[] = {
        {"request_file", FCM_request_file, METH_VARARGS, "Request a file to be cached"},
        {"is_in_cache", FCM_is_in_cache, METH_VARARGS, "Check if a file is in the cache"},
        {"read_cache", FCM_read_cache, METH_VARARGS, "Read a file from the cache"},
        {"cache_status", FCM_cache_status, METH_NOARGS, "Print cache status"},
        {"set_root", FCM_set_root, METH_VARARGS, "Set the root directory"},
        {nullptr, nullptr, 0, nullptr}  // Sentinel
    };
    
    static PyTypeObject FileCacheManagerType = {
        PyVarObject_HEAD_INIT(nullptr, 0)
        "fcache_cpp.FileCacheManager",  /* tp_name */
        sizeof(FCMObject),              /* tp_basicsize */
        0,                              /* tp_itemsize */
        (destructor)FCM_dealloc,        /* tp_dealloc */
        0,                              /* tp_vectorcall_offset */
        0,                              /* tp_getattr */
        0,                              /* tp_setattr */
        0,                              /* tp_as_async */
        0,                              /* tp_repr */
        0,                              /* tp_as_number */
        0,                              /* tp_as_sequence */
        0,                              /* tp_as_mapping */
        0,                              /* tp_hash */
        0,                              /* tp_call */
        0,                              /* tp_str */
        0,                              /* tp_getattro */
        0,                              /* tp_setattro */
        0,                              /* tp_as_buffer */
        Py_TPFLAGS_DEFAULT,             /* tp_flags */
        "C++ implementation of FileCacheManager", /* tp_doc */
        0,                              /* tp_traverse */
        0,                              /* tp_clear */
        0,                              /* tp_richcompare */
        0,                              /* tp_weaklistoffset */
        0,                              /* tp_iter */
        0,                              /* tp_iternext */
        FCM_methods,                    /* tp_methods */
        0,                              /* tp_members */
        0,                              /* tp_getset */
        0,                              /* tp_base */
        0,                              /* tp_dict */
        0,                              /* tp_descr_get */
        0,                              /* tp_descr_set */
        0,                              /* tp_dictoffset */
        0,                              /* tp_init */
        0,                              /* tp_alloc */
        FCM_new,                        /* tp_new */
    };
    
    static PyModuleDef fcache_module = {
        PyModuleDef_HEAD_INIT,
        .m_name = "fcache_cpp",
        .m_doc = "C++ implementation of FileCacheManager",
        .m_size = -1,
    };
    
    PyMODINIT_FUNC PyInit_fcache_cpp(void) {
        if (PyType_Ready(&FileCacheManagerType) < 0)
            return nullptr;
        
        PyObject* m = PyModule_Create(&fcache_module);
        if (m == nullptr)
            return nullptr;
        
        Py_INCREF(&FileCacheManagerType);
        if (PyModule_AddObject(m, "FileCacheManager", (PyObject*)&FileCacheManagerType) < 0) {
            Py_DECREF(&FileCacheManagerType);
            Py_DECREF(m);
            return nullptr;
        }
        
        return m;
    }
}
