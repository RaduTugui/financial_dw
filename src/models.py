"""
Data models for the financial data warehouse
"""

from datetime import datetime
from uuid import uuid4
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

@dataclass
class FinancialInstrument:
    """Financial instrument model"""
    instrumentId: str
    symbol: str
    name: str
    description: str
    instrumentClass: str  # stock, bond, crypto, option, future, etc.
    region: str
    currency: str
    isActive: bool = True
    validFrom: datetime = None
    validTo: datetime = None
    transactionStart: datetime = None
    transactionEnd: datetime = None
    deletionMarker: Optional[str] = None
    createdAt: datetime = None
    updatedAt: datetime = None
    
    def __post_init__(self):
        if self.createdAt is None:
            self.createdAt = datetime.utcnow()
        if self.updatedAt is None:
            self.updatedAt = datetime.utcnow()
        if self.validFrom is None:
            self.validFrom = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary, handling datetime objects"""
        data = asdict(self)
        for key in ['validFrom', 'validTo', 'transactionStart', 'transactionEnd', 'createdAt', 'updatedAt']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class TimeSeriesData:
    """Time series data point model"""
    seriesId: str
    instrumentId: str
    dataSourceId: str
    dataTimestamp: datetime
    indicators: Dict[str, Any]  # open, close, high, low, volume, etc.
    dataQuality: str = "verified"  # verified, preliminary, estimated
    validFrom: datetime = None
    validTo: datetime = None
    transactionStart: datetime = None
    transactionEnd: datetime = None
    recordedAt: datetime = None
    
    def __post_init__(self):
        if self.recordedAt is None:
            self.recordedAt = datetime.utcnow()
        if self.validFrom is None:
            self.validFrom = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        for key in ['dataTimestamp', 'validFrom', 'validTo', 'transactionStart', 'transactionEnd', 'recordedAt']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class DataSource:
    """Data provider/source model"""
    dataSourceId: str
    providerName: str
    providerType: str  # nasdaq, bloomberg, internal, etc.
    apiEndpoint: str
    description: str
    dataQuality: str = "verified"
    validFrom: datetime = None
    validTo: datetime = None
    transactionStart: datetime = None
    transactionEnd: datetime = None
    createdAt: datetime = None
    updatedAt: datetime = None
    
    def __post_init__(self):
        if self.createdAt is None:
            self.createdAt = datetime.utcnow()
        if self.updatedAt is None:
            self.updatedAt = datetime.utcnow()
        if self.validFrom is None:
            self.validFrom = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        for key in ['validFrom', 'validTo', 'transactionStart', 'transactionEnd', 'createdAt', 'updatedAt']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class DataProvenance:
    """Data provenance tracking model"""
    provenanceId: str
    instrumentId: str
    sourceId: str
    sourceType: str  # original_feed, transformed, aggregated
    ingestTime: datetime
    rawDataHash: str
    ingestionMethod: str
    transformationLogic: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        if isinstance(data['ingestTime'], datetime):
            data['ingestTime'] = data['ingestTime'].isoformat()
        return data

@dataclass
class InstrumentAttribute:
    """Instrument attribute model (for heterogeneous attributes)"""
    attributeId: str
    instrumentId: str
    attributeName: str
    attributeValue: Any
    attributeType: str  # string, number, boolean, date, etc.
    validFrom: datetime = None
    validTo: datetime = None
    transactionStart: datetime = None
    transactionEnd: datetime = None
    
    def __post_init__(self):
        if self.validFrom is None:
            self.validFrom = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        for key in ['validFrom', 'validTo', 'transactionStart', 'transactionEnd']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class Portfolio:
    """Portfolio model"""
    portfolioId: str
    portfolioName: str
    ownerType: str  # company, individual
    ownerId: str
    createdAt: datetime = None
    validFrom: datetime = None
    validTo: datetime = None
    transactionStart: datetime = None
    transactionEnd: datetime = None
    
    def __post_init__(self):
        if self.createdAt is None:
            self.createdAt = datetime.utcnow()
        if self.validFrom is None:
            self.validFrom = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        for key in ['createdAt', 'validFrom', 'validTo', 'transactionStart', 'transactionEnd']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class PortfolioHolding:
    """Portfolio holding model"""
    holdingId: str
    portfolioId: str
    instrumentId: str
    quantity: float
    averageCost: float
    acquiredDate: datetime
    validFrom: datetime = None
    validTo: datetime = None
    transactionStart: datetime = None
    transactionEnd: datetime = None
    
    def __post_init__(self):
        if self.validFrom is None:
            self.validFrom = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        for key in ['acquiredDate', 'validFrom', 'validTo', 'transactionStart', 'transactionEnd']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class AnalyticsJob:
    """Analytics/ML job model"""
    jobId: str
    jobType: str  # trend_analysis, forecast, risk_assessment, etc.
    targetInstrumentId: str
    parameters: Dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed
    scheduledAt: datetime = None
    executedAt: datetime = None
    resultLocation: Optional[str] = None
    
    def __post_init__(self):
        if self.scheduledAt is None:
            self.scheduledAt = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        for key in ['scheduledAt', 'executedAt']:
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data
