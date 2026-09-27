from pathlib import Path
import re
import pandas as pd


DATA_DIR = Path(
    r"D:\Portfolio Projects\wind-asset-analytics-platform\data\raw\scada"
)

COLUMN_RENAME_MAP = {
    "Timestamp start": "event_start",
    "Timestamp end": "event_end",
    "Duration": "duration",
    "Status": "status",
    "Code": "event_code",
    "Message": "message",
    "Comment": "comment",
    "Service contract category": "service_contract_category",
    "IEC category": "iec_category",
}


def extract_turbine_id(file_name):
    match = re.search(r"Kelmarsh_(\d+)", file_name)

    if not match:
        raise ValueError(
            f"Could not extract turbine ID from {file_name}"
        )

    return f"KWF{match.group(1)}"


def duration_to_seconds(duration_value):
    if pd.isna(duration_value):
        return None

    value = str(duration_value).strip()

    try:
        parts = value.split(":")

        if len(parts) != 3:
            return None

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])

        return (
            hours * 3600
            + minutes * 60
            + seconds
        )

    except (ValueError, TypeError):
        return None


def load_event_file(file_path):
    df = pd.read_csv(
        file_path,
        comment="#",
        low_memory=False,
    )

    df.columns = [
        col.strip()
        if isinstance(col, str)
        else col
        for col in df.columns
    ]

    missing_columns = [
        col
        for col in COLUMN_RENAME_MAP
        if col not in df.columns
    ]

    if missing_columns:
        print(
            f"\nWARNING: Missing columns in "
            f"{file_path.name}"
        )

        for col in missing_columns:
            print(f"  - {col}")

    df = df[
        [
            col
            for col in COLUMN_RENAME_MAP
            if col in df.columns
        ]
    ].copy()

    df = df.rename(
        columns=COLUMN_RENAME_MAP
    )

    df["event_start"] = pd.to_datetime(
        df["event_start"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )

    df["event_end"] = pd.to_datetime(
        df["event_end"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )

    df["duration_seconds"] = (
        df["duration"]
        .apply(duration_to_seconds)
    )

    df["duration_hours"] = (
        df["duration_seconds"] / 3600
    )

    df["turbine_id"] = extract_turbine_id(
        file_path.name
    )

    df["source_file"] = file_path.name

    return df


def validate_events(df):
    print("\n" + "=" * 60)
    print("EVENT DATA QUALITY CHECKS")
    print("=" * 60)

    print(
        f"\nRows: {len(df):,}"
    )

    print(
        f"Turbines: "
        f"{df['turbine_id'].nunique()}"
    )

    print(
        f"Invalid event_start: "
        f"{df['event_start'].isna().sum():,}"
    )

    print(
        f"Invalid event_end: "
        f"{df['event_end'].isna().sum():,}"
    )

    print(
        f"Missing duration_seconds: "
        f"{df['duration_seconds'].isna().sum():,}"
    )

    print("\nSTATUS COUNTS:")
    print(
        df["status"]
        .value_counts(dropna=False)
    )

    print("\nIEC CATEGORY COUNTS:")
    print(
        df["iec_category"]
        .value_counts(dropna=False)
        .head(20)
    )

    print("\nTOP EVENT CODES:")
    print(
        df["event_code"]
        .value_counts()
        .head(20)
    )

    print("\nTOP MESSAGES:")
    print(
        df["message"]
        .value_counts()
        .head(20)
    )

    print("\nLONGEST EVENTS:")

    longest = (
        df[
            [
                "turbine_id",
                "event_start",
                "event_end",
                "duration_hours",
                "status",
                "event_code",
                "message",
                "iec_category",
            ]
        ]
        .sort_values(
            "duration_hours",
            ascending=False,
        )
        .head(10)
    )

    print(
        longest.to_string(
            index=False
        )
    )


def main():
    event_files = sorted(
        DATA_DIR.glob("Status_*.csv")
    )

    if not event_files:
        raise FileNotFoundError(
            f"No status files found in {DATA_DIR}"
        )

    frames = []

    for file_path in event_files:
        print(
            f"Loading {file_path.name}"
        )

        event_df = load_event_file(
            file_path
        )

        print(
            f"  Rows: {len(event_df):,} | "
            f"Columns: {len(event_df.columns)}"
        )

        frames.append(event_df)

    combined_df = pd.concat(
        frames,
        ignore_index=True,
    )

    print("\n" + "=" * 60)
    print("COMBINED TURBINE EVENTS")
    print("=" * 60)

    validate_events(
        combined_df
    )

    return combined_df


if __name__ == "__main__":
    main()