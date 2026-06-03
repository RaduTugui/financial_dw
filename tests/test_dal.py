"""
Unit Tests for Financial Data Warehouse
Tests DAL (Data Access Layer) and Ingestion pipeline

Run with:
    pytest tests/ -v
    pytest tests/ -v --tb=short
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB database"""
    db = MagicMock()
    db.financial_instruments = MagicMock()
    db.time_series_data       = MagicMock()
    db.data_sources           = MagicMock()
    db.data_provenance        = MagicMock()
    db.instrument_attributes  = MagicMock()
    return db

@pytest.fixture
def sample_instrument():
    return {
        'instrumentId': 'INST_TEST001',
        'symbol': 'TSLA',
        'name': 'Tesla Inc',
        'description': 'Electric vehicle company',
        'instrumentClass': 'stock',
        'region': 'US',
        'currency': 'USD',
        'isActive': True,
        'validFrom': datetime(2026, 1, 1),
        'validTo': None,
        'deletionMarker': None
    }

@pytest.fixture
def sample_time_series():
    return {
        'seriesId': 'TS_TEST001',
        'instrumentId': 'INST_TEST001',
        'dataSourceId': 'DS_TEST001',
        'dataTimestamp': '2026-05-01T00:00:00',
        'indicators': {
            'open': 250.0,
            'close': 255.0,
            'high': 258.0,
            'low': 248.0,
            'volume': 50000000
        },
        'dataQuality': 'verified'
    }

@pytest.fixture
def sample_source():
    return {
        'dataSourceId': 'DS_TEST001',
        'providerName': 'Yahoo Finance',
        'providerType': 'yahoo',
        'apiEndpoint': 'https://query1.finance.yahoo.com',
        'description': 'Free real-time data'
    }


# ══════════════════════════════════════════════════════════
# MODEL TESTS
# ══════════════════════════════════════════════════════════

class TestModels:
    """Test data model dataclasses"""

    def test_financial_instrument_creation(self):
        from src.models import FinancialInstrument
        inst = FinancialInstrument(
            instrumentId='INST_001',
            symbol='AAPL',
            name='Apple Inc',
            description='Consumer electronics',
            instrumentClass='stock',
            region='US',
            currency='USD'
        )
        assert inst.symbol == 'AAPL'
        assert inst.isActive == True
        assert inst.validTo is None
        assert inst.deletionMarker is None

    def test_financial_instrument_to_dict(self):
        from src.models import FinancialInstrument
        inst = FinancialInstrument(
            instrumentId='INST_001',
            symbol='AAPL',
            name='Apple Inc',
            description='Consumer electronics',
            instrumentClass='stock',
            region='US',
            currency='USD'
        )
        d = inst.to_dict()
        assert isinstance(d, dict)
        assert d['symbol'] == 'AAPL'
        assert d['isActive'] == True
        assert 'instrumentId' in d
        assert 'validFrom' in d

    def test_time_series_creation(self):
        from src.models import TimeSeriesData
        ts = TimeSeriesData(
            seriesId='TS_001',
            instrumentId='INST_001',
            dataSourceId='DS_001',
            dataTimestamp=datetime(2026, 5, 1),
            indicators={'close': 200.0, 'open': 198.0, 'high': 202.0, 'low': 197.0, 'volume': 1000000}
        )
        assert ts.seriesId == 'TS_001'
        assert ts.indicators['close'] == 200.0
        assert ts.dataQuality == 'verified'


    def test_data_provenance_hash(self):
        from src.models import DataProvenance
        prov = DataProvenance(
            provenanceId='PROV_001',
            instrumentId='INST_001',
            sourceId='DS_001',
            sourceType='bulk_import',
            ingestTime=datetime(2026, 5, 1),
            rawDataHash='abc123',
            ingestionMethod='bulk_api_post'
        )
        assert prov.rawDataHash == 'abc123'
        assert prov.ingestionMethod == 'bulk_api_post'


