import json
from collections import defaultdict

# Load the scraped data
with open('vt_dining_data.json', 'r') as f:
    data = json.load(f)

print("=== Available Foods for AI Meal Planning ===\n")

# Categorize foods to see what's available
proteins = []
carbs = []
vegetables = []
fruits = []
dairy = []
cereals = []
other = []

for hall in data['dining_halls']:
    hall_name = hall['name']
    
    for meal_period, meal_data in hall.get('meal_periods', {}).items():
        items = meal_data.get('items', [])
        
        for item in items:
            name = item['name'].lower()
            nutrition = item.get('nutrition', {})
            
            if not nutrition.get('calories', 0):
                continue
                
            food_info = f"{item['name']} ({hall_name}) - {nutrition.get('calories', 0)}cal"
            
            # Categorize foods
            if any(word in name for word in ['chicken', 'beef', 'fish', 'turkey', 'pork', 'egg', 'tofu']):
                proteins.append(food_info)
            elif any(word in name for word in ['rice', 'pasta', 'bread', 'bagel', 'wrap', 'tortilla', 'noodle', 'potato']):
                carbs.append(food_info)
            elif any(word in name for word in ['lettuce', 'tomato', 'pepper', 'onion', 'broccoli', 'carrot', 'spinach', 'salad']):
                vegetables.append(food_info)
            elif any(word in name for word in ['apple', 'banana', 'orange', 'berry', 'fruit']):
                fruits.append(food_info)
            elif any(word in name for word in ['milk', 'cheese', 'yogurt', 'butter']):
                dairy.append(food_info)
            elif any(word in name for word in ['cereal', 'cornflakes', 'lucky charms', 'fruity pebbles']):
                cereals.append(food_info)
            else:
                other.append(food_info)

# Print categorized results
categories = [
    ("PROTEINS (Main Dishes)", proteins),
    ("CARBOHYDRATES (Rice/Pasta/Bread)", carbs),
    ("VEGETABLES", vegetables),
    ("FRUITS", fruits),
    ("DAIRY", dairy),
    ("CEREALS", cereals),
    ("OTHER ITEMS", other)
]

for category_name, items in categories:
    print(f"\n{category_name}: {len(items)} items")
    for item in items[:10]:  # Show first 10 items
        print(f"  • {item}")
    if len(items) > 10:
        print(f"  ... and {len(items) - 10} more")

print(f"\n=== SUMMARY ===")
print(f"Total food items with nutrition: {sum(len(items) for _, items in categories)}")
print(f"Proteins available: {len(proteins)}")
print(f"Carbs available: {len(carbs)}")
print(f"Vegetables available: {len(vegetables)}")
print(f"Cereals available: {len(cereals)}")

# Show what's being sent to AI
print(f"\n=== WHAT AI SEES (First 20 items) ===")
count = 0
for hall in data['dining_halls']:
    for meal_period, meal_data in hall.get('meal_periods', {}).items():
        items = meal_data.get('items', [])
        for item in items:
            nutrition = item.get('nutrition', {})
            if nutrition.get('calories') and count < 20:
                print(f"{item['name']} ({hall['name']}, {meal_period.title()}) - "
                      f"Cal: {nutrition.get('calories', 0)}, "
                      f"P: {nutrition.get('protein', 0)}g, "
                      f"C: {nutrition.get('carbs', 0)}g, "
                      f"F: {nutrition.get('fat', 0)}g")
                count += 1