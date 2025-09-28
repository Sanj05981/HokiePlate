import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import re
import logging
from typing import Dict, List, Optional
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VTDiningScraper:
    def __init__(self, max_items_per_meal: int = None):
        self.base_url = "https://foodpro.students.vt.edu"
        self.menu_base = "https://foodpro.students.vt.edu/menus"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        
        # Configurable limits
        self.max_items_per_meal = max_items_per_meal or int(os.getenv('MAX_ITEMS_PER_MEAL', '10'))
        self.request_delay = float(os.getenv('SCRAPER_DELAY', '1.0'))
        
        # Known dining halls and their location numbers
        self.dining_halls = {}
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 2
    
    def make_request(self, url: str, retries: int = None) -> Optional[requests.Response]:
        """Make HTTP request with retry logic"""
        if retries is None:
            retries = self.max_retries
            
        for attempt in range(retries + 1):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"All retry attempts failed for {url}")
                    return None
    
    def discover_dining_halls(self) -> List[Dict]:
        """Discover all dining halls from the main menu page"""
        try:
            logger.info("Discovering dining halls...")
            response = self.make_request(f"{self.menu_base}/")
            
            if not response:
                logger.error("Failed to fetch main menu page")
                return self.get_fallback_dining_halls()
            
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
            
            logger.info(f"Discovered {len(dining_halls)} dining halls")
            return dining_halls if dining_halls else self.get_fallback_dining_halls()
            
        except Exception as e:
            logger.error(f"Error discovering dining halls: {e}")
            return self.get_fallback_dining_halls()
    
    def get_fallback_dining_halls(self) -> List[Dict]:
        """Updated fallback list based on actual VT dining halls"""
        logger.info("Using fallback dining halls list")
        return [
            {'name': 'D2 at Dietrick Hall', 'location_num': '15', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=15&naFlag=1'},
            {'name': 'Food Court / Hokie Grill at Owens', 'location_num': '09', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=09&naFlag=1'},
            {'name': 'Turner Place at Lavery Hall', 'location_num': '14', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=14&naFlag=1'},
            {'name': 'West End at Cochrane Hall', 'location_num': '16', 'url': f'{self.base_url}/menus/MenuAtLocation.aspx?locationNum=16&naFlag=1'},
        ]
    
    def get_meal_periods_and_categories(self, dining_hall_url: str) -> Dict:
        """Get breakfast, lunch, dinner and their food items for a dining hall"""
        try:
            logger.info(f"Scraping meal periods from {dining_hall_url}")
            response = self.make_request(dining_hall_url)
            
            if not response:
                logger.error(f"Failed to fetch dining hall page: {dining_hall_url}")
                return {}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            meal_data = {}
            
            # Look for food items with nutrition label links
            food_links = soup.find_all('a', href=re.compile(r'label\.aspx'))
            
            logger.info(f"Found {len(food_links)} food items with nutrition labels")
            
            for link in food_links:
                item_name = link.get_text(strip=True)
                item_url = link.get('href')
                
                if not item_name:
                    continue
                
                # Find the recipe identifier
                recipe_div = self.find_recipe_identifier(link)
                
                if recipe_div:
                    recipe_text = recipe_div.get_text(strip=True)
                    logger.debug(f"Found recipe: {recipe_text} for item: {item_name}")
                    
                    # Extract meal period from recipe identifier
                    meal_period = self.extract_meal_period(recipe_text)
                    
                    if meal_period:
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
                    logger.debug(f"No recipe identifier found for: {item_name}")
            
            # Log meal period summary
            for period, items in meal_data.items():
                logger.info(f"  {period}: {len(items)} items")
            
            return meal_data
            
        except Exception as e:
            logger.error(f"Error getting meal periods: {e}")
            return {}
    
    def find_recipe_identifier(self, link) -> Optional[BeautifulSoup]:
        """Find recipe identifier div near the food item link"""
        current_element = link
        
        # Search through next siblings and their children for recipe identifier
        for _ in range(10):  # Limit search to avoid infinite loops
            current_element = current_element.find_next()
            if not current_element:
                break
            
            if (current_element.name == 'div' and 
                'report_recipe_identifier' in current_element.get('class', [])):
                return current_element
        
        return None
    
    def extract_meal_period(self, recipe_text: str) -> Optional[str]:
        """Extract meal period from recipe identifier text"""
        if '*' in recipe_text:
            parts = recipe_text.split('*')
            if len(parts) >= 4:
                meal_period = parts[-1].lower().strip()
                # Normalize meal period names
                meal_period_map = {
                    'breakfast': 'breakfast',
                    'lunch': 'lunch', 
                    'dinner': 'dinner',
                    'brunch': 'brunch',
                    'late night': 'late_night'
                }
                return meal_period_map.get(meal_period, meal_period)
        return None
    
    def get_nutrition_from_item_page(self, item_url: str) -> Dict:
        """Get detailed nutrition info from label.aspx page"""
        try:
            response = self.make_request(item_url)
            
            if not response:
                logger.warning(f"Failed to fetch nutrition page: {item_url}")
                return {}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            nutrition = {}
            
            # Get page text for pattern matching
            page_text = soup.get_text()
            
            # Enhanced nutrition label patterns
            patterns = {
                'calories': [
                    r'calories?\s*[:\-]?\s*(\d+)',
                    r'(\d+)\s*calories?',
                    r'cal[:\-]?\s*(\d+)'
                ],
                'protein': [
                    r'protein\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'(\d+\.?\d*)\s*g\s*protein',
                    r'prot[:\-]?\s*(\d+\.?\d*)\s*g'
                ],
                'carbs': [
                    r'(?:total\s+)?carbohydrate\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'carbs?\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'(\d+\.?\d*)\s*g\s*carb'
                ],
                'fat': [
                    r'(?:total\s+)?fat\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'(\d+\.?\d*)\s*g\s*fat',
                    r'fat[:\-]?\s*(\d+\.?\d*)\s*g'
                ],
                'fiber': [
                    r'dietary\s+fiber\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'fiber\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'(\d+\.?\d*)\s*g\s*fiber'
                ],
                'sodium': [
                    r'sodium\s*[:\-]?\s*(\d+\.?\d*)\s*mg',
                    r'(\d+\.?\d*)\s*mg\s*sodium',
                    r'salt\s*[:\-]?\s*(\d+\.?\d*)\s*mg'
                ],
                'sugars': [
                    r'(?:total\s+)?sugars?\s*[:\-]?\s*(\d+\.?\d*)\s*g',
                    r'(\d+\.?\d*)\s*g\s*sugar',
                    r'sugar[:\-]?\s*(\d+\.?\d*)\s*g'
                ]
            }
            
            # Try multiple patterns for each nutrient
            for nutrient, pattern_list in patterns.items():
                for pattern in pattern_list:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        try:
                            value = float(match.group(1))
                            if nutrient == 'calories':
                                nutrition[nutrient] = int(value)
                            else:
                                nutrition[nutrient] = round(value, 1)
                            break  # Stop trying patterns once we find a match
                        except (ValueError, IndexError):
                            continue
            
            # Look for allergen/dietary information
            allergens = self.extract_allergens(soup)
            nutrition['allergens'] = allergens
            nutrition['dietary_tags'] = self.extract_dietary_tags(allergens, soup)
            
            # Add serving size if available
            serving_size = self.extract_serving_size(page_text)
            if serving_size:
                nutrition['serving_size'] = serving_size
            
            return nutrition
            
        except Exception as e:
            logger.error(f"Error getting nutrition from {item_url}: {e}")
            return {}
    
    def extract_serving_size(self, page_text: str) -> Optional[str]:
        """Extract serving size information"""
        serving_patterns = [
            r'serving\s*size\s*[:\-]?\s*([^,\n]+)',
            r'portion\s*[:\-]?\s*([^,\n]+)',
            r'size\s*[:\-]?\s*(\d+\.?\d*\s*(?:oz|g|ml|cup|piece))'
        ]
        
        for pattern in serving_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def extract_allergens(self, soup: BeautifulSoup) -> List[str]:
        """Extract allergen information from food item page"""
        allergens = []
        
        # Look for allergen section
        allergen_section = soup.find('div', class_=re.compile(r'allergen', re.I))
        if allergen_section:
            allergen_text = allergen_section.get_text()
            allergens.extend(self.parse_allergen_text(allergen_text))
        else:
            # Look for allergen info in the full page text
            page_text = soup.get_text().lower()
            
            # Look for "contains:" section
            if 'contains:' in page_text:
                contains_section = page_text.split('contains:')[1].split('.')[0]
                allergens.extend(self.parse_allergen_text(contains_section))
            
            # Look for "allergens:" section
            if 'allergens:' in page_text:
                allergen_section = page_text.split('allergens:')[1].split('.')[0]
                allergens.extend(self.parse_allergen_text(allergen_section))
        
        return list(set(allergens))  # Remove duplicates
    
    def parse_allergen_text(self, text: str) -> List[str]:
        """Parse allergen text and identify common allergens"""
        allergens = []
        text_lower = text.lower()
        
        # Common allergens mapping
        allergen_keywords = {
            'milk': ['milk', 'dairy', 'lactose'],
            'eggs': ['egg', 'eggs'],
            'fish': ['fish'],
            'shellfish': ['shellfish', 'shrimp', 'crab', 'lobster'],
            'tree_nuts': ['tree nuts', 'almonds', 'walnuts', 'pecans', 'cashews'],
            'peanuts': ['peanuts', 'peanut'],
            'wheat': ['wheat', 'gluten'],
            'soybeans': ['soy', 'soybeans', 'soybean']
        }
        
        for allergen, keywords in allergen_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                allergens.append(allergen)
        
        return allergens
    
    def extract_dietary_tags(self, allergens: List[str], soup: BeautifulSoup = None) -> List[str]:
        """Convert allergen info and other indicators to dietary tags"""
        tags = []
        allergen_list = [a.lower() for a in allergens]
        
        # Check for common dietary restrictions based on allergens
        if 'milk' not in allergen_list and 'eggs' not in allergen_list:
            # Could be vegan, but need to check for other animal products
            if not any(animal in allergen_list for animal in ['fish', 'shellfish']):
                tags.append('potentially_vegan')
        
        if 'milk' not in allergen_list:
            tags.append('dairy_free')
        
        if 'wheat' not in allergen_list:
            tags.append('gluten_free')
        
        if 'peanuts' not in allergen_list and 'tree_nuts' not in allergen_list:
            tags.append('nut_free')
        
        # Look for explicit dietary labels on the page
        if soup:
            page_text = soup.get_text().lower()
            dietary_indicators = {
                'vegetarian': ['vegetarian', 'veggie'],
                'vegan': ['vegan'],
                'halal': ['halal'],
                'kosher': ['kosher'],
                'organic': ['organic'],
                'low_sodium': ['low sodium', 'reduced sodium'],
                'whole_grain': ['whole grain', 'whole wheat']
            }
            
            for tag, indicators in dietary_indicators.items():
                if any(indicator in page_text for indicator in indicators):
                    tags.append(tag)
        
        return list(set(tags))  # Remove duplicates
    
    def scrape_all_data(self) -> Dict:
        """Main method to scrape all dining hall data"""
        logger.info("Starting VT FoodPro dining data scrape...")
        all_data = {
            'last_updated': datetime.now().isoformat(),
            'dining_halls': [],
            'scraper_config': {
                'max_items_per_meal': self.max_items_per_meal,
                'request_delay': self.request_delay
            }
        }
        
        # Discover dining halls
        dining_halls = self.discover_dining_halls()
        logger.info(f"Found {len(dining_halls)} dining halls")
        
        successful_halls = 0
        total_items_scraped = 0
        
        for hall in dining_halls:
            logger.info(f"\nScraping {hall['name']}...")
            hall_data = {
                'name': hall['name'],
                'location_num': hall['location_num'],
                'url': hall['url'],
                'meal_periods': {},
                'scrape_status': 'pending'
            }
            
            try:
                # Get meal periods and their food items
                meal_data = self.get_meal_periods_and_categories(hall['url'])
                
                hall_items_count = 0
                for meal_period, items in meal_data.items():
                    logger.info(f"  {meal_period.title()}: {len(items)} items found")
                    
                    # Limit items per meal period
                    limited_items = items[:self.max_items_per_meal]
                    items_with_nutrition = []
                    
                    for i, item in enumerate(limited_items):
                        logger.info(f"    Getting nutrition for: {item['name']} ({i+1}/{len(limited_items)})")
                        nutrition = self.get_nutrition_from_item_page(item['url'])
                        item['nutrition'] = nutrition
                        items_with_nutrition.append(item)
                        hall_items_count += 1
                        total_items_scraped += 1
                        
                        # Respectful delay between requests
                        time.sleep(self.request_delay)
                    
                    hall_data['meal_periods'][meal_period] = {
                        'items': items_with_nutrition,
                        'total_available': len(items),
                        'scraped_count': len(items_with_nutrition)
                    }
                
                hall_data['scrape_status'] = 'completed'
                hall_data['items_scraped'] = hall_items_count
                successful_halls += 1
                
            except Exception as e:
                logger.error(f"Error scraping {hall['name']}: {e}")
                hall_data['scrape_status'] = 'failed'
                hall_data['error'] = str(e)
            
            all_data['dining_halls'].append(hall_data)
        
        # Add summary statistics
        all_data['scrape_summary'] = {
            'total_halls': len(dining_halls),
            'successful_halls': successful_halls,
            'failed_halls': len(dining_halls) - successful_halls,
            'total_items_scraped': total_items_scraped,
            'scrape_duration': (datetime.now() - datetime.fromisoformat(all_data['last_updated'])).total_seconds()
        }
        
        # Save to JSON file
        try:
            with open('vt_dining_data.json', 'w') as f:
                json.dump(all_data, f, indent=2)
            logger.info(f"Data saved to vt_dining_data.json")
        except Exception as e:
            logger.error(f"Error saving data to file: {e}")
        
        logger.info(f"\nScraping complete!")
        logger.info(f"Successfully scraped {successful_halls}/{len(dining_halls)} dining halls")
        logger.info(f"Total items with nutrition data: {total_items_scraped}")
        
        return all_data
    
    def quick_test(self) -> bool:
        """Quick test to check if scraper is working"""
        logger.info("Running quick test...")
        
        try:
            # Get one dining hall
            dining_halls = self.get_fallback_dining_halls()
            test_hall = dining_halls[0]
            
            logger.info(f"Testing with: {test_hall['name']}")
            logger.info(f"URL: {test_hall['url']}")
            
            # Test basic connectivity
            response = self.make_request(test_hall['url'])
            if not response:
                logger.error("Failed to connect to dining hall page")
                return False
            
            # Try to get meal periods
            meal_data = self.get_meal_periods_and_categories(test_hall['url'])
            logger.info(f"Found meal periods: {list(meal_data.keys())}")
            
            if meal_data:
                # Test nutrition extraction on one item
                first_meal = list(meal_data.values())[0]
                if first_meal:
                    test_item = first_meal[0]
                    logger.info(f"Testing nutrition extraction for: {test_item['name']}")
                    
                    nutrition = self.get_nutrition_from_item_page(test_item['url'])
                    logger.info(f"Nutrition data: {nutrition}")
                    
                    if nutrition:
                        logger.info("✓ Quick test passed!")
                        return True
            
            logger.warning("Test completed but no nutrition data found")
            return False
            
        except Exception as e:
            logger.error(f"Quick test failed: {e}")
            return False

# Test the scraper
if __name__ == "__main__":
    # Configure from environment or use defaults
    max_items = int(os.getenv('MAX_ITEMS_PER_MEAL', '5'))  # Reduced for testing
    
    scraper = VTDiningScraper(max_items_per_meal=max_items)
    
    # Run quick test first
    if scraper.quick_test():
        logger.info("Quick test passed, running full scrape...")
        data = scraper.scrape_all_data()
        logger.info(f"Scraping completed. Check vt_dining_data.json for results.")
    else:
        logger.error("Quick test failed. Please check your internet connection and try again.")