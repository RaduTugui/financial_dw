"""
UC3 - Apache Spark ML Prediction Workflow
Financial Data Warehouse - Acme Ltd

This module uses Apache Spark MLlib to build a price prediction model
for financial instruments using Linear Regression.

Requirements:
    pip install pyspark

Usage:
    python src/spark/spark_ml_forecast.py
    python src/spark/spark_ml_forecast.py --symbol TSLA
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.regression import LinearRegression, RandomForestRegressor
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml import Pipeline
import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def create_spark_session():
    """Create a Spark session for ML workloads"""
    spark = SparkSession.builder \
        .appName("FinancialDataWarehouse-ML") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_instrument_data(symbol="TSLA"):
    """Load time series data for a specific instrument from REST API"""
    import requests

    print(f"  → Loading data for {symbol}...")

    instruments = requests.get("http://localhost:5000/api/instruments?limit=200").json()
    sources = requests.get("http://localhost:5000/api/sources").json()

    # Find instrument
    instrument = next(
        (i for i in instruments['data'] if i['symbol'] == symbol),
        None
    )
    if not instrument:
        print(f"  ✗ Instrument {symbol} not found!")
        return []

    # Find Yahoo Finance source
    yahoo_src = next(
        (s for s in sources['data'] if s['providerType'] == 'yahoo'),
        None
    )
    if not yahoo_src:
        print("  ✗ Yahoo Finance source not found!")
        return []

    # Fetch time series
    ts = requests.get(
        "http://localhost:5000/api/timeseries",
        params={
            "instrumentId": instrument['assetId'],
            "dataSourceId": yahoo_src['dataSourceId'],
            "limit": 500
        }
    ).json()

    records = []
    for i, record in enumerate(reversed(ts.get('data', []))):
        records.append({
            "day_index":  float(i),
            "open":       float(record['indicators'].get('open', 0) or 0),
            "close":      float(record['indicators'].get('close', 0) or 0),
            "high":       float(record['indicators'].get('high', 0) or 0),
            "low":        float(record['indicators'].get('low', 0) or 0),
            "volume":     float(record['indicators'].get('volume', 0) or 0),
            "timestamp":  record.get('dataTimestamp', '')
        })

    print(f"  ✓ Loaded {len(records)} records for {symbol}")
    return records, instrument['name']


def engineer_features(df):
    """
    Feature engineering for ML model:
    - Moving averages (7-day, 14-day)
    - Price momentum
    - Volatility (high-low range)
    - Volume momentum
    """
    window_7  = Window.orderBy("day_index").rowsBetween(-6, 0)
    window_14 = Window.orderBy("day_index").rowsBetween(-13, 0)
    window_lag = Window.orderBy("day_index")

    df = df \
        .withColumn("ma_7",       F.avg("close").over(window_7)) \
        .withColumn("ma_14",      F.avg("close").over(window_14)) \
        .withColumn("prev_close", F.lag("close", 1).over(window_lag)) \
        .withColumn("prev_close2",F.lag("close", 2).over(window_lag)) \
        .withColumn("momentum",   F.col("close") - F.lag("close", 5).over(window_lag)) \
        .withColumn("volatility", F.col("high") - F.col("low")) \
        .withColumn("vol_ma_7",   F.avg("volume").over(window_7)) \
        .withColumn("price_range_pct",
            (F.col("high") - F.col("low")) / F.col("close") * 100
        ) \
        .withColumn("next_close", F.lead("close", 1).over(window_lag))

    # Drop rows with nulls (from window functions)
    df = df.dropna()

    return df


def train_linear_regression(spark, df, symbol):
    """
    Train a Linear Regression model to predict next day's closing price
    """
    print(f"\n  📊 Linear Regression Model for {symbol}")

    feature_cols = ["open", "high", "low", "close", "volume",
                    "ma_7", "ma_14", "prev_close", "prev_close2",
                    "momentum", "volatility", "vol_ma_7", "price_range_pct"]

    # Assemble features
    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features_raw")
    scaler    = StandardScaler(inputCol="features_raw", outputCol="features",
                               withStd=True, withMean=True)
    lr        = LinearRegression(featuresCol="features", labelCol="next_close",
                                 maxIter=100, regParam=0.1, elasticNetParam=0.5)

    pipeline = Pipeline(stages=[assembler, scaler, lr])

    # Train/test split (80/20)
    train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
    print(f"     Training samples: {train_df.count()}, Test samples: {test_df.count()}")

    # Train
    model = pipeline.fit(train_df)

    # Evaluate
    predictions = model.transform(test_df)
    evaluator_rmse = RegressionEvaluator(labelCol="next_close", predictionCol="prediction",
                                          metricName="rmse")
    evaluator_r2   = RegressionEvaluator(labelCol="next_close", predictionCol="prediction",
                                          metricName="r2")
    evaluator_mae  = RegressionEvaluator(labelCol="next_close", predictionCol="prediction",
                                          metricName="mae")

    rmse = evaluator_rmse.evaluate(predictions)
    r2   = evaluator_r2.evaluate(predictions)
    mae  = evaluator_mae.evaluate(predictions)

    print(f"     RMSE: ${rmse:.4f}")
    print(f"     MAE:  ${mae:.4f}")
    print(f"     R²:   {r2:.4f}")

    # Show sample predictions
    print(f"\n     Sample Predictions vs Actual:")
    predictions.select("close", "next_close", "prediction") \
        .withColumn("error_pct",
            F.round(F.abs(F.col("prediction") - F.col("next_close")) /
                    F.col("next_close") * 100, 2)
        ) \
        .withColumn("prediction", F.round("prediction", 2)) \
        .show(5)

    # Next day forecast (latest data point)
    latest = df.orderBy("day_index", ascending=False).limit(1)
    forecast = model.transform(latest)
    next_price = forecast.select("prediction").collect()[0][0]
    current_price = latest.select("close").collect()[0][0]
    change_pct = (next_price - current_price) / current_price * 100

    print(f"\n     🔮 Next Day Forecast for {symbol}:")
    print(f"        Current price:  ${current_price:.2f}")
    print(f"        Predicted next: ${next_price:.2f}")
    print(f"        Expected change: {change_pct:+.2f}%")

    return model, rmse, r2


def train_random_forest(spark, df, symbol):
    """
    Train a Random Forest model for price direction classification
    """
    print(f"\n  🌲 Random Forest Regressor for {symbol}")

    feature_cols = ["open", "high", "low", "close", "volume",
                    "ma_7", "ma_14", "momentum", "volatility"]

    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
    rf = RandomForestRegressor(featuresCol="features", labelCol="next_close",
                               numTrees=50, maxDepth=5, seed=42)

    pipeline = Pipeline(stages=[assembler, rf])

    train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)

    model = pipeline.fit(train_df)
    predictions = model.transform(test_df)

    evaluator = RegressionEvaluator(labelCol="next_close", predictionCol="prediction",
                                     metricName="rmse")
    rmse = evaluator.evaluate(predictions)
    r2_eval = RegressionEvaluator(labelCol="next_close", predictionCol="prediction",
                                   metricName="r2")
    r2 = r2_eval.evaluate(predictions)

    print(f"     RMSE: ${rmse:.4f}")
    print(f"     R²:   {r2:.4f}")

    # Feature importance
    rf_model = model.stages[-1]
    importances = list(zip(feature_cols, rf_model.featureImportances.toArray()))
    importances.sort(key=lambda x: x[1], reverse=True)

    print(f"\n     Feature Importances:")
    for feat, imp in importances[:5]:
        bar = "█" * int(imp * 50)
        print(f"     {feat:20s} {bar} {imp:.4f}")

    return model, rmse, r2


def main():
    parser = argparse.ArgumentParser(description='Spark ML Price Forecasting')
    parser.add_argument('--symbol', default='TSLA', help='Instrument symbol (default: TSLA)')
    args = parser.parse_args()

    symbol = args.symbol.upper()

    print("=" * 65)
    print("  Financial Data Warehouse — Apache Spark ML Forecasting")
    print("  UC3: Price Prediction using MLlib")
    print("=" * 65)

    # Create Spark session
    print("\n── Initializing Spark ML Session ─────────────────────────")
    spark = create_spark_session()
    print(f"  ✓ Spark version: {spark.version}")

    # Load data
    print(f"\n── Loading Data for {symbol} ─────────────────────────────")
    result = load_instrument_data(symbol)

    if not result:
        spark.stop()
        return

    records, name = result
    if len(records) < 30:
        print(f"  ✗ Not enough data for {symbol} (need at least 30 records)")
        spark.stop()
        return

    # Create DataFrame
    df = spark.createDataFrame(records)

    # Feature engineering
    print(f"\n── Feature Engineering ───────────────────────────────────")
    df = engineer_features(df)
    df.cache()
    print(f"  ✓ Features engineered: {len(df.columns)} columns")
    print(f"  ✓ Training samples available: {df.count()}")

    # Train models
    print(f"\n── Model Training ────────────────────────────────────────")
    lr_model, lr_rmse, lr_r2     = train_linear_regression(spark, df, symbol)
    rf_model, rf_rmse, rf_r2     = train_random_forest(spark, df, symbol)

    # Model comparison
    print(f"\n── Model Comparison ──────────────────────────────────────")
    print(f"  {'Model':<25} {'RMSE':>10} {'R²':>10}")
    print(f"  {'-'*45}")
    print(f"  {'Linear Regression':<25} ${lr_rmse:>9.4f} {lr_r2:>10.4f}")
    print(f"  {'Random Forest':<25} ${rf_rmse:>9.4f} {rf_r2:>10.4f}")

    best = "Linear Regression" if lr_rmse < rf_rmse else "Random Forest"
    print(f"\n  🏆 Best model: {best}")

    print("\n" + "=" * 65)
    print(f"  ✅ ML Forecasting Complete for {symbol} ({name})")
    print("=" * 65)

    spark.stop()


if __name__ == "__main__":
    main()