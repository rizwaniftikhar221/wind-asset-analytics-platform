from pathlib import Path
import os

from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from load_events import main as build_events_dataframe


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


DATABASE = os.getenv("SNOWFLAKE_DATABASE", "WIND_ANALYTICS")
SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "RAW")
WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "WIND_WH")


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {DATABASE}.{SCHEMA}.TURBINE_EVENTS (
    EVENT_START TIMESTAMP_NTZ,
    EVENT_END TIMESTAMP_NTZ,
    DURATION VARCHAR,
    STATUS VARCHAR,
    EVENT_CODE INTEGER,
    MESSAGE VARCHAR,
    COMMENT VARCHAR,
    SERVICE_CONTRACT_CATEGORY VARCHAR,
    IEC_CATEGORY VARCHAR,
    DURATION_SECONDS FLOAT,
    DURATION_HOURS FLOAT,
    TURBINE_ID VARCHAR,
    SOURCE_FILE VARCHAR,
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


def main():
    validate_environment()

    print("=" * 60)
    print("BUILDING TURBINE EVENTS DATAFRAME")
    print("=" * 60)

    df = build_events_dataframe()

    print(f"\nRows prepared: {len(df):,}")
    print(
        f"Turbines: "
        f"{df['turbine_id'].nunique()}"
    )

    if df["event_start"].isna().any():
        raise ValueError(
            "Invalid event_start timestamps detected."
        )

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

        cursor.execute(CREATE_TABLE_SQL)

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {DATABASE}.{SCHEMA}.TURBINE_EVENTS
            """
        )

        existing_rows = cursor.fetchone()[0]

        if existing_rows > 0:
            raise RuntimeError(
                f"TURBINE_EVENTS already contains "
                f"{existing_rows:,} rows."
            )

        print(
            f"\nLoading {len(df):,} event records..."
        )

        success, chunks, rows_loaded, _ = write_pandas(
            conn=connection,
            df=df,
            table_name="TURBINE_EVENTS",
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
                COUNT(*),
                COUNT(DISTINCT TURBINE_ID),
                MIN(EVENT_START),
                MAX(EVENT_START),
                COUNT_IF(
                    IEC_CATEGORY = 'Forced outage'
                )
            FROM {DATABASE}.{SCHEMA}.TURBINE_EVENTS
            """
        )

        result = cursor.fetchone()

        print("\nSNOWFLAKE VALIDATION")
        print("=" * 60)

        print(f"Rows: {result[0]:,}")
        print(f"Turbines: {result[1]}")
        print(f"First event: {result[2]}")
        print(f"Last event: {result[3]}")
        print(
            f"Forced outage records: {result[4]:,}"
        )

    finally:
        connection.close()
        print("\nSnowflake connection closed.")


if __name__ == "__main__":
    main()