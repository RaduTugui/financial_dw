# Financial Data Warehouse - Acme Ltd

## What is this?
A REST API platform built with Flask + MongoDB to store and query financial market data.

---

## STEP 1 - Start MongoDB with Docker

```bash
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -v mongodb_data:/data/db \
  mongo:latest
```

Verify it's running:
```bash
docker ps
```

---

## STEP 2 - Setup Python

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate        # Linux/Mac
# OR
venv\Scripts\activate           # Windows

# Install packages
pip install -r requirements.txt
```

---

## STEP 3 - Run the App

```bash
python app.py
```

You should see:
```
✓ MongoDB connection established
✓ All indexes created
Running on http://0.0.0.0:5000/
```

---

## STEP 4 - Load Sample Data

Open a NEW terminal (keep app.py running):

```bash
source venv/bin/activate
python sample_data_generator.py
```

This creates:
- 3 data sources (Nasdaq, Bloomberg, Internal)
- 6 instruments (TSLA, MSFT, AAPL, BTC, ETH, GLD)
- ~540 time series price records

---

## STEP 5 - Test the API

```bash
# Health check
curl http://localhost:5000/health

# Q1 - List all instruments
curl http://localhost:5000/api/instruments

# Q3 - List all data sources
curl http://localhost:5000/api/sources
```

For Q2, Q4, Q5 you need the IDs returned from Q1/Q3:

```bash
# Q2 - Get instrument details (use an ID from Q1)
curl http://localhost:5000/api/instruments/INST_XXXXXXXXXXXX

# Q4 - Get source details (use an ID from Q3)
curl http://localhost:5000/api/sources/DS_XXXXXXXXXXXX

# Q5 - Get time series (use IDs from Q1 and Q3)
curl "http://localhost:5000/api/timeseries?instrumentId=INST_XXXXXXXXXXXX&dataSourceId=DS_XXXXXXXXXXXX"
```

---

## API Endpoints Reference

### Data Access
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /api/instruments | List all instruments (Q1) |
| GET | /api/instruments/{id} | Get instrument details (Q2) |
| GET | /api/sources | List all data sources (Q3) |
| GET | /api/sources/{id} | Get source details (Q4) |
| GET | /api/timeseries | Get time series data (Q5) |
| GET | /api/timeseries/latest | Get latest price |
| GET | /api/analytics/timeseries-stats | Get statistics |
| GET | /api/analytics/compare | Compare instruments |
| GET | /api/provenance/{id} | Get data provenance |

### Data Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /ingest/register-source | Register a data provider |
| POST | /ingest/register-instrument | Register an instrument |
| POST | /ingest/timeseries | Add time series data |
| POST | /ingest/bulk-timeseries | Bulk add time series data |

### MCP (for LLM integration later)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /mcp/tools | List available tools |
| POST | /mcp/call | Call a tool |

---

## Project Structure

```
financial_dw/
│
├── app.py                      ← MAIN FILE (run this)
├── requirements.txt            ← Python packages
├── sample_data_generator.py    ← Creates test data
├── .env.example                ← Copy to .env to configure
│
└── src/
    ├── database.py             ← MongoDB connection
    ├── models.py               ← Data models
    ├── services.py             ← Business logic
    ├── routes/
    │   ├── api.py              ← REST API endpoints
    │   ├── data_ingest.py      ← Data ingestion endpoints
    │   └── mcp_server.py       ← MCP tools (for LLM later)
    └── utils/
        └── error_handlers.py   ← Error handling
```

---

## Troubleshooting

**"Connection refused" when starting Flask**
→ MongoDB is not running. Run the docker command in STEP 1.

**"ModuleNotFoundError"**
→ Virtual environment not activated or packages not installed.
→ Run: pip install -r requirements.txt

**"Port 5000 already in use"**
→ Edit app.py last line, change port=5000 to port=5001

**MongoDB data check**
```bash
docker exec -it mongodb mongosh
use financial_dw
db.financial_instruments.countDocuments()
db.time_series_data.countDocuments()
exit
```

**Stop/Start MongoDB**
```bash
docker stop mongodb    # Stop
docker start mongodb   # Start again
```

---

## Configuration (optional)

Copy .env.example to .env and edit:
```bash
cp .env.example .env
```

Default settings (no changes needed for local testing):
```
MONGO_URI=mongodb://localhost:27017/financial_dw
FLASK_DEBUG=True
PORT=5000
```
