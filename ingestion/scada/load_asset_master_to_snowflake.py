from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "scada"
    / "Kelmarsh_WT_static.csv"
)

load_dotenv(PROJECT_ROOT / ".env")


DATABASE = os.getenv("SNOWFLAKE_DATABASE", "WIND_ANALYTICS")
SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "RAW")
WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "WIND_WH")


COLUMN_RENAME_MAP = {
    "Wind Farm": "wind_farm",
    "Title": "turbine_name",
    "Alternative Title": "turbine_id",
    "Identity": "manufacturer_identity",
    "Manufacturer": "manufacturer",
    "Model": "model",
    "Rated power (kW)": "rated_power_kw",
    "Hub Height (m)": "hub_height_m",
    "Rotor Diameter (m)": "rotor_diameter_m",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Elevation (m)": "elevation_m",
    "Country": "country",
    "Commercial Operations Date": "commercial_operations_date",
}


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {DATABASE}.{SCHEMA}.ASSET_MASTER (
    WIND_FARM VARCHAR,
    TURBINE_NAME VARCHAR,
    TURBINE_ID VARCHAR,
    MANUFACTURER_IDENTITY VARCHAR,
    MANUFACTURER VARCHAR,
    MODEL VARCHAR,
    RATED_POWER_KW FLOAT,
    HUB_HEIGHT_M FLOAT,
    ROTOR_DIAMETER_M FLOAT,
    LATITUDE FLOAT,
    LONGITUDE FLOAT,
    ELEVATION_M FLOAT,
    COUNTRY VARCHAR,
    COMMERCIAL_OPERATIONS_DATE DATE,
    INGESTED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
"""


def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
    )


def main():
    df = pd.read_csv(DATA_FILE)

    df = df.rename(columns=COLUMN_RENAME_MAP)

    df["commercial_operations_date"] = pd.to_datetime(
        df["commercial_operations_date"],
        format="%d/%m/%Y",
        errors="coerce",
    ).dt.date

    print("=" * 60)
    print("ASSET MASTER VALIDATION")
    print("=" * 60)

    print(f"Rows: {len(df)}")
    print(f"Unique turbines: {df['turbine_id'].nunique()}")

    if df["turbine_id"].duplicated().any():
        raise ValueError("Duplicate turbine IDs detected.")

    if df["commercial_operations_date"].isna().any():
        raise ValueError(
            "Invalid commercial operations date detected."
        )

    df.columns = [
        column.upper()
        for column in df.columns
    ]

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            f"USE WAREHOUSE {WAREHOUSE}"
        )

        cursor.execute(CREATE_TABLE_SQL)

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {DATABASE}.{SCHEMA}.ASSET_MASTER
            """
        )

        existing_rows = cursor.fetchone()[0]

        if existing_rows > 0:
            raise RuntimeError(
                f"ASSET_MASTER already contains "
                f"{existing_rows} rows."
            )

        success, chunks, rows_loaded, _ = write_pandas(
            conn=connection,
            df=df,
            table_name="ASSET_MASTER",
            database=DATABASE,
            schema=SCHEMA,
            quote_identifiers=False,
            use_logical_type=True,
        )

        print("\nLOAD RESULT")
        print("=" * 60)
        print(f"Success: {success}")
        print(f"Rows loaded: {rows_loaded}")

        cursor.execute(
            f"""
            SELECT
                COUNT(*),
                COUNT(DISTINCT TURBINE_ID),
                MIN(COMMERCIAL_OPERATIONS_DATE),
                MAX(COMMERCIAL_OPERATIONS_DATE)
            FROM {DATABASE}.{SCHEMA}.ASSET_MASTER
            """
        )

        result = cursor.fetchone()

        print("\nSNOWFLAKE VALIDATION")
        print("=" * 60)
        print(f"Rows: {result[0]}")
        print(f"Turbines: {result[1]}")
        print(f"First COD: {result[2]}")
        print(f"Last COD: {result[3]}")

    finally:
        connection.close()
        print("\nSnowflake connection closed.")


if __name__ == "__main__":
    main()