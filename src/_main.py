import json
import logging
import os
import re  # Import the regex module
from pathlib import Path

import ipdb
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.models import DailyLog, FoodItem, Meal, NewFoodEntry, UserLog

# Configure logging to write informational messages and above to 'app.log'.
# 'filemode='a'' appends to the log file if it exists, otherwise creates it.
# 'format' defines the structure of log messages.
logging.basicConfig(
    level=logging.INFO,
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
)

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')


# USDA API KEY
API_KEY = open('data/usda_database_api_key.txt').read().strip()


# --- Persistent Food Cache ---
FOOD_CACHE_PATH = Path('data/food_cache.json')
FOOD_LOG_PATH = Path('data/food_log.json')


def load_food_cache() -> dict:
    """Loads the food cache from a JSON file."""
    if not os.path.exists(FOOD_CACHE_PATH):
        FOOD_CACHE_PATH.touch()
        return {}
    with open(FOOD_CACHE_PATH, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            logging.error(
                f'Could not decode {FOOD_CACHE_PATH}, starting with an empty cache.'
            )
            return {}


def save_food_cache() -> None:
    """Saves the food cache to a JSON file."""
    with open(FOOD_CACHE_PATH, 'w') as f:
        json.dump(food_cache, f, indent=4)


# Load the cache at startup.
food_cache = load_food_cache()


# Helper function to safely extract a numeric nutrient value from a dictionary.
# It handles cases where the value might be missing, not a number, or a string with units.
def get_numeric_nutrient(nutriments, key):
    value = nutriments.get(key)
    if value is None:
        return None
    try:
        # Attempt to convert the value directly to a float.
        return float(value)
    except ValueError:
        # If direct conversion fails, check if it's a string that contains a number.
        if isinstance(value, str):
            # Use regex to extract the leading number from a string, optionally followed by units like 'kcal' or 'g'.
            match = re.match(r'(\d+(\.\d+)?)\s*(?:kcal|g)', value)
            if match:
                # If a number is found, convert it to a float.
                return float(match.group(1))
        # If no numeric value can be extracted, return None.
        return None


def get_usda_food_info(query: str, api_key: str = API_KEY) -> list:
    """
    queries the usda food database and returns all results

    params:
        query: string naming the food (e.g. 'greek yogurt')
        api_key: api key for USDA database

    returns:
        food: list of all matches for the query.
    """
    url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    foods = []
    if 'yogurt' in query:
        ipdb.set_trace()

    # get results in order of source
    for datatype in ['Foundation', 'SR Legacy', 'Survey (FNDDS)', 'Branded']:
        params = {
            'query': query,
            'dataType': datatype,
            'api_key': api_key,
            'pageSize': 5,
        }
        results = []
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            results = response.json()['foods']
        except requests.exceptions.RequestException as e:
            logging.error(f'Request error: could not fetch data for {query}: {e}')
        # Log any JSON decoding errors.
        except json.JSONDecodeError as e:
            logging.error(f'Error decoding JSON for {query}: {e}')

        foods.extend(results)

    if not foods:
        logging.error(f'No match found for query {query}.')
    return foods


def get_best_match(foods: list) -> dict:
    """
    takes the query results and extracts the most likely
    food

    searches in order through the Foundation, SR Legacy, Survey (FNDDS),
    and Branded categories
    """
    return foods[0]


def extract_macros(food: dict) -> dict[str, float]:
    # get nutrient info
    nutrient_data = food['foodNutrients']
    # map nutrient names to indices in nutrient_data
    nutrient_indices = {n['nutrientName']: id for id, n in enumerate(nutrient_data)}

    # get calories
    calories_per_100g = None
    if 'Energy (Atwater General Factors)' in nutrient_indices:
        id = nutrient_indices['Energy (Atwater General Factors)']
        calories_per_100g = nutrient_data[id]['value']
    elif 'Energy' in nutrient_indices:
        id = nutrient_indices['Energy']
        calories_per_100g = nutrient_data[id]['value']
    assert calories_per_100g is not None, 'No data for calories'

    # get protein
    protein_per_100g = None
    if 'Protein' in nutrient_indices:
        id = nutrient_indices['Protein']
        protein_per_100g = nutrient_data[id]['value']
    assert protein_per_100g is not None, 'No data for protein.'

    # get carbs
    carbs_per_100g = None
    if 'Carbohydrate, by difference' in nutrient_indices:
        id = nutrient_indices['Carbohydrate, by difference']
        carbs_per_100g = nutrient_data[id]['value']
    assert carbs_per_100g is not None, 'No data for carbs.'

    # get fat
    fat_per_100g = None
    if 'Total lipid (fat)' in nutrient_indices:
        id = nutrient_indices['Total lipid (fat)']
        fat_per_100g = nutrient_data[id]['value']
    assert fat_per_100g is not None, 'No data for fat.'

    return {
        'calories_per_100g': calories_per_100g,
        'protein_per_100g': protein_per_100g,
        'carbs_per_100g': carbs_per_100g,
        'fat_per_100g': fat_per_100g,
    }


def compute_nutrients(item: FoodItem, cached_info: dict) -> FoodItem:
    if item.weight is not None:
        if (
            'calories_per_100g' in cached_info
            and cached_info['calories_per_100g'] is not None
        ):
            item.calories = (cached_info['calories_per_100g'] / 100) * item.weight
        if (
            'protein_per_100g' in cached_info
            and cached_info['protein_per_100g'] is not None
        ):
            item.protein = (cached_info['protein_per_100g'] / 100) * item.weight
        if (
            'carbs_per_100g' in cached_info
            and cached_info['carbs_per_100g'] is not None
        ):
            item.carbs = (cached_info['carbs_per_100g'] / 100) * item.weight
        if 'fat_per_100g' in cached_info and cached_info['fat_per_100g'] is not None:
            item.fat = (cached_info['fat_per_100g'] / 100) * item.weight
        return item
    else:
        logging.error(f'No weight information for {item.name}.')
        return item


# Function to populate a FoodItem with calorie and macronutrient information.
# for now, assume the only input is weight; if food not in cache, fetch info from USDA
def get_food_info(item: FoodItem, fetch_from_api: bool = True):
    """
    Populates the food item with calorie and macronutrient information.
    """
    # If item not in cache, cache it.
    if item.name not in food_cache and not fetch_from_api:
        logging.warning(f"Food item '{item.name}' not in cache and API fetch disabled.")
        return item

    if item.name not in food_cache:
        usda_data = get_usda_food_info(item.name)
        macro_data = extract_macros(usda_data)
        food_cache[item.name] = macro_data
        save_food_cache()

    cached_info = food_cache[item.name]

    item = compute_nutrients(item, cached_info)
    return item


# API endpoint to retrieve all user logs.
@app.get('/logs', response_model=UserLog)
def read_logs():
    # Open and load the calorie log data from a JSON file.
    with open(FOOD_LOG_PATH) as f:
        data = json.load(f)
    # Validate the loaded data against the UserLog Pydantic model.
    user_log = UserLog(**data)
    # Iterate through each daily log.
    for log in user_log.logs:
        # Iterate through each meal in the daily log.
        for meal in log.meals:
            # Iterate through each food item in the meal.
            for item in meal.items:
                # Populate food item with nutritional info (from cache or API).
                item = get_food_info(item, fetch_from_api=True)
        # Calculate total calories and macronutrients for the day.
        log.calculate_totals()
    # Return the complete user log with updated nutritional information.
    return user_log


# API endpoint to retrieve a specific daily log by date.
@app.get('/logs/{date}', response_model=DailyLog)
def read_log(date: str):
    # Open and load the calorie log data from a JSON file.
    with open(FOOD_LOG_PATH) as f:
        data = json.load(f)
    # Validate the loaded data against the UserLog Pydantic model.
    user_log = UserLog(**data)
    # Iterate through each daily log to find the matching date.
    for log in user_log.logs:
        if log.date == date:
            # If a match is found, populate food items and calculate totals for that day.
            for meal in log.meals:
                for item in meal.items:
                    get_food_info(item, fetch_from_api=True)
            log.calculate_totals()
            # Return the specific daily log.
            return log
    # If no log is found for the given date, raise an HTTP 404 Not Found error.
    raise HTTPException(status_code=404, detail='Log not found')


# API endpoint to add a new food entry to the logs.
@app.post('/logs')
def add_log(entry: NewFoodEntry):
    # Log the received new food entry for debugging purposes.
    logging.info(f'Received new food entry: {entry.model_dump_json(indent=2)}')
    try:
        # Open the calorie log file in read and write mode.
        with open(FOOD_LOG_PATH, 'r+') as f:
            # Load existing data.
            data = json.load(f)
            # Validate existing data against the UserLog Pydantic model.
            user_log = UserLog(**data)

            # Find the daily log for the entry's date.
            log_for_date = None
            for log in user_log.logs:
                if log.date == entry.date:
                    log_for_date = log
                    break

            # If no log exists for the date, create a new one and add it to the user's logs.
            if not log_for_date:
                log_for_date = DailyLog(date=entry.date, meals=[])
                user_log.logs.append(log_for_date)

            # Find the meal within the daily log for the entry's meal name.
            meal_for_name = None
            for meal in log_for_date.meals:
                if meal.name == entry.meal:
                    meal_for_name = meal
                    break

            # If no meal exists for the name, create a new one and add it to the daily log's meals.
            if not meal_for_name:
                meal_for_name = Meal(name=entry.meal, items=[])
                log_for_date.meals.append(meal_for_name)

            # Create a new FoodItem from the entry data.
            food_item = FoodItem(
                name=entry.food_name,
                weight=entry.weight,
                cal=entry.calories,
                quantity=entry.quantity,
            )
            # Populate food item with nutritional info (from cache or API).
            get_food_info(food_item, fetch_from_api=True)
            # Add the new food item to the appropriate meal.
            meal_for_name.items.append(food_item)

            # Move the file pointer to the beginning to overwrite the file.
            f.seek(0)
            # Write the updated user log data (as JSON) back to the file, formatted with 4-space indentation.
            f.write(user_log.model_dump_json(indent=4))
            # Truncate the file to remove any remaining old content if the new content is shorter.
            f.truncate()

        # Return a success message.
        return {'message': 'Entry added successfully'}
    except Exception as e:
        # Log any errors that occur during the process.
        logging.error(f'Error adding entry: {e}')
        # Raise an HTTP 500 Internal Server Error if an unexpected error occurs.
        raise HTTPException(status_code=500, detail=str(e))


# API endpoint for the root URL, serving the main HTML page.
@app.get('/')
async def read_index():
    # Return the 'index.html' file as the response.
    return FileResponse('static/index.html')


@app.get('/')
async def read_root():
    return FileResponse('static/index.html')
