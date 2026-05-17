"""
Data ingestion routes
Implements UC1: Data Ingest from Financial Data Providers
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from src.services import (
    InstrumentService, TimeSeriesService, DataSourceService,
    ProvenanceService, AttributeService
)
import requests
from typing import List, Dict, Any

ingest_bp = Blueprint('ingest', __name__)


def _normalize_timestamp(ts):
    """Parse timestamp string and normalize to UTC naive datetime"""
    if isinstance(ts, datetime):
        # Already a datetime - strip timezone if present
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
            # Strip timezone offset - normalize to UTC naive
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


# ============================================================================
# DATA SOURCE REGISTRATION
# ============================================================================

@ingest_bp.route('/register-source', methods=['POST'])
def register_data_source():
    """Register a new financial data source/provider"""
    try:
        data = request.get_json()

        required_fields = ['providerName', 'providerType', 'apiEndpoint', 'description']
        if not all(field in data for field in required_fields):
            return jsonify({'error': f'Missing required fields: {required_fields}'}), 400

        result = DataSourceService.register_data_source(
            provider_name=data['providerName'],
            provider_type=data['providerType'],
            api_endpoint=data['apiEndpoint'],
            description=data['description']
        )

        return jsonify({
            'status': 'success',
            'data': result
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# INSTRUMENT CREATION & REGISTRATION
# ============================================================================

@ingest_bp.route('/register-instrument', methods=['POST'])
def register_instrument():
    """Register a new financial instrument"""
    try:
        data = request.get_json()

        required_fields = ['symbol', 'name', 'description', 'instrumentClass', 'region', 'currency']
        if not all(field in data for field in required_fields):
            return jsonify({'error': f'Missing required fields: {required_fields}'}), 400

        result = InstrumentService.create_instrument(
            symbol=data['symbol'],
            name=data['name'],
            description=data['description'],
            instrument_class=data['instrumentClass'],
            region=data['region'],
            currency=data['currency']
        )

        # If custom attributes provided, add them
        if 'attributes' in data and isinstance(data['attributes'], dict):
            for attr_name, attr_value in data['attributes'].items():
                AttributeService.add_attribute(
                    instrument_id=result['instrumentId'],
                    attribute_name=attr_name,
                    attribute_value=attr_value,
                    attribute_type=type(attr_value).__name__
                )

        return jsonify({
            'status': 'success',
            'data': result
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# TIME SERIES DATA INGESTION
# ============================================================================

@ingest_bp.route('/timeseries', methods=['POST'])
def ingest_time_series():
    """
    Ingest time series data point(s)
    Single data point or bulk ingestion
    """
    try:
        data = request.get_json()

        # Support both single record and bulk
        records = data if isinstance(data, list) else [data]

        ingested_count = 0
        errors = []

        for record in records:
            try:
                required_fields = ['instrumentId', 'dataSourceId', 'dataTimestamp', 'indicators']
                if not all(field in record for field in required_fields):
                    errors.append(f"Record missing fields: {required_fields}")
                    continue

                # Parse and normalize timestamp to UTC
                timestamp = _normalize_timestamp(record['dataTimestamp'])

                # Prepare time series data
                ts_data = {
                    'seriesId': f"TS_{__import__('uuid').uuid4().hex[:12].upper()}",
                    'instrumentId': record['instrumentId'],
                    'dataSourceId': record['dataSourceId'],
                    'dataTimestamp': timestamp,
                    'indicators': record['indicators'],
                    'dataQuality': record.get('dataQuality', 'verified'),
                    'validFrom': datetime.utcnow(),
                    'recordedAt': datetime.utcnow()
                }

                # Insert
                result = TimeSeriesService.insert_time_series(
                    instrument_id=record['instrumentId'],
                    data_source_id=record['dataSourceId'],
                    data_timestamp=timestamp,
                    indicators=record['indicators']
                )

                # Record provenance
                ProvenanceService.record_provenance(
                    instrument_id=record['instrumentId'],
                    source_id=record['dataSourceId'],
                    source_type='time_series_data',
                    raw_data=record,
                    ingestion_method='api_post',
                    transformation_logic=record.get('transformationLogic')
                )

                ingested_count += 1

            except Exception as e:
                errors.append(f"Error processing record: {str(e)}")

        return jsonify({
            'status': 'success' if ingested_count > 0 else 'partial',
            'ingestedCount': ingested_count,
            'totalAttempted': len(records),
            'errors': errors if errors else None
        }), 201 if ingested_count > 0 else 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# BULK DATA INGESTION
# ============================================================================

@ingest_bp.route('/bulk-timeseries', methods=['POST'])
def bulk_ingest_timeseries():
    """
    Bulk ingest time series records efficiently
    Optimized for large data imports
    """
    try:
        data = request.get_json()

        if 'records' not in data:
            return jsonify({'error': 'Missing "records" field'}), 400

        records = data['records']
        if not isinstance(records, list):
            return jsonify({'error': '"records" must be an array'}), 400

        # Transform and prepare records
        prepared_records = []

        for record in records:
            try:
                required_fields = ['instrumentId', 'dataSourceId', 'dataTimestamp', 'indicators']
                if not all(field in record for field in required_fields):
                    continue

                timestamp = _normalize_timestamp(record['dataTimestamp'])

                prepared = {
                    'seriesId': f"TS_{__import__('uuid').uuid4().hex[:12].upper()}",
                    'instrumentId': record['instrumentId'],
                    'dataSourceId': record['dataSourceId'],
                    'dataTimestamp': timestamp,
                    'indicators': record['indicators'],
                    'dataQuality': record.get('dataQuality', 'verified'),
                    'validFrom': datetime.utcnow(),
                    'recordedAt': datetime.utcnow()
                }

                prepared_records.append(prepared)

            except Exception as e:
                continue

        if not prepared_records:
            return jsonify({'error': 'No valid records to insert'}), 400

        # Bulk insert
        result = TimeSeriesService.bulk_insert_time_series(prepared_records)

        # Record provenance for all records
        for record in prepared_records:
            ProvenanceService.record_provenance(
                instrument_id=record['instrumentId'],
                source_id=record['dataSourceId'],
                source_type='bulk_import',
                raw_data=record,
                ingestion_method='bulk_api_post'
            )

        return jsonify({
            'status': 'success',
            'data': result
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EXTERNAL API DATA FETCHING
# ============================================================================

@ingest_bp.route('/fetch-from-api', methods=['POST'])
def fetch_and_ingest_from_api():
    """
    Fetch data from external API and ingest it
    Used to pull data from Nasdaq, Bloomberg, etc.
    """
    try:
        data = request.get_json()

        required_fields = ['dataSourceId', 'apiEndpoint', 'params']
        if not all(field in data for field in required_fields):
            return jsonify({'error': f'Missing required fields: {required_fields}'}), 400

        # Get data source info
        source = DataSourceService.get_data_source(data['dataSourceId'])
        if not source:
            return jsonify({'error': 'Data source not found'}), 404

        # Fetch from external API
        try:
            response = requests.get(
                data['apiEndpoint'],
                params=data['params'],
                timeout=30
            )
            response.raise_for_status()
            external_data = response.json()

        except requests.RequestException as e:
            return jsonify({'error': f'Failed to fetch from API: {str(e)}'}), 502

        # Transform external data to our format (implementation depends on API format)
        # This is a generic example
        processed_records = _transform_external_data(
            external_data,
            data.get('transformationLogic', 'default')
        )

        # Ingest transformed data
        ingested = 0
        for record in processed_records:
            try:
                TimeSeriesService.insert_time_series(
                    instrument_id=record['instrumentId'],
                    data_source_id=data['dataSourceId'],
                    data_timestamp=record['dataTimestamp'],
                    indicators=record['indicators']
                )

                ProvenanceService.record_provenance(
                    instrument_id=record['instrumentId'],
                    source_id=data['dataSourceId'],
                    source_type='external_api',
                    raw_data=record,
                    ingestion_method='api_fetch',
                    transformation_logic=data.get('transformationLogic')
                )

                ingested += 1

            except Exception as e:
                continue

        return jsonify({
            'status': 'success',
            'ingestedRecords': ingested,
            'totalProcessed': len(processed_records),
            'message': f'Fetched and ingested {ingested} records from {source["providerName"]}'
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _transform_external_data(external_data: Any, logic: str) -> List[Dict]:
    """
    Transform external API data to our time series format
    This is a placeholder - actual implementation depends on provider API format
    """
    records = []

    # Handle different data structures
    if isinstance(external_data, list):
        for item in external_data:
            records.append(_transform_single_record(item, logic))

    elif isinstance(external_data, dict):
        # Check for common API response structures
        if 'data' in external_data and isinstance(external_data['data'], list):
            for item in external_data['data']:
                records.append(_transform_single_record(item, logic))
        else:
            records.append(_transform_single_record(external_data, logic))

    return [r for r in records if r is not None]


def _transform_single_record(item: Dict, logic: str) -> Dict:
    """Transform a single external record"""
    try:
        # Generic transformation - customize based on actual API
        return {
            'instrumentId': item.get('instrumentId') or item.get('symbol') or item.get('id'),
            'dataSourceId': item.get('dataSourceId'),
            'dataTimestamp': datetime.fromisoformat(item.get('timestamp')) if item.get(
                'timestamp') else datetime.utcnow(),
            'indicators': {
                'open': float(item.get('open', 0)),
                'close': float(item.get('close', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'volume': float(item.get('volume', 0)),
                **{k: v for k, v in item.items() if
                   k not in ['open', 'close', 'high', 'low', 'volume', 'timestamp', 'instrumentId', 'dataSourceId',
                             'symbol', 'id']}
            }
        }

    except Exception:
        return None


# ============================================================================
# FETCH FROM YAHOO FINANCE (UI button)
# ============================================================================

@ingest_bp.route('/fetch-yahoo', methods=['POST'])
def fetch_from_yahoo():
    """
    Fetch real data from Yahoo Finance for a specific instrument.
    Called from the UI 'Fetch & Ingest' button.
    """
    try:
        data = request.get_json()
        instrument_id = data.get('instrumentId')
        source_id = data.get('dataSourceId')
        ticker = data.get('ticker')
        days = data.get('days', 90)

        if not all([instrument_id, source_id, ticker]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Fetch from Yahoo Finance using curl_cffi
        try:
            import yfinance as yf
            try:
                from curl_cffi import requests as cffi_requests
                session = cffi_requests.Session(impersonate='chrome')
                stock = yf.Ticker(ticker, session=session)
            except ImportError:
                stock = yf.Ticker(ticker)

            hist = stock.history(period=f"{days}d", interval="1d", auto_adjust=True)

            if hist is None or hist.empty:
                return jsonify({'error': f'No data found for ticker {ticker}'}), 404

        except ImportError:
            return jsonify({'error': 'yfinance not installed. Run: pip install yfinance'}), 500

        # Prepare records
        records = []
        for date, row in hist.iterrows():
            try:
                records.append({
                    "instrumentId": instrument_id,
                    "dataSourceId": source_id,
                    "dataTimestamp": date.strftime('%Y-%m-%dT%H:%M:%S'),
                    "indicators": {
                        "open": round(float(row['Open']), 4),
                        "close": round(float(row['Close']), 4),
                        "high": round(float(row['High']), 4),
                        "low": round(float(row['Low']), 4),
                        "volume": int(row.get('Volume', 0)),
                        "dividends": round(float(row.get('Dividends', 0)), 6),
                        "stock_splits": float(row.get('Stock Splits', 0))
                    },
                    "dataQuality": "verified"
                })
            except Exception:
                continue

        if not records:
            return jsonify({'error': 'No valid records to ingest'}), 400

        # Bulk ingest
        result = TimeSeriesService.bulk_insert_time_series(records)

        # Record provenance
        ProvenanceService.record_provenance(
            instrument_id=instrument_id,
            source_id=source_id,
            source_type='live_api',
            raw_data={
                'ticker': ticker,
                'days': days,
                'recordCount': len(records)
            },
            ingestion_method='ui_fetch_yahoo'
        )

        return jsonify({
            'status': 'success',
            'fetched': len(records),
            'ingested': result.get('inserted', 0),
            'ticker': ticker
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500