from pathlib import Path
import re
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "scada"
SELECTED_COLUMNS = [
    "Date and time",
    "Wind speed (m/s)",
    "Density adjusted wind speed (m/s)",
    "Wind direction (°)",
    "Nacelle position (°)",
    "Power (kW)",
    "Energy Export (kWh)",
    "Potential power default PC (kW)",
    "Rotor speed (RPM)",
    "Gearbox speed (RPM)",
    "Gear oil temperature (°C)",
    "Generator bearing front temperature (°C)",
    "Nacelle temperature (°C)",
    "Data Availability",
]

COLUMN_RENAME_MAP = {
    "Date and time": "timestamp",
    "Wind speed (m/s)": "wind_speed_ms",
    "Density adjusted wind speed (m/s)": "density_adjusted_wind_speed_ms",
    "Wind direction (°)": "wind_direction_deg",
    "Nacelle position (°)": "nacelle_position_deg",
    "Power (kW)": "power_kw",
    "Energy Export (kWh)": "energy_export_kwh",
    "Potential power default PC (kW)": "potential_power_kw",
    "Rotor speed (RPM)": "rotor_speed_rpm",
    "Gearbox speed (RPM)": "gearbox_speed_rpm",
    "Gear oil temperature (°C)": "gear_oil_temperature_c",
    "Generator bearing front temperature (°C)": (
        "generator_bearing_front_temperature_c"
    ),
    "Nacelle temperature (°C)": "nacelle_temperature_c",
    "Data Availability": "data_availability",
}


def extract_turbine_id(file_name):
    match = re.search(r"Kelmarsh_(\d+)", file_name)

    if not match:
        raise ValueError(
            f"Could not extract turbine ID from {file_name}"
        )

    return f"KWF{match.group(1)}"


def load_turbine_file(file_path):
    source_columns = [
        "# Date and time",
        "Wind speed (m/s)",
        "Density adjusted wind speed (m/s)",
        "Wind direction (°)",
        "Nacelle position (°)",
        "Power (kW)",
        "Energy Export (kWh)",
        "Potential power default PC (kW)",
        "Rotor speed (RPM)",
        "Gearbox speed (RPM)",
        "Gear oil temperature (°C)",
        "Generator bearing front temperature (°C)",
        "Nacelle temperature (°C)",
        "Data Availability",
    ]

    df = pd.read_csv(
        file_path,
        skiprows=9,
        header=0,
        usecols=source_columns,
    )

    # Clean source header names
    df.columns = [
        col.replace("# ", "", 1).strip()
        if isinstance(col, str)
        else col
        for col in df.columns
    ]

    turbine_id = extract_turbine_id(file_path.name)

    # Validate required source columns
    missing_columns = [
        col for col in SELECTED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        print(
            f"\nWARNING: Missing columns in {file_path.name}"
        )

        for col in missing_columns:
            print(f"  - {col}")

    available_columns = [
        col for col in SELECTED_COLUMNS
        if col in df.columns
    ]

    df = df[available_columns].copy()

    # Standardize names for Snowflake/dbt
    df = df.rename(columns=COLUMN_RENAME_MAP)

    # Convert timestamp
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    # Add lineage columns
    df["turbine_id"] = turbine_id
    df["source_file"] = file_path.name

    return df


def validate_combined_data(combined_df):
    print("\n" + "=" * 60)
    print("DATA QUALITY CHECKS")
    print("=" * 60)

    print("\nDATA AVAILABILITY:")
    print(
        combined_df["data_availability"]
        .value_counts(dropna=False)
        .sort_index()
    )

    print("\nFIRST VALID POWER RECORD BY TURBINE:")

    for turbine_id, group in combined_df.groupby(
        "turbine_id"
    ):
        valid = group[
            group["power_kw"].notna()
        ].sort_values("timestamp")

        if not valid.empty:
            first_row = valid.iloc[0]

            print(
                f"{turbine_id}: "
                f"{first_row['timestamp']} | "
                f"Power = {first_row['power_kw']}"
            )
        else:
            print(
                f"{turbine_id}: No valid power records"
            )

    print("\nVALID POWER ROWS BY TURBINE:")

    print(
        combined_df.groupby(
            "turbine_id"
        )["power_kw"].count()
    )

    print("\nNULL COUNTS:")

    print(
        combined_df.isna()
        .sum()
        .sort_values(ascending=False)
    )

    print("\nTIMESTAMP RANGE:")

    print(
        combined_df.groupby("turbine_id")[
            "timestamp"
        ].agg(["min", "max"])
    )

    print("\nDUPLICATE TURBINE + TIMESTAMP ROWS:")

    duplicate_count = combined_df.duplicated(
        subset=[
            "turbine_id",
            "timestamp",
        ]
    ).sum()

    print(duplicate_count)


def main():
    turbine_files = sorted(
        DATA_DIR.glob(
            "Turbine_Data_*.csv"
        )
    )

    if not turbine_files:
        raise FileNotFoundError(
            f"No turbine files found in {DATA_DIR}"
        )

    frames = []

    for file_path in turbine_files:
        print(
            f"Loading {file_path.name}"
        )

        turbine_df = load_turbine_file(
            file_path
        )

        print(
            f"  Rows: {len(turbine_df):,} | "
            f"Columns: {len(turbine_df.columns)}"
        )

        frames.append(turbine_df)

    combined_df = pd.concat(
        frames,
        ignore_index=True,
    )

    print("\n" + "=" * 60)
    print("COMBINED SCADA DATASET")
    print("=" * 60)

    print(
        f"\nRows: {len(combined_df):,}"
    )

    print(
        f"Columns: {len(combined_df.columns)}"
    )

    print("\nCOLUMNS:")

    for col in combined_df.columns:
        print(f"  - {col}")

    print("\nTURBINE ROW COUNTS:")

    print(
        combined_df[
            "turbine_id"
        ].value_counts()
    )

    print("\nSAMPLE:")

    print(
        combined_df.head()
        .to_string()
    )

    validate_combined_data(
        combined_df
    )
    return combined_df

if __name__ == "__main__":
    main()