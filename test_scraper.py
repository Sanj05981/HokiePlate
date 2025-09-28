#!/usr/bin/env python3
"""
Test script for VT dining scraper
Run this to test if the scraper is working before running the full app
"""

from scraper import VTDiningScraper
import json

def test_scraper():
    print("=== VT Dining Scraper Test ===\n")
    
    scraper = VTDiningScraper()
    
    print("1. Testing dining hall discovery...")
    dining_halls = scraper.discover_dining_halls()
    
    if dining_halls:
        print(f"✓ Found {len(dining_halls)} dining halls:")
        for hall in dining_halls:
            print(f"  - {hall['name']} (Location: {hall['location_num']})")
    else:
        print("✗ No dining halls found, using fallback list")
        dining_halls = scraper.get_fallback_dining_halls()
    
    print(f"\n2. Testing meal periods for {dining_halls[0]['name']}...")
    test_hall = dining_halls[0]
    meal_data = scraper.get_meal_periods_and_categories(test_hall['url'])
    
    if meal_data:
        print(f"✓ Found meal periods: {list(meal_data.keys())}")
        
        # Show sample items from each meal
        for meal_period, items in meal_data.items():
            print(f"  {meal_period.title()}: {len(items)} items")
            if items:
                print(f"    Sample: {items[0]['name']}")
        
        # Test getting nutrition for one item
        first_meal = list(meal_data.values())[0]
        if first_meal:
            test_item = first_meal[0]
            print(f"\n3. Testing nutrition for: {test_item['name']}")
            nutrition = scraper.get_nutrition_from_item_page(test_item['url'])
            
            if nutrition:
                print(f"✓ Found nutrition data: {nutrition}")
            else:
                print("⚠ No nutrition data found")
        else:
            print("✗ No items found in meal period")
    else:
        print("✗ No meal periods found")
    
    print("\n=== Test Complete ===")

def quick_scrape_test():
    """Quick test that only scrapes one item"""
    print("=== Quick Scrape Test ===\n")
    
    scraper = VTDiningScraper()
    
    # Use fallback dining hall
    dining_halls = scraper.get_fallback_dining_halls()
    test_hall = dining_halls[0]  # D2 at Dietrick Hall
    
    print(f"Testing {test_hall['name']}")
    print(f"URL: {test_hall['url']}")
    
    # Manual test - try to access the page
    try:
        import requests
        response = requests.get(test_hall['url'])
        print(f"✓ Page accessible (Status: {response.status_code})")
        
        # Look for common elements
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check if we can find any links
        links = soup.find_all('a')
        print(f"✓ Found {len(links)} links on page")
        
        # Look for meal-related text
        page_text = soup.get_text().lower()
        meals_found = []
        for meal in ['breakfast', 'lunch', 'dinner']:
            if meal in page_text:
                meals_found.append(meal)
        
        if meals_found:
            print(f"✓ Found meal periods: {meals_found}")
        else:
            print("⚠ No meal periods found in text")
        
        # Save the HTML for manual inspection
        with open('test_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("✓ Saved page HTML to 'test_page.html' for inspection")
        
    except Exception as e:
        print(f"✗ Error accessing page: {e}")

def test_small_scrape():
    """Test scraping just a few items"""
    print("=== Small Scrape Test ===\n")
    
    scraper = VTDiningScraper()
    
    print("Running limited scrape (2 dining halls, 3 items per meal)...")
    data = scraper.scrape_all_data()
    
    if data and data.get('dining_halls'):
        print(f"✓ Successfully scraped {len(data['dining_halls'])} dining halls")
        
        for hall in data['dining_halls']:
            print(f"\n{hall['name']}:")
            for meal_period, meal_data in hall.get('meal_periods', {}).items():
                items = meal_data.get('items', [])
                print(f"  {meal_period.title()}: {len(items)} items")
                
                for item in items:
                    nutrition = item.get('nutrition', {})
                    calories = nutrition.get('calories', 'N/A')
                    protein = nutrition.get('protein', 'N/A')
                    print(f"    - {item['name']}: {calories} cal, {protein}g protein")
    else:
        print("✗ Scraping failed")

if __name__ == "__main__":
    print("Choose test type:")
    print("1. Quick test (just check if page is accessible)")
    print("2. Full scraper test")
    print("3. Small scrape test (actually get nutrition data)")
    
    choice = input("Enter 1, 2, or 3: ").strip()
    
    if choice == "1":
        quick_scrape_test()
    elif choice == "2":
        test_scraper()
    elif choice == "3":
        test_small_scrape()
    else:
        print("Invalid choice, running quick test...")
        quick_scrape_test()