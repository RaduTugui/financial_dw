# Financial Data Warehouse — Acme Ltd

A production-ready financial data warehouse platform built with **Flask** and **MongoDB**. Collects real market data from financial vendors, stores it with full temporal history, exposes it via a RESTful API, includes Apache Spark analytics and ML forecasting, and provides an AI-powered assistant for natural language data exploration.

---

## 🎬 Demo Video

**[▶️ Watch Demo Video (3 minutes)](Demo.mp4)**

> The demo video `Demo.mp4` is included in the root of this repository and covers:
> - Live data ingestion from Yahoo Finance
> - REST API (Q1-Q5) curl demonstrations  
> - Time Series charts with real verified price data
> - Data Provenance with SHA256 hashing
> - Apache Spark analytics and ML forecasting
> - AI Assistant powered by Claude + MCP (multi-step agentic behavior)
> - Temporal database — soft delete and restore workflow

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MongoDB 7.0+
- Java 8+ (required for Apache Spark)
- Anthropic API key (for AI Assistant)

### Install & Run
```bash
git clone https://github.com/RaduTugui/financial_dw.git
cd financial_dw
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your API keys
python app.py          # Terminal 1
python sample_data_generator.py  # Terminal 2
# Open http://127.0.0.1:5000/ui
```

---

## 📁 Project Structure

```
financial_dw/
├── Demo.mp4                        ← 3-minute demo video
├── app.py                          ← Flask entry point
├── sample_data_generator.py        ← Data ingestion pipeline
├── pytest.ini                      ← Test configuration
├── requirements.txt
├── .env.example
├── templates/
│   └── dashboard.html              ← Full UI (dark/light/system theme)
├── tests/
│   └── test_dal.py                 ← 30+ unit tests
└── src/
    ├── database.py                 ← MongoDB init + indexes
    ├── models.py                   ← 8 temporal dataclasses
    ├── services.py                 ← DAL service layer
    ├── routes/
    │   ├── api.py                  ← REST API (Q1-Q5) + Spark trigger
    │   ├── data_ingest.py          ← Ingest + retry + DLQ
    │   ├── mcp_server.py           ← 10 MCP tools
    │   └── ai_chat.py              ← Claude AI + anti-hallucination
    ├── spark/
    │   ├── spark_analytics.py      ← UC3: Spark aggregations (M6)
    │   └── spark_ml_forecast.py    ← UC3: Spark ML forecasting (M7)
    └── utils/
        └── error_handlers.py
```

---

## 🧪 Unit Tests

```bash
pip install pytest
pytest tests/ -v
```

| Test Class | Coverage |
|-----------|---------|
| `TestModels` | Data model creation & serialization |
| `TestInstrumentService` | DAL CRUD operations |
| `TestTimeSeriesService` | Time series insert/query/bulk |
| `TestDataSourceService` | Source registration |
| `TestProvenanceService` | SHA256 hashing & determinism |
| `TestTemporalDatabase` | No in-place mutations, soft delete |
| `TestIngestionPipeline` | Flask endpoints, API contracts |
| `TestDataQuality` | Data normalization |

---

## ⚡ Apache Spark Analytics (UC3)

### Install PySpark
```bash
pip install pyspark==3.5.0 --timeout 300
```

### Run Spark Aggregation (M6)
```bash
python src/spark/spark_analytics.py
```
Computes: min/max/avg/stddev, 7-day/30-day moving averages, VaR 95%/99%, Sharpe ratio

### Run Spark ML Forecasting (M7)
```bash
python src/spark/spark_ml_forecast.py --symbol TSLA
python src/spark/spark_ml_forecast.py --symbol AAPL
```
Models: Linear Regression + Random Forest with RMSE/R²/MAE metrics + next day forecast

