"""
RESTful API routes for financial data consumption
Implements UC2: Expose Financial Data for Consumption via RESTful API
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from src.services import (
    InstrumentService, TimeSeriesService, DataSourceService,
    ProvenanceService, PortfolioService, AttributeService
)

api_bp = Blueprint('api', __name__)


# ============================================================================
# FINANCIAL INSTRUMENTS ENDPOINTS
# ============================================================================

@api_bp.route('/instruments', methods=['GET'])
def list_instruments():
    """
    Q1: Return limited info about all financial assets available
    Returns list of instruments with identification data
    """
    try:
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)

        instruments = InstrumentService.list_instruments(limit=limit, offset=offset)

        # Return limited info (Q1 requirement)
        simplified = [{
            'assetId': inst['instrumentId'],
            'symbol': inst['symbol'],
            'name': inst['name'],
            'instrumentClass': inst['instrumentClass'],
            'region': inst['region']
        } for inst in instruments]

        return jsonify({
            'status': 'success',
            'count': len(simplified),
            'limit': limit,
            'offset': offset,
            'data': simplified
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/instruments/<instrument_id>', methods=['GET'])
def get_instrument_details(instrument_id):
    """
    Q2: Return all details of an asset knowing its identifier
    """
    try:
        instrument = InstrumentService.get_instrument(instrument_id)

        if not instrument:
            return jsonify({'error': 'Instrument not found'}), 404

        # Get attributes
        attributes = AttributeService.get_attributes(instrument_id)

        # Get data sources providing data for this instrument
        data_sources = DataSourceService.list_data_sources_for_instrument(instrument_id)

        return jsonify({
            'status': 'success',
            'data': {
                **instrument,
                'attributes': attributes,
                'dataSources': data_sources
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/instruments/symbol/<symbol>', methods=['GET'])
def get_instrument_by_symbol(symbol):
    """Get instrument by symbol"""
    try:
        instrument = InstrumentService.get_instrument_by_symbol(symbol)

        if not instrument:
            return jsonify({'error': f'Instrument {symbol} not found'}), 404

        return jsonify({
            'status': 'success',
            'data': instrument
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/instruments/class/<instrument_class>', methods=['GET'])
def get_instruments_by_class(instrument_class):
    """Get all instruments of a specific class"""
    try:
        limit = request.args.get('limit', default=100, type=int)
        instruments = InstrumentService.list_instruments_by_class(
            instrument_class, limit=limit
        )

        return jsonify({
            'status': 'success',
            'count': len(instruments),
            'class': instrument_class,
            'data': instruments
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DATA SOURCES ENDPOINTS
# ============================================================================

@api_bp.route('/sources', methods=['GET'])
def list_data_sources():
    """
    Q3: Return limited info about all sources of data available
    Returns list of data sources with identification data
    """
    try:
        sources = DataSourceService.list_data_sources()

        # Return limited info (Q3 requirement)
        simplified = [{
            'dataSourceId': source['dataSourceId'],
            'providerName': source['providerName'],
            'providerType': source['providerType'],
            'description': source['description']
        } for source in sources]

        return jsonify({
            'status': 'success',
            'count': len(simplified),
            'data': simplified
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sources/<source_id>', methods=['GET'])
def get_source_details(source_id):
    """
    Q4: Return all details of a data source knowing its identifier
    """
    try:
        source = DataSourceService.get_data_source(source_id)

        if not source:
            return jsonify({'error': 'Data source not found'}), 404

        return jsonify({
            'status': 'success',
            'data': source
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# TIME SERIES DATA ENDPOINTS
# ============================================================================

@api_bp.route('/timeseries', methods=['GET'])
def get_time_series():
    """
    Q5: Return time-series data for specified asset and data source identifiers
    """
    try:
        instrument_id = request.args.get('instrumentId', type=str)
        data_source_id = request.args.get('dataSourceId', type=str)
        start_date = request.args.get('startDate', type=str)
        end_date = request.args.get('endDate', type=str)
        limit = request.args.get('limit', default=1000, type=int)

        if not instrument_id or not data_source_id:
            return jsonify({
                'error': 'Missing required parameters: instrumentId, dataSourceId'
            }), 400

        # Parse dates
        start_datetime = None
        end_datetime = None

        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date)
            except ValueError:
                return jsonify({'error': 'Invalid startDate format (use ISO format)'}), 400

        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date)
            except ValueError:
                return jsonify({'error': 'Invalid endDate format (use ISO format)'}), 400

        # Retrieve time series
        data = TimeSeriesService.get_time_series(
            instrument_id=instrument_id,
            data_source_id=data_source_id,
            start_date=start_datetime,
            end_date=end_datetime,
            limit=limit
        )

        if not data:
            return jsonify({
                'status': 'success',
                'count': 0,
                'data': [],
                'message': 'No time series data found'
            }), 200

        return jsonify({
            'status': 'success',
            'count': len(data),
            'instrumentId': instrument_id,
            'dataSourceId': data_source_id,
            'dateRange': {
                'startDate': start_date,
                'endDate': end_date
            },
            'data': data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/timeseries/latest', methods=['GET'])
def get_latest_price():
    """Get the most recent price for an instrument"""
    try:
        instrument_id = request.args.get('instrumentId', type=str)
        data_source_id = request.args.get('dataSourceId', type=str)

        if not instrument_id or not data_source_id:
            return jsonify({
                'error': 'Missing required parameters: instrumentId, dataSourceId'
            }), 400

        data = TimeSeriesService.get_latest_price(instrument_id, data_source_id)

        if not data:
            return jsonify({'error': 'No data found'}), 404

        return jsonify({
            'status': 'success',
            'data': data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PROVENANCE ENDPOINTS
# ============================================================================

@api_bp.route('/provenance/<instrument_id>', methods=['GET'])
def get_instrument_provenance(instrument_id):
    """Get data provenance history for an instrument"""
    try:
        provenance = ProvenanceService.get_provenance(instrument_id)

        return jsonify({
            'status': 'success',
            'instrumentId': instrument_id,
            'count': len(provenance),
            'data': provenance
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PORTFOLIO ENDPOINTS
# ============================================================================

@api_bp.route('/portfolios/<portfolio_id>/holdings', methods=['GET'])
def get_portfolio_holdings(portfolio_id):
    """Get all holdings in a portfolio"""
    try:
        holdings = PortfolioService.get_portfolio_holdings(portfolio_id)

        return jsonify({
            'status': 'success',
            'portfolioId': portfolio_id,
            'count': len(holdings),
            'data': holdings
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# TEMPORAL DELETION (soft delete - never physically deletes)
# ============================================================================

@api_bp.route('/instruments/<instrument_id>', methods=['DELETE'])
def delete_instrument(instrument_id):
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'user_requested')

        instrument = InstrumentService.get_instrument(instrument_id)
        if not instrument:
            return jsonify({'error': 'Instrument not found or already inactive'}), 404

        result = InstrumentService.mark_instrument_inactive(instrument_id, reason)

        return jsonify({
            'status': 'success',
            'message': 'Instrument marked as inactive (temporal deletion - record preserved)',
            'data': result
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ANALYTICS & AGGREGATION ENDPOINTS
# ============================================================================

@api_bp.route('/analytics/timeseries-stats', methods=['GET'])
def get_timeseries_stats():
    """
    UC3: Provide analytics capabilities
    Return aggregated statistics for a time series
    """
    try:
        instrument_id = request.args.get('instrumentId', type=str)
        data_source_id = request.args.get('dataSourceId', type=str)
        start_date = request.args.get('startDate', type=str)
        end_date = request.args.get('endDate', type=str)

        if not instrument_id or not data_source_id:
            return jsonify({
                'error': 'Missing required parameters: instrumentId, dataSourceId'
            }), 400

        # Parse dates
        start_datetime = None
        end_datetime = None

        if start_date:
            start_datetime = datetime.fromisoformat(start_date)
        if end_date:
            end_datetime = datetime.fromisoformat(end_date)

        # Get time series
        data = TimeSeriesService.get_time_series(
            instrument_id, data_source_id,
            start_datetime, end_datetime, limit=10000
        )

        if not data:
            return jsonify({
                'error': 'No data available for analysis'
            }), 404

        # Extract closing prices
        prices = []
        for record in data:
            if 'indicators' in record and 'close' in record['indicators']:
                prices.append(float(record['indicators']['close']))

        if not prices:
            return jsonify({
                'error': 'No closing price data available'
            }), 404

        # Calculate statistics
        prices.sort()
        n = len(prices)

        stats = {
            'count': n,
            'minPrice': min(prices),
            'maxPrice': max(prices),
            'avgPrice': sum(prices) / n,
            'medianPrice': prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2,
            'firstPrice': prices[0],
            'lastPrice': prices[-1],
            'priceChange': prices[-1] - prices[0],
            'percentChange': ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] != 0 else 0
        }

        return jsonify({
            'status': 'success',
            'instrumentId': instrument_id,
            'dataSourceId': data_source_id,
            'stats': stats
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/compare', methods=['GET'])
def compare_instruments():
    """Compare multiple instruments"""
    try:
        ids = request.args.getlist('instrumentIds')

        if not ids or len(ids) < 2:
            return jsonify({
                'error': 'At least 2 instrument IDs required for comparison'
            }), 400

        comparison = []
        for inst_id in ids:
            instrument = InstrumentService.get_instrument(inst_id)
            if instrument:
                comparison.append({
                    'instrumentId': inst_id,
                    'symbol': instrument.get('symbol'),
                    'name': instrument.get('name'),
                    'instrumentClass': instrument.get('instrumentClass'),
                    'region': instrument.get('region')
                })

        return jsonify({
            'status': 'success',
            'count': len(comparison),
            'data': comparison
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HEALTH & DOCUMENTATION
# ============================================================================

@api_bp.route('/docs', methods=['GET'])
def api_documentation():
    """API documentation"""
    return jsonify({
        'service': 'Financial Data Warehouse API',
        'version': '1.0.0',
        'endpoints': {
            'instruments': {
                'GET /api/instruments': 'List all instruments (Q1)',
                'GET /api/instruments/<id>': 'Get instrument details (Q2)',
                'GET /api/instruments/symbol/<symbol>': 'Get by symbol',
                'GET /api/instruments/class/<class>': 'Filter by class'
            },
            'timeseries': {
                'GET /api/timeseries': 'Get time series (Q5)',
                'GET /api/timeseries/latest': 'Get latest price'
            },
            'sources': {
                'GET /api/sources': 'List data sources (Q3)',
                'GET /api/sources/<id>': 'Get source details (Q4)'
            },
            'analytics': {
                'GET /api/analytics/timeseries-stats': 'Get statistics',
                'GET /api/analytics/compare': 'Compare instruments'
            },
            'provenance': {
                'GET /api/provenance/<instrument_id>': 'Get provenance history'
            }
        }
    }), 200


# ============================================================================
# RESTORE & INACTIVE INSTRUMENTS
# ============================================================================

@api_bp.route('/instruments/inactive', methods=['GET'])
def list_inactive_instruments():
    try:
        from src.database import get_db
        db = get_db()
        instruments = list(db.financial_instruments.find({'isActive': False}))
        for inst in instruments:
            inst.pop('_id', None)
        return jsonify({'status': 'success', 'count': len(instruments), 'data': instruments}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/instruments/<instrument_id>/restore', methods=['POST'])
def restore_instrument(instrument_id):
    try:
        from src.database import get_db
        from datetime import datetime
        db = get_db()
        instrument = db.financial_instruments.find_one({'instrumentId': instrument_id})
        if not instrument:
            return jsonify({'error': 'Instrument not found'}), 404
        if instrument.get('isActive', True):
            return jsonify({'error': 'Instrument is already active'}), 400
        db.financial_instruments.update_one(
            {'instrumentId': instrument_id},
            {'$set': {'isActive': True, 'validTo': None, 'deletionMarker': None, 'updatedAt': datetime.utcnow()}}
        )
        return jsonify({'status': 'success', 'message': f'Instrument restored successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500