# ══════════════════════════════════════════════════════════
# DAL (SERVICE) TESTS
# ══════════════════════════════════════════════════════════

class TestInstrumentService:
    """Test InstrumentService DAL methods"""

    @patch('src.services.get_db')
    def test_get_instrument_returns_none_when_not_found(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.financial_instruments.find_one.return_value = None

        from src.services import InstrumentService
        result = InstrumentService.get_instrument('INST_NONEXISTENT')
        assert result is None

    @patch('src.services.get_db')
    def test_get_instrument_strips_id(self, mock_get_db, mock_db, sample_instrument):
        mock_get_db.return_value = mock_db
        doc = {**sample_instrument, '_id': 'some_object_id'}
        mock_db.financial_instruments.find_one.return_value = doc

        from src.services import InstrumentService
        result = InstrumentService.get_instrument('INST_TEST001')
        assert '_id' not in result
        assert result['symbol'] == 'TSLA'

    @patch('src.services.get_db')
    def test_get_instrument_by_symbol(self, mock_get_db, mock_db, sample_instrument):
        mock_get_db.return_value = mock_db
        mock_db.financial_instruments.find_one.return_value = sample_instrument

        from src.services import InstrumentService
        result = InstrumentService.get_instrument_by_symbol('TSLA')
        assert result is not None
        mock_db.financial_instruments.find_one.assert_called_once_with(
            {'symbol': 'TSLA', 'isActive': True}
        )

    @patch('src.services.get_db')
    def test_list_instruments_returns_list(self, mock_get_db, mock_db, sample_instrument):
        mock_get_db.return_value = mock_db
        mock_db.financial_instruments.find.return_value.skip.return_value.limit.return_value = [sample_instrument]

        from src.services import InstrumentService
        result = InstrumentService.list_instruments()
        assert isinstance(result, list)

    @patch('src.services.get_db')
    def test_mark_instrument_inactive(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.financial_instruments.update_one.return_value = mock_result

        from src.services import InstrumentService
        result = InstrumentService.mark_instrument_inactive('INST_001', 'test_reason')
        assert result['markedInactive'] == True
        # Verify no DELETE was called (temporal database)
        mock_db.financial_instruments.delete_one.assert_not_called()

    @patch('src.services.get_db')
    def test_create_instrument_returns_id(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.financial_instruments.insert_one.return_value = MagicMock()

        from src.services import InstrumentService
        result = InstrumentService.create_instrument(
            symbol='NVDA',
            name='NVIDIA Corporation',
            description='GPU manufacturer',
            instrument_class='stock',
            region='US',
            currency='USD'
        )
        assert 'instrumentId' in result
        assert result['symbol'] == 'NVDA'
        mock_db.financial_instruments.insert_one.assert_called_once()


class TestTimeSeriesService:
    """Test TimeSeriesService DAL methods"""

    @patch('src.services.get_db')
    def test_get_time_series_returns_list(self, mock_get_db, mock_db, sample_time_series):
        mock_get_db.return_value = mock_db
        mock_db.time_series_data.find.return_value.sort.return_value.limit.return_value = [sample_time_series]

        from src.services import TimeSeriesService
        result = TimeSeriesService.get_time_series('INST_001', 'DS_001')
        assert isinstance(result, list)

    @patch('src.services.get_db')
    def test_get_latest_price_returns_none_when_empty(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.time_series_data.find_one.return_value = None

        from src.services import TimeSeriesService
        result = TimeSeriesService.get_latest_price('INST_001', 'DS_001')
        assert result is None

    @patch('src.services.get_db')
    def test_bulk_insert_returns_count(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_result = MagicMock()
        mock_result.inserted_ids = ['id1', 'id2', 'id3']
        mock_db.time_series_data.insert_many.return_value = mock_result

        from src.services import TimeSeriesService
        records = [{'seriesId': f'TS_{i}'} for i in range(3)]
        result = TimeSeriesService.bulk_insert_time_series(records)
        assert result['inserted'] == 3

    @patch('src.services.get_db')
    def test_insert_time_series(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.time_series_data.insert_one.return_value = MagicMock()

        from src.services import TimeSeriesService
        result = TimeSeriesService.insert_time_series(
            instrument_id='INST_001',
            data_source_id='DS_001',
            data_timestamp=datetime(2026, 5, 1),
            indicators={'close': 200.0, 'open': 198.0}
        )
        assert 'seriesId' in result
        mock_db.time_series_data.insert_one.assert_called_once()


class TestDataSourceService:
    """Test DataSourceService DAL methods"""

    @patch('src.services.get_db')
    def test_register_data_source(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.data_sources.insert_one.return_value = MagicMock()

        from src.services import DataSourceService
        result = DataSourceService.register_data_source(
            provider_name='Yahoo Finance',
            provider_type='yahoo',
            api_endpoint='https://yahoo.com',
            description='Free data'
        )
        assert 'dataSourceId' in result
        assert result['providerName'] == 'Yahoo Finance'

    @patch('src.services.get_db')
    def test_list_data_sources(self, mock_get_db, mock_db, sample_source):
        mock_get_db.return_value = mock_db
        mock_db.data_sources.find.return_value = [sample_source]

        from src.services import DataSourceService
        result = DataSourceService.list_data_sources()
        assert isinstance(result, list)


class TestProvenanceService:
    """Test ProvenanceService - data lineage tracking"""

    @patch('src.services.get_db')
    def test_record_provenance_creates_hash(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.data_provenance.insert_one.return_value = MagicMock()

        from src.services import ProvenanceService
        result = ProvenanceService.record_provenance(
            instrument_id='INST_001',
            source_id='DS_001',
            source_type='bulk_import',
            raw_data={'test': 'data'},
            ingestion_method='bulk_api_post'
        )
        assert 'provenanceId' in result
        assert 'rawDataHash' in result
        assert len(result['rawDataHash']) == 64  # SHA256 hex length

    @patch('src.services.get_db')
    def test_provenance_hash_is_deterministic(self, mock_get_db, mock_db):
        mock_get_db.return_value = mock_db
        mock_db.data_provenance.insert_one.return_value = MagicMock()

        from src.services import ProvenanceService
        raw_data = {'instrumentId': 'INST_001', 'count': 90}

        result1 = ProvenanceService.record_provenance(
            'INST_001', 'DS_001', 'bulk_import', raw_data, 'bulk_api_post'
        )
        result2 = ProvenanceService.record_provenance(
            'INST_001', 'DS_001', 'bulk_import', raw_data, 'bulk_api_post'
        )
        # Same data should produce same hash
        assert result1['rawDataHash'] == result2['rawDataHash']


# ══════════════════════════════════════════════════════════
# TEMPORAL DATABASE TESTS
# ══════════════════════════════════════════════════════════

class TestTemporalDatabase:
    """Test temporal database design — no in-place mutations"""

    def test_instrument_has_temporal_fields(self):
        from src.models import FinancialInstrument
        inst = FinancialInstrument(
            instrumentId='INST_001', symbol='TEST', name='Test',
            description='', instrumentClass='stock', region='US', currency='USD'
        )
        d = inst.to_dict()
        assert 'validFrom' in d
        assert 'validTo' in d
        assert 'isActive' in d
        assert 'deletionMarker' in d
        assert d['isActive'] == True
        assert d['validTo'] is None
        assert d['deletionMarker'] is None

    @patch('src.services.get_db')
    def test_delete_uses_marker_not_physical_delete(self, mock_get_db, mock_db):
        """Temporal deletion must NOT call delete_one"""
        mock_get_db.return_value = mock_db
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_db.financial_instruments.update_one.return_value = mock_result

        from src.services import InstrumentService
        InstrumentService.mark_instrument_inactive('INST_001', 'test')

        # CRITICAL: delete_one must NEVER be called
        mock_db.financial_instruments.delete_one.assert_not_called()
        # update_one IS called (to set isActive=False)
        mock_db.financial_instruments.update_one.assert_called_once()

    def test_time_series_has_temporal_fields(self):
        from src.models import TimeSeriesData
        ts = TimeSeriesData(
            seriesId='TS_001', instrumentId='INST_001', dataSourceId='DS_001',
            dataTimestamp=datetime(2026, 5, 1), indicators={'close': 100.0}
        )
        d = ts.to_dict()
        assert 'validFrom' in d
        assert 'recordedAt' in d


# ══════════════════════════════════════════════════════════
# INGESTION PIPELINE TESTS
# ══════════════════════════════════════════════════════════

class TestIngestionPipeline:
    """Test data ingestion pipeline"""

    def test_flask_app_creates_successfully(self):
        """Test Flask app can be created"""
        from app import create_app
        app = create_app()
        assert app is not None

    def test_health_endpoint(self):
        """Test health check endpoint"""
        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'

    def test_root_redirects_to_ui(self):
        """Test root URL redirects to /ui"""
        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get('/')
        assert response.status_code == 302
        assert '/ui' in response.location

    @patch('src.services.get_db')
    def test_instruments_endpoint_returns_list(self, mock_get_db, mock_db, sample_instrument):
        mock_get_db.return_value = mock_db
        mock_db.financial_instruments.find.return_value.skip.return_value.limit.return_value = [sample_instrument]
        mock_db.financial_instruments.count_documents.return_value = 1

        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get('/api/instruments')
        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data

    @patch('src.services.get_db')
    def test_sources_endpoint_returns_list(self, mock_get_db, mock_db, sample_source):
        mock_get_db.return_value = mock_db
        mock_db.data_sources.find.return_value = [sample_source]

        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get('/api/sources')
        assert response.status_code == 200

    def test_register_instrument_missing_fields(self):
        """Test that missing required fields returns 400"""
        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.post('/ingest/register-instrument',
                               json={'symbol': 'TEST'})  # missing required fields
        assert response.status_code in [400, 500]

    @patch('src.services.get_db')
    def test_bulk_timeseries_requires_records(self, mock_get_db, mock_db):
        """Test bulk ingest returns 400 without records field"""
        mock_get_db.return_value = mock_db

        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.post('/ingest/bulk-timeseries',
                               json={'data': []})  # wrong field name
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════
# DATA QUALITY TESTS
# ══════════════════════════════════════════════════════════

class TestDataQuality:
    """Test data quality and normalization"""

    def test_clean_function_removes_mongo_id(self):
        from src.services import _clean
        doc = {'_id': 'mongo_id', 'symbol': 'TSLA', 'name': 'Tesla'}
        result = _clean(doc)
        assert '_id' not in result
        assert result['symbol'] == 'TSLA'

    def test_clean_function_handles_none(self):
        from src.services import _clean
        result = _clean(None)
        assert result is None

    def test_clean_function_converts_datetime(self):
        from src.services import _clean
        doc = {'validFrom': datetime(2026, 5, 1, 10, 0, 0), 'symbol': 'TEST'}
        result = _clean(doc)
        assert isinstance(result['validFrom'], str)
        assert '2026-05-01' in result['validFrom']

    def test_model_indicators_stored_correctly(self):
        from src.models import TimeSeriesData
        indicators = {'open': 100.0, 'close': 105.0, 'high': 106.0, 'low': 99.0, 'volume': 1000000}
        ts = TimeSeriesData(
            seriesId='TS_001', instrumentId='INST_001', dataSourceId='DS_001',
            dataTimestamp=datetime(2026, 5, 1), indicators=indicators
        )
        d = ts.to_dict()
        assert d['indicators']['close'] == 105.0
        assert d['indicators']['volume'] == 1000000