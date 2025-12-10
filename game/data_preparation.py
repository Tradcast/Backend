import os
import glob
import random
import pandas as pd
from configs.config import get_klines_dir


def load_parquet_klines(start_index: int = 0, debug: bool = False):
    """
    Dynamically loads all .parquet files in the klines directory.
    Returns a dict: { token_symbol: dataframe }
    """
    klines_dir = get_klines_dir()
    pattern = os.path.join(klines_dir, "*.parquet")
    files = glob.glob(pattern)

    if debug:
        print("Using klines directory:", klines_dir)
        print("Found parquet files:", files)

    spike_df_map = {}

    for fp in files:
        filename = os.path.basename(fp)

        # Extract token name (before first "_")
        token = filename.split("_")[0].lower()

        try:
            df = pd.read_parquet(fp)

            # Optional cut start index
            if start_index > 0:
                df = df.iloc[start_index:].reset_index(drop=True)

            spike_df_map[token] = df

            if debug:
                print(f"Loaded {token}: shape={df.shape}")

        except Exception as e:
            print(f"Error loading {fp}: {e}")

    return spike_df_map


print(get_klines_dir())
spike_df_map = load_parquet_klines(start_index=35)
random_token = random.choice(list(spike_df_map.keys()))

if __name__ == '__main__':
    print(random_token, spike_df_map)


# Example usage:
# price_flow = PriceFlow(token_selection=random_token)


