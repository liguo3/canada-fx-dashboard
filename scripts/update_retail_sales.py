import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "canada_retail_sales.csv"

# Legacy / inactive tables (historical)
LEGACY_CURRENT_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/20100008-eng.zip"
LEGACY_CHAINED_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/20100078-eng.zip"

# Current tables
CURRENT_CURRENT_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/20100056-eng.zip"
CURRENT_CHAINED_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/20100067-eng.zip"


def download_zip(url: str) -> bytes:
    print(f"Scarico: {url}")
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    print("Download completato")
    return r.content


def load_main_csv_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and "meta" not in n.lower()
        ]
        if not csv_names:
            raise RuntimeError("Nessun CSV trovato nello zip.")
        with zf.open(csv_names[0]) as f:
            return pd.read_csv(f, low_memory=False)


def find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for c in df.columns:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    raise KeyError(f"Colonna non trovata tra: {candidates}")


def build_text_blob(df: pd.DataFrame, excluded_cols: list[str]) -> pd.Series:
    text_cols = [c for c in df.columns if df[c].dtype == object and c not in excluded_cols]
    blob = pd.Series("", index=df.index, dtype="object")
    for c in text_cols:
        blob = blob + " | " + df[c].astype(str)
    return blob.str.lower()


def parse_current_dollars(url: str) -> pd.DataFrame:
    raw = load_main_csv_from_zip(download_zip(url))

    ref_col = find_column(raw, ["REF_DATE"])
    geo_col = find_column(raw, ["GEO", "Geography"])
    value_col = find_column(raw, ["VALUE"])

    df = raw.copy().rename(columns={
        ref_col: "date",
        geo_col: "geo",
        value_col: "value",
    })

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["geo"] = df["geo"].astype(str).str.strip().str.lower()

    blob = build_text_blob(df, ["date", "geo", "value"])

    df = df[df["geo"] == "canada"]
    df = df[blob.str.contains("retail trade", na=False)]

    priority = (
        blob.str.contains("total", na=False).astype(int) * 10
        + blob.str.contains("all", na=False).astype(int) * 5
        + blob.str.contains("seasonally adjusted", na=False).astype(int) * 3
    )

    df = df.assign(priority=priority)
    df = df.dropna(subset=["date", "value"]).sort_values(["date", "priority"])
    df = df.drop_duplicates(subset=["date"], keep="last")

    # Both legacy/current current-dollar tables are x 1,000
    df["retail_sales_current_dollars"] = df["value"] * 1000
    return df[["date", "retail_sales_current_dollars"]].copy()


def parse_chained_dollars(url: str) -> pd.DataFrame:
    raw = load_main_csv_from_zip(download_zip(url))

    ref_col = find_column(raw, ["REF_DATE"])
    value_col = find_column(raw, ["VALUE"])

    df = raw.copy().rename(columns={
        ref_col: "date",
        value_col: "value",
    })

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    blob = build_text_blob(df, ["date", "value"])

    df = df[
        blob.str.contains("retail trade", na=False)
        & (
            blob.str.contains("2017 chained", na=False)
            | blob.str.contains("volume", na=False)
            | blob.str.contains("constant prices", na=False)
        )
    ]

    priority = (
        blob.str.contains("total", na=False).astype(int) * 10
        + blob.str.contains("all", na=False).astype(int) * 5
        + blob.str.contains("seasonally adjusted", na=False).astype(int) * 3
    )

    df = df.assign(priority=priority)
    df = df.dropna(subset=["date", "value"]).sort_values(["date", "priority"])
    df = df.drop_duplicates(subset=["date"], keep="last")

    # Legacy/current chained-dollar tables are x 1,000,000
    df["retail_sales_chained_2017_dollars"] = df["value"] * 1_000_000
    return df[["date", "retail_sales_chained_2017_dollars"]].copy()


def add_release_dates(df: pd.DataFrame) -> pd.DataFrame:
    # Approximation for older history
    df["release_date"] = df["date"] + pd.offsets.MonthBegin(1) + pd.Timedelta(days=19)

    # Known official recent dates
    official = {
        "2025-12-01": "2026-02-20",
        "2026-01-01": "2026-03-20",
    }
    for ref_date, rel_date in official.items():
        mask = df["date"] == pd.Timestamp(ref_date)
        df.loc[mask, "release_date"] = pd.Timestamp(rel_date)

    return df


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Legacy block
    legacy_current = parse_current_dollars(LEGACY_CURRENT_URL)
    legacy_chained = parse_chained_dollars(LEGACY_CHAINED_URL)
    legacy = pd.merge(legacy_current, legacy_chained, on="date", how="outer")
    legacy = legacy[legacy["date"] <= "2022-12-01"].copy()

    # Current block
    current_current = parse_current_dollars(CURRENT_CURRENT_URL)
    current_chained = parse_chained_dollars(CURRENT_CHAINED_URL)
    current = pd.merge(current_current, current_chained, on="date", how="outer")
    current = current[current["date"] >= "2023-01-01"].copy()

    out = pd.concat([legacy, current], ignore_index=True).sort_values("date")
    out = out[out["date"] >= "2000-01-01"].copy()
    out = out.drop_duplicates(subset=["date"], keep="last")
    out = add_release_dates(out)

    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out["release_date"] = pd.to_datetime(out["release_date"]).dt.strftime("%Y-%m-%d")

    out.to_csv(OUTPUT_FILE, index=False)

    print(f"Salvato: {OUTPUT_FILE}")
    print(out.head(12).to_string(index=False))
    print(out.tail(12).to_string(index=False))


if __name__ == "__main__":
    main()