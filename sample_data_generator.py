"""
Financial Data Warehouse - Data Vendor Integration

The project description says:
  "Open source data is usually historical and limited to some
   time frames and for selected instruments"

This means Nasdaq provides HISTORICAL CSV downloads - not live API.
We support TWO ingestion modes:

  MODE 1 - CSV Import (Nasdaq open/historical data):
    1. Download CSV manually from data.nasdaq.com
    2. Place in data/nasdaq/ folder
    3. Run this script - it reads and ingests the CSV

  MODE 2 - Live API (Yahoo Finance, no key needed):
    Calls Yahoo Finance directly for real-time data

  MODE 3 - Simulated (always works, fallback):
    Generates realistic fake data for testing

HOW TO GET FREE NASDAQ CSV DATA:
  1. Go to https://data.nasdaq.com
  2. Log in with your account
  3. Search for "WIKI" or "LBMA" or "FRED"
  4. Click Download → CSV
  5. Save to data/nasdaq/ folder in this project
  6. Run: python sample_data_generator.py
"""

import os
import csv
import json
import random
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

BASE_URL       = "http://localhost:5000"
NASDAQ_API_KEY = os.getenv("NASDAQ_API_KEY", "")

# ─────────────────────────────────────────────────────────
# NASDAQ CSV FILES
# Download these from data.nasdaq.com and put them here
# ─────────────────────────────────────────────────────────
NASDAQ_CSV_DIR = "data/nasdaq"

# Map CSV filenames to instrument symbols
# When you download from Nasdaq, rename the file accordingly
# e.g. WIKI-AAPL.csv, LBMA-GOLD.csv, BITFINEX-BTCUSD.csv
NASDAQ_CSV_MAP = {
    "WIKI-AAPL.csv":       {"symbol": "AAPL",    "col_map": {"open":"open","high":"high","low":"low","close":"close","volume":"volume","adj. open":"open","adj. close":"close"}},
    "WIKI-MSFT.csv":       {"symbol": "MSFT",    "col_map": {"open":"open","high":"high","low":"low","close":"close","volume":"volume","adj. open":"open","adj. close":"close"}},
    "WIKI-TSLA.csv":       {"symbol": "TSLA",    "col_map": {"open":"open","high":"high","low":"low","close":"close","volume":"volume"}},
    "WIKI-GOOGL.csv":      {"symbol": "GOOGL",   "col_map": {"open":"open","high":"high","low":"low","close":"close","volume":"volume"}},
    "LBMA-GOLD.csv":       {"symbol": "GOLD",    "col_map": {"usdm":"close","usdpm":"open","usdpm - pm high":"high","usdpm - pm low":"low"}},
    "LBMA-SILVER.csv":     {"symbol": "SILVER",  "col_map": {"usdm":"close"}},
    "BITFINEX-BTCUSD.csv": {"symbol": "BTC-USD", "col_map": {"last":"close","high":"high","low":"low","bid":"open","volume":"volume"}},
    "BITFINEX-ETHUSD.csv": {"symbol": "ETH-USD", "col_map": {"last":"close","high":"high","low":"low","bid":"open","volume":"volume"}},
    "FRED-DGS10.csv":      {"symbol": "US10Y",   "col_map": {"value":"close"}},
}

