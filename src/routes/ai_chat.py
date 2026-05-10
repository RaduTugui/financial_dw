"""
AI Chat route - connects Claude AI to the MCP tools
Implements UC4: LLM Integration
"""

from flask import Blueprint, request, jsonify
import os
import requests

ai_bp = Blueprint('ai', __name__)

CLAUDE_MODEL = 'claude-sonnet-4-5'

@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    """
    Proxy endpoint between the UI and Claude API.
    The UI sends messages + tools, we forward to Claude and return the response.
    Claude will decide which MCP tools to call, and the UI executes them.
    """
    # Read API key at request time (not import time) so .env is loaded
    api_key = os.getenv('ANTHROPIC_API_KEY', '')

    if not api_key:
        return jsonify({
            'error': 'ANTHROPIC_API_KEY not set in .env file',
            'content': [{'type': 'text', 'text': '⚠️ Please add ANTHROPIC_API_KEY to your .env file and restart Flask.'}],
            'stop_reason': 'end_turn'
        }), 200

    try:
        data     = request.get_json()
        messages = data.get('messages', [])
        tools    = data.get('tools', [])
        system   = data.get('system', '')

        # Call Claude API
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key':         api_key,
                'anthropic-version': '2023-06-01',
                'content-type':      'application/json'
            },
            json={
                'model':      CLAUDE_MODEL,
                'max_tokens': 1024,
                'system':     system,
                'messages':   messages,
                'tools':      tools if tools else []
            },
            timeout=30
        )

        if response.status_code != 200:
            error_text = response.json().get('error', {}).get('message', response.text)
            return jsonify({
                'error': f'Claude API error: {error_text}',
                'content': [{'type': 'text', 'text': f'❌ Claude API error: {error_text}'}],
                'stop_reason': 'end_turn'
            }), 200

        return jsonify(response.json()), 200

    except requests.Timeout:
        return jsonify({
            'error': 'Request timed out',
            'content': [{'type': 'text', 'text': '⏱️ Request timed out. Please try again.'}],
            'stop_reason': 'end_turn'
        }), 200

    except Exception as e:
        return jsonify({
            'error': str(e),
            'content': [{'type': 'text', 'text': f'❌ Error: {str(e)}'}],
            'stop_reason': 'end_turn'
        }), 200