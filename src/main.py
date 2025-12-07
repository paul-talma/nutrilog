import json
import logging
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from src.models import (
    DailyLog,
    FoodCache,
    FoodEntry,
    FoodInfo,
    FoodItem,
    Meal,
    UserLog,
)

logger = logging.getLogger('uvicorn')

FOOD_CACHE_PATH = Path('data/food_cache.json')
FOOD_LOG_PATH = Path('data/food_log.json')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup.

    Initializes the food cache, loads API keys from environment variables,
    and processes existing user log data to calculate nutritional values.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    # Startup: load cache once when server starts
    global food_cache
    food_cache = get_food_cache()
    load_dotenv()
    global API_KEY
    API_KEY = os.environ['USDA_API_KEY']
    global API_URL
    API_URL = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    global NUTRIENTS
    NUTRIENTS = {
        'calories': 1008,
        'energy_atwater_general': 2047,
        'energy_atwater_specific': 2048,
        'protein': 1003,
        'carbs': 1005,
        'fat': 1004,
    }
    initialize_user_log()
    yield


app = FastAPI(lifespan=lifespan)
app.mount('/static', StaticFiles(directory='static'), name='static')


def get_food_cache() -> FoodCache:
    """Loads the food cache from a JSON file.

    Returns:
        FoodCache: A dictionary-like object mapping food names to their nutritional info.
    """
    try:
        with open(FOOD_CACHE_PATH) as f:
            cache_dict = json.load(f)
            return {
                name: FoodInfo.model_validate(data) for name, data in cache_dict.items()
            }
    except (FileNotFoundError, json.JSONDecodeError, ValidationError):
        logger.warning('Invalid food cache. Starting with an empty cache.')
        return {}


def update_food_cache(name: str, food_info: FoodInfo):
    """Adds or updates an entry in the in-memory food cache.

    Args:
        name (str): The name of the food item.
        food_info (FoodInfo): The nutritional information for the food item.
    """
    food_cache[name] = food_info
    logger.info(f'Added {name} to cache.')


def write_food_cache():
    """Persists the current in-memory food cache to a JSON file."""
    dict_cache = convert_cache_to_dict()
    with tempfile.NamedTemporaryFile(
        'w', dir=FOOD_CACHE_PATH.parent, delete=False
    ) as f:
        f.write(json.dumps(dict_cache, indent=2))
        temp_path = f.name
    os.replace(temp_path, FOOD_CACHE_PATH)


def convert_cache_to_dict():
    """Converts the FoodCache object to a dictionary for JSON serialization.

    Returns:
        dict: The food cache as a dictionary.
    """
    dict_cache = {k: v.model_dump() for k, v in food_cache.items()}
    return dict_cache


def migrate_log_data(log_data: dict) -> dict:
    """Migrates old log data by adding unique `data_id` to food items if missing.

    Args:
        log_data (dict): The raw log data loaded from the JSON file.

    Returns:
        dict: The migrated log data with `data_id` fields ensured.
    """
    if 'logs' in log_data:
        for day in log_data['logs']:
            if 'meals' in day:
                for meal in day['meals']:
                    if 'items' in meal:
                        for item in meal['items']:
                            if 'data_id' not in item or not item['data_id']:
                                item['data_id'] = str(uuid.uuid4())
                            for k in item:
                                if not item[k]:
                                    item[k] = 0
    return log_data


def get_user_log() -> UserLog:
    """Loads the user's food log from a JSON file.

    Performs data migration if necessary and validates the data against the UserLog model.
    If the file is not found, corrupted, or invalid, an empty log is returned and initialized.

    Returns:
        UserLog: The user's food log.
    """
    try:
        with open(FOOD_LOG_PATH) as f:
            log_data = json.load(f)
        log_data = migrate_log_data(log_data)
        user_log = UserLog.model_validate(log_data)
        write_user_log(user_log)
        return user_log
    except FileNotFoundError as e:
        logger.warning(f'No log file found at {e}.')
        logger.info('Starting with empty log.')
    except json.JSONDecodeError as e:
        logger.warning(f'Could not decode log: {e}.')
        logger.info('Starting with empty log.')
    except ValidationError as e:
        logger.warning(f'Invalid user logs: {e}')
        logger.info('Starting with empty log.')
    user_log = UserLog(user='Paul', logs=[])
    write_user_log(user_log)
    return user_log


