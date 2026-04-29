import os
import joblib
import logging

class AnomalyDetector:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), "..", "models", "anomaly_detector.joblib")
        
        if not os.path.exists(model_path):
            logging.error(f"Anomaly detector model not found at {model_path}")
            self.model = None
        else:
            self.model = joblib.load(model_path)
            logging.info(f"AnomalyDetector loaded from {model_path}")

    def is_anomaly(self, X_scaled):
        """
        Returns True if the input is an anomaly, False otherwise.
        IsolationForest returns 1 for inliers and -1 for outliers.
        """
        if self.model is None:
            return False
            
        prediction = self.model.predict(X_scaled)
        return bool(prediction[0] == -1)
