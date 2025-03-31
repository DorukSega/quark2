'''
Adaptive Weighted Markov Model with Temporal Decay

This module implements a modified Markov chain that:
1. Considers variable influence from multiple previous states
2. Applies exponential decay to give more weight to recent file accesses
3. Uses parameterized learning rate for online adaptation
4. Combines evidence from multiple history entries for prediction

Unlike traditional fixed-order Markov models that use exact state tuples,
this model weighs influence from all recent states based on recency.
'''

from modules.OPT_base import Base_Opt
from collections import defaultdict

class AdaptiveMarkov_Opt(Base_Opt):
    def __init__(self, history_length=5, learning_rate=0.1, decay=0.9):
        super().__init__()
        self.history_length = min(max(1, history_length), 10)  # Clamp between 1 and 10
        self.learning_rate = min(max(0.01, learning_rate), 1.0)  # Clamp between 0.01 and 1.0
        self.decay = min(max(0.5, decay), 0.99)  # Clamp between 0.5 and 0.99
        self.transitions = defaultdict(lambda: defaultdict(float))
    
    def log_read(self, file_read):
        super().log_read(file_read)
        
        # Update transition weights from recent history to current file
        history = self.history[:-1]  # All except current
        for i, prev_file in enumerate(history[-self.history_length:]):
            if prev_file != file_read:  # Avoid self-transitions
                # Calculate influence based on recency (more recent = higher influence)
                influence = self.decay ** (len(history[-self.history_length:]) - i - 1)
                # Update weight
                self.transitions[prev_file][file_read] += self.learning_rate * influence
    
    def predict_nexts(self, file_read=None, num_predictions=1):
        # Start with full history
        context = list(self.history)
        if file_read and (not context or context[-1] != file_read):
            context.append(file_read)
        
        if not context:
            return None
        
        # Calculate scores for all potential next files
        scores = defaultdict(float)
        
        # Number of files in recent history to consider
        relevant_history = context[-self.history_length:]
        
        for i, hist_file in enumerate(relevant_history):
            # Weight by recency
            influence = self.decay ** (len(relevant_history) - i - 1)
            
            # Skip if no transitions from this file
            if hist_file not in self.transitions:
                continue
                
            # Add weighted transitions
            for next_file, weight in self.transitions[hist_file].items():
                scores[next_file] += weight * influence
        
        # Remove current file from predictions
        current = context[-1] if context else None
        if current in scores:
            del scores[current]
        
        if not scores:
            return None
        
        if num_predictions == 1:
            # Return highest scoring file
            return max(scores.items(), key=lambda x: x[1])[0]
        else:
            # Return top N files
            sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:num_predictions]
            return [file for file, _ in sorted_files] or None
    
    def status_fmt(self):
        super().status_fmt()
        print(f"Adaptive Markov - History: {self.history_length}, LR: {self.learning_rate}, Decay: {self.decay}")
        
        # Show predictions for current state
        if self.history:
            current = self.history[-1]
            print(f"Current file: {current}")
            prediction = self.predict_nexts(current)
            if prediction:
                print(f"Predicted next: {prediction}")
            
            # Show top transitions from current state
            if current in self.transitions:
                print("Top transitions:")
                sorted_trans = sorted(self.transitions[current].items(), 
                                    key=lambda x: x[1], reverse=True)[:3]
                for dest, weight in sorted_trans:
                    print(f"  → {dest}: {weight:.4f}")
            else:
                print("Current file not in transition model")
