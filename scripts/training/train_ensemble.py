import argparse
import gc
import logging
import math
import os

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from catboost import CatBoostClassifier, CatBoostRegressor
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import HuberRegressor, LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from tqdm import tqdm
from xgboost import XGBClassifier, XGBRegressor


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class EnsembleTrainer:
    def __init__(
        self,
        data_dir="data/mode_ready_data",
        model_dir="services/model-service/app/models",
        max_rows=1_200_000,
        random_state=42,
    ):
        self.data_dir = data_dir
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        self.feature_cols = []
        self.categorical_cols = ["sector", "quality_flag"]
        self.target_cols = ["target_prob", "target_mfe", "target_mae"]
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.max_rows = max_rows
        self.random_state = random_state

    def load_data(self, start_date="2025-01-01", end_date="2026-12-31"):
        """Load a bounded sample from parquet files so training does not blow memory."""
        files = sorted(f for f in os.listdir(self.data_dir) if f.endswith(".parquet"))
        if not files:
            logging.error("No parquet files found in %s", self.data_dir)
            return pd.DataFrame()

        all_dfs = []
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        per_file_cap = max(1, math.ceil(self.max_rows / len(files)))

        logging.info(
            "Extracting %s to %s across %s files with max_rows=%s (per_file_cap=%s)...",
            start_date,
            end_date,
            len(files),
            self.max_rows,
            per_file_cap,
        )

        for file in tqdm(files, desc="Processing Files"):
            filepath = os.path.join(self.data_dir, file)
            try:
                table = pq.read_table(
                    filepath,
                    filters=[
                        ("timestamp", ">=", start_ts),
                        ("timestamp", "<=", end_ts),
                    ],
                )
                df = table.to_pandas()
                if df.empty:
                    continue

                # Check for target columns
                missing = [c for c in self.target_cols if c not in df.columns]
                if missing:
                    logging.error("File %s is missing targets: %s. Run calculate_targets.py first.", file, missing)
                    continue

                # Only train on rows where a strategy actually fired
                if 'strategy_fired' in df.columns:
                    df = df[df['strategy_fired'] != 'None']
                
                if df.empty:
                    continue

                if len(df) > per_file_cap:
                    df = df.sample(n=per_file_cap, random_state=self.random_state)

                for col in df.select_dtypes(include=["float64"]).columns:
                    df[col] = df[col].astype("float32")

                all_dfs.append(df)
            except Exception as exc:
                logging.error("Error loading %s: %s", file, exc)

        if not all_dfs:
            logging.error("No data found after filtering.")
            return pd.DataFrame()

        logging.info("Concatenating sampled dataframes...")
        combined_df = pd.concat(all_dfs, ignore_index=True)
        del all_dfs
        gc.collect()

        if len(combined_df) > self.max_rows:
            combined_df = combined_df.sample(
                n=self.max_rows,
                random_state=self.random_state,
            ).reset_index(drop=True)

        logging.info("Final train dataset shape after bounded sampling: %s", combined_df.shape)
        return combined_df

    def preprocess(self, df):
        logging.info("Starting preprocessing...")
        exclude = ["timestamp", "date", "Target", "symbol"] + self.target_cols
        self.feature_cols = [col for col in df.columns if col not in exclude]

        for col in self.categorical_cols:
            if col in df.columns:
                logging.info("Encoding categorical column: %s", col)
                encoder = LabelEncoder()
                df[col] = encoder.fit_transform(df[col].astype(str))
                self.label_encoders[col] = encoder

        self.feature_cols = [
            col for col in self.feature_cols if pd.api.types.is_numeric_dtype(df[col])
        ]
        logging.info("Using %s numeric features.", len(self.feature_cols))

        df[self.feature_cols] = df[self.feature_cols].fillna(0)

        logging.info("Fitting scaler...")
        scaler_data = df[self.feature_cols].to_numpy(dtype="float32", copy=False)
        self.scaler.fit(scaler_data)
        return df

    def train_models(self, X, y, target_name):
        logging.info("Training models for %s...", target_name)
        is_classifier = target_name == "target_prob"

        split_kwargs = {
            "test_size": 0.2,
            "random_state": self.random_state,
        }
        if is_classifier and len(np.unique(y)) > 1:
            split_kwargs["stratify"] = y

        X_train, X_val, y_train, y_val = train_test_split(X, y, **split_kwargs)

        if is_classifier:
            classes = np.unique(y_train)
            if len(classes) == 2:
                weights = compute_class_weight("balanced", classes=classes, y=y_train)
                scale_pos = weights[1] / weights[0]
            else:
                scale_pos = 1.0

            models = {
                "logistic": LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=self.random_state,
                ),
                "rf": RandomForestClassifier(
                    n_estimators=120,
                    max_depth=10,
                    min_samples_leaf=25,
                    class_weight="balanced",
                    n_jobs=1,
                    random_state=self.random_state,
                ),
                "xgb": XGBClassifier(
                    n_estimators=120,
                    learning_rate=0.08,
                    max_depth=6,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    tree_method="hist",
                    eval_metric="logloss",
                    scale_pos_weight=scale_pos,
                    n_jobs=1,
                    random_state=self.random_state,
                ),
                "lgbm": LGBMClassifier(
                    n_estimators=120,
                    class_weight="balanced",
                    subsample=0.8,
                    colsample_bytree=0.8,
                    num_leaves=63,
                    n_jobs=1,
                    verbose=-1,
                    random_state=self.random_state,
                ),
                "cat": CatBoostClassifier(
                    iterations=120,
                    depth=6,
                    learning_rate=0.08,
                    auto_class_weights="Balanced",
                    silent=True,
                    thread_count=1,
                    random_seed=self.random_state,
                ),
                "nb": GaussianNB(),
            }
        else:
            models = {
                "ridge": HuberRegressor(max_iter=500),
                "rf": RandomForestRegressor(
                    n_estimators=100,
                    max_depth=10,
                    min_samples_leaf=25,
                    n_jobs=1,
                    random_state=self.random_state,
                ),
                "xgb": XGBRegressor(
                    n_estimators=100,
                    max_depth=6,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    tree_method="hist",
                    objective="reg:absoluteerror",
                    n_jobs=1,
                    random_state=self.random_state,
                ),
                "lgbm": LGBMRegressor(
                    n_estimators=100,
                    objective="mae",
                    subsample=0.8,
                    colsample_bytree=0.8,
                    num_leaves=63,
                    n_jobs=1,
                    verbose=-1,
                    random_state=self.random_state,
                ),
                "cat": CatBoostRegressor(
                    iterations=100,
                    depth=6,
                    learning_rate=0.08,
                    loss_function="MAE",
                    silent=True,
                    thread_count=1,
                    random_seed=self.random_state,
                ),
            }

        trained = {}
        meta_features = []

        for name, model in models.items():
            logging.info("  Training %s...", name)
            model.fit(X_train, y_train)
            trained[name] = model
            joblib.dump(model, os.path.join(self.model_dir, f"{target_name}_{name}.joblib"))

            if is_classifier:
                meta_features.append(model.predict_proba(X_val)[:, 1].reshape(-1, 1))
            else:
                meta_features.append(model.predict(X_val).reshape(-1, 1))

        logging.info("  Training meta ensemble...")
        X_meta = np.hstack(meta_features)
        if is_classifier:
            meta_model = LogisticRegression(
                class_weight="balanced",
                random_state=self.random_state,
            )
        else:
            meta_model = HuberRegressor()

        meta_model.fit(X_meta, y_val)
        
        # Save validation metrics
        val_preds = meta_model.predict(X_meta) if not is_classifier else meta_model.predict_proba(X_meta)[:, 1]
        joblib.dump({
            "target": target_name,
            "y_val": y_val,
            "val_preds": val_preds,
            "meta_features": X_meta
        }, os.path.join(self.model_dir, f"{target_name}_validation_results.joblib"))

        joblib.dump(meta_model, os.path.join(self.model_dir, f"{target_name}_meta.joblib"))
        trained["meta"] = meta_model
        return trained

    def run(self, start_date="2025-01-01", end_date="2026-12-31"):
        df = self.load_data(start_date=start_date, end_date=end_date)
        if df.empty:
            return

        df = self.preprocess(df)

        logging.info("Training anomaly detector...")
        X_scaled = self.scaler.transform(df[self.feature_cols].to_numpy(dtype="float32", copy=False))
        iso = IsolationForest(contamination=0.01, n_jobs=1, random_state=self.random_state)
        iso.fit(X_scaled)
        joblib.dump(iso, os.path.join(self.model_dir, "anomaly_detector.joblib"))

        for target in self.target_cols:
            self.train_models(X_scaled, df[target].to_numpy(), target)
            gc.collect()

        joblib.dump(self.scaler, os.path.join(self.model_dir, "scaler.joblib"))
        joblib.dump(self.label_encoders, os.path.join(self.model_dir, "label_encoders.joblib"))
        joblib.dump(self.feature_cols, os.path.join(self.model_dir, "feature_columns.joblib"))
        logging.info("Training completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the ensemble on a bounded parquet sample.")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2026-12-31")
    parser.add_argument("--max-rows", type=int, default=1_200_000)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    trainer = EnsembleTrainer(max_rows=args.max_rows, random_state=args.random_state)
    trainer.run(start_date=args.start_date, end_date=args.end_date)
