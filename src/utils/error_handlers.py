"""
Error handlers and utility functions
"""

from flask import jsonify
from datetime import datetime

def register_error_handlers(app):
    """Register Flask error handlers"""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': str(error),
            'timestamp': datetime.utcnow().isoformat()
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'timestamp': datetime.utcnow().isoformat()
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

class ValidationError(Exception):
    """Custom validation error"""
    pass

class NotFoundError(Exception):
    """Custom not found error"""
    pass

def validate_required_fields(data: dict, required_fields: list) -> bool:
    """Validate that all required fields are present"""
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValidationError(f'Missing required fields: {missing}')
    return True

def format_response(status: str, data=None, message: str = None, error: str = None):
    """Format API response"""
    response = {'status': status}
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    if error:
        response['error'] = error
    
    response['timestamp'] = datetime.utcnow().isoformat()
    
    return response
