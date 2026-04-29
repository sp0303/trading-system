import pandas as pd
import numpy as np
import os
import joblib
import logging
from tqdm import tqdm
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ModelEvaluator:
    def __init__(self, data_dir="data/mode_ready_data", model_dir="services/model-service/app/models"):
        self.data_dir = data_dir
        self.model_dir = model_dir
        
        # Load artifacts
        self.scaler = joblib.load(os.path.join(self.model_dir, "scaler.joblib"))
        self.label_encoders = joblib.load(os.path.join(self.model_dir, "label_encoders.joblib"))
        self.feature_cols = joblib.load(os.path.join(self.model_dir, "feature_columns.joblib"))
        
        self.targets = ['target_prob', 'target_mfe', 'target_mae']
        self.models = {}
        self.load_models()

    def load_models(self):
        """Load all models and meta-ensembles."""
        for target in self.targets:
            self.models[target] = {}
            # List all joblib files for this target
            files = [f for f in os.listdir(self.model_dir) if f.startswith(f"{target}_") and f.endswith(".joblib")]
            for f in files:
                name = f.replace(f"{target}_", "").replace(".joblib", "")
                self.models[target][name] = joblib.load(os.path.join(self.model_dir, f))
        logging.info("All models loaded for evaluation.")

    def predict_ensemble(self, X_scaled, target):
        """Get the meta-ensemble prediction for a target."""
        comp_models = self.models[target]
        meta = comp_models['meta']
        
        preds = []
        is_clf = (target == 'target_prob')
        
        # Predict with individual components
        for name, model in comp_models.items():
            if name == 'meta': continue
            if is_clf:
                preds.append(model.predict_proba(X_scaled)[:, 1].reshape(-1, 1))
            else:
                preds.append(model.predict(X_scaled).reshape(-1, 1))
        
        # Stack and predict with meta
        X_meta = np.hstack(preds)
        return meta.predict(X_meta)

    def run_eval(self, test_start="2026-01-01"):
        """Evaluate on unseen 2026 data."""
        files = [f for f in os.listdir(self.data_dir) if f.endswith('.parquet')]
        
        all_results = []
        logging.info(f"Evaluating on data starting from {test_start}...")
        
        for file in tqdm(files, desc="Evaluating Stocks"):
            df = pd.read_parquet(os.path.join(self.data_dir, file))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter for test period
            test_df = df[df['timestamp'] >= test_start].copy()
            if test_df.empty: continue
            
            # Preprocess
            for col, le in self.label_encoders.items():
                if col in test_df.columns:
                    test_df[col] = le.transform(test_df[col].astype(str))
            
            test_df[self.feature_cols] = test_df[self.feature_cols].fillna(0)
            X_scaled = self.scaler.transform(test_df[self.feature_cols].values.astype('float32'))
            
            # Predict
            results = {'symbol': file.split('_')[0]}
            for target in self.targets:
                y_true = test_df[target].values
                y_pred = self.predict_ensemble(X_scaled, target)
                
                if target == 'target_prob':
                    results[f'{target}_acc'] = accuracy_score(y_true, (y_pred > 0.5).astype(int))
                else:
                    results[f'{target}_mae'] = mean_absolute_error(y_true, y_pred)
                    results[f'{target}_r2'] = r2_score(y_true, y_pred)
            
            all_results.append(results)
            
        report_df = pd.DataFrame(all_results)
        self.generate_report(report_df)

    def generate_report(self, df):
        """Print summary metrics."""
        print("\n" + "="*40)
        print("  ENSEMBLE PERFORMANCE REPORT (JAN 2026)")
        print("="*40)
        print(f"Total Stocks Evaluated: {len(df)}")
        print(f"Avg Accuracy (Prob):    {df['target_prob_acc'].mean():.2%}")
        print(f"Avg MAE (MFE Profit):   {df['target_mfe_mae'].mean():.4f} R")
        print(f"Avg MAE (MAE Drawdown): {df['target_mae_mae'].mean():.4f} R")
        print(f"Avg R2 (MFE Profit):    {df['target_mfe_r2'].mean():.4f}")
        print("="*40)
        
        # Save to file
        report_path = os.path.join(self.model_dir, "evaluation_report.csv")
        df.to_csv(report_path, index=False)
        logging.info(f"Detailed report saved to {report_path}")

if __name__ == "__main__":
    evaluator = ModelEvaluator()
    evaluator.run_eval()