### Trigger via REST API
```bash
# Aggregation analytics
curl -X POST http://localhost:5000/api/analytics/spark \
  -H "Content-Type: application/json" \
  -d '{"job_type": "analytics"}'

# ML forecasting
curl -X POST http://localhost:5000/api/analytics/spark \
  -H "Content-Type: application/json" \
  -d '{"job_type": "ml", "symbol": "TSLA"}'
```

---

## 📡 REST API (UC2: Q1-Q5)

| Query | Endpoint |
|-------|----------|
| Q1 | `GET /api/instruments` |
| Q2 | `GET /api/instruments/{id}` |
| Q3 | `GET /api/sources` |
| Q4 | `GET /api/sources/{id}` |
| Q5 | `GET /api/timeseries?instrumentId=X&dataSourceId=Y&limit=10&offset=0` |

### Offset Pagination (Q5)
```bash
curl "http://localhost:5000/api/timeseries?instrumentId=X&dataSourceId=Y&limit=10&offset=0"
curl "http://localhost:5000/api/timeseries?instrumentId=X&dataSourceId=Y&limit=10&offset=10"
```

### All Endpoints
```
GET/POST /api/analytics/spark          Spark job trigger
GET      /api/analytics/timeseries-stats  Statistics
GET      /api/analytics/compare        Compare instruments
DELETE   /api/instruments/{id}         Soft delete
POST     /api/instruments/{id}/restore Restore
GET      /api/instruments/inactive     Deleted instruments
GET      /ingest/dlq                   Dead letter queue
POST     /ingest/dlq/retry             Retry failed ingestions
GET      /health                       Health check
```

---

## 🗄️ Temporal Database Design

Every record has:
```
validFrom / validTo    → valid time range
isActive               → soft delete flag
deletionMarker         → "DELETED_date_reason"
year / month           → partition fields
```

Rules enforced:
- ❌ No UPDATE in place
- ❌ No DELETE in place  
- ✅ Changes = new version
- ✅ Deletion = marker

---

## 🤖 AI Assistant (UC4)

10 MCP tools + Claude AI with strict anti-hallucination:
- Only uses data from tool results
- Never uses training knowledge for prices
- Cites which tool was called for every claim
- Multi-step agentic reasoning

---

## 📊 Data Vendors

| Vendor | Status |
|--------|--------|
| Yahoo Finance | ✅ Active (real verified data) |
| Nasdaq Data Link | ⚠ Registered (network blocked) |
| Simulated Data | ✅ Active |

### Ingestion Features
- Idempotent (skips existing dates)
- Retry with exponential backoff
- Dead Letter Queue for failures
- Concurrent ingestion safety
- Year/month partitioning

---

## ✅ Full Requirements Coverage

| # | Requirement | Status |
|---|-------------|--------|
| M1 | NoSQL database | ✅ MongoDB 7.0 |
| M2 | Temporal/versioned data | ✅ validFrom/validTo/isActive/deletionMarker |
| M3 | Provenance on every record | ✅ SHA256 + sourceId + timestamp |
| M4 | External data ingestion | ✅ Yahoo Finance + Nasdaq + Simulated |
| M5 | REST API Q1-Q5 | ✅ All implemented + pagination |
| M6 | Spark aggregation workflow | ✅ spark_analytics.py |
| M7 | Spark ML workflow | ✅ spark_ml_forecast.py |
| M8 | LLM via MCP | ✅ 10 tools + Claude Sonnet |
| - | Demo video | ✅ Demo.mp4 |
| - | Unit tests | ✅ 30+ tests in tests/test_dal.py |
| - | Year-based partitioning | ✅ year/month fields |
| - | Offset pagination | ✅ limit/offset on Q5 |
| - | Retry + DLQ | ✅ Exponential backoff + /ingest/dlq |
| - | Anti-hallucination | ✅ Strict system prompt |

---

**Built with:** Flask · MongoDB · PySpark · Python 3.12 · Yahoo Finance · Claude AI · MCP  
**GitHub:** https://github.com/RaduTugui/financial_dw  
**Demo:** [Demo.mp4](Demo.mp4)