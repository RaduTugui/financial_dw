"""
Database initialization and MongoDB setup
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ServerSelectionTimeoutError
from datetime import datetime
import os

mongo_client = None
db = None

def init_db(app):
    """Initialize MongoDB connection and create indexes"""
    global mongo_client, db
    
    try:
        mongo_uri = app.config.get('MONGO_URI', 'mongodb://localhost:27017/financial_dw')
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Verify connection
        mongo_client.admin.command('ping')
        
        db = mongo_client.financial_dw
        
        # Create collections and indexes
        _create_collections()
        _create_indexes()
        
        print("✓ MongoDB connection established successfully")
        return db
    
    except ServerSelectionTimeoutError:
        print("✗ Failed to connect to MongoDB. Make sure it's running.")
        raise

def get_db():
    """Get the database connection"""
    global db
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    return db

def _create_collections():
    """Create required collections if they don't exist"""
    db = get_db()
    collections = [
        'financial_instruments',
        'time_series_data',
        'data_sources',
        'data_provenance',
        'instrument_attributes',
        'portfolios',
        'portfolio_holdings',
        'analytics_jobs'
    ]
    
    for collection in collections:
        if collection not in db.list_collection_names():
            db.create_collection(collection)
            print(f"✓ Created collection: {collection}")

def _create_indexes():
    """Create indexes for efficient querying"""
    db = get_db()
    
    # Financial Instruments indexes
    db.financial_instruments.create_index([('symbol', ASCENDING)], unique=True)
    db.financial_instruments.create_index([('instrumentId', ASCENDING)], unique=True)
    db.financial_instruments.create_index([('instrumentClass', ASCENDING)])
    db.financial_instruments.create_index([('isActive', ASCENDING)])
    db.financial_instruments.create_index([('validFrom', ASCENDING), ('validTo', ASCENDING)])
    
    # Time Series Data indexes
    db.time_series_data.create_index([('instrumentId', ASCENDING), ('dataSourceId', ASCENDING)])
    db.time_series_data.create_index([('dataTimestamp', DESCENDING)])
    db.time_series_data.create_index([('seriesId', ASCENDING)])
    
    # Data Sources indexes
    db.data_sources.create_index([('dataSourceId', ASCENDING)], unique=True)
    db.data_sources.create_index([('providerName', ASCENDING)])
    
    # Data Provenance indexes
    db.data_provenance.create_index([('provenanceId', ASCENDING)], unique=True)
    db.data_provenance.create_index([('dataSourceId', ASCENDING)])
    
    # Instrument Attributes indexes
    db.instrument_attributes.create_index([('instrumentId', ASCENDING), ('attributeId', ASCENDING)])
    db.instrument_attributes.create_index([('attributeName', ASCENDING)])
    
    # Portfolio indexes
    db.portfolios.create_index([('portfolioId', ASCENDING)], unique=True)
    
    # Portfolio Holdings indexes
    db.portfolio_holdings.create_index([('portfolioId', ASCENDING), ('instrumentId', ASCENDING)])
    
    # Analytics Jobs indexes
    db.analytics_jobs.create_index([('jobId', ASCENDING)], unique=True)
    db.analytics_jobs.create_index([('status', ASCENDING)])
    
    print("✓ All indexes created successfully")

def close_db():
    """Close database connection"""
    global mongo_client
    if mongo_client:
        mongo_client.close()
        print("✓ Database connection closed")