# ─────────────────────────────────────────────────────────
# INSTRUMENTS
# ─────────────────────────────────────────────────────────
INSTRUMENTS = [
    {"symbol": "TSLA",   "name": "Tesla Inc",            "description": "Electric vehicle and clean energy company", "instrumentClass": "stock",     "region": "US",     "currency": "USD", "yahoo_ticker": "TSLA",    "attributes": {"sector": "Technology", "exchange": "NASDAQ"}},
    {"symbol": "MSFT",   "name": "Microsoft Corporation","description": "Cloud computing and software company",       "instrumentClass": "stock",     "region": "US",     "currency": "USD", "yahoo_ticker": "MSFT",    "attributes": {"sector": "Technology", "exchange": "NASDAQ"}},
    {"symbol": "AAPL",   "name": "Apple Inc",            "description": "Consumer electronics and software company",  "instrumentClass": "stock",     "region": "US",     "currency": "USD", "yahoo_ticker": "AAPL",    "attributes": {"sector": "Technology", "exchange": "NASDAQ"}},
    {"symbol": "GOOGL",  "name": "Alphabet Inc",         "description": "Search and cloud computing company",         "instrumentClass": "stock",     "region": "US",     "currency": "USD", "yahoo_ticker": "GOOGL",   "attributes": {"sector": "Technology", "exchange": "NASDAQ"}},
    {"symbol": "BTC-USD","name": "Bitcoin",              "description": "Decentralized digital currency",             "instrumentClass": "crypto",    "region": "Global", "currency": "USD", "yahoo_ticker": "BTC-USD", "attributes": {"blockchain": "Bitcoin"}},
    {"symbol": "ETH-USD","name": "Ethereum",             "description": "Smart contract platform",                    "instrumentClass": "crypto",    "region": "Global", "currency": "USD", "yahoo_ticker": "ETH-USD", "attributes": {"blockchain": "Ethereum"}},
    {"symbol": "GOLD",   "name": "Gold",                 "description": "Gold spot price - London Bullion Market",    "instrumentClass": "commodity", "region": "Global", "currency": "USD", "yahoo_ticker": "GC=F",    "attributes": {"type": "precious_metal", "unit": "troy_ounce"}},
    {"symbol": "SILVER", "name": "Silver",               "description": "Silver spot price - London Bullion Market",  "instrumentClass": "commodity", "region": "Global", "currency": "USD", "yahoo_ticker": "SI=F",    "attributes": {"type": "precious_metal", "unit": "troy_ounce"}},
    {"symbol": "US10Y",  "name": "US 10-Year Treasury",  "description": "US 10-Year Treasury Yield",                 "instrumentClass": "bond",      "region": "US",     "currency": "USD", "yahoo_ticker": "^TNX",    "attributes": {"type": "government_bond", "maturity": "10Y"}},
]

# ══════════════════════════════════════════════════════════
# REGISTER SOURCES & INSTRUMENTS
# ══════════════════════════════════════════════════════════

def register_data_sources():
    """Register all financial data vendors"""

    # Check if any Nasdaq CSVs exist
    nasdaq_csvs_found = os.path.isdir(NASDAQ_CSV_DIR) and any(
        f.endswith('.csv') for f in os.listdir(NASDAQ_CSV_DIR)
    ) if os.path.isdir(NASDAQ_CSV_DIR) else False

    sources = [
        {
            "providerName": "Yahoo Finance",
            "providerType": "yahoo",
            "apiEndpoint":  "https://query1.finance.yahoo.com/v8/finance/chart/",
            "description":  "Free real-time and historical data. Stocks, ETFs, crypto."
        },
        {
            "providerName": "Nasdaq Data Link",
            "providerType": "nasdaq",
            "apiEndpoint":  "https://data.nasdaq.com/api/v3/datasets",
            "description":  "Open historical data: WIKI stocks, LBMA metals, FRED macro, Bitfinex crypto"
        },
        {
            "providerName": "Simulated Data",
            "providerType": "internal",
            "apiEndpoint":  "internal://simulator",
            "description":  "Simulated market data for development and testing"
        }
    ]

    # Check existing FIRST - never create duplicates
    registered = {}
    existing = requests.get(f"{BASE_URL}/api/sources").json()
    for s in existing.get('data', []):
        ptype = s.get('providerType')
        if ptype and ptype not in registered:
            registered[ptype] = s['dataSourceId']
            print(f"  ↩ Already exists: {s['providerName']} → {s['dataSourceId']}")

    # Only register sources not yet in DB
    for source in sources:
        if source['providerType'] in registered:
            continue
        r = requests.post(f"{BASE_URL}/ingest/register-source", json=source)
        if r.status_code == 201:
            data = r.json()['data']
            registered[source['providerType']] = data['dataSourceId']
            print(f"  ✓ New: {source['providerName']} → {data['dataSourceId']}")
    return registered

