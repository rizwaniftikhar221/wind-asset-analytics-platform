from pathlib import Path
import os

from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from load_scada import main as build_scada_dataframe


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


DATABASE = os.getenv("SNOWFLAKE_DATABASE", "WIND_ANALYTICS")
SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "RAW")
WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "WIND_WH")

TARGET_TABLE = "SCADA"
STAGE_TABLE = "SCADA_STAGE"


CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {DATABASE}.{SCHEMA}.{TARGET_TABLE} (
    TIMESTAMP TIMESTAMP_NTZ,
    WIND_SPEED_MS FLOAT,
    DENSITY_ADJUSTED_WIND_SPEED_MS FLOAT,
    WIND_DIRECTION_DEG FLOAT,
    NACELLE_POSITION_DEG FLOAT,
    POWER_KW FLOAT,
    ENERGY_EXPORT_KWH FLOAT,
    POTENTIAL_POWER_KW FLOAT,
    ROTOR_SPEED_RPM FLOAT,
    GEARBOX_SPEED_RPM FLOAT,
    GEAR_OIL_TEMPERATURE_C FLOAT,
    GENERATOR_BEARING_FRONT_TEMPERATURE_C FLOAT,
    NACELLE_TEMPERATURE_C FLOAT,
    DATA_AVAILABILITY INTEGER,
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


def validate_dataframe(df):
    print("\n" + "=" * 60)
    print("PRE LOAD VALIDATION")
    print("=" * 60)

    print(f"Rows prepared: {len(df):,}")
    print(f"Columns prepared: {len(df.columns)}")

    duplicate_count = df.duplicated(
        subset=["turbine_id", "timestamp"]
    ).sum()

    invalid_timestamp_count = df["timestamp"].isna().sum()

    print(
        f"Duplicate turbine + timestamp records: "
        f"{duplicate_count:,}"
    )

    print(
        f"Invalid timestamps: "
        f"{invalid_timestamp_count:,}"
    )

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate turbine + timestamp records detected."
        )

    if invalid_timestamp_count > 0:
        raise ValueError(
            "Invalid timestamps detected."
        )


