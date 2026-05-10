# Financial Data Warehouse — Acme Ltd

A production-ready financial data warehouse platform built with **Flask** and **MongoDB**. Collects real market data from financial vendors, stores it with full temporal history, exposes it via a RESTful API, and provides an AI-powered assistant for natural language data exploration.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MongoDB 7.0+ running on `localhost:27017`
- An Anthropic API key (for AI Assistant)

### Install MongoDB on Ubuntu 24.04
```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl start mongod && sudo systemctl enable mongod
```

### Setup & Run
```bash
# 1. Clone the repository
git clone https://github.com/RaduTugui/financial_dw.git
cd financial_dw

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your API keys

# 5. Start the Flask server (Terminal 1)
python app.py

# 6. Load sample data (Terminal 2)
python sample_data_generator.py

# 7. Open the dashboard
# http://127.0.0.1:5000/ui
```

---

## 📁 Project Structure

```
financial_dw/
│
├── app.py                          # Flask application entry point
├── requirements.txt                # Python dependencies
├── sample_data_generator.py        # Data vendor integration & sample data
├── .env.example                    # Environment variables template
│
├── templates/
│   └── dashboard.html              # Full dashboard UI (dark/light/system theme)
│
└── src/
    ├── database.py                 # MongoDB initialization & indexes
    ├── models.py                   # Data models (8 dataclasses)
    ├── services.py                 # Business logic (6 service classes)
    │
    ├── routes/
    │   ├── api.py                  # REST API endpoints (UC2: Q1-Q5)
    │   ├── data_ingest.py          # Data ingestion endpoints (UC1)
    │   ├── mcp_server.py           # MCP tools for LLM integration (UC4)
    │   └── ai_chat.py              # Claude AI chat proxy (UC4)
    │
    └── utils/
        └── error_handlers.py       # Flask error handlers
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill in your keys:

```env
MONGO_URI=mongodb://localhost:27017/financial_dw
FLASK_DEBUG=True
NASDAQ_API_KEY=your_nasdaq_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

---

## 🗄️ Data Model

### Collections (8 total — all temporal)

| Collection | Description |
|-----------|-------------|
| `financial_instruments` | Master records for all assets |
| `time_series_data` | Price/indicator data over time |
| `data_sources` | Registered data providers |
| `data_provenance` | Data lineage & integrity tracking |
| `instrument_attributes` | Heterogeneous custom attributes |
| `portfolios` | Portfolio definitions |
| `portfolio_holdings` | Assets held in portfolios |
| `analytics_jobs` | ML/analytics job tracking |

### Temporal Database Design

Every record contains:
```
validFrom        → when this version became valid
validTo          → null = still valid; date = expired
isActive         → true = active; false = soft deleted
deletionMarker   → "DELETED_2026-05-10_reason" if deleted
transactionStart/End → when WE recorded/superseded it
```

Rules enforced:
- No UPDATE in place — changes create new versions
- No DELETE in place — deletion sets isActive=false + deletionMarker
- Full historical queries at any point in time

---

## 📡 REST API

### UC2 — Required Queries (Q1-Q5)

| Query | Endpoint | Description |
|-------|----------|-------------|
| Q1 | `GET /api/instruments` | List all instruments (limited info) |
| Q2 | `GET /api/instruments/{id}` | Full instrument details |
| Q3 | `GET /api/sources` | List all data sources |
| Q4 | `GET /api/sources/{id}` | Full data source details |
| Q5 | `GET /api/timeseries?instrumentId=X&dataSourceId=Y` | Time series data |

### Additional Endpoints

```
GET    /api/timeseries/latest              Latest price
GET    /api/analytics/timeseries-stats    Statistics (min/max/avg/median)
GET    /api/analytics/compare             Compare multiple instruments
GET    /api/provenance/{id}               Data lineage
GET    /api/instruments/inactive          List soft-deleted instruments
POST   /api/instruments/{id}/restore      Restore soft-deleted instrument
DELETE /api/instruments/{id}              Soft delete (temporal deletion)
GET    /health                            Health check
```

### Example Requests

