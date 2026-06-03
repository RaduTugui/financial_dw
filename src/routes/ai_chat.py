"""
AI Chat route - connects Claude AI to the MCP tools
Implements UC4: LLM Integration via MCP

Hallucination Prevention:
- Claude is explicitly instructed to ONLY use data from MCP tool results
- System prompt forbids generic finance knowledge
- All responses must cite which tool was called
- If no tool data available, Claude must say so explicitly
"""

from flask import Blueprint, request, jsonify
import os
import requests

ai_bp = Blueprint('ai', __name__)

CLAUDE_MODEL = 'claude-sonnet-4-5'

# Strict system prompt to prevent hallucination
ANTI_HALLUCINATION_SYSTEM = """You are an AI assistant for Acme Ltd's Financial Data Warehouse.

CRITICAL RULES - YOU MUST FOLLOW THESE:
1. You MUST call MCP tools to get data BEFORE answering any question about prices, trends, or statistics
2. You MUST NEVER use your training knowledge about stock prices, crypto prices, or market data
3. You MUST ONLY state facts that come directly from tool results
4. If a tool returns no data, you MUST say "I don't have data for that in the warehouse"
5. You MUST mention which tool you called and what it returned
6. NEVER make up prices, percentages, or statistics
7. If asked about current prices without tool data, say "Let me check the warehouse" and call get_latest_price

GROUNDING REQUIREMENT:
Every factual claim about financial data MUST be traceable to a specific tool call result.
Prefix data-backed claims with the source, e.g.: "According to the warehouse data: TSLA closed at $428.35"

AVAILABLE DATA:
- Real verified data from Yahoo Finance (dataQuality: verified)
- Simulated data for testing (dataQuality: simulated)
- Always mention the data quality in your response
"""

@ai_bp.route('/chat', methods=['POST'])
def ai_chat():
    """
    Proxy endpoint between the UI and Claude API.
    Includes strict hallucination prevention via system prompt.
    """
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

        # Combine user system prompt with anti-hallucination rules
        full_system = ANTI_HALLUCINATION_SYSTEM + "\n\n" + system

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
                'system':     full_system,
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