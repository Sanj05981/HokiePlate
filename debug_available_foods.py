import json

# Load the menu data (same as your app does)
with open('vt_dining_data.json', 'r') as f:
    menu_data = json.load(f)

# Copy your exact format_foods_for_ai function here
def format_foods_for_ai(menu_data):
    """Format menu data for AI prompt"""
    formatted = []
    
    for hall in menu_data.get('dining_halls', []):
        hall_name = hall['name']
        
        for meal_period, period_data in hall.get('meal_periods', {}).items():
            items = period_data.get('items', [])
            for item in items:
                nutrition = item.get('nutrition', {})
                if nutrition.get('calories'):
                    formatted.append(
                        f"{item['name']} ({hall_name}, {meal_period.title()}) - "
                        f"Cal: {nutrition.get('calories', 0)}, "
                        f"P: {nutrition.get('protein', 0)}g, "
                        f"C: {nutrition.get('carbs', 0)}g, "
                        f"F: {nutrition.get('fat', 0)}g"
                    )
    
    return '\n'.join(formatted[:150])  # Your current limit

# Test the function
available_foods = format_foods_for_ai(menu_data)

print("=== WHAT THE AI ACTUALLY SEES ===")
print(f"Total foods sent to AI: {len(available_foods.split(chr(10)))}")
print(f"Character count: {len(available_foods)}")
print("\nFirst 30 food items:")
print("-" * 80)

for i, line in enumerate(available_foods.split('\n')[:30]):
    if line.strip():
        print(f"{i+1:2}. {line}")

print("-" * 80)

# Analyze content
food_lines = available_foods.split('\n')
cereal_count = sum(1 for line in food_lines if 'cereal' in line.lower())
chicken_count = sum(1 for line in food_lines if 'chicken' in line.lower())
wrap_count = sum(1 for line in food_lines if 'wrap' in line.lower())

print(f"\nCONTENT ANALYSIS:")
print(f"Cereals in first 150 items: {cereal_count}")
print(f"Chicken dishes in first 150 items: {chicken_count}")
print(f"Wraps in first 150 items: {wrap_count}")

if cereal_count > chicken_count:
    print("❌ PROBLEM: More cereals than chicken dishes!")
    print("This is why AI is choosing cereal for meals.")
else:
    print("✅ GOOD: More real protein dishes than cereals.")

# Show first occurrence of good foods
print(f"\nFIRST GOOD FOODS FOUND:")
for i, line in enumerate(food_lines):
    if any(word in line.lower() for word in ['chicken', 'wrap', 'sandwich', 'panini']) and i < 50:
        print(f"  Position {i+1}: {line}")
        break
else:
    print("  ❌ No chicken/wraps/sandwiches in first 50 items!")