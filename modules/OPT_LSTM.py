from modules.OPT_base import Base_Opt
from collections import Counter
from typing import Optional
import pickle

class LSTM_Opt(Base_Opt):
    """
    An LSTM-based model for next file prediction using PyTorch.
    """
    def __init__(self, max_files=1000, embedding_dim=64, lstm_units=128):
        super().__init__()
        self.max_files = max_files
        self.embedding_dim = embedding_dim
        self.lstm_units = lstm_units
        self.file_to_id = {}
        self.id_to_file = {}
        self.next_id = 0
        self.model = None
        self.model_initialized = False
        
    def _initialize_model(self):
        """Initialize the LSTM model using PyTorch"""
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
        except ImportError:
            raise ImportError("PyTorch is required for LSTM model")
        # Define model architecture as a PyTorch module
        class FileSeqLSTM(nn.Module):
            def __init__(self, vocab_size, embedding_dim, hidden_dim, output_dim):
                super(FileSeqLSTM, self).__init__()
                self.embedding = nn.Embedding(vocab_size, embedding_dim)
                self.lstm = nn.LSTM(embedding_dim, hidden_dim, batch_first=True)
                self.fc = nn.Linear(hidden_dim, output_dim)
                
            def forward(self, x):
                embedded = self.embedding(x)
                lstm_out, _ = self.lstm(embedded)
                # Take only the last output
                out = self.fc(lstm_out[:, -1, :])
                return out
        
        # Create model instance
        self.model = FileSeqLSTM(
            vocab_size=self.max_files,
            embedding_dim=self.embedding_dim,
            hidden_dim=self.lstm_units,
            output_dim=self.max_files
        )
        
        # Set up optimizer and loss
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.CrossEntropyLoss()
        self.model_initialized = True
        print('Model Initialized')
    
    def _get_file_id(self, filepath):
        """Get ID for file, creating a new one if needed"""
        if filepath not in self.file_to_id:
            if self.next_id >= self.max_files:
                # If we hit the limit, reset the least used files
                usage_counts = Counter(self.history)
                least_common = [f for f, _ in usage_counts.most_common()[:-100]]
                for file in least_common:
                    if file in self.file_to_id:
                        file_id = self.file_to_id[file]
                        del self.file_to_id[file]
                        del self.id_to_file[file_id]

            self.file_to_id[filepath] = self.next_id
            self.id_to_file[self.next_id] = filepath
            self.next_id += 1
            
        return self.file_to_id[filepath]
    
    def _prepare_sequences(self, window_size=3):
        """Prepare sequences for training"""
        import numpy as np
        import torch
        
        if len(self.history) < window_size + 1:
            return None, None
            
        sequences = []
        next_files = []
        
        for i in range(len(self.history) - window_size):
            seq = [self._get_file_id(self.history[i + j]) for j in range(window_size)]
            next_file = self._get_file_id(self.history[i + window_size])
            
            sequences.append(seq)
            next_files.append(next_file)
        
        # Convert to PyTorch tensors
        return torch.LongTensor(sequences), torch.LongTensor(next_files)
    
    def update_model(self, batch_size=32, epochs=1):
        """Update the model with recent data"""
        import torch
        
        if not self.model_initialized:
            self._initialize_model()
            
        X, y = self._prepare_sequences()
        if X is None or len(X) < batch_size:
            return  # Not enough data
        
        self.model.train()
        
        # Simple training loop
        for _ in range(epochs):
            # Process in batches
            for i in range(0, len(X), batch_size):
                if i + batch_size > len(X):
                    continue
                    
                batch_X = X[i:i+batch_size]
                batch_y = y[i:i+batch_size]
                
                # Forward pass
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                
                # Backward pass
                loss.backward()
                self.optimizer.step()
    
    def log_read(self, file_read: str):
        """Log a file read and update the model if enough data"""
        super().log_read(file_read)

        if not self.model_initialized:
            self._initialize_model()

        # Update model every 5 reads TODO: this needs to be set by user
        if len(self.history) % 5 == 0 and len(self.history) >= 4:
            self.update_model()
    
    def predict_nexts(self, file_read=None, num_predictions=1) -> Optional[str]:
        """Predict the next file to be accessed"""
        import torch
        import os
            
        if not self.model_initialized or len(self.history) < 3:
            return None
            
        # Get the most recent sequence
        self.model.eval()
        with torch.no_grad():
            recent_file_ids = [self._get_file_id(f) for f in self.history[-3:]]
            input_tensor = torch.LongTensor([recent_file_ids])
            
            # Make prediction
            output = self.model(input_tensor)
            probabilities = torch.softmax(output, dim=1)
            
            # Get top 5 predictions
            values, indices = torch.topk(probabilities, 5)
            top_indices = indices[0].tolist()
            
            # Return the highest probability existing file
            for idx in top_indices:
                if idx in self.id_to_file:
                    print(idx)
                    predicted_file = self.id_to_file[idx]
                    if self.file_exists(predicted_file):
                        return predicted_file

        return None
        
    def save(self, filepath):
        """Save the model to disk"""
        import torch
        
        if not self.model_initialized:
            return
            
        # Save vocabularies
        with open(f"{filepath}_vocab.pkl", 'wb') as f:
            pickle.dump((self.file_to_id, self.id_to_file, self.next_id), f)
            
        # Save neural network
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'embedding_dim': self.embedding_dim,
            'lstm_units': self.lstm_units,
            'max_files': self.max_files
        }, filepath)
        
    @classmethod
    def load(cls, filepath):
        """Load the model from disk"""
        try:
            import torch
        except ImportError:
            raise ImportError("PyTorch is required for LSTM model")
            
        # Load vocabularies
        with open(f"{filepath}_vocab.pkl", 'rb') as f:
            file_to_id, id_to_file, next_id = pickle.load(f)
            
        # Load model parameters
        checkpoint = torch.load(filepath)
        
        # Create new model with saved parameters
        model = cls(
            max_files=checkpoint['max_files'],
            embedding_dim=checkpoint['embedding_dim'],
            lstm_units=checkpoint['lstm_units']
        )
        
        # Restore vocabularies
        model.file_to_id = file_to_id
        model.id_to_file = id_to_file
        model.next_id = next_id
        
        # Initialize model architecture
        model._initialize_model()
        
        # Load weights and optimizer state
        model.model.load_state_dict(checkpoint['model_state_dict'])
        model.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        
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

        # LSTMModel specific information
        status.append(f"Vocabulary size: {len(self.file_to_id)}/{self.max_files}")

        # Training status
        if not self.model_initialized:
            if len(self.history) < 4:
                status.append(f"Model training: Need more history (have {len(self.history)}, need 4)")
            else:
                status.append("Model training: Pending initialization")

        # Prediction readiness
        min_history = 3
        if not len(self.history) >= min_history:
            status.append(f"Prediction: Need more history (have {len(self.history)}, need {min_history})")
            
        print("\n".join(status))
