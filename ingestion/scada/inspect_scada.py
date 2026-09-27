from pathlib import Path
import pandas as pd

DATA_DIR = Path(
    r"D:\Portfolio Projects\wind-asset-analytics-platform\data\raw\scada"
)


def inspect_file(file_path, rows=5):
    print("\n" + "=" * 100)
    print(f"FILE: {file_path.name}")
    print("=" * 100)

    df = pd.read_csv(
        file_path,
        comment="#",
        nrows=rows,
        low_memory=False
    )

    print(f"\nSample shape: {df.shape}")

    print("\nCOLUMNS:")
    for i, column in enumerate(df.columns, start=1):
        print(f"{i}. {column}")

    print("\nDATA TYPES:")
    print(df.dtypes)

    print("\nSAMPLE DATA:")
    print(df.to_string())


def main():
    turbine_files = sorted(DATA_DIR.glob("Turbine_Data_*.csv"))
    status_files = sorted(DATA_DIR.glob("Status_*.csv"))

    static_file = DATA_DIR / "Kelmarsh_WT_static.csv"
    mapping_file = DATA_DIR / "Kelmarsh_WT_dataSignalMapping.csv"

    print(f"Found {len(turbine_files)} turbine files")
    print(f"Found {len(status_files)} status files")

    if turbine_files:
        inspect_file(turbine_files[0])

    if status_files:
        inspect_file(status_files[0])

    if static_file.exists():
        inspect_file(static_file)

    if mapping_file.exists():
        inspect_file(mapping_file)


if __name__ == "__main__":
    main()