def main():
    validate_environment()

    print("=" * 60)
    print("BUILDING SCADA DATAFRAME")
    print("=" * 60)

    df = build_scada_dataframe()

    validate_dataframe(df)

    # Match Snowflake column naming convention
    df.columns = [
        column.upper()
        for column in df.columns
    ]

    print("\nConnecting to Snowflake...")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        print(
            f"Using warehouse: {WAREHOUSE}"
        )

        cursor.execute(
            f"USE WAREHOUSE {WAREHOUSE}"
        )

        print(
            f"Creating {DATABASE}.{SCHEMA}.{TARGET_TABLE} "
            f"if it does not exist..."
        )

        cursor.execute(CREATE_TABLE_SQL)

        # Count current target rows before MERGE
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {DATABASE}.{SCHEMA}.{TARGET_TABLE}
            """
        )

        rows_before = cursor.fetchone()[0]

        print(
            f"Rows currently in "
            f"{DATABASE}.{SCHEMA}.{TARGET_TABLE}: "
            f"{rows_before:,}"
        )

        # Create temporary staging table
        print(
            f"\nCreating temporary staging table "
            f"{STAGE_TABLE}..."
        )

        cursor.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE
            {DATABASE}.{SCHEMA}.{STAGE_TABLE}
            LIKE {DATABASE}.{SCHEMA}.{TARGET_TABLE}
            """
        )

        print(
            f"\nLoading {len(df):,} rows into "
            f"{STAGE_TABLE}..."
        )

        success, chunks, rows_loaded, _ = write_pandas(
            conn=connection,
            df=df,
            table_name=STAGE_TABLE,
            database=DATABASE,
            schema=SCHEMA,
            quote_identifiers=False,
            chunk_size=50000,
            use_logical_type=True,
        )

        print("\n" + "=" * 60)
        print("STAGING LOAD RESULT")
        print("=" * 60)

        print(f"Success: {success}")
        print(f"Chunks: {chunks}")
        print(f"Rows staged: {rows_loaded:,}")

        if not success:
            raise RuntimeError(
                "Failed to load SCADA staging table."
            )

        print("\nRunning Snowflake MERGE...")

        merge_sql = f"""
        MERGE INTO {DATABASE}.{SCHEMA}.{TARGET_TABLE} AS target
        USING {DATABASE}.{SCHEMA}.{STAGE_TABLE} AS source

        ON target.TURBINE_ID = source.TURBINE_ID
        AND target.TIMESTAMP = source.TIMESTAMP

        WHEN MATCHED THEN UPDATE SET
            target.WIND_SPEED_MS =
                source.WIND_SPEED_MS,
            target.DENSITY_ADJUSTED_WIND_SPEED_MS =
                source.DENSITY_ADJUSTED_WIND_SPEED_MS,
            target.WIND_DIRECTION_DEG =
                source.WIND_DIRECTION_DEG,
            target.NACELLE_POSITION_DEG =
                source.NACELLE_POSITION_DEG,
            target.POWER_KW =
                source.POWER_KW,
            target.ENERGY_EXPORT_KWH =
                source.ENERGY_EXPORT_KWH,
            target.POTENTIAL_POWER_KW =
                source.POTENTIAL_POWER_KW,
            target.ROTOR_SPEED_RPM =
                source.ROTOR_SPEED_RPM,
            target.GEARBOX_SPEED_RPM =
                source.GEARBOX_SPEED_RPM,
            target.GEAR_OIL_TEMPERATURE_C =
                source.GEAR_OIL_TEMPERATURE_C,
            target.GENERATOR_BEARING_FRONT_TEMPERATURE_C =
                source.GENERATOR_BEARING_FRONT_TEMPERATURE_C,
            target.NACELLE_TEMPERATURE_C =
                source.NACELLE_TEMPERATURE_C,
            target.DATA_AVAILABILITY =
                source.DATA_AVAILABILITY,
            target.SOURCE_FILE =
                source.SOURCE_FILE

        WHEN NOT MATCHED THEN INSERT (
            TIMESTAMP,
            WIND_SPEED_MS,
            DENSITY_ADJUSTED_WIND_SPEED_MS,
            WIND_DIRECTION_DEG,
            NACELLE_POSITION_DEG,
            POWER_KW,
            ENERGY_EXPORT_KWH,
            POTENTIAL_POWER_KW,
            ROTOR_SPEED_RPM,
            GEARBOX_SPEED_RPM,
            GEAR_OIL_TEMPERATURE_C,
            GENERATOR_BEARING_FRONT_TEMPERATURE_C,
            NACELLE_TEMPERATURE_C,
            DATA_AVAILABILITY,
            TURBINE_ID,
            SOURCE_FILE
        )
        VALUES (
            source.TIMESTAMP,
            source.WIND_SPEED_MS,
            source.DENSITY_ADJUSTED_WIND_SPEED_MS,
            source.WIND_DIRECTION_DEG,
            source.NACELLE_POSITION_DEG,
            source.POWER_KW,
            source.ENERGY_EXPORT_KWH,
            source.POTENTIAL_POWER_KW,
            source.ROTOR_SPEED_RPM,
            source.GEARBOX_SPEED_RPM,
            source.GEAR_OIL_TEMPERATURE_C,
            source.GENERATOR_BEARING_FRONT_TEMPERATURE_C,
            source.NACELLE_TEMPERATURE_C,
            source.DATA_AVAILABILITY,
            source.TURBINE_ID,
            source.SOURCE_FILE
        )
        """

        cursor.execute(merge_sql)

        merge_result = cursor.fetchone()

        print("\n" + "=" * 60)
        print("MERGE RESULT")
        print("=" * 60)

        print(
            f"Snowflake MERGE result: {merge_result}"
        )

        # Final validation
        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT TURBINE_ID)
                    AS turbine_count,
                MIN(TIMESTAMP)
                    AS min_timestamp,
                MAX(TIMESTAMP)
                    AS max_timestamp,
                COUNT_IF(DATA_AVAILABILITY = 1)
                    AS available_records
            FROM {DATABASE}.{SCHEMA}.{TARGET_TABLE}
            """
        )

        result = cursor.fetchone()

        rows_after = result[0]

        print("\n" + "=" * 60)
        print("SNOWFLAKE VALIDATION")
        print("=" * 60)

        print(
            f"Rows before MERGE: {rows_before:,}"
        )

        print(
            f"Rows after MERGE: {rows_after:,}"
        )

        print(
            f"Net new rows: "
            f"{rows_after - rows_before:,}"
        )

        print(
            f"Turbines: {result[1]}"
        )

        print(
            f"Minimum timestamp: {result[2]}"
        )

        print(
            f"Maximum timestamp: {result[3]}"
        )

        print(
            f"Available SCADA records: "
            f"{result[4]:,}"
        )

        print(
            "\nSCADA ingestion with MERGE "
            "completed successfully."
        )

    finally:
        connection.close()

        print(
            "Snowflake connection closed."
        )


if __name__ == "__main__":
    main()