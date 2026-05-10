"""
Financial Data Warehouse - Flask Application
Acme Ltd
"""

from flask import Flask, jsonify, render_template, redirect
from flask_cors import CORS
from dotenv import load_dotenv
import os
from datetime import datetime

from src.database import init_db
from src.routes.api import api_bp
from src.routes.data_ingest import ingest_bp
from src.routes.mcp_server import mcp_bp
from src.routes.ai_chat import ai_bp
from src.utils.error_handlers import register_error_handlers

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/financial_dw')
    app.config['JSON_SORT_KEYS'] = False

    CORS(app, resources={r"/api/*": {"origins": "*"}, r"/mcp/*": {"origins": "*"}})

    init_db(app)

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(ingest_bp, url_prefix='/ingest')
    app.register_blueprint(mcp_bp, url_prefix='/mcp')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')

    register_error_handlers(app)

    # Root → always redirect to UI (fixes back button going to JSON)
    @app.route('/', methods=['GET'])
    def root():
        return redirect('/ui', code=302)

    # Dashboard UI
    @app.route('/ui', methods=['GET'])
    def dashboard_ui():
        return render_template('dashboard.html')

    # Health check
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'Financial Data Warehouse'
        }), 200

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=os.getenv('FLASK_DEBUG', True), host='0.0.0.0', port=5000)