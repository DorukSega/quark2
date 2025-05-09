class Base_Opt:
    history: list[str] | list
    file_exists_cache: dict
    source_dir: str
    name: str = 'Base'

    def __init__(self):
        self.history = []

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

    def predict_nexts(self, file_read=None, num_predictions=1):
        return

    def status_fmt(self):
        # prints last 5 items from history
        print(self.history[-5:])
