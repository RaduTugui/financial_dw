"""
Data ingestion routes
Implements UC1: Data Ingest from Financial Data Providers
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from src.services import (
    InstrumentService, TimeSeriesService, DataSourceService,
    ProvenanceService, AttributeService
)
import requests
from typing import List, Dict, Any

ingest_bp = Blueprint('ingest', __name__)

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

        return jsonify({'status': 'success', 'data': result}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# INSTRUMENT REGISTRATION
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

        # Add custom attributes if provided
        if 'attributes' in data and isinstance(data['attributes'], dict):
            for attr_name, attr_value in data['attributes'].items():
                AttributeService.add_attribute(
                    instrument_id=result['instrumentId'],
                    attribute_name=attr_name,
                    attribute_value=attr_value,
                    attribute_type=type(attr_value).__name__
                )

        return jsonify({'status': 'success', 'data': result}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SINGLE TIME SERIES INGESTION
# ============================================================================

@ingest_bp.route('/timeseries', methods=['POST'])
def ingest_time_series():
    """
    Ingest one or more time series data points.
    Accepts a single record or an array.
    """
    try:
        data = request.get_json()
        records = data if isinstance(data, list) else [data]

        ingested_count = 0
        errors = []

        # Track which (instrument, source) pairs we've already recorded provenance for
        provenance_recorded = set()

        for record in records:
            try:
                required_fields = ['instrumentId', 'dataSourceId', 'dataTimestamp', 'indicators']
                if not all(field in record for field in required_fields):
                    errors.append(f"Record missing required fields: {required_fields}")
                    continue

                # Parse timestamp
                timestamp = record['dataTimestamp']
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)

                # Insert time series
                TimeSeriesService.insert_time_series(
                    instrument_id=record['instrumentId'],
                    data_source_id=record['dataSourceId'],
                    data_timestamp=timestamp,
                    indicators=record['indicators']
                )

                # Record provenance once per (instrument, source) pair
                prov_key = (record['instrumentId'], record['dataSourceId'])
                if prov_key not in provenance_recorded:
                    ProvenanceService.record_provenance(
                        instrument_id=record['instrumentId'],
                        source_id=record['dataSourceId'],
                        source_type='time_series_data',
                        raw_data={'instrumentId': record['instrumentId'],
                                  'dataSourceId': record['dataSourceId'],
                                  'ingestionMethod': 'api_post'},
                        ingestion_method='api_post',
                        transformation_logic=record.get('transformationLogic')
                    )
                    provenance_recorded.add(prov_key)

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
# BULK TIME SERIES INGESTION (optimized)
# ============================================================================

@ingest_bp.route('/bulk-timeseries', methods=['POST'])
def bulk_ingest_timeseries():
    """
    Bulk ingest time series records efficiently.
    Optimized for large imports from data vendors.

    Key optimization: records ONE provenance entry per (instrument, source)
    combination instead of one per record — prevents thousands of duplicate
    provenance entries when ingesting 90 days of data.
    """
    try:
        data = request.get_json()

        if 'records' not in data:
            return jsonify({'error': 'Missing "records" field'}), 400

        records = data['records']
        if not isinstance(records, list):
            return jsonify({'error': '"records" must be an array'}), 400

        # ── Prepare records for bulk insert ──
        prepared_records = []
        from uuid import uuid4

        for record in records:
            try:
                required_fields = ['instrumentId', 'dataSourceId', 'dataTimestamp', 'indicators']
                if not all(field in record for field in required_fields):
                    continue

                timestamp = record['dataTimestamp']
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)

                prepared_records.append({
                    'seriesId':      f"TS_{uuid4().hex[:12].upper()}",
                    'instrumentId':  record['instrumentId'],
                    'dataSourceId':  record['dataSourceId'],
                    'dataTimestamp': timestamp,
                    'indicators':    record['indicators'],
                    'dataQuality':   record.get('dataQuality', 'verified'),
                    'validFrom':     datetime.utcnow(),
                    'recordedAt':    datetime.utcnow()
                })

            except Exception:
                continue

        if not prepared_records:
            return jsonify({'error': 'No valid records to insert'}), 400

        # ── Bulk insert all time series records ──
        result = TimeSeriesService.bulk_insert_time_series(prepared_records)

        # ── Record provenance: ONE entry per (instrument, source) pair ──
        # Group records by (instrumentId, dataSourceId)
        groups = {}
        for record in prepared_records:
            key = (record['instrumentId'], record['dataSourceId'])
            if key not in groups:
                groups[key] = {
                    'instrumentId': record['instrumentId'],
                    'dataSourceId': record['dataSourceId'],
                    'count': 0,
                    'firstTimestamp': record['dataTimestamp'],
                    'lastTimestamp':  record['dataTimestamp'],
                    'dataQuality':    record.get('dataQuality', 'verified')
                }
            groups[key]['count'] += 1
            # Track date range
            if record['dataTimestamp'] < groups[key]['firstTimestamp']:
                groups[key]['firstTimestamp'] = record['dataTimestamp']
            if record['dataTimestamp'] > groups[key]['lastTimestamp']:
                groups[key]['lastTimestamp'] = record['dataTimestamp']

        # One provenance record per (instrument, source) — not per data point!
        for key, group in groups.items():
            ProvenanceService.record_provenance(
                instrument_id=group['instrumentId'],
                source_id=group['dataSourceId'],
                source_type='bulk_import',
                raw_data={
                    'instrumentId':   group['instrumentId'],
                    'dataSourceId':   group['dataSourceId'],
                    'recordCount':    group['count'],
                    'firstTimestamp': str(group['firstTimestamp']),
                    'lastTimestamp':  str(group['lastTimestamp']),
                    'dataQuality':    group['dataQuality'],
                    'ingestionMethod': 'bulk_api_post'
                },
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
    Fetch data from external provider API and ingest it.
    Used to pull data from Nasdaq Data Link, Bloomberg, etc.
    """
    try:
        data = request.get_json()

        required_fields = ['dataSourceId', 'apiEndpoint', 'params']
        if not all(field in data for field in required_fields):
            return jsonify({'error': f'Missing required fields: {required_fields}'}), 400

        # Verify the data source exists
        source = DataSourceService.get_data_source(data['dataSourceId'])
        if not source:
            return jsonify({'error': 'Data source not found'}), 404

        # Fetch from external provider
        try:
            response = requests.get(
                data['apiEndpoint'],
                params=data['params'],
                timeout=30
            )
            response.raise_for_status()
            external_data = response.json()

        except requests.RequestException as e:
            return jsonify({'error': f'Failed to fetch from provider API: {str(e)}'}), 502

        # Transform to our standard format
        processed_records = _transform_external_data(
            external_data,
            data.get('transformationLogic', 'default')
        )

        # Ingest records
        ingested = 0
        for record in processed_records:
            try:
                TimeSeriesService.insert_time_series(
                    instrument_id=record['instrumentId'],
                    data_source_id=data['dataSourceId'],
                    data_timestamp=record['dataTimestamp'],
                    indicators=record['indicators']
                )
                ingested += 1
            except Exception:
                continue

        # One provenance record for the entire fetch operation
        if ingested > 0:
            ProvenanceService.record_provenance(
                instrument_id=data.get('instrumentId', 'unknown'),
                source_id=data['dataSourceId'],
                source_type='external_api',
                raw_data={
                    'apiEndpoint':    data['apiEndpoint'],
                    'recordsFetched': ingested,
                    'transformationLogic': data.get('transformationLogic', 'default')
                },
                ingestion_method='api_fetch',
                transformation_logic=data.get('transformationLogic')
            )

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
    """Transform external API response to our standard time series format"""
    records = []

    if isinstance(external_data, list):
        for item in external_data:
            r = _transform_single_record(item, logic)
            if r:
                records.append(r)

    elif isinstance(external_data, dict):
        if 'data' in external_data and isinstance(external_data['data'], list):
            for item in external_data['data']:
                r = _transform_single_record(item, logic)
                if r:
                    records.append(r)
        else:
            r = _transform_single_record(external_data, logic)
            if r:
                records.append(r)

    return records


def _transform_single_record(item: Dict, logic: str) -> Dict:
    """Transform a single external record to our standard format"""
    try:
        return {
            'instrumentId':  item.get('instrumentId') or item.get('symbol') or item.get('id'),
            'dataSourceId':  item.get('dataSourceId'),
            'dataTimestamp': datetime.fromisoformat(item['timestamp']) if item.get('timestamp') else datetime.utcnow(),
            'indicators': {
                'open':   float(item.get('open',   0)),
                'close':  float(item.get('close',  0)),
                'high':   float(item.get('high',   0)),
                'low':    float(item.get('low',    0)),
                'volume': float(item.get('volume', 0)),
                # Include any extra fields from the provider
                **{k: v for k, v in item.items()
                   if k not in ['open', 'close', 'high', 'low', 'volume',
                                'timestamp', 'instrumentId', 'dataSourceId', 'symbol', 'id']}
            }
        }
    except Exception:
        return None