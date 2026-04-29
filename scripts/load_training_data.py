import pandas as pd
import os
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_data_for_training(symbols=None, data_dir=None):
    """
    Load mode-ready parquet files into a single pandas DataFrame for training.
    """
    if data_dir is None:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(BASE_DIR, "data", "mode_ready_data")
    if not os.path.exists(data_dir):
        logging.error(f"Directory not found: {data_dir}")
        return pd.DataFrame()

    all_files = [f for f in os.listdir(data_dir) if f.endswith('.parquet')]
    
    if symbols:
        # Filter files by symbol (case insensitive)
        symbols_lower = [s.lower() for s in symbols]
        files_to_load = [f for f in all_files if any(s in f.lower() for s in symbols_lower)]
    else:
        files_to_load = all_files

    if not files_to_load:
        logging.warning("No matching files found.")
        return pd.DataFrame()

    logging.info(f"Loading {len(files_to_load)} files from {data_dir}...")
    
    dfs = []
    for file in tqdm(files_to_load, desc="Loading Parquet Files"):
        try:
            df = pd.read_parquet(os.path.join(data_dir, file))
            dfs.append(df)
        except Exception as e:
            logging.error(f"Error loading {file}: {e}")

    if not dfs:
        return pd.DataFrame()

    combined_df = pd.concat(dfs, ignore_index=True)
    logging.info(f"Loaded {len(combined_df)} rows for {len(dfs)} stocks.")
    
    return combined_df

if __name__ == "__main__":
    # Example usage
    df = load_data_for_training(symbols=['RELIANCE'])
    if not df.empty:
        print(df.head())
        print(f"Total Columns: {len(df.columns)}")
