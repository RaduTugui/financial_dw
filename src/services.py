"""
Core business logic and operations
"""

from src.database import get_db
from src.models import (
    FinancialInstrument, TimeSeriesData, DataSource, DataProvenance,
    InstrumentAttribute, Portfolio, PortfolioHolding
)
from datetime import datetime
from uuid import uuid4
from typing import Dict, List, Optional, Any
import hashlib
import json


def _clean(doc):
    """Remove MongoDB _id and convert datetimes to ISO strings"""
    if not doc:
        return doc
    doc.pop('_id', None)
    # Convert all datetime values to ISO format strings
    for key, val in list(doc.items()):
        if isinstance(val, datetime):
            doc[key] = val.isoformat()
        elif isinstance(val, dict):
            for k, v in list(val.items()):
                if isinstance(v, datetime):
                    val[k] = v.isoformat()
    return doc

def _clean_list(docs):
    """Clean a list of MongoDB documents"""
    return [_clean(doc) for doc in docs]


class InstrumentService:
    """Service for financial instrument operations"""

    @staticmethod
    def create_instrument(symbol, name, description, instrument_class, region, currency):
        db = get_db()
        instrument = FinancialInstrument(
            instrumentId=f"INST_{uuid4().hex[:12].upper()}",
            symbol=symbol, name=name, description=description,
            instrumentClass=instrument_class, region=region, currency=currency
        )
        db.financial_instruments.insert_one(instrument.to_dict())
        return {'instrumentId': instrument.instrumentId, 'symbol': symbol, 'message': 'Instrument created successfully'}

    @staticmethod
    def get_instrument(instrument_id):
        db = get_db()
        return _clean(db.financial_instruments.find_one({'instrumentId': instrument_id, 'isActive': True}))

    @staticmethod
    def get_instrument_by_symbol(symbol):
        db = get_db()
        return _clean(db.financial_instruments.find_one({'symbol': symbol, 'isActive': True}))

    @staticmethod
    def list_instruments(limit=100, offset=0):
        db = get_db()
        return _clean_list(list(db.financial_instruments.find({'isActive': True}).skip(offset).limit(limit)))

    @staticmethod
    def list_instruments_by_class(instrument_class, limit=100):
        db = get_db()
        return _clean_list(list(db.financial_instruments.find({'instrumentClass': instrument_class, 'isActive': True}).limit(limit)))

    @staticmethod
    def mark_instrument_inactive(instrument_id, marker_reason=None):
        db = get_db()
        deletion_marker = f"DELETED_{datetime.utcnow().isoformat()}_{marker_reason or 'no_reason'}"
        result = db.financial_instruments.update_one(
            {'instrumentId': instrument_id},
            {'$set': {'isActive': False, 'validTo': datetime.utcnow(), 'deletionMarker': deletion_marker, 'updatedAt': datetime.utcnow()}}
        )
        return {'instrumentId': instrument_id, 'markedInactive': result.modified_count > 0, 'deletionMarker': deletion_marker}

    @staticmethod
    def get_historical_version(instrument_id, at_timestamp):
        db = get_db()
        return _clean(db.financial_instruments.find_one({
            'instrumentId': instrument_id,
            'validFrom': {'$lte': at_timestamp},
            '$or': [{'validTo': None}, {'validTo': {'$gte': at_timestamp}}]
        }))


class TimeSeriesService:
    """Service for time series data operations"""

    @staticmethod
    def insert_time_series(instrument_id, data_source_id, data_timestamp, indicators):
        db = get_db()
        ts_data = TimeSeriesData(
            seriesId=f"TS_{uuid4().hex[:12].upper()}",
            instrumentId=instrument_id, dataSourceId=data_source_id,
            dataTimestamp=data_timestamp, indicators=indicators
        )
        db.time_series_data.insert_one(ts_data.to_dict())
        return {'seriesId': ts_data.seriesId, 'message': 'Time series data inserted'}

    @staticmethod
    def get_time_series(instrument_id, data_source_id, start_date=None, end_date=None, limit=1000):
        db = get_db()
        query = {'instrumentId': instrument_id, 'dataSourceId': data_source_id}
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['dataTimestamp'] = date_query
        return _clean_list(list(db.time_series_data.find(query).sort('dataTimestamp', -1).limit(limit)))

    @staticmethod
    def bulk_insert_time_series(records):
        db = get_db()
        if not records:
            return {'inserted': 0, 'message': 'No records to insert'}
        result = db.time_series_data.insert_many(records)
        return {'inserted': len(result.inserted_ids), 'message': f'Inserted {len(result.inserted_ids)} records'}

    @staticmethod
    def get_latest_price(instrument_id, data_source_id):
        db = get_db()
        return _clean(db.time_series_data.find_one(
            {'instrumentId': instrument_id, 'dataSourceId': data_source_id},
            sort=[('dataTimestamp', -1)]
        ))


