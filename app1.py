from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import threading
import time
import schedule
from datetime import datetime, timedelta
from scraper1 import VTDiningScraper
from openai import OpenAI
import logging
from functools import wraps
import re

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize OpenAI client properly
openai_client = None
if os.getenv('OPENAI_API_KEY'):
    try:
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        logger.info("OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
else:
    logger.warning("OPENAI_API_KEY not found in environment variables")

# Global variables for menu data
current_menu_data = {}
last_update = None
scraper = VTDiningScraper()

# Simple rate limiting decorator
def rate_limit(max_requests_per_minute=10):
    def decorator(f):
        calls = {}
        
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            client_ip = request.remote_addr
            
            # Clean old entries
            minute_ago = now - 60
            calls[client_ip] = [call_time for call_time in calls.get(client_ip, []) if call_time > minute_ago]
            
            # Check rate limit
            if len(calls.get(client_ip, [])) >= max_requests_per_minute:
                return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
            
            # Record this call
            calls.setdefault(client_ip, []).append(now)
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

# Input validation decorator
def validate_json(required_fields=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({"error": "Invalid JSON data"}), 400
            
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({"error": f"Missing required fields: {missing_fields}"}), 400
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def load_menu_data():
    """Load menu data from JSON file"""
    global current_menu_data, last_update
    
    try:
        with open('vt_dining_data.json', 'r') as f:
            current_menu_data = json.load(f)
            last_update = datetime.fromisoformat(current_menu_data.get('last_updated', datetime.now().isoformat()))
            logger.info(f"Loaded menu data from {last_update}")
    except FileNotFoundError:
        logger.info("No existing menu data found, will scrape fresh data")
        update_menu_data()
    except Exception as e:
        logger.error(f"Error loading menu data: {e}")
        current_menu_data = {"dining_halls": []}

def update_menu_data():
    """Scrape fresh data from VT website"""
    global current_menu_data, last_update
    
    logger.info("Updating menu data...")
    try:
        current_menu_data = scraper.scrape_all_data()
        last_update = datetime.now()
        logger.info("Menu data updated successfully!")
    except Exception as e:
        logger.error(f"Error updating menu data: {e}")

def schedule_daily_updates():
    """Schedule daily data updates"""
    schedule.every().day.at("06:00").do(update_menu_data)
    
    while True:
        schedule.run_pending()
        time.sleep(3600)

def start_scheduler():
    """Start background scheduler"""
    scheduler_thread = threading.Thread(target=schedule_daily_updates, daemon=True)
    scheduler_thread.start()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "last_data_update": last_update.isoformat() if last_update else None,
        "dining_halls_count": len(current_menu_data.get('dining_halls', [])),
        "openai_configured": openai_client is not None,
        "version": "1.1.0"
    })

@app.route('/api/dining-halls', methods=['GET'])
def get_dining_halls():
    """Get list of all dining halls with their food items"""
    try:
        return jsonify({
            "success": True,
            "data": current_menu_data.get('dining_halls', []),
            "last_updated": current_menu_data.get('last_updated')
        })
    except Exception as e:
        logger.error(f"Error getting dining halls: {e}")
        return jsonify({"error": "Failed to retrieve dining halls"}), 500

@app.route('/api/chatbot/meal-plan', methods=['POST'])
@rate_limit(max_requests_per_minute=5)  # Lower limit for AI endpoints
@validate_json()
def generate_meal_plan():
    """Generate personalized meal plan using OpenAI"""
    try:
        data = request.json
        
        # Extract and validate user preferences
        calories = data.get('calories', 2000)
        dietary_restrictions = data.get('dietary_restrictions', [])
        macro_focus = data.get('macro_focus', {'protein': 25, 'carbs': 45, 'fat': 30})
        food_preferences = data.get('food_preferences', '')
        
        # Input validation
        if not isinstance(calories, (int, float)) or calories < 800 or calories > 5000:
            return jsonify({"error": "Calories must be between 800-5000"}), 400
        
        if not isinstance(dietary_restrictions, list):
            return jsonify({"error": "Dietary restrictions must be a list"}), 400
        
        # Validate macro percentages
        if isinstance(macro_focus, dict):
            total_macros = sum(macro_focus.values())
            if abs(total_macros - 100) > 5:  # Allow 5% tolerance
                return jsonify({"error": "Macro percentages should sum to approximately 100%"}), 400
        
        # Sanitize text inputs
        food_preferences = re.sub(r'[^\w\s,.-]', '', str(food_preferences)[:500])
        
        # Generate meal plan
        meal_plan = create_ai_meal_plan(
            current_menu_data, 
            int(calories), 
            dietary_restrictions, 
            macro_focus, 
            food_preferences
        )
        
        return jsonify({
            "success": True,
            "data": meal_plan
        })
        
    except Exception as e:
        logger.error(f"Error generating meal plan: {e}")
        return jsonify({"error": "Failed to generate meal plan"}), 500

