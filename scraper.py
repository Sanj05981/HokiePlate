import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import re

class VTDiningScraper:
    def __init__(self):
        self.base_url = "https://foodpro.students.vt.edu"
        self.menu_base = "https://foodpro.students.vt.edu/menus"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        
        # Known dining halls and their location numbers (we'll discover these)
        self.dining_halls = {}
    
    def discover_dining_halls(self):
        """Discover all dining halls from the main menu page"""
        try:
            # Get the main menu page
            response = self.session.get(f"{self.menu_base}/")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            dining_halls = []
            
            # Look for dining hall buttons with MenuAtLocation.aspx links
            hall_links = soup.find_all('a', href=re.compile(r'MenuAtLocation\.aspx\?locationNum='))
            
            for link in hall_links:
                href = link.get('href')
                title = link.get('title', '').strip()
                
                if title and href:
                    # Extract location number
                    location_match = re.search(r'locationNum=([^&]+)', href)
                    if location_match:
                        location_num = location_match.group(1)
                        full_url = f"{self.base_url}/menus/{href}"
                        
                        dining_halls.append({
                            'name': title,
                            'location_num': location_num,
                            'url': full_url
                        })
            
            return dining_halls
            
        except Exception as e:
            print(f"Error discovering dining halls: {e}")
            return self.get_fallback_dining_halls()
    
    def get_fallback_dining_halls(self):
        """Updated fallback list based on actual VT dining halls"""
        return [
            {'name': 'D2 at Dietrick Hall', 'location_num': '15', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=15&naFlag=1'},
            {'name': 'Food Court / Hokie Grill at Owens', 'location_num': '09', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=09&naFlag=1'},
            {'name': 'Turner Place at Lavery Hall', 'location_num': '14', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=14&naFlag=1'},
            {'name': 'West End at Cochrane Hall', 'location_num': '16', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=16&naFlag=1'},
        ]
    
    def get_meal_periods_and_categories(self, dining_hall_url):
        """Get breakfast, lunch, dinner and their food items for a dining hall"""
        try:
            response = self.session.get(dining_hall_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            meal_data = {}
            
            # Look for food items with nutrition label links
            food_links = soup.find_all('a', href=re.compile(r'label\.aspx'))
            
            print(f"Found {len(food_links)} food items with nutrition labels")
            
            for link in food_links:
                item_name = link.get_text(strip=True)
                item_url = link.get('href')
                
                if not item_name:
                    continue
                
                # Find the recipe identifier that should be near this link
                # Look for the next div with class "report_recipe_identifier"
                current_element = link
                recipe_div = None
                
                # Search through next siblings and their children for recipe identifier
                for _ in range(10):  # Limit search to avoid infinite loops
                    current_element = current_element.find_next()
                    if not current_element:
                        break
                    
                    if current_element.name == 'div' and 'report_recipe_identifier' in current_element.get('class', []):
                        recipe_div = current_element
                        break
                
                if recipe_div:
                    recipe_text = recipe_div.get_text(strip=True)
                    print(f"Found recipe: {recipe_text} for item: {item_name}")
                    
                    # Extract meal period from recipe identifier (format: recipeNum*portion*something*MealPeriod)
                    if '*' in recipe_text:
                        parts = recipe_text.split('*')
                        if len(parts) >= 4:
                            meal_period = parts[-1].lower()  # Last part should be meal period
                            
                            if meal_period not in meal_data:
                                meal_data[meal_period] = []
                            
                            # Create full URL for nutrition label
                            full_url = f"{self.base_url}/menus/{item_url}" if not item_url.startswith('http') else item_url
                            
                            meal_data[meal_period].append({
                                'name': item_name,
                                'url': full_url,
                                'recipe_id': recipe_text
                            })
                else:
                    print(f"No recipe identifier found for: {item_name}")
            
            print(f"Organized into meal periods: {list(meal_data.keys())}")
            for period, items in meal_data.items():
                print(f"  {period}: {len(items)} items")
            
            return meal_data
            
        except Exception as e:
            print(f"Error getting meal periods: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def get_food_items_from_category(self, category_url):
        """This method is now integrated into get_meal_periods_and_categories"""
        # Not needed since we get items directly from the dining hall page
        return []
    
    def get_nutrition_from_item_page(self, item_url):
        """Get detailed nutrition info from label.aspx page"""
        try:
            response = self.session.get(item_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            nutrition = {}
            
            # The label.aspx pages typically show nutrition facts in a structured format
            # Look for nutrition facts table or divs
            
            # Try to find nutrition values using common patterns
            page_text = soup.get_text()
            
            # Common nutrition label patterns
            patterns = {
                'calories': r'calories?\s*[:\-]?\s*(\d+)',
                'protein': r'protein\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                'carbs': r'(?:total\s+)?carbohydrate\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                'fat': r'(?:total\s+)?fat\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                'fiber': r'dietary\s+fiber\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                'sodium': r'sodium\s*[:\-]?\s*(\d+\.?\d*)\s*mg',
                'sugars': r'(?:total\s+)?sugars?\s*[:\-]?\s*(\d+\.?\d*)\s*g'
            }
            
            for nutrient, pattern in patterns.items():
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    if nutrient == 'calories':
                        nutrition[nutrient] = int(value)
                    else:
                        nutrition[nutrient] = value
            
            # Look for allergen/dietary information
            allergens = self.extract_allergens(soup)
            nutrition['allergens'] = allergens
            nutrition['dietary_tags'] = self.extract_dietary_tags(allergens, soup)
            
            return nutrition
            
        except Exception as e:
            print(f"Error getting nutrition from {item_url}: {e}")
            return {}
    
    def extract_allergens(self, soup):
        """Extract allergen information from food item page"""
        allergens = []
        
        # Look for allergen section
        allergen_section = soup.find('div', class_=re.compile(r'allergen', re.I))
        if allergen_section:
            allergen_text = allergen_section.get_text()
            # Common allergens to look for
            common_allergens = ['milk', 'eggs', 'fish', 'shellfish', 'tree nuts', 'peanuts', 'wheat', 'soybeans']
            
            for allergen in common_allergens:
                if allergen in allergen_text.lower():
                    allergens.append(allergen)
        else:
            # Look for allergen info in the full page text
            page_text = soup.get_text().lower()
            if 'contains:' in page_text:
                contains_section = page_text.split('contains:')[1].split('.')[0]
                common_allergens = ['milk', 'eggs', 'fish', 'shellfish', 'tree nuts', 'peanuts', 'wheat', 'soybeans']
                
                for allergen in common_allergens:
                    if allergen in contains_section:
                        allergens.append(allergen)
        
        return allergens
    
    def extract_dietary_tags(self, allergens, soup=None):
        """Convert allergen info and other indicators to dietary tags"""
        tags = []
        allergen_list = [a.lower() for a in allergens]
        
        # Check for common dietary restrictions
        if 'milk' not in allergen_list and 'eggs' not in allergen_list:
            tags.append('vegan')
        elif 'milk' not in allergen_list:
            tags.append('dairy-free')
        
        if 'wheat' not in allergen_list:
            tags.append('gluten-free')
        
        if soup:
            page_text = soup.get_text().lower()
            if 'vegetarian' in page_text:
                tags.append('vegetarian')
            if 'vegan' in page_text:
                tags.append('vegan')
            if 'halal' in page_text:
                tags.append('halal')
        
        return list(set(tags))  # Remove duplicates
    
    def scrape_all_data(self):
        """Main method to scrape all dining hall data"""
        print("Starting VT FoodPro dining data scrape...")
        all_data = {
            'last_updated': datetime.now().isoformat(),
            'dining_halls': []
        }
        
        # Discover dining halls
        dining_halls = self.discover_dining_halls()
        print(f"Found {len(dining_halls)} dining halls")
        
        # Just test with one dining hall for now
        for hall in dining_halls:  # Limit to first 2 for testing
            print(f"\nScraping {hall['name']}...")
            hall_data = {
                'name': hall['name'],
                'location_num': hall['location_num'],
                'url': hall['url'],
                'meal_periods': {}
            }
            
            # Get meal periods and their food items
            meal_data = self.get_meal_periods_and_categories(hall['url'])
            
            for meal_period, items in meal_data.items():
                print(f"  {meal_period.title()}: {len(items)} items")
                
                # Get nutrition for first few items only (for testing)
                items_with_nutrition = []
                for item in items:  # Limit to 3 items per meal for testing
                    print(f"    Getting nutrition for: {item['name']}")
                    nutrition = self.get_nutrition_from_item_page(item['url'])
                    item['nutrition'] = nutrition
                    items_with_nutrition.append(item)
                    time.sleep(1)  # Be respectful to server
                
                hall_data['meal_periods'][meal_period] = {
                    'items': items_with_nutrition
                }
            
            all_data['dining_halls'].append(hall_data)
        
        # Save to JSON file
        with open('vt_dining_data.json', 'w') as f:
            json.dump(all_data, f, indent=2)
        
        print(f"\nScraping complete! Data saved to vt_dining_data.json")
        return all_data
    
    def quick_test(self):
        """Quick test to check if scraper is working"""
        print("Running quick test...")
        
        # Get one dining hall
        dining_halls = self.get_fallback_dining_halls()
        test_hall = dining_halls[0]
        
        print(f"Testing with: {test_hall['name']}")
        print(f"URL: {test_hall['url']}")
        
        # Try to get meal periods
        meal_data = self.get_meal_periods_and_categories(test_hall['url'])
        print(f"Found meal periods: {list(meal_data.keys())}")
        
        if meal_data:
            # Test one category
            first_meal = list(meal_data.values())[0]
            if first_meal:
                test_category = first_meal[0]
                print(f"Testing category: {test_category['name']}")
                
                items = self.get_food_items_from_category(test_category['url'])
                print(f"Found {len(items)} items")
                
                if items:
                    print(f"Sample item: {items[0]}")
        
        return True

# Test the scraper
if __name__ == "__main__":
    scraper = VTDiningScraper()
    data = scraper.scrape_all_data()
    print(f"Scraped data for {len(data['dining_halls'])} dining halls")