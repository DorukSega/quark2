from modules.OPT_base import Base_Opt

class Markov_Opt(Base_Opt):
    def __init__(self, order=2):
        super().__init__()
        self.order = max(1, order)
        self.transitions = {}
    
    def log_read(self, file_read):
        super().log_read(file_read)
        
        if len(self.history) <= self.order:
            return
            
        state = tuple(self.history[-self.order-1:-1])
        
        if state not in self.transitions:
            self.transitions[state] = {}
        
        self.transitions[state].setdefault(file_read, 0)
        self.transitions[state][file_read] += 1
    
    def _get_next(self, context):
        state = tuple(context[-self.order:])
        
        # Try reducing order if needed
        while state and (state not in self.transitions or not self.transitions[state]):
            state = state[1:]
        
        if not state or state not in self.transitions:
            return None
            
        # Get best prediction for this state
        transitions = self.transitions[state]
        return max(transitions.items(), key=lambda x: x[1])[0]
    
    def predict_nexts(self, file_read=None, num_predictions=1):
        # Start with current context
        context = list(self.history)
        if file_read and (not context or context[-1] != file_read):
            context.append(file_read)
        
        if len(context) < self.order:
            return None
        
        # Single prediction case
        if num_predictions == 1:
            return self._get_next(context)
        
        # Multiple predictions case
        result = []
        for _ in range(num_predictions):
            next_file = self._get_next(context)
            if not next_file:
                break
                
            result.append(next_file)
            context.append(next_file)
        
        return result or None
    
    def status_fmt(self):
        super().status_fmt()
        print(f"Markov model - Order: {self.order}, States: {len(self.transitions)}")
        
        if len(self.history) >= self.order:
            state = tuple(self.history[-self.order:])
            
            if state in self.transitions:
                print(f"Transitions from {state}:")
                sorted_trans = sorted(self.transitions[state].items(), 
                                    key=lambda x: x[1], reverse=True)[:3]
                for dest, count in sorted_trans:
                    print(f"  → {dest}: {count}")
            else:
                print(f"No transitions found for state: {state}")
