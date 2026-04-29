from abc import ABC, abstractmethod
import os
import joblib

class BaseModel(ABC):
    def __init__(self, model_name: str, model_type: str):
        """
        model_type: 'classification' (for probability) or 'regression' (for return/drawdown)
        """
        self.model_name = model_name
        self.model_type = model_type
        self.model = None

    @abstractmethod
    def train(self, X, y):
        pass

    @abstractmethod
    def predict(self, X):
        pass

    def save(self, directory: str):
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        path = os.path.join(directory, f"{self.model_name}.joblib")
        joblib.dump(self.model, path)
        print(f"Model saved to {path}")

    def load(self, directory: str):
        path = os.path.join(directory, f"{self.model_name}.joblib")
        if os.path.exists(path):
            self.model = joblib.load(path)
            print(f"Model loaded from {path}")
            return True
        return False
