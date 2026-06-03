"""
UC3 - Apache Spark Analytics Workflow
Financial Data Warehouse - Acme Ltd

This module uses Apache Spark to perform aggregation and analytics
on financial time series data stored in MongoDB.

Requirements:
    pip install pyspark pymongo

Usage:
    python src/spark/spark_analytics.py
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def create_spark_session():
    """Create a Spark session connected to MongoDB"""
    spark = SparkSession.builder \
        .appName("FinancialDataWarehouse-Analytics") \
        .config("spark.mongodb.input.uri", "mongodb://localhost:27017/financial_dw.time_series_data") \
        .config("spark.mongodb.output.uri", "mongodb://localhost:27017/financial_dw.spark_results") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_data_from_api():
    """
    Load time series data from the Flask REST API.
    This approach works without the MongoDB Spark Connector.
    """
    import requests

    print("  → Fetching data from REST API...")

    # Get all instruments
    instruments = requests.get("http://localhost:5000/api/instruments?limit=200").json()
    sources = requests.get("http://localhost:5000/api/sources").json()

    # Find Yahoo Finance source
    yahoo_src = next(
        (s for s in sources['data'] if s['providerType'] == 'yahoo'),
        None
    )

    if not yahoo_src:
        print("  ✗ Yahoo Finance source not found!")
        return []

    all_records = []
    for inst in instruments['data']:
        ts = requests.get(
            f"http://localhost:5000/api/timeseries",
            params={
                "instrumentId": inst['assetId'],
                "dataSourceId": yahoo_src['dataSourceId'],
                "limit": 500
            }
        ).json()

        for record in ts.get('data', []):
            all_records.append({
                "symbol":        inst['symbol'],
                "name":          inst['name'],
                "instrumentClass": inst['instrumentClass'],
                "instrumentId":  inst['assetId'],
                "dataSourceId":  yahoo_src['dataSourceId'],
                "dataTimestamp": record.get('dataTimestamp', ''),
                "open":          float(record['indicators'].get('open', 0) or 0),
                "close":         float(record['indicators'].get('close', 0) or 0),
                "high":          float(record['indicators'].get('high', 0) or 0),
                "low":           float(record['indicators'].get('low', 0) or 0),
                "volume":        float(record['indicators'].get('volume', 0) or 0),
                "dataQuality":   record.get('dataQuality', 'unknown')
            })

    print(f"  ✓ Loaded {len(all_records)} records from API")
    return all_records


def run_aggregation_analytics(spark, df):
    """
    UC3 - Aggregation Analytics
    Computes: count, min, max, avg, stddev, volatility per instrument
    """
    print("\n── Aggregation Analytics ──────────────────────────────────")

    # Register as temp view for SQL queries
    df.createOrReplaceTempView("time_series")

    # Aggregation per instrument
    agg_df = df.groupBy("symbol", "name", "instrumentClass") \
        .agg(
            F.count("close").alias("data_points"),
            F.round(F.min("close"), 2).alias("min_price"),
            F.round(F.max("close"), 2).alias("max_price"),
            F.round(F.avg("close"), 2).alias("avg_price"),
            F.round(F.stddev("close"), 4).alias("price_stddev"),
            F.round(F.min("low"), 2).alias("min_low"),
            F.round(F.max("high"), 2).alias("max_high"),
            F.round(F.avg("volume"), 0).alias("avg_volume"),
            F.round(F.sum("volume"), 0).alias("total_volume")
        ) \
        .orderBy("instrumentClass", "symbol")

    print("\n  📊 Aggregated Statistics per Instrument:")
    agg_df.show(truncate=False)

    # Price range analysis using Spark SQL
    print("\n  📊 Price Range Analysis (Spark SQL):")
    spark.sql("""
        SELECT 
            symbol,
            instrumentClass,
            ROUND(MAX(high) - MIN(low), 2) as price_range,
            ROUND((MAX(high) - MIN(low)) / AVG(close) * 100, 2) as range_pct,
            COUNT(*) as trading_days
        FROM time_series
        GROUP BY symbol, instrumentClass
        ORDER BY range_pct DESC
    """).show(truncate=False)

    return agg_df


def run_trend_analytics(spark, df):
    """
    UC3 - Trend Analytics using Spark Window Functions
    Computes: moving averages, daily returns, trend direction
    """
    print("\n── Trend Analytics (Window Functions) ────────────────────")

    # Window spec for moving averages
    window_7d  = Window.partitionBy("symbol").orderBy("dataTimestamp").rowsBetween(-6, 0)
    window_30d = Window.partitionBy("symbol").orderBy("dataTimestamp").rowsBetween(-29, 0)
    window_lag = Window.partitionBy("symbol").orderBy("dataTimestamp")

    # Compute moving averages and daily returns
    trend_df = df \
        .withColumn("ma_7d",  F.round(F.avg("close").over(window_7d), 2)) \
        .withColumn("ma_30d", F.round(F.avg("close").over(window_30d), 2)) \
        .withColumn("prev_close", F.lag("close", 1).over(window_lag)) \
        .withColumn("daily_return",
            F.round((F.col("close") - F.lag("close", 1).over(window_lag)) /
                    F.lag("close", 1).over(window_lag) * 100, 4)
        )

    # Trend summary per instrument
    print("\n  📈 Moving Averages & Trend Direction:")
    trend_df.groupBy("symbol") \
        .agg(
            F.round(F.last("ma_7d"), 2).alias("latest_ma_7d"),
            F.round(F.last("ma_30d"), 2).alias("latest_ma_30d"),
            F.round(F.avg("daily_return"), 4).alias("avg_daily_return_pct"),
            F.round(F.stddev("daily_return"), 4).alias("volatility"),
            F.round(
                (F.last("close") - F.first("close")) / F.first("close") * 100,
                2
            ).alias("total_return_pct")
        ) \
        .withColumn("trend",
            F.when(F.col("total_return_pct") > 5, "STRONG UPTREND")
             .when(F.col("total_return_pct") > 0, "UPTREND")
             .when(F.col("total_return_pct") > -5, "DOWNTREND")
             .otherwise("STRONG DOWNTREND")
        ) \
        .orderBy("total_return_pct", ascending=False) \
        .show(truncate=False)

    return trend_df


def run_comparison_analytics(spark, df):
    """
    UC3 - Cross-instrument comparison analytics
    """
    print("\n── Cross-Instrument Comparison ───────────────────────────")

    spark.sql("""
        SELECT 
            symbol,
            instrumentClass,
            ROUND(AVG(close), 2) as avg_price,
            ROUND(STDDEV(close) / AVG(close) * 100, 2) as coefficient_of_variation_pct,
            ROUND((LAST(close) - FIRST(close)) / FIRST(close) * 100, 2) as period_return_pct,
            ROUND(AVG(high - low), 2) as avg_daily_range,
            COUNT(*) as trading_days
        FROM time_series
        GROUP BY symbol, instrumentClass
        ORDER BY period_return_pct DESC
    """).show(truncate=False)


def run_risk_analytics(spark, df):
    """
    UC3 - Risk Analytics
    Computes Value at Risk (VaR) approximation and Sharpe-like ratio
    """
    print("\n── Risk Analytics ────────────────────────────────────────")

    window_lag = Window.partitionBy("symbol").orderBy("dataTimestamp")

    risk_df = df \
        .withColumn("daily_return",
            (F.col("close") - F.lag("close", 1).over(window_lag)) /
            F.lag("close", 1).over(window_lag) * 100
        ) \
        .filter(F.col("daily_return").isNotNull())

    # Risk metrics per instrument
    risk_df.groupBy("symbol", "instrumentClass") \
        .agg(
            F.round(F.avg("daily_return"), 4).alias("mean_daily_return"),
            F.round(F.stddev("daily_return"), 4).alias("daily_volatility"),
            F.round(F.expr("percentile(daily_return, 0.05)"), 4).alias("var_95"),
            F.round(F.expr("percentile(daily_return, 0.01)"), 4).alias("var_99"),
            F.count("daily_return").alias("observations")
        ) \
        .withColumn("sharpe_approx",
            F.round(F.col("mean_daily_return") / F.col("daily_volatility"), 4)
        ) \
        .withColumn("risk_level",
            F.when(F.abs(F.col("daily_volatility")) > 3, "HIGH RISK")
             .when(F.abs(F.col("daily_volatility")) > 1.5, "MEDIUM RISK")
             .otherwise("LOW RISK")
        ) \
        .orderBy("daily_volatility", ascending=False) \
        .show(truncate=False)


def main():
    print("=" * 65)
    print("  Financial Data Warehouse — Apache Spark Analytics")
    print("  UC3: Data Aggregation, Analytics and Data Mining")
    print("=" * 65)

    # Create Spark session
    print("\n── Initializing Spark Session ────────────────────────────")
    spark = create_spark_session()
    print(f"  ✓ Spark version: {spark.version}")

    # Load data from REST API
    print("\n── Loading Data from REST API ────────────────────────────")
    records = load_data_from_api()

    if not records:
        print("  ✗ No data loaded. Make sure Flask is running: python app.py")
        spark.stop()
        return

    # Create Spark DataFrame
    df = spark.createDataFrame(records)
    df.cache()
    print(f"  ✓ Created Spark DataFrame with {df.count()} rows")
    print(f"  ✓ Schema: {', '.join(df.columns)}")

    # Run analytics workflows
    run_aggregation_analytics(spark, df)
    run_trend_analytics(spark, df)
    run_comparison_analytics(spark, df)
    run_risk_analytics(spark, df)

    print("\n" + "=" * 65)
    print("  ✅ Spark Analytics Complete!")
    print("=" * 65)

    spark.stop()


if __name__ == "__main__":
    main()