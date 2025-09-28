import json
import os
from dotenv import load_dotenv

load_dotenv()

print("=== VT Dining Chatbot Debug ===\n")

# Check environment variables
print("1. Environment Variables:")
print(f"   OpenAI API Key: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Missing'}")
print(f"   Admin API Key: {'✅ Set' if os.getenv('ADMIN_API_KEY') else '❌ Missing'}")
print(f"   OpenAI Key Format: {'✅ Correct' if os.getenv('OPENAI_API_KEY', '').startswith('sk-') else '❌ Wrong format'}")
print()

# Check scraped data
print("2. Scraped Data Analysis:")
try:
    with open('vt_dining_data.json', 'r') as f:
        data = json.load(f)
    
    print(f"   Data file exists: ✅")
    print(f"   Last updated: {data.get('last_updated', 'Unknown')}")
    print(f"   Dining halls found: {len(data.get('dining_halls', []))}")
    
    total_items = 0
    items_with_nutrition = 0
    
    for hall in data.get('dining_halls', []):
        print(f"\n   📍 {hall['name']}:")
        print(f"      Status: {hall.get('scrape_status', 'unknown')}")
        
        for meal_period, meal_data in hall.get('meal_periods', {}).items():
            items = meal_data.get('items', [])
            items_with_nutr = sum(1 for item in items if item.get('nutrition', {}).get('calories', 0) > 0)
            
            print(f"      {meal_period}: {len(items)} items, {items_with_nutr} with nutrition")
            total_items += len(items)
            items_with_nutrition += items_with_nutr
            
            # Show sample items
            for item in items[:2]:  # Show first 2 items
                nutrition = item.get('nutrition', {})
                print(f"        • {item['name']}: {nutrition.get('calories', 0)} cal, {nutrition.get('protein', 0)}g protein")
    
    print(f"\n   Summary:")
    print(f"   Total items scraped: {total_items}")
    print(f"   Items with nutrition data: {items_with_nutrition}")
    print(f"   Success rate: {(items_with_nutrition/total_items*100) if total_items > 0 else 0:.1f}%")

except FileNotFoundError:
    print("   ❌ vt_dining_data.json not found - run scraper.py first")
except Exception as e:
    print(f"   ❌ Error reading data: {e}")

print()

# Test OpenAI connection
print("3. OpenAI Connection Test:")
try:
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5,
        timeout=10
    )
    print("   ✅ OpenAI connection successful")
    print(f"   Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"   ❌ OpenAI error: {e}")

print()

# Check if AI would have data to work with
print("4. AI Data Availability:")
if total_items > 0 and items_with_nutrition > 0:
    print(f"   ✅ Sufficient data for AI ({items_with_nutrition} items with nutrition)")
else:
    print(f"   ❌ Insufficient data for AI (only {items_with_nutrition} items with nutrition)")
    print("   Recommendation: Re-run scraper or check VT website availability")

print("\n=== Debug Complete ===")