def register_instruments():
    """Register all financial instruments"""
    # Check existing FIRST - never create duplicates
    registered = {}
    existing = requests.get(f"{BASE_URL}/api/instruments?limit=200").json()
    for i in existing.get('data', []):
        if i['symbol'] not in registered:
            registered[i['symbol']] = i['assetId']
            print(f"  ↩ Already exists: {i['symbol']} → {i['assetId']}")

    # Only register instruments not yet in DB
    for inst in INSTRUMENTS:
        if inst['symbol'] in registered:
            continue
        payload = {k: inst[k] for k in ["symbol","name","description","instrumentClass","region","currency"]}
        payload["attributes"] = inst.get("attributes", {})
        r = requests.post(f"{BASE_URL}/ingest/register-instrument", json=payload)
        if r.status_code == 201:
            data = r.json()['data']
            registered[inst["symbol"]] = data['instrumentId']
            print(f"  ✓ New: {inst['symbol']} → {data['instrumentId']}")
    return registered

# ══════════════════════════════════════════════════════════
# MODE 1: NASDAQ CSV IMPORT
# ══════════════════════════════════════════════════════════

def load_nasdaq_csv(filepath, col_map):
    """
    Load a CSV file downloaded from data.nasdaq.com

    Nasdaq CSV format example (WIKI/AAPL):
      Date,Open,High,Low,Close,Volume,Ex-Dividend,Split Ratio,...
      2018-03-27,173.68,175.15,166.92,168.34,38962839.0,0.0,1.0,...

    Nasdaq CSV format example (LBMA/GOLD):
      Date,USD (PM),USD (AM),GBP (PM),GBP (AM),...
      2024-01-02,2063.35,2055.5,...
    """
    records = []
    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Date column (always first)
                date_str = row.get('Date') or row.get('date') or row.get('DATE')
                if not date_str:
                    continue

                # Map columns to our standard indicators
                indicators = {}
                row_lower = {k.lower().strip(): v for k, v in row.items()}

                for nasdaq_col, our_col in col_map.items():
                    val = row_lower.get(nasdaq_col.lower())
                    if val and val.strip() and val.strip() != 'None':
                        try:
                            indicators[our_col] = round(float(val.strip()), 4)
                        except ValueError:
                            pass

                if "close" not in indicators:
                    continue

                # Fill missing OHLC
                indicators.setdefault("open",   indicators["close"])
                indicators.setdefault("high",   indicators["close"])
                indicators.setdefault("low",    indicators["close"])
                indicators.setdefault("volume", 0)

                try:
                    # Parse date
                    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
                    records.append({
                        "dataTimestamp": dt.strftime("%Y-%m-%dT00:00:00"),
                        "indicators":    indicators,
                        "dataQuality":   "verified"
                    })
                except ValueError:
                    continue

        print(f"    ✓ Loaded {len(records)} records from {os.path.basename(filepath)}")
        return records

    except Exception as e:
        print(f"    ✗ Error reading {filepath}: {e}")
        return []

