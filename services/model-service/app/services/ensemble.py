import os
import joblib
import pandas as pd
import numpy as np
from app.services.anomaly import AnomalyDetector
import logging

class EnsemblePredictor:
    def __init__(self, model_dir=None):
        if model_dir is None:
            # Default to the app/models directory relative to this file
            model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        
        self.model_dir = model_dir
        self.scaler = joblib.load(os.path.join(self.model_dir, "scaler.joblib"))
        self.label_encoders = joblib.load(os.path.join(self.model_dir, "label_encoders.joblib"))
        self.feature_cols = joblib.load(os.path.join(self.model_dir, "feature_columns.joblib"))
        
        # Initialize sub-services
        self.anomaly_detector = AnomalyDetector(os.path.join(self.model_dir, "anomaly_detector.joblib"))
        
        self.targets = ['target_prob', 'target_mfe', 'target_mae']
        self.models = {}
        self._load_all_models()
        logging.info("EnsemblePredictor initialized with all models and artifacts.")

    def _load_all_models(self):
        # Whitelist of model types to prevent loading arbitrary artifacts as models
        ALLOWED_MODELS = {'logistic', 'rf', 'xgb', 'lgbm', 'cat', 'nb', 'ridge', 'meta'}
        
        for target in self.targets:
            self.models[target] = {}
            files = [f for f in os.listdir(self.model_dir) if f.startswith(f"{target}_") and f.endswith(".joblib")]
            for f in files:
                if "validation_results" in f:
                    continue
                
                name = f.replace(f"{target}_", "").replace(".joblib", "")
                if name in ALLOWED_MODELS:
                    self.models[target][name] = joblib.load(os.path.join(self.model_dir, f))
                    logging.info(f"Loaded {target} model: {name}")
                else:
                    logging.debug(f"Skipping non-model artifact: {f}")

    def predict(self, features_dict):
        """
        Generate predictions for probability, MFE, MAE and Anomaly status.
        """
        # Convert dictionary to DataFrame with correct order
        df = pd.DataFrame([features_dict])
        
        # Preprocess categorical
        for col, le in self.label_encoders.items():
            if col in df.columns:
                df[col] = le.transform(df[col].astype(str))
        
        # Ensure all feature columns exist and are in the right order
        # Fill missing features with 0
        X = df.reindex(columns=self.feature_cols, fill_value=0).values.astype('float32')
        X_scaled = self.scaler.transform(X)
        
        # Anomaly Detection
        is_anomaly = self.anomaly_detector.is_anomaly(X_scaled)
        
        results = {}
        for target in self.targets:
            results[target] = self._predict_target(X_scaled, target)
            
        # Confidence calculation (simplified: variance across ensemble member predictions)
        # Higher confidence if model components agree more
        confidence = self._calculate_confidence(X_scaled)
            
        return {
            "probability": results['target_prob'],
            "expected_return": results['target_mfe'],
            "expected_drawdown": results['target_mae'],
            "is_anomaly": is_anomaly,
            "confidence": confidence,
            "models_used": list(self.models['target_prob'].keys())
        }

    def _predict_target(self, X_scaled, target):
        comp_models = self.models[target]
        meta = comp_models.get('meta')
        if not meta:
            logging.warning(f"Meta-model missing for target: {target}")
            return 0.0
            
        preds = []
        is_clf = (target == 'target_prob')
        for name, model in comp_models.items():
            if name == 'meta': continue
            if is_clf:
                preds.append(model.predict_proba(X_scaled)[:, 1].reshape(-1, 1))
            else:
                preds.append(model.predict(X_scaled).reshape(-1, 1))
        
        X_meta = np.hstack(preds)
        
        # Deep Telemetry: Reveal the raw base-model conviction
        if is_clf:
            model_names = [n for n in comp_models.keys() if n != 'meta']
            telemetry = {name: float(p[0]) for name, p in zip(model_names, preds)}
            logging.debug(f"[Ensemble] Raw Probabilities for {target}: {telemetry}")
            
            # Use predict_proba for the meta-model to get continuous probability
            prediction = float(meta.predict_proba(X_meta)[0, 1])
        else:
            prediction = float(meta.predict(X_meta)[0])
            
        logging.debug(f"[Ensemble] Final {target} Aggregation: {prediction}")
        return prediction

    def _calculate_confidence(self, X_scaled):
        # Calculate standard deviation of probabilities from all 6 classifier models
        comp_models = self.models['target_prob']
        preds = []
        for name, model in comp_models.items():
            if name == 'meta': continue
            preds.append(model.predict_proba(X_scaled)[:, 1])
        
        # std of 0.5 means disagreement, std of 0 means perfect agreement
        # map to 1.0 (perfect agreement) to 0.0 (max disagreement)
        std = np.std(preds)
        # Theoretically max std for values in [0,1] is 0.5
        confidence = max(0.0, 1.0 - (std / 0.5))
        return float(confidence)
