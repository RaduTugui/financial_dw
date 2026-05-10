"""
MCP Server integration for LLM-powered assistant
Implements UC4: Integration with Large Language Models (LLM)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from src.services import (
    InstrumentService, TimeSeriesService, DataSourceService,
    ProvenanceService
)
import json

mcp_bp = Blueprint('mcp', __name__)

"""
MCP Tools exposed to the LLM Assistant
Each tool follows the MCP protocol structure
"""


# ── HELPER FUNCTIONS ──────────────────────────────────────────

def _resolve_instrument_id(instrument_id: str) -> str:
    """Resolve symbol or partial name to instrument ID"""
    if not instrument_id:
        raise ValueError('instrument_id is required')
    # Already an ID
    if instrument_id.startswith('INST_'):
        return instrument_id
    # Try as symbol
    instrument = InstrumentService.get_instrument_by_symbol(instrument_id.upper())
    if instrument:
        return instrument['instrumentId']
    # Try case-insensitive symbol
    instruments = InstrumentService.list_instruments(limit=200)
    for inst in instruments:
        if inst['symbol'].upper() == instrument_id.upper():
            return inst['instrumentId']
        if instrument_id.upper() in inst['name'].upper():
            return inst['instrumentId']
    raise ValueError(f'Instrument not found: {instrument_id}')


def _resolve_source_id(data_source_id: str, instrument_id: str = None) -> str:
    """Resolve source name/type to source ID, defaulting to Yahoo Finance"""
    if not data_source_id:
        # Auto-select best source for instrument
        if instrument_id:
            sources = DataSourceService.list_data_sources_for_instrument(instrument_id)
            if sources:
                yahoo = next((s for s in sources if s['providerType'] == 'yahoo'), None)
                return yahoo['dataSourceId'] if yahoo else sources[0]['dataSourceId']
        # Fall back to any yahoo source
        all_sources = DataSourceService.list_data_sources()
        yahoo = next((s for s in all_sources if s['providerType'] == 'yahoo'), None)
        if yahoo:
            return yahoo['dataSourceId']
        return all_sources[0]['dataSourceId'] if all_sources else None

    if data_source_id.startswith('DS_'):
        return data_source_id

    # Resolve by name or type
    all_sources = DataSourceService.list_data_sources()
    for s in all_sources:
        if (s['providerName'].lower() == data_source_id.lower() or
                s['providerType'].lower() == data_source_id.lower() or
                data_source_id.lower() in s['providerName'].lower()):
            return s['dataSourceId']
    return data_source_id


MCP_TOOLS = {
    "list_instruments": {
        "description": "List all available financial instruments in the warehouse",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of instruments to return (default: 50)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination (default: 0)"
                },
                "class": {
                    "type": "string",
                    "description": "Filter by instrument class (optional)"
                }
            }
        }
    },
    "get_instrument": {
        "description": "Get detailed information about a specific financial instrument",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {
                    "type": "string",
                    "description": "The instrument ID or symbol"
                }
            },
            "required": ["instrument_id"]
        }
    },
    "get_timeseries": {
        "description": "Retrieve time series data for an instrument from a specific data source",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {
                    "type": "string",
                    "description": "The instrument ID"
                },
                "data_source_id": {
                    "type": "string",
                    "description": "The data source ID"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date (ISO format, optional)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (ISO format, optional)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum records to return (default: 100)"
                }
            },
            "required": ["instrument_id", "data_source_id"]
        }
    },
    "get_latest_price": {
        "description": "Get the most recent price data for an instrument",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {
                    "type": "string",
                    "description": "The instrument ID"
                },
                "data_source_id": {
                    "type": "string",
                    "description": "The data source ID"
                }
            },
            "required": ["instrument_id", "data_source_id"]
        }
    },
    "list_data_sources": {
        "description": "List all available data sources (providers)",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    "get_data_source": {
        "description": "Get information about a specific data source",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_source_id": {
                    "type": "string",
                    "description": "The data source ID"
                }
            },
            "required": ["data_source_id"]
        }
    },
    "compute_statistics": {
        "description": "Compute statistics (min, max, avg, median) for a time series",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {
                    "type": "string",
                    "description": "The instrument ID"
                },
                "data_source_id": {
                    "type": "string",
                    "description": "The data source ID"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date (ISO format, optional)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (ISO format, optional)"
                }
            },
            "required": ["instrument_id", "data_source_id"]
        }
    },
    "compare_instruments": {
        "description": "Compare multiple instruments to identify trends and differences",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of instrument IDs to compare"
                }
            },
            "required": ["instrument_ids"]
        }
    },
    "analyze_trend": {
        "description": "Analyze trend for an instrument (direction, volatility)",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {
                    "type": "string",
                    "description": "The instrument ID"
                },
                "data_source_id": {
                    "type": "string",
                    "description": "The data source ID"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 30)"
                }
            },
            "required": ["instrument_id", "data_source_id"]
        }
    },
    "get_provenance": {
        "description": "Get data provenance information for an instrument",
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument_id": {
                    "type": "string",
                    "description": "The instrument ID"
                }
            },
            "required": ["instrument_id"]
        }
    }
}


# ============================================================================
# MCP TOOL ENDPOINTS
# ============================================================================

@mcp_bp.route('/tools', methods=['GET'])
def list_mcp_tools():
    """List all available MCP tools for the LLM assistant"""
    return jsonify({
        'tools': [
            {
                'name': tool_name,
                **tool_def
            }
            for tool_name, tool_def in MCP_TOOLS.items()
        ]
    }), 200


@mcp_bp.route('/call', methods=['POST'])
def call_mcp_tool():
    """
    Execute an MCP tool
    Request format:
    {
        "tool_name": "list_instruments",
        "arguments": {...}
    }
    """
    try:
        data = request.get_json()

        if 'tool_name' not in data:
            return jsonify({'error': 'Missing tool_name'}), 400

        tool_name = data['tool_name']
        arguments = data.get('arguments', {})

        # Dispatch to appropriate tool handler
        if tool_name == 'list_instruments':
            result = _tool_list_instruments(arguments)

        elif tool_name == 'get_instrument':
            result = _tool_get_instrument(arguments)

        elif tool_name == 'get_timeseries':
            result = _tool_get_timeseries(arguments)

        elif tool_name == 'get_latest_price':
            result = _tool_get_latest_price(arguments)

        elif tool_name == 'list_data_sources':
            result = _tool_list_data_sources(arguments)

        elif tool_name == 'get_data_source':
            result = _tool_get_data_source(arguments)

        elif tool_name == 'compute_statistics':
            result = _tool_compute_statistics(arguments)

        elif tool_name == 'compare_instruments':
            result = _tool_compare_instruments(arguments)

        elif tool_name == 'analyze_trend':
            result = _tool_analyze_trend(arguments)

        elif tool_name == 'get_provenance':
            result = _tool_get_provenance(arguments)

        else:
            return jsonify({'error': f'Unknown tool: {tool_name}'}), 404

        return jsonify({
            'status': 'success',
            'tool': tool_name,
            'result': result
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# MCP TOOL IMPLEMENTATIONS
# ============================================================================

def _tool_list_instruments(args: dict) -> dict:
    """Implementation of list_instruments tool"""
    limit = args.get('limit', 50)
    offset = args.get('offset', 0)
    class_filter = args.get('class')

    if class_filter:
        instruments = InstrumentService.list_instruments_by_class(class_filter, limit)
    else:
        instruments = InstrumentService.list_instruments(limit, offset)

    return {
        'count': len(instruments),
        'instruments': [{
            'assetId': inst['instrumentId'],
            'symbol': inst['symbol'],
            'name': inst['name'],
            'class': inst['instrumentClass'],
            'region': inst['region'],
            'currency': inst['currency']
        } for inst in instruments]
    }


def _tool_get_instrument(args: dict) -> dict:
    """Implementation of get_instrument tool"""
    instrument_id = args.get('instrument_id')

    if not instrument_id:
        raise ValueError('instrument_id is required')

    # Try ID first, then symbol
    instrument = InstrumentService.get_instrument(instrument_id)
    if not instrument:
        instrument = InstrumentService.get_instrument_by_symbol(instrument_id)

    if not instrument:
        raise ValueError(f'Instrument {instrument_id} not found')

    return {
        'instrumentId': instrument['instrumentId'],
        'symbol': instrument['symbol'],
        'name': instrument['name'],
        'description': instrument['description'],
        'class': instrument['instrumentClass'],
        'region': instrument['region'],
        'currency': instrument['currency'],
        'isActive': instrument['isActive']
    }


def _tool_get_timeseries(args: dict) -> dict:
    """Implementation of get_timeseries tool"""
    instrument_id = _resolve_instrument_id(args.get('instrument_id', ''))
    data_source_id = _resolve_source_id(args.get('data_source_id', ''), instrument_id)
    start_date = args.get('start_date')
    end_date = args.get('end_date')
    limit = args.get('limit', 100)

    start_datetime = datetime.fromisoformat(start_date) if start_date else None
    end_datetime = datetime.fromisoformat(end_date) if end_date else None

    data = TimeSeriesService.get_time_series(
        instrument_id, data_source_id,
        start_datetime, end_datetime, limit
    )

    return {
        'count': len(data),
        'instrumentId': instrument_id,
        'dataSourceId': data_source_id,
        'data': data[:limit]
    }


def _tool_get_latest_price(args: dict) -> dict:
    """Implementation of get_latest_price tool"""
    instrument_id = args.get('instrument_id')
    data_source_id = args.get('data_source_id')

    if not instrument_id:
        raise ValueError('instrument_id is required')

    # Resolve symbol to instrument ID if needed
    if not instrument_id.startswith('INST_'):
        instrument = InstrumentService.get_instrument_by_symbol(instrument_id)
        if not instrument:
            raise ValueError(f'Instrument {instrument_id} not found')
        instrument_id = instrument['instrumentId']

    # If no data_source_id provided, use first available source
    if not data_source_id:
        sources = DataSourceService.list_data_sources_for_instrument(instrument_id)
        if not sources:
            return {'message': f'No data sources found for instrument'}
        # Prefer Yahoo Finance
        yahoo = next((s for s in sources if s['providerType'] == 'yahoo'), None)
        data_source_id = yahoo['dataSourceId'] if yahoo else sources[0]['dataSourceId']

    # Also resolve source name to ID if needed
    if not data_source_id.startswith('DS_'):
        all_sources = DataSourceService.list_data_sources()
        source = next((s for s in all_sources if
                       s['providerName'].lower() == data_source_id.lower() or
                       s['providerType'].lower() == data_source_id.lower()), None)
        if source:
            data_source_id = source['dataSourceId']

    data = TimeSeriesService.get_latest_price(instrument_id, data_source_id)

    if not data:
        return {'message': f'No recent price data found for {instrument_id}'}

    return {
        'timestamp': data.get('dataTimestamp'),
        'indicators': data.get('indicators', {}),
        'dataQuality': data.get('dataQuality')
    }


def _tool_list_data_sources(args: dict) -> dict:
    """Implementation of list_data_sources tool"""
    sources = DataSourceService.list_data_sources()

    return {
        'count': len(sources),
        'sources': [{
            'dataSourceId': src['dataSourceId'],
            'providerName': src['providerName'],
            'providerType': src['providerType'],
            'description': src['description']
        } for src in sources]
    }


def _tool_get_data_source(args: dict) -> dict:
    """Implementation of get_data_source tool"""
    data_source_id = args.get('data_source_id')

    if not data_source_id:
        raise ValueError('data_source_id is required')

    source = DataSourceService.get_data_source(data_source_id)

    if not source:
        raise ValueError(f'Data source {data_source_id} not found')

    return {
        'dataSourceId': source['dataSourceId'],
        'providerName': source['providerName'],
        'providerType': source['providerType'],
        'apiEndpoint': source['apiEndpoint'],
        'description': source['description']
    }


def _tool_compute_statistics(args: dict) -> dict:
    """Implementation of compute_statistics tool"""
    instrument_id = _resolve_instrument_id(args.get('instrument_id', ''))
    data_source_id = _resolve_source_id(args.get('data_source_id', ''), instrument_id)
    start_date = args.get('start_date')
    end_date = args.get('end_date')

    start_datetime = datetime.fromisoformat(start_date) if start_date else None
    end_datetime = datetime.fromisoformat(end_date) if end_date else None

    data = TimeSeriesService.get_time_series(
        instrument_id, data_source_id,
        start_datetime, end_datetime, limit=10000
    )

    if not data:
        raise ValueError('No data available for analysis')

    # Extract prices
    prices = []
    for record in data:
        if 'indicators' in record and 'close' in record['indicators']:
            prices.append(float(record['indicators']['close']))

    if not prices:
        raise ValueError('No price data available')

    prices.sort()
    n = len(prices)

    return {
        'count': n,
        'minPrice': min(prices),
        'maxPrice': max(prices),
        'avgPrice': sum(prices) / n,
        'medianPrice': prices[n // 2],
        'firstPrice': prices[0],
        'lastPrice': prices[-1],
        'priceChange': prices[-1] - prices[0],
        'volatility': max(prices) - min(prices)
    }


def _tool_compare_instruments(args: dict) -> dict:
    """Implementation of compare_instruments tool"""
    instrument_ids = args.get('instrument_ids', [])

    if not instrument_ids or len(instrument_ids) < 2:
        raise ValueError('At least 2 instrument IDs required')

    comparison = []
    for inst_id in instrument_ids:
        instrument = InstrumentService.get_instrument(inst_id)
        if not instrument:
            instrument = InstrumentService.get_instrument_by_symbol(inst_id)

        if instrument:
            comparison.append({
                'instrumentId': instrument['instrumentId'],
                'symbol': instrument['symbol'],
                'name': instrument['name'],
                'class': instrument['instrumentClass'],
                'region': instrument['region']
            })

    return {
        'count': len(comparison),
        'instruments': comparison
    }


def _tool_analyze_trend(args: dict) -> dict:
    """Implementation of analyze_trend tool"""
    instrument_id = _resolve_instrument_id(args.get('instrument_id', ''))
    data_source_id = _resolve_source_id(args.get('data_source_id', ''), instrument_id)
    days = args.get('days', 30)

    data = TimeSeriesService.get_time_series(
        instrument_id, data_source_id,
        limit=1000
    )

    if not data:
        raise ValueError('No data available')

    # Extract prices
    prices = []
    for record in data:
        if 'indicators' in record and 'close' in record['indicators']:
            prices.append(float(record['indicators']['close']))

    if len(prices) < 2:
        return {'message': 'Insufficient data for trend analysis'}

    # Simple trend analysis
    recent_avg = sum(prices[:min(days, len(prices))]) / min(days, len(prices))
    older_avg = sum(prices[min(days, len(prices)):]) / max(1, len(prices) - days)

    trend = 'upward' if recent_avg > older_avg else 'downward' if recent_avg < older_avg else 'stable'
    change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0

    return {
        'trend': trend,
        'recentAvg': recent_avg,
        'olderAvg': older_avg,
        'changePercent': change_percent,
        'volatility': max(prices) - min(prices)
    }


def _tool_get_provenance(args: dict) -> dict:
    """Implementation of get_provenance tool"""
    instrument_id = args.get('instrument_id')

    if not instrument_id:
        raise ValueError('instrument_id is required')

    provenance = ProvenanceService.get_provenance(instrument_id)

    return {
        'count': len(provenance),
        'provenance': [{
            'provenanceId': p['provenanceId'],
            'sourceId': p['sourceId'],
            'sourceType': p['sourceType'],
            'ingestTime': p['ingestTime'],
            'ingestionMethod': p['ingestionMethod']
        } for p in provenance]
    }