def ingest_nasdaq_csvs(instrument_ids, source_id):
    """Scan data/nasdaq/ folder and ingest any CSV files found"""

    if not os.path.isdir(NASDAQ_CSV_DIR):
        os.makedirs(NASDAQ_CSV_DIR, exist_ok=True)
        print(f"  ℹ Created folder: {NASDAQ_CSV_DIR}/")
        print(f"  ℹ Download CSV files from data.nasdaq.com and put them here")
        print(f"  ℹ Expected filenames:")
        for fname in NASDAQ_CSV_MAP.keys():
            print(f"      {fname}")
        return 0

    csv_files = [f for f in os.listdir(NASDAQ_CSV_DIR) if f.endswith('.csv')]
    if not csv_files:
        print(f"  ℹ No CSV files found in {NASDAQ_CSV_DIR}/")
        print(f"  ℹ Download from data.nasdaq.com and place files there")
        print(f"  ℹ Expected filenames: {', '.join(NASDAQ_CSV_MAP.keys())}")
        return 0

    total = 0
    for fname in csv_files:
        if fname not in NASDAQ_CSV_MAP:
            print(f"  ⚠ Unknown file: {fname} (skipping)")
            continue

        mapping    = NASDAQ_CSV_MAP[fname]
        symbol     = mapping["symbol"]
        col_map    = mapping["col_map"]
        inst_id    = instrument_ids.get(symbol)

        if not inst_id:
            print(f"  ⚠ Instrument {symbol} not registered (skipping {fname})")
            continue

        print(f"\n  📄 {fname} → {symbol}")
        filepath = os.path.join(NASDAQ_CSV_DIR, fname)
        records  = load_nasdaq_csv(filepath, col_map)

        if records:
            n = ingest_records(inst_id, source_id, records)
            total += n
            print(f"    → Ingested {n} records into warehouse")

    return total

# ══════════════════════════════════════════════════════════
# MODE 2: YAHOO FINANCE (live API)
# ══════════════════════════════════════════════════════════

def fetch_yahoo_finance(ticker, days=90):
    """
    Fetch real historical data from Yahoo Finance.
    Uses curl_cffi to bypass bot detection (Incapsula/Cloudflare).
    Install: pip install yfinance curl_cffi --upgrade
    """
    try:
        import yfinance as yf
        print(f"    → Yahoo Finance: {ticker}...")

        # Use curl_cffi session to bypass bot detection
        # This is required on networks where Yahoo blocks standard requests
        try:
            from curl_cffi import requests as cffi_requests
            session = cffi_requests.Session(impersonate='chrome')
            stock = yf.Ticker(ticker, session=session)
        except ImportError:
            # Fallback to standard session if curl_cffi not installed
            stock = yf.Ticker(ticker)

        hist = None
        for period in [f"{days}d", "3mo", "6mo"]:
            try:
                hist = stock.history(period=period, interval="1d", auto_adjust=True)
                if not hist.empty:
                    break
            except Exception:
                continue

        if hist is None or hist.empty:
            print(f"    ✗ No data for {ticker}")
            return []

        records = []
        for date, row in hist.iterrows():
            try:
                records.append({
                    "dataTimestamp": date.isoformat(),
                    "indicators": {
                        "open":         round(float(row['Open']),   4),
                        "close":        round(float(row['Close']),  4),
                        "high":         round(float(row['High']),   4),
                        "low":          round(float(row['Low']),    4),
                        "volume":       int(row.get('Volume', 0)),
                        "dividends":    round(float(row.get('Dividends', 0)), 6),
                        "stock_splits": float(row.get('Stock Splits', 0))
                    },
                    "dataQuality": "verified"
                })
            except Exception:
                continue

        print(f"    ✓ {len(records)} real days from Yahoo Finance")
        return records

    except ImportError:
        print("    ✗ Run: pip install yfinance curl_cffi --upgrade")
        return []
    except Exception as e:
        print(f"    ✗ Yahoo error: {e}")
        return []

# ══════════════════════════════════════════════════════════
# MODE 3: SIMULATED DATA
# ══════════════════════════════════════════════════════════

BASE_PRICES = {
    "TSLA": 242.0, "MSFT": 370.0, "AAPL": 178.0, "GOOGL": 175.0,
    "BTC-USD": 42000.0, "ETH-USD": 2200.0,
    "GOLD": 1950.0, "SILVER": 23.0, "US10Y": 4.5,
}

