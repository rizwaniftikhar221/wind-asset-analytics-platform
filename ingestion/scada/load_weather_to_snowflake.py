from pathlib import Path
import os

from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from load_weather import main as build_weather_dataframe


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


DATABASE = os.getenv("SNOWFLAKE_DATABASE", "WIND_ANALYTICS")
SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "RAW")
WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "WIND_WH")


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {DATABASE}.{SCHEMA}.WEATHER (
    TIMESTAMP TIMESTAMP_NTZ,
    TEMPERATURE_2M_C FLOAT,
    SURFACE_PRESSURE_HPA FLOAT,
    WIND_SPEED_100M_MS FLOAT,
    WIND_DIRECTION_100M_DEG FLOAT,
    LATITUDE FLOAT,
    LONGITUDE FLOAT,
    ELEVATION_M FLOAT,
    SOURCE VARCHAR,
    INGESTED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
"""


def validate_environment():
    required_variables = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ]

    missing = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing:
        raise EnvironmentError(
            "Missing Snowflake environment variables: "
            + ", ".join(missing)
        )


def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
    )


def validate_dataframe(df):
    print("\n" + "=" * 60)
    print("PRE LOAD WEATHER VALIDATION")
    print("=" * 60)

    print(f"Rows prepared: {len(df):,}")
    print(f"Columns prepared: {len(df.columns)}")

    invalid_timestamps = df["timestamp"].isna().sum()
    duplicate_timestamps = df["timestamp"].duplicated().sum()

    print(f"Invalid timestamps: {invalid_timestamps:,}")
    print(f"Duplicate timestamps: {duplicate_timestamps:,}")

    if invalid_timestamps > 0:
        raise ValueError(
            "Invalid weather timestamps detected."
        )

    if duplicate_timestamps > 0:
        raise ValueError(
            "Duplicate weather timestamps detected."
        )


def main():
    validate_environment()

    print("=" * 60)
    print("BUILDING WEATHER DATAFRAME")
    print("=" * 60)

    df = build_weather_dataframe()

    validate_dataframe(df)

    df.columns = [
        column.upper()
        for column in df.columns
    ]

    print("\nConnecting to Snowflake...")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            f"USE WAREHOUSE {WAREHOUSE}"
        )

        print(
            f"Creating {DATABASE}.{SCHEMA}.WEATHER "
            f"if required..."
        )

        cursor.execute(CREATE_TABLE_SQL)

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {DATABASE}.{SCHEMA}.WEATHER
            """
        )

        existing_rows = cursor.fetchone()[0]

        if existing_rows > 0:
            raise RuntimeError(
                f"{DATABASE}.{SCHEMA}.WEATHER already contains "
                f"{existing_rows:,} rows. "
                "Load stopped to prevent duplicates."
            )

        print(
            f"\nLoading {len(df):,} rows into "
            f"{DATABASE}.{SCHEMA}.WEATHER..."
        )

        success, chunks, rows_loaded, _ = write_pandas(
            conn=connection,
            df=df,
            table_name="WEATHER",
            database=DATABASE,
            schema=SCHEMA,
            quote_identifiers=False,
            use_logical_type=True,
        )

        print("\n" + "=" * 60)
        print("LOAD RESULT")
        print("=" * 60)

        print(f"Success: {success}")
        print(f"Chunks: {chunks}")
        print(f"Rows loaded: {rows_loaded:,}")

        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT TIMESTAMP) AS timestamp_count,
                MIN(TIMESTAMP) AS min_timestamp,
                MAX(TIMESTAMP) AS max_timestamp,
                COUNT_IF(WIND_SPEED_100M_MS IS NULL)
                    AS missing_wind_speed
            FROM {DATABASE}.{SCHEMA}.WEATHER
            """
        )

        result = cursor.fetchone()

        print("\n" + "=" * 60)
        print("SNOWFLAKE VALIDATION")
        print("=" * 60)

        print(f"Rows: {result[0]:,}")
        print(f"Unique timestamps: {result[1]:,}")
        print(f"Minimum timestamp: {result[2]}")
        print(f"Maximum timestamp: {result[3]}")
        print(
            f"Missing wind speed records: {result[4]:,}"
        )

        if result[0] != len(df):
            raise RuntimeError(
                "Row count mismatch between weather dataframe "
                "and Snowflake."
            )

        print(
            "\nWeather ingestion completed successfully."
        )

    finally:
        connection.close()
        print("Snowflake connection closed.")


if __name__ == "__main__":
    main()