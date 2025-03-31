from modules.OPT_base import Base_Opt
from collections import defaultdict, Counter
import os
from typing import Optional
import pickle

class Markov_Opt(Base_Opt):
    """
    A Markov Chain-based model that predicts the next file access based on recent history.
    Can be incrementally updated without full retraining.
    """
    def __init__(self, order=3, decay_factor=0.95):
        super().__init__()
        self.order = order  # Length of history to consider
        self.decay_factor = decay_factor  # For reducing importance of old observations
        self.transitions = defaultdict(Counter)  # Stores transition probabilities
    
    def _get_context(self, n=None):
        """Get the last n files accessed as a context tuple"""
        n = n or self.order
        context_size = min(n, len(self.history))
        if context_size == 0:
            return tuple()
        return tuple(self.history[-context_size:])
    

    
    def log_read(self, file_read: str):
        """
        Log a file access and update the model incrementally
        """
        # Update transitions with variable history lengths
        for i in range(1, min(self.order + 1, len(self.history) + 1)):
            context = self._get_context(i)
            self.transitions[context][file_read] += 1
            
            # Apply decay to other transitions from this context
            for dest, count in self.transitions[context].items():
                if dest != file_read:
                    self.transitions[context][dest] *= self.decay_factor
        
        # Update history
        super().log_read(file_read)
        
        # Occasionally clean up the cache
        self._clear_obsolete_cache()
    
    def predict_nexts(self, file_read=None) -> Optional[str]:
        """
        Predict the next file to be accessed based on recent history
        
        Args:
            file_read: The file that was just read (if not already in history)
            
        Returns:
            The predicted next file path or None if no prediction can be made
        """
        # Log the current read if provided
        if file_read is not None:
            self.log_read(file_read)
        
        # Try different context lengths, from longest to shortest
        for context_length in range(self.order, 0, -1):
            context = self._get_context(context_length)
            if not context or context not in self.transitions:
                continue
                
            # Find most likely transitions that point to existing files
            candidates = []
            for next_file, count in self.transitions[context].most_common():
                if self._file_exists(next_file):
                    candidates.append((next_file, count))
                    
            if candidates:
                # Return highest probability existing file
                return candidates[0][0]
        
        # Fall back to the most frequently accessed file overall
        all_files = Counter()
        for context, destinations in self.transitions.items():
            all_files.update(destinations)
            
        for file, _ in all_files.most_common():
            if self._file_exists(file):
                return file
                
        return None
    
    def save(self, filepath):
        """Save the model to disk"""
        with open(filepath, 'wb') as f:
            pickle.dump((self.transitions, self.order, self.decay_factor), f)
            
    @classmethod
    def load(cls, filepath):
        """Load the model from disk"""
        with open(filepath, 'rb') as f:
            transitions, order, decay_factor = pickle.load(f)
            
        model = cls(order=order, decay_factor=decay_factor)
        model.transitions = transitions
        return model

    def status_fmt(self):
        """
        Returns a formatted string with the current status of the model.
        Includes information about history size, learning capacity, and prediction readiness.
        """
        status = []
        
        # Common information for both models
        status.append(f"History size: {len(self.history)}")
        status.append(f"Last 5 entries: {self.history[-5:]}")

        # MarkovModel specific information
        context_counts = {len(ctx): len(transitions) 
                        for ctx, transitions in self.transitions.items()}
        
        total_transitions = sum(len(transitions) for transitions in self.transitions.values())
        unique_contexts = len(self.transitions)
        
        status.append(f"Markov Chain (order={self.order})")
        status.append(f"Decay factor: {self.decay_factor:.2f}")
        status.append(f"Unique contexts: {unique_contexts}")
        status.append(f"Total transitions: {total_transitions}")
        
        # Show context length distribution
        if context_counts:
            ctx_info = [f"{length}-gram: {count}" for length, count in sorted(context_counts.items())]
            status.append(f"Context distribution: {', '.join(ctx_info)}")
        
        min_history = 1
        if not len(self.history) >= min_history:
            status.append(f"Prediction: Need more history (have {len(self.history)}, need {min_history})")
            
        print("\n".join(status))
