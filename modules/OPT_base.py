class Base_Opt:
    history: list[str] | list

    def __init__(self):
        self.history = []
        #self.file_exists_cache = {}  # Caches file existence checks

    def last_file_read(self, other_than=None) -> str | None:
        if not self.history:
            return None
        if not other_than:
            return self.history[-1]
        for file in reversed(self.history):
            if file != other_than:
                return file

    def log_read(self, file_read: str):
        self.history.append(file_read)
        # train the model here ?

    def predict_nexts(self, file_read):
        return

    def status_fmt(self):
        # prints last 5 items from history
        print(self.history[-5:])

    def _file_exists(self, filepath):
        """Check if file exists with caching"""
        return True
        if filepath not in self.file_exists_cache:
            self.file_exists_cache[filepath] = os.path.exists(filepath)
        return self.file_exists_cache[filepath]
        
    def _clear_obsolete_cache(self, max_size=1000):
        """Clear cache if it grows too large"""
        return
        if len(self.file_exists_cache) > max_size:
            self.file_exists_cache.clear()
