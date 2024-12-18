# app.py
from flask import Flask, render_template, request, jsonify
from boardgame_advisor import BoardGameAdvisor
import asyncio
from functools import wraps

app = Flask(__name__)
advisor = BoardGameAdvisor()

def async_route(route_function):
    @wraps(route_function)
    def wrapped(*args, **kwargs):
        return asyncio.run(route_function(*args, **kwargs))
    return wrapped

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/recommend', methods=['POST'])
@async_route
async def recommend():
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Request must be JSON'
        }), 400

    data = request.get_json()
    
    try:
        if not data or 'player_count' not in data or 'players' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required data'
            }), 400

        recommendations = await advisor.get_recommendations(
            player_count=data['player_count'],
            players=data['players']
        )
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        print(f"Error in recommendation: {str(e)}")  # For debugging
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

if __name__ == '__main__':
    app.run(debug=True)