def make_generic_user_log():
    """Creates a new, empty user log file at the specified FOOD_LOG_PATH."""
    data = {
        'user': 'Paul',
        'logs': [],
    }
    FOOD_LOG_PATH.touch()
    with open(FOOD_LOG_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def write_user_log(user_log: UserLog):
    """Writes the current UserLog object to a JSON file.

    Args:
        user_log (UserLog): The user log object to write.
    """
    with tempfile.NamedTemporaryFile('w', dir=FOOD_LOG_PATH.parent, delete=False) as f:
        f.write(user_log.model_dump_json(indent=2))
        temp_path = f.name
    os.replace(temp_path, FOOD_LOG_PATH)
    logger.info('Saved user log.')


def initialize_user_log():
    """Initializes the user log by populating nutritional information for existing entries.

    Retrieves food information for each item from the cache or API,
    calculates macros, and computes daily totals for all logs.
    """
    user_log = get_user_log()
    for day in user_log.logs:
        for meal in day.meals:
            for item in meal.items:
                if not item.weight and not item.quantity:
                    item.calories = item.protein = item.carbs = item.fat = None
                    continue
                try:
                    item_info = get_food_info(item.name)
                    add_info(item, item_info)
                except HTTPException as e:
                    logger.warning(e.detail)
                    item.calories = item.protein = item.carbs = item.fat = None
        day.compute_totals()
    write_user_log(user_log)


@app.get('/')
async def read_root():
    """Serves the main HTML page for the application.

    Returns:
        FileResponse: The 'index.html' file from the static directory.
    """
    return FileResponse('static/index.html')


@app.post('/logs/new_entry')
async def new_entry(entry: FoodEntry):
    """Adds a new food entry to the user's log.

    Retrieves nutritional information for the food item, adds it to the
    appropriate meal and daily log, and then persists the updated log.

    Args:
        entry (FoodEntry): The food entry data submitted by the user.

    Returns:
        dict: A confirmation message.
    """
    logger.info(f'Received new food entry: {entry.model_dump_json(indent=2)}')

    entry_id = str(uuid.uuid4())
    # get user, day, meal, and food_item
    user_log = get_user_log()
    daily_log = get_daily_log(date=entry.date, logs=user_log.logs)
    meal = get_meal_for_day(entry.meal, daily_log.meals)
    food_item = FoodItem(name=entry.food_name, data_id=entry_id, weight=entry.weight)

    try:
        food_info = get_food_info(food_item.name)
    except HTTPException as e:
        logger.warning(e.detail)
        raise HTTPException(status_code=404, detail=e.detail)

    add_info(food_item, food_info)
    meal.items.append(food_item)
    daily_log.compute_totals()
    write_user_log(user_log)

    return {'message': f'entry {entry} added successfully!'}


def get_meal_for_day(meal_name: str, meals: list[Meal]) -> Meal:
    """Retrieves a meal object for a given meal name from a list of meals.

    If the meal does not exist, a new Meal object is created and added to the list.

    Args:
        meal_name (str): The name of the meal (e.g., 'breakfast', 'lunch').
        meals (list[Meal]): A list of Meal objects for a specific day.

    Returns:
        Meal: The found or newly created Meal object.
    """
    for meal in meals:
        if meal.name == meal_name:
            return meal
    meal = Meal(name=meal_name, items=[])
    meals.append(meal)
    return meal


def get_daily_log(date: str, logs: list[DailyLog]) -> DailyLog:
    """Retrieves a DailyLog object for a given date from a list of daily logs.

    If the log for the specified date does not exist, a new DailyLog object
    is created and added to the list.

    Args:
        date (str): The date in 'YYYY-MM-DD' format.
        logs (list[DailyLog]): A list of DailyLog objects.

    Returns:
        DailyLog: The found or newly created DailyLog object.
    """
    for log in logs:
        if log.date == date:
            return log
    log = DailyLog(date=date, meals=[])
    logs.append(log)
    return log


def add_info(item: FoodItem, food_info: FoodInfo):
    """Calculates and assigns nutritional values to a FoodItem.

    Based on the item's weight and the provided FoodInfo, it computes
    calories, protein, carbs, and fat.

    Args:
        item (FoodItem): The food item to update.
        food_info (FoodInfo): The nutritional information per 100g.
    """
    # TODO: handle quantity instead of weight
    if item.weight is not None:
        factor = item.weight / 100
        item.calories = food_info.calories_per_100g * factor
        item.protein = food_info.protein_per_100g * factor
        item.carbs = food_info.carbs_per_100g * factor
        item.fat = food_info.fat_per_100g * factor
        return
    item.calories = item.protein = item.carbs = item.fat = None


def get_food_info(name: str) -> FoodInfo:
    """Retrieves nutritional information for a food item.

    First checks the in-memory cache, then queries the external API if not found.
    Results from the API are cached for future use.

    Args:
        name (str): The name of the food item.

    Returns:
        FoodInfo: The nutritional information for the food item.
    """
    food_info = food_cache.get(name, None)
    if food_info:
        logger.info(f'Fetched info for {name} from cache.')
    else:
        logger.info(f'Querying API for {name}.')
        food_info = get_food_info_from_api(name)
        update_food_cache(name, food_info)
        write_food_cache()
    return food_info


def get_food_info_from_api(query: str) -> FoodInfo:
    """Fetches food nutritional information from the USDA API.

    Args:
        query (str): The search query for the food item.

    Returns:
        FoodInfo: The processed nutritional information.

    Raises:
        HTTPException: If no nutrition data is found for the query.
    """
    api_response = query_api(query)
    if not api_response:
        raise HTTPException(
            status_code=404,
            detail=f'No nutrition data found for {query}. Check spelling or try another description.',
        )

    food_info = convert_api_response_to_FoodInfo(api_response)
    return food_info


def query_api(query: str):
    """Queries the USDA FoodData Central API for food items.

    Searches across different data types (Foundation, SR Legacy, Survey, Branded)
    and aggregates the results.

    Args:
        query (str): The search term for food items.

    Returns:
        list[dict]: A list of dictionaries, each representing a food item from the API.
    """
    foods = []
    for datatype in ['Foundation', 'SR Legacy', 'Survey (FNDDS)', 'Branded']:
        params = {
            'query': query,
            'dataType': datatype,
            'api_key': API_KEY,
            'pageSize': 5,
        }
        results = []
        try:
            response = requests.get(API_URL, params=params)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            results = response.json()['foods']
        except requests.exceptions.RequestException as e:
            logger.error(f'Request error: could not fetch data for {query}: {e}')
        # Log any JSON decoding errors.
        except json.JSONDecodeError as e:
            logger.error(f'Error decoding JSON for {query}: {e}')

        foods.extend(results)

    return foods


def convert_api_response_to_FoodInfo(food_info_list: list[dict]) -> FoodInfo:
    """Converts a raw API response list of food information into a structured FoodInfo object.

    Args:
        food_info_list (list[dict]): A list of food dictionaries from the API response.

    Returns:
        FoodInfo: A Pydantic model containing the extracted nutritional information.
    """
    # TODO: better sort through options
    food_info = food_info_list[0]
    nutrients = food_info['foodNutrients']
    # values = {
    #     f'{nutrient_name}_per_100g': get_nutrient(nutrient_id, nutrients)
    #     for nutrient_name, nutrient_id in NUTRIENTS.items()
    # }
    values = {
        'calories_per_100g': get_calories_from_nutrients(nutrients),
        'protein_per_100g': get_protein_from_nutrients(nutrients),
        'carbs_per_100g': get_carbs_from_nutrients(nutrients),
        'fat_per_100g': get_fat_from_nutrients(nutrients),
    }
    return FoodInfo(**values)


# TODO: abstract get_X_from_nutrients into this
def get_nutrient(nutrient_id: int, nutrients: dict) -> float:
    """Extracts a specific nutrient value from a list of nutrient dictionaries.

    Args:
        nutrient_id (int): The ID of the nutrient to retrieve.
        nutrients (dict): A dictionary containing nutrient information.

    Returns:
        float: The value of the requested nutrient.

    Raises:
        ValueError: If the specified nutrient ID is not found.
    """
    for n in nutrients:
        if n['nutrientId'] == nutrient_id:
            return float(n['value'])
    raise ValueError(f'No {nutrient_id} value found.')


def get_calories_from_nutrients(nutrients: dict) -> float:
    """Extracts calorie information from a list of nutrients.

    Checks for specific calorie nutrient IDs (calories, energy_atwater_specific, energy_atwater_general).

    Args:
        nutrients (dict): A dictionary containing nutrient information.

    Returns:
        float: The calorie value, or 0 if not found.
    """
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == NUTRIENTS['calories']:
            return float(n['value'])
        elif n['nutrientId'] == NUTRIENTS['energy_atwater_specific']:
            return float(n['value'])
        elif n['nutrientId'] == NUTRIENTS['energy_atwater_general']:
            return float(n['value'])
    logger.warning('No energy calue found.')
    return 0


def get_protein_from_nutrients(nutrients: dict) -> float:
    """Extracts protein information from a list of nutrients.

    Args:
        nutrients (dict): A dictionary containing nutrient information.

    Returns:
        float: The protein value, or 0 if not found.
    """
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == 1003:
            return float(n['value'])
    logger.warning('No protein value found.')
    return 0


def get_carbs_from_nutrients(nutrients: dict) -> float:
    """Extracts carbohydrate information from a list of nutrients.

    Args:
        nutrients (dict): A dictionary containing nutrient information.

    Returns:
        float: The carbohydrate value, or 0 if not found.
    """
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == 1005:
            return float(n['value'])
    logger.warning('No carbs value found.')
    return 0


def get_fat_from_nutrients(nutrients: dict) -> float:
    """Extracts fat information from a list of nutrients.

    Args:
        nutrients (dict): A dictionary containing nutrient information.

    Returns:
        float: The fat value, or 0 if not found.
    """
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == 1004:
            return float(n['value'])
    logger.warning('No fat value found.')
    return 0


@app.get('/logs/today')
async def get_today_logs():
    """Retrieves the daily log for the current date.

    Returns:
        DailyLog: The DailyLog object for today, or None if no entries exist.
    """
    day = str(date.today())
    logger.info(f'Fetching daily panel data for {day}.')

    user_log = get_user_log()
    for log in user_log.logs:
        if log.date == day:
            logger.info('Found daily log')
            return log
    logger.info('No daily log found')
    return None


@app.get('/logs/all')
async def get_all_logs():
    """Retrieves all historical daily logs for the user.

    Computes and updates the total nutritional values for each daily log before returning.

    Returns:
        list[DailyLog]: A list of all DailyLog objects.
    """
    logger.info('Fetching all logs.')
    user_log = get_user_log()
    daily_logs = user_log.logs
    for day in daily_logs:
        day.compute_totals()
    return daily_logs


@app.delete('/logs/delete_entry/{data_id}')
async def delete_entry(data_id: str):
    """Deletes a specific food entry from the user's log.

    Identifies the food item by its unique `data_id`, removes it from the log,
    recomputes daily totals, and persists the updated log.

    Args:
        data_id (str): The unique identifier of the food item to delete.
    """
    logger.info(f'Removing item #{data_id} from the logs.')
    user_log = get_user_log()
    for day in user_log.logs:
        for meal in day.meals:
            for item in meal.items:
                if item.data_id == data_id:
                    meal.items.remove(item)
                    day.compute_totals()
                    write_user_log(user_log)
                    return
