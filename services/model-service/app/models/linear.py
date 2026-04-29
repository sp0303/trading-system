from sklearn.linear_model import LogisticRegression, Ridge
from app.models.base import BaseModel
import pandas as pd

class LogisticRegressionModel(BaseModel):
    def __init__(self, model_name: str = "logistic_regression"):
        super().__init__(model_name, "classification")
        self.model = LogisticRegression(max_iter=1000)

    def train(self, X, y):
        print(f"Training {self.model_name}...")
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]

class RidgeRegressionModel(BaseModel):
    def __init__(self, model_name: str = "ridge_regression"):
        super().__init__(model_name, "regression")
        self.model = Ridge()

    def train(self, X, y):
        print(f"Training {self.model_name}...")
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)