```bash
# List all instruments (Q1)
curl http://localhost:5000/api/instruments

# Get time series (Q5)
curl "http://localhost:5000/api/timeseries?instrumentId=INST_XXX&dataSourceId=DS_YYY"

# Soft delete
curl -X DELETE http://localhost:5000/api/instruments/INST_XXX \
  -H "Content-Type: application/json" \
  -d '{"reason": "delisted"}'

# Restore
curl -X POST http://localhost:5000/api/instruments/INST_XXX/restore
```

---

## 📊 Data Vendors

| Vendor | Type | Status | Data |
|--------|------|--------|------|
| **Yahoo Finance** | Live API | Active | Stocks, ETFs, Crypto, Commodities |
| **Nasdaq Data Link** | REST API | Registered | Blocked by network WAF* |
| **Simulated Data** | Internal | Active | Realistic OHLCV for testing |

> *Nasdaq Data Link is fully implemented with authentication. Access is blocked by Incapsula WAF at ISP level — not a code issue. Yahoo Finance serves as the primary verified source.

### Instruments

| Symbol | Name | Class |
|--------|------|-------|
| TSLA | Tesla Inc | Stock |
| MSFT | Microsoft Corporation | Stock |
| AAPL | Apple Inc | Stock |
| GOOGL | Alphabet Inc | Stock |
| BTC-USD | Bitcoin | Crypto |
| ETH-USD | Ethereum | Crypto |
| GOLD | Gold | Commodity |
| SILVER | Silver | Commodity |
| US10Y | US 10-Year Treasury | Bond |

---

## 🤖 AI Assistant (UC4)

Powered by **Claude AI + MCP Protocol**. Answers questions grounded in real warehouse data.

### MCP Tools Available

| Tool | What it does |
|------|-------------|
| `list_instruments` | Browse available assets |
| `get_instrument` | Get asset details |
| `get_timeseries` | Fetch price history |
| `get_latest_price` | Current price |
| `compute_statistics` | Min/max/avg/median |
| `analyze_trend` | Trend & volatility |
| `compare_instruments` | Side-by-side comparison |
| `list_data_sources` | Browse providers |
| `get_data_source` | Provider details |
| `get_provenance` | Data lineage |

### Example Questions

```
"What instruments are available?"
"What's the trend for TSLA?"
"Compare MSFT and AAPL performance"
"What are Bitcoin's statistics for the last month?"
"Where does the data come from?"
```

Claude automatically chains multiple tools for complex questions (agentic behavior).

---

## 🖥️ Dashboard Pages

| Page | Features |
|------|---------|
| Dashboard | Stats overview, instruments list, data sources |
| Instruments | Search, filter, Details modal, Chart, Delete/Restore |
| Time Series | Price chart, volume chart, stats bar, date range picker |
| Data Sources | Vendors with Active/No data status badges |
| Provenance | Data lineage with SHA256 integrity hashes |
| AI Assistant | Natural language chat + tool call log |
| Ingest Data | Manually add instruments and price data |

**Themes:** 🌙 Dark / ☀️ Light / 💻 System (saved in localStorage)

---

## ✅ Requirements Coverage

| Requirement | Status |
|-------------|--------|
| UC1: Data Ingest from providers | ✅ |
| UC1: Provenance tracking | ✅ |
| UC2: Q1-Q5 REST API queries | ✅ |
| UC3: Analytics & aggregation | ✅ |
| UC4: LLM via MCP | ✅ |
| Bonus: Agentic multi-step AI | ✅ |
| NoSQL database (MongoDB) | ✅ |
| Heterogeneous data model | ✅ |
| Temporal database design | ✅ |

---

## 🛠️ Troubleshooting

**MongoDB not connecting**
```bash
sudo systemctl start mongod
```

**Yahoo Finance data not loading**
```bash
pip install yfinance curl_cffi --upgrade
```

**AI Assistant not responding**
- Verify `ANTHROPIC_API_KEY` is in `.env`
- Restart Flask after editing `.env`

---

## 📦 Dependencies

```
Flask==2.3.3
Flask-CORS==4.0.0
pymongo==4.5.0
python-dotenv==1.0.0
requests==2.31.0
yfinance==1.3.0
curl_cffi
nasdaq-data-link
```

---

**Built with:** Flask · MongoDB · Python 3.12 · Yahoo Finance · Claude AI · MCP  
**GitHub:** https://github.com/RaduTugui/financial_dw  
**Version:** 1.0.0 | **Status:** Complete