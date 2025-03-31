'''
    Simple Weighted Graph that will be used to predict the next potential read.
    It will greedly pick the edge with highest weight.
'''
from modules.OPT_base import Base_Opt

class SWG_Opt(Base_Opt):
    graph: dict
    '''
    Example Graph Structure:
    ```
        graph = {
            'A': {
                'B': 2, # A -2-> B 
                'C': 1, # A -1-> C
            },
        }
    ```
    '''

    def __init__(self):
        super().__init__()
        self.graph = {}

    def log_read(self, file_read: str):
        super().log_read(file_read)
        last_file_read = self.last_file_read(file_read)
        if last_file_read:
            # l_f_r -> f_r (weight++)
            if last_file_read not in self.graph:
                self.graph[last_file_read] = {}
            if file_read not in self.graph[last_file_read]:
                self.graph[last_file_read][file_read] = 0
            self.graph[last_file_read][file_read] += 1

    def predict_nexts(self, file_read):
        if file_read in self.graph:
            file_graph = self.graph[file_read]
            assert isinstance(file_graph, dict)
            next_file = max(file_graph, key=lambda k: file_graph[k])
            return next_file
