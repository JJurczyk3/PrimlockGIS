# Normaisation of the initial coordinates
from pathlib import Path
import pandas as pd # Might later switch to Python built-in csv module, but pandas is more convenient for now.

ROOT_DIR = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT_DIR / "data" / "initial_coords.csv"

def load_coords(csv_path: Path):
    # Import the coursework data from the CSV file.
    # Use skipinitialspace and strip column names to handle spaces in the CSV header.
    df = pd.read_csv(csv_path, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    return df

df = load_coords(CSV_PATH)

min_x = int(df["x_coord"].min())
min_y = int(df["y_coord"].min())
min_z = int(df["z_coord"].min())

coords_x = []
coords_y = []

for i in range(len(df["x_coord"])):
    coords_x.append(int(df.at[i, "x_coord"] - min_x))
    coords_y.append(int(df.at[i, "y_coord"] - min_y))

max_x = int(max(coords_x))
max_y = int(max(coords_y))
max_z = int(df["z_coord"].max())

print(min(coords_x))
print(min(coords_y))
print(min_z)
print(max_x)
print(max_y)
print(max_z)