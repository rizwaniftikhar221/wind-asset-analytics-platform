from pathlib import Path
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# Representative Kelmarsh wind farm coordinate
LATITUDE = 52.4010
LONGITUDE = -0.9450

START_DATE = "2016-01-01"
END_DATE = "2016-12-31"


API_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
)


PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "start_date": START_DATE,
    "end_date": END_DATE,
    "hourly": [
        "temperature_2m",
        "surface_pressure",
        "wind_speed_100m",
        "wind_direction_100m",
    ],
    "wind_speed_unit": "ms",
    "timezone": "UTC",
}


def fetch_weather_data():
    print("Requesting historical weather data...")

    response = requests.get(
        API_URL,
        params=PARAMS,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def build_dataframe(payload):
    hourly = payload["hourly"]

    df = pd.DataFrame(hourly)

    df = df.rename(
        columns={
            "time": "timestamp",
            "temperature_2m": "temperature_2m_c",
            "surface_pressure": "surface_pressure_hpa",
            "wind_speed_100m": "wind_speed_100m_ms",
            "wind_direction_100m": "wind_direction_100m_deg",
        }
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df["latitude"] = payload["latitude"]
    df["longitude"] = payload["longitude"]
    df["elevation_m"] = payload.get(
        "elevation"
    )

    df["source"] = "open_meteo"

    return df


def validate_weather(df):
    print("\n" + "=" * 60)
    print("WEATHER DATA QUALITY CHECKS")
    print("=" * 60)

    print(
        f"Rows: {len(df):,}"
    )

    print(
        f"Invalid timestamps: "
        f"{df['timestamp'].isna().sum():,}"
    )

    print(
        f"Duplicate timestamps: "
        f"{df['timestamp'].duplicated().sum():,}"
    )

    print("\nTIMESTAMP RANGE:")

    print(
        df["timestamp"].min(),
        "→",
        df["timestamp"].max(),
    )

    print("\nNULL COUNTS:")

    print(
        df.isna()
        .sum()
        .sort_values(
            ascending=False
        )
    )

    print("\nSAMPLE:")

    print(
        df.head()
        .to_string(
            index=False
        )
    )


def main():
    payload = fetch_weather_data()

    df = build_dataframe(
        payload
    )

    validate_weather(
        df
    )

    output_file = (
        OUTPUT_DIR
        / "kelmarsh_weather_2016.csv"
    )

    df.to_csv(
        output_file,
        index=False,
    )

    print(
        f"\nWeather file saved to:\n"
        f"{output_file}"
    )

    return df


if __name__ == "__main__":
    main()