@app.route('/api/chatbot/quick-suggest', methods=['POST'])
@rate_limit(max_requests_per_minute=15)
@validate_json(['message'])
def quick_suggest():
    """Quick food suggestions based on user input"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        # Input validation and sanitization
        if len(user_message) > 200:
            return jsonify({"error": "Message too long (max 200 characters)"}), 400
        
        user_message = re.sub(r'[^\w\s,.-]', '', user_message)
        
        suggestions = generate_quick_suggestions(user_message, current_menu_data)
        
        return jsonify({
            "success": True,
            "data": {"suggestions": suggestions}
        })
        
    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        return jsonify({"error": "Failed to generate suggestions"}), 500

@app.route('/api/refresh-data', methods=['POST'])
def refresh_data():
    """Manually refresh menu data - protected endpoint"""
    # Simple API key protection
    api_key = request.headers.get('X-API-Key')
    expected_key = os.getenv('ADMIN_API_KEY', 'default-admin-key-change-me')
    
    if api_key != expected_key:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        update_menu_data()
        return jsonify({
            "success": True,
            "message": "Data refreshed successfully",
            "updated_at": last_update.isoformat() if last_update else None
        })
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return jsonify({"error": "Failed to refresh data"}), 500

def create_ai_meal_plan(menu_data, calories, restrictions, macros, preferences):
    """Use OpenAI to create a personalized meal plan"""
    
    if not openai_client:
        logger.warning("OpenAI client not available, using fallback")
        return create_fallback_meal_plan(menu_data, calories)
    
    # Format available food data for AI
    available_foods = format_foods_for_ai(menu_data)
    
    if not available_foods:
        logger.warning("No food data available, using fallback")
        return create_fallback_meal_plan(menu_data, calories)
    
    # Create restrictions string
    restrictions_str = ", ".join(restrictions) if restrictions else "None"
    
    prompt = f"""You are a nutrition expert helping a Virginia Tech student create a meal plan for today.

STUDENT REQUIREMENTS:
- Target calories: {calories}
- Dietary restrictions: {restrictions_str}
- Macro targets: Protein {macros.get('protein', 25)}%, Carbs {macros.get('carbs', 45)}%, Fat {macros.get('fat', 30)}%
- Food preferences: {preferences or 'None specified'}

AVAILABLE FOODS TODAY AT VT DINING HALLS:
{available_foods}

Create a complete meal plan with breakfast, lunch, dinner, and optional snacks.
Focus on creating balanced, realistic meals using ONLY the foods listed above.
Ensure the total calories are within 10% of the target.