def generate_simulated_data(symbol, days=90):
    """Generate realistic simulated OHLCV data"""
    price = BASE_PRICES.get(symbol, 100.0)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    for day in range(days):
        date = start + timedelta(days=day)
        if date.weekday() >= 5:
            continue
        price  *= (1 + random.uniform(-0.03, 0.03))
        open_p  = round(price * random.uniform(0.98, 1.00), 4)
        close_p = round(price * random.uniform(0.99, 1.01), 4)
        high_p  = round(max(open_p, close_p) * random.uniform(1.00, 1.02), 4)
        low_p   = round(min(open_p, close_p) * random.uniform(0.98, 1.00), 4)
        records.append({
            "dataTimestamp": date.strftime("%Y-%m-%dT00:00:00"),
            "indicators": {
                "open": open_p, "close": close_p,
                "high": high_p, "low":   low_p,
                "volume": int(random.uniform(1_000_000, 50_000_000))
            },
            "dataQuality": "simulated"
        })
    print(f"    ✓ {len(records)} simulated days")
    return records

# ══════════════════════════════════════════════════════════
# INGEST
# ══════════════════════════════════════════════════════════

def ingest_records(instrument_id, source_id, records):
    if not records:
        return 0
    bulk = [
        {
            "instrumentId":  instrument_id,
            "dataSourceId":  source_id,
            "dataTimestamp": r["dataTimestamp"],
            "indicators":    r["indicators"],
            "dataQuality":   r.get("dataQuality", "verified")
        }
        for r in records
    ]
    resp = requests.post(
        f"{BASE_URL}/ingest/bulk-timeseries",
        json={"records": bulk},
        timeout=30
    )
    if resp.status_code == 201:
        return resp.json()['data']['inserted']
    print(f"    ✗ Ingest error: {resp.text[:100]}")
    return 0

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("  Acme Ltd — Financial Data Warehouse")
    print("  Data Vendor Integration")
    print("=" * 65)

    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print("\n✗ Cannot connect. Run: python app.py first!")
        return

    print(f"\n── Step 1: Registering Vendors ───────────────────────────────")
    source_ids = register_data_sources()

    print(f"\n── Step 2: Registering Instruments ───────────────────────────")
    instrument_ids = register_instruments()

    total = 0

    # ── MODE 1: Nasdaq CSV files ──────────────────────────────────
    print(f"\n── Step 3a: Nasdaq Data Link (CSV Import) ─────────────────────")
    print(f"  (Download CSVs from data.nasdaq.com → data/nasdaq/ folder)")
    if source_ids.get("nasdaq"):
        n = ingest_nasdaq_csvs(instrument_ids, source_ids["nasdaq"])
        total += n
        if n > 0:
            print(f"  ✓ Total Nasdaq records ingested: {n}")

    # ── MODE 2: Yahoo Finance (live) ──────────────────────────────
    print(f"\n── Step 3b: Yahoo Finance (Live API) ─────────────────────────")
    for inst in INSTRUMENTS:
        symbol = inst["symbol"]
        if symbol not in instrument_ids or not source_ids.get("yahoo"):
            continue
        print(f"\n  📊 {symbol}")
        records = fetch_yahoo_finance(inst["yahoo_ticker"], days=90)
        if records:
            n = ingest_records(instrument_ids[symbol], source_ids["yahoo"], records)
            total += n
            print(f"    → Ingested {n} Yahoo records")

    # ── MODE 3: Simulated (always runs) ───────────────────────────
    print(f"\n── Step 3c: Simulated Data (Fallback) ────────────────────────")
    for inst in INSTRUMENTS:
        symbol = inst["symbol"]
        if symbol not in instrument_ids or not source_ids.get("internal"):
            continue
        print(f"  📊 {symbol}")
        records = generate_simulated_data(symbol, days=90)
        n = ingest_records(instrument_ids[symbol], source_ids["internal"], records)
        total += n

    print("\n" + "=" * 65)
    print(f"  ✅ Done! Total records ingested: {total}")
    print("=" * 65)
    print(f"\n  Dashboard:  http://localhost:5000/ui")
    print(f"\n  💡 To add real Nasdaq data:")
    print(f"     1. Log in at https://data.nasdaq.com")
    print(f"     2. Search WIKI, LBMA, BITFINEX, or FRED datasets")
    print(f"     3. Download CSV → save to data/nasdaq/ folder")
    print(f"     4. Run this script again")
    print()

if __name__ == '__main__':
    main()