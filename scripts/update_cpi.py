import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "canada_inflation_rate.csv"

# Statistics Canada - monthly CPI, not seasonally adjusted
HEADLINE_ZIP_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/18100004-eng.zip"


def download_zip(url: str) -> bytes:
    print(f"Scarico: {url}")
    r = requests.get(url, timeout=60)
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


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_main_csv_from_zip(download_zip(HEADLINE_ZIP_URL))

    ref_col = find_column(raw, ["REF_DATE"])
    geo_col = find_column(raw, ["GEO", "Geography"])
    value_col = find_column(raw, ["VALUE"])
    product_col = find_column(
        raw,
        ["Products and product groups", "Products and product group", "Products"]
    )

    df = raw[[ref_col, geo_col, product_col, value_col]].copy()
    df.columns = ["date", "geo", "product", "cpi_index"]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["cpi_index"] = pd.to_numeric(df["cpi_index"], errors="coerce")
    df["geo"] = df["geo"].astype(str).str.strip().str.lower()
    df["product"] = df["product"].astype(str).str.strip().str.lower()

    # Canada + headline all-items
    df = df[df["geo"] == "canada"]
    df = df[df["product"] == "all-items"]

    df = df.dropna(subset=["date", "cpi_index"]).sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last")

    # YoY inflation rate
    df["inflation_rate"] = df["cpi_index"].pct_change(12) * 100

    # Solo dal 2000
    df = df[df["date"] >= "2000-01-01"].copy()

    out = df[["date", "inflation_rate"]].copy()

    # release date: stima base = metà del mese successivo
    out["release_date"] = out["date"] + pd.offsets.MonthBegin(1) + pd.Timedelta(days=14)

    # override ufficiali recenti
    official = {
        "2026-02-01": "2026-03-16",
        "2026-03-01": "2026-04-20",
        "2026-04-01": "2026-05-19",
        "2026-05-01": "2026-06-22",
    }

    for ref_date, rel_date in official.items():
        mask = out["date"] == pd.Timestamp(ref_date)
        out.loc[mask, "release_date"] = pd.Timestamp(rel_date)

    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out["release_date"] = pd.to_datetime(out["release_date"]).dt.strftime("%Y-%m-%d")

    out.to_csv(OUTPUT_FILE, index=False)

    print(f"Salvato: {OUTPUT_FILE}")
    print(out.tail(12).to_string(index=False))


if __name__ == "__main__":
    main()