Return ONLY valid JSON in this exact format:
{{
    "meal_plan": {{
        "breakfast": [
            {{
                "item": "Food Name",
                "dining_hall": "Hall Name", 
                "calories": 000,
                "protein": 00,
                "carbs": 00,
                "fat": 00
            }}
        ],
        "lunch": [...],
        "dinner": [...],
        "snacks": [...]
    }},
    "totals": {{
        "calories": 0000,
        "protein": 000,
        "carbs": 000, 
        "fat": 000
    }},
    "notes": "Brief explanation of food choices and how they meet the student's goals"
}}"""
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful nutrition assistant. Always respond with valid JSON only."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500,
            timeout=30
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Clean response (remove markdown code blocks if present)
        if ai_response.startswith('```json'):
            ai_response = ai_response[7:]
        if ai_response.endswith('```'):
            ai_response = ai_response[:-3]
        ai_response = ai_response.strip()
        
        # Parse the JSON response
        meal_plan = json.loads(ai_response)
        
        # Validate the response structure
        if not validate_meal_plan_structure(meal_plan):
            logger.warning("AI returned invalid meal plan structure, using fallback")
            return create_fallback_meal_plan(menu_data, calories)
        
        return meal_plan
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error from AI response: {e}")
        return create_fallback_meal_plan(menu_data, calories)
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return create_fallback_meal_plan(menu_data, calories)

def validate_meal_plan_structure(meal_plan):
    """Validate that meal plan has the expected structure"""
    required_keys = ['meal_plan', 'totals', 'notes']
    if not all(key in meal_plan for key in required_keys):
        return False
    
    meal_periods = ['breakfast', 'lunch', 'dinner']
    if not all(period in meal_plan['meal_plan'] for period in meal_periods):
        return False
    
    total_keys = ['calories', 'protein', 'carbs', 'fat']
    if not all(key in meal_plan['totals'] for key in total_keys):
        return False
    
    return True

def format_foods_for_ai(menu_data):
    """Format menu data for AI prompt - prioritize real meals"""
    
    proteins = []
    carbs = []
    other_foods = []
    
    for hall in menu_data.get('dining_halls', []):
        hall_name = hall['name']
        
        for meal_period, period_data in hall.get('meal_periods', {}).items():
            items = period_data.get('items', [])
            for item in items:
                nutrition = item.get('nutrition', {})
                calories = nutrition.get('calories', 0)
                
                if calories < 50:  # Skip condiments and low-cal items
                    continue
                    
                name_lower = item['name'].lower()
                food_line = (f"{item['name']} ({hall_name}, {meal_period.title()}) - "
                           f"Cal: {calories}, P: {nutrition.get('protein', 0)}g, "
                           f"C: {nutrition.get('carbs', 0)}g, F: {nutrition.get('fat', 0)}g")
                
                # Skip cereals, milk, juice completely
                if any(word in name_lower for word in ['cereal', 'milk', 'juice', 'dispenser']):
                    continue
                
                # Prioritize proteins
                if any(word in name_lower for word in ['chicken', 'beef', 'fish', 'wrap', 'sandwich', 'panini', 'burger', 'egg']):
                    proteins.append(food_line)
                # Then substantial carbs
                elif any(word in name_lower for word in ['bagel', 'bread', 'rice', 'pasta', 'potato']):
                    carbs.append(food_line)
                else:
                    other_foods.append(food_line)
    
    # Put proteins first, limit total to fit in AI context
    all_foods = proteins[:80] + carbs[:40] + other_foods[:30]  # 150 total
    return '\n'.join(all_foods)

def create_fallback_meal_plan(menu_data, target_calories):
    """Simple fallback meal plan if AI fails"""
    breakfast_items = []
    lunch_items = []
    dinner_items = []
    
    for hall in menu_data.get('dining_halls', []):
        for meal_period, period_data in hall.get('meal_periods', {}).items():
            items = period_data.get('items', [])
            for item in items[:3]:  # Take more items for better variety
                nutrition = item.get('nutrition', {})
                if nutrition.get('calories', 0) > 0:
                    food_item = {
                        "item": item['name'],
                        "dining_hall": hall['name'],
                        "calories": nutrition.get('calories', 0),
                        "protein": nutrition.get('protein', 0),
                        "carbs": nutrition.get('carbs', 0),
                        "fat": nutrition.get('fat', 0)
                    }
                    
                    if 'breakfast' in meal_period.lower():
                        breakfast_items.append(food_item)
                    elif 'lunch' in meal_period.lower():
                        lunch_items.append(food_item)
                    elif 'dinner' in meal_period.lower():
                        dinner_items.append(food_item)
    
    # Select items to approximate target calories
    selected_breakfast = breakfast_items[:2] if breakfast_items else []
    selected_lunch = lunch_items[:2] if lunch_items else []
    selected_dinner = dinner_items[:2] if dinner_items else []
    
    all_items = selected_breakfast + selected_lunch + selected_dinner
    total_calories = sum(item['calories'] for item in all_items)
    total_protein = sum(item['protein'] for item in all_items)
    total_carbs = sum(item['carbs'] for item in all_items)
    total_fat = sum(item['fat'] for item in all_items)
    
    return {
        "meal_plan": {
            "breakfast": selected_breakfast,
            "lunch": selected_lunch,
            "dinner": selected_dinner,
            "snacks": []
        },
        "totals": {
            "calories": int(total_calories),
            "protein": round(total_protein, 1),
            "carbs": round(total_carbs, 1),
            "fat": round(total_fat, 1)
        },
        "notes": "Basic meal plan using available VT dining options. AI meal planning temporarily unavailable."
    }

def generate_quick_suggestions(message, menu_data):
    """Generate quick food suggestions based on user input"""
    message_lower = message.lower()
    suggestions = []
    
    # Find relevant foods based on keywords
    for hall in menu_data.get('dining_halls', []):
        for meal_period, period_data in hall.get('meal_periods', {}).items():
            items = period_data.get('items', [])
            for item in items:
                item_name_lower = item['name'].lower()
                nutrition = item.get('nutrition', {})
                
                # Enhanced keyword matching
                if any(keyword in message_lower for keyword in ['protein', 'workout', 'gym', 'muscle']):
                    if nutrition.get('protein', 0) > 15:
                        suggestions.append(f"💪 {item['name']} at {hall['name']} - {nutrition.get('protein', 0)}g protein")
                
                elif any(keyword in message_lower for keyword in ['quick', 'fast', 'rush', 'hurry']):
                    if any(fast_food in item_name_lower for fast_food in ['cereal', 'bagel', 'coffee', 'juice', 'muffin']):
                        suggestions.append(f"⚡ Quick option: {item['name']} at {hall['name']}")
                
                elif any(keyword in message_lower for keyword in ['healthy', 'light', 'diet', 'low cal']):
                    if nutrition.get('calories', 0) < 300 and nutrition.get('calories', 0) > 50:
                        suggestions.append(f"🥗 Healthy: {item['name']} at {hall['name']} - {nutrition.get('calories', 0)} cal")
                
                elif any(keyword in message_lower for keyword in ['sweet', 'dessert', 'sugar']):
                    if any(sweet in item_name_lower for sweet in ['cookie', 'cake', 'pie', 'ice cream', 'fruit']):
                        suggestions.append(f"🍪 Sweet treat: {item['name']} at {hall['name']}")
    
    # Remove duplicates and limit
    suggestions = list(dict.fromkeys(suggestions))[:5]
    
    if not suggestions:
        suggestions = ["🍽️ Check out today's specials at your nearest VT dining hall!"]
    
    return suggestions

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Load initial data
    load_menu_data()
    
    # Start background scheduler
    start_scheduler()
    
    logger.info("Starting VT Nutrition API...")
    logger.info("Visit http://localhost:5001/api/health to check status")
    
    # Run Flask app
    app.run(debug=True, port=5002, host='0.0.0.0')