class DataSourceService:
    """Service for data source management"""

    @staticmethod
    def register_data_source(provider_name, provider_type, api_endpoint, description):
        db = get_db()
        source = DataSource(
            dataSourceId=f"DS_{uuid4().hex[:12].upper()}",
            providerName=provider_name, providerType=provider_type,
            apiEndpoint=api_endpoint, description=description
        )
        db.data_sources.insert_one(source.to_dict())
        return {'dataSourceId': source.dataSourceId, 'providerName': provider_name, 'message': 'Data source registered'}

    @staticmethod
    def get_data_source(data_source_id):
        db = get_db()
        return _clean(db.data_sources.find_one({'dataSourceId': data_source_id}))

    @staticmethod
    def list_data_sources():
        db = get_db()
        return _clean_list(list(db.data_sources.find()))

    @staticmethod
    def list_data_sources_for_instrument(instrument_id):
        db = get_db()
        sources = db.time_series_data.distinct('dataSourceId', {'instrumentId': instrument_id})
        return _clean_list(list(db.data_sources.find({'dataSourceId': {'$in': sources}})))


class ProvenanceService:
    """Service for data provenance tracking"""

    @staticmethod
    def record_provenance(instrument_id, source_id, source_type, raw_data,
                          ingestion_method, transformation_logic=None):
        db = get_db()
        raw_data_hash = hashlib.sha256(
            json.dumps(raw_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        provenance = DataProvenance(
            provenanceId=f"PROV_{uuid4().hex[:12].upper()}",
            instrumentId=instrument_id, sourceId=source_id,
            sourceType=source_type, ingestTime=datetime.utcnow(),
            rawDataHash=raw_data_hash, ingestionMethod=ingestion_method,
            transformationLogic=transformation_logic
        )
        db.data_provenance.insert_one(provenance.to_dict())
        return {'provenanceId': provenance.provenanceId, 'rawDataHash': raw_data_hash}

    @staticmethod
    def get_provenance(instrument_id):
        """Get provenance history for an instrument - one record per source"""
        db = get_db()

        # Group by sourceId to avoid returning hundreds of duplicate records
        # (one per time series point is too many - return one summary per source)
        pipeline = [
            {'$match': {'instrumentId': instrument_id}},
            {'$sort': {'ingestTime': -1}},
            {'$group': {
                '_id': '$sourceId',
                'provenanceId':    {'$first': '$provenanceId'},
                'instrumentId':    {'$first': '$instrumentId'},
                'sourceId':        {'$first': '$sourceId'},
                'sourceType':      {'$first': '$sourceType'},
                'ingestTime':      {'$first': '$ingestTime'},
                'rawDataHash':     {'$first': '$rawDataHash'},
                'ingestionMethod': {'$first': '$ingestionMethod'},
                'totalRecords':    {'$sum': 1}
            }},
            {'$project': {'_id': 0}}
        ]

        results = list(db.data_provenance.aggregate(pipeline))

        # Enrich with source name
        for r in results:
            source = db.data_sources.find_one({'dataSourceId': r.get('sourceId')})
            if source:
                r['providerName'] = source.get('providerName', 'Unknown')
                r['providerType'] = source.get('providerType', 'Unknown')
            else:
                r['providerName'] = 'Unknown'
                r['providerType'] = 'Unknown'

        return results


class PortfolioService:
    """Service for portfolio management"""

    @staticmethod
    def create_portfolio(portfolio_name, owner_type, owner_id):
        db = get_db()
        portfolio = Portfolio(
            portfolioId=f"PORT_{uuid4().hex[:12].upper()}",
            portfolioName=portfolio_name, ownerType=owner_type, ownerId=owner_id
        )
        db.portfolios.insert_one(portfolio.to_dict())
        return {'portfolioId': portfolio.portfolioId, 'portfolioName': portfolio_name, 'message': 'Portfolio created'}

    @staticmethod
    def add_holding(portfolio_id, instrument_id, quantity, average_cost, acquired_date):
        db = get_db()
        holding = PortfolioHolding(
            holdingId=f"HOLD_{uuid4().hex[:12].upper()}",
            portfolioId=portfolio_id, instrumentId=instrument_id,
            quantity=quantity, averageCost=average_cost, acquiredDate=acquired_date
        )
        db.portfolio_holdings.insert_one(holding.to_dict())
        return {'holdingId': holding.holdingId, 'message': 'Holding added to portfolio'}

    @staticmethod
    def get_portfolio_holdings(portfolio_id):
        db = get_db()
        return _clean_list(list(db.portfolio_holdings.find({'portfolioId': portfolio_id})))


class AttributeService:
    """Service for heterogeneous instrument attributes"""

    @staticmethod
    def add_attribute(instrument_id, attribute_name, attribute_value, attribute_type):
        db = get_db()
        attribute = InstrumentAttribute(
            attributeId=f"ATTR_{uuid4().hex[:12].upper()}",
            instrumentId=instrument_id, attributeName=attribute_name,
            attributeValue=attribute_value, attributeType=attribute_type
        )
        db.instrument_attributes.insert_one(attribute.to_dict())
        return {'attributeId': attribute.attributeId, 'message': 'Attribute added'}

    @staticmethod
    def get_attributes(instrument_id):
        db = get_db()
        return _clean_list(list(db.instrument_attributes.find({'instrumentId': instrument_id})))