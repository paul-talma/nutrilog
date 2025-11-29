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
from fastapi import FastAPI
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
    yield


app = FastAPI(lifespan=lifespan)
app.mount('/static', StaticFiles(directory='static'), name='static')


def get_food_cache() -> FoodCache:
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
    food_cache[name] = food_info
    logger.info(f'Added {name} to cache.')


def write_food_cache():
    dict_cache = convert_cache_to_dict()
    with tempfile.NamedTemporaryFile(
        'w', dir=FOOD_CACHE_PATH.parent, delete=False
    ) as f:
        f.write(json.dumps(dict_cache, indent=2))
        temp_path = f.name
    os.replace(temp_path, FOOD_CACHE_PATH)


def convert_cache_to_dict():
    dict_cache = {k: v.model_dump() for k, v in food_cache.items()}
    return dict_cache


def get_user_log() -> UserLog:
    try:
        with open(FOOD_LOG_PATH) as f:
            return UserLog.model_validate_json(f.read())
    except (FileNotFoundError, json.JSONDecodeError, ValidationError):
        logger.warning('Invalid user logs. Starting with a fresh log.')
        user_log = UserLog(user='Paul', logs=[])
        write_user_log(user_log)
        return user_log


def make_user_log():
    # TODO: generalize
    data = {
        'user': 'Paul',
        'logs': [],
    }
    FOOD_LOG_PATH.touch()
    with open(FOOD_LOG_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def write_user_log(user_log: UserLog):
    with tempfile.NamedTemporaryFile('w', dir=FOOD_LOG_PATH.parent, delete=False) as f:
        f.write(user_log.model_dump_json(indent=2))
        temp_path = f.name
    os.replace(temp_path, FOOD_LOG_PATH)


@app.get('/')
async def read_root():
    return FileResponse('static/index.html')


@app.post('/logs/new_entry')
async def new_entry(entry: FoodEntry):
    logger.info(f'Received new food entry: {entry.model_dump_json(indent=2)}')

    entry_id = str(uuid.uuid4())
    # get user, day, meal, and food_item
    user_log = get_user_log()
    daily_log = get_daily_log(date=entry.date, logs=user_log.logs)
    meal = get_meal_for_day(entry.meal, daily_log.meals)
    food_item = FoodItem(name=entry.food_name, data_id=entry_id)
    meal.items.append(food_item)

    food_item.weight = entry.weight
    add_info(food_item)

    daily_log.calculate_totals()
    write_user_log(user_log)

    return {'message': f'entry {entry} added successfully!'}


def get_meal_for_day(meal_name: str, meals: list[Meal]) -> Meal:
    for meal in meals:
        if meal.name == meal_name:
            return meal
    meals.append(Meal(name=meal_name, items=[]))
    return meals[-1]


def get_daily_log(date: str, logs: list[DailyLog]) -> DailyLog:
    for log in logs:
        if log.date == date:
            return log
    logs.append(DailyLog(date=date, meals=[]))
    return logs[-1]


def get_food_item(food_name: str) -> FoodItem:
    return FoodItem(name=food_name)


def add_info(item: FoodItem):
    food_info = get_food_info(item.name)
    assert item.weight is not None
    factor = item.weight / 100
    item.calories = food_info.calories_per_100g * factor
    item.protein = food_info.protein_per_100g * factor
    item.carbs = food_info.carbs_per_100g * factor
    item.fat = food_info.fat_per_100g * factor


def get_food_info(name: str) -> FoodInfo:
    food_info = food_cache.get(name, None)
    if food_info:
        logger.info(f'Fetched info for {name} from cache.')
    else:
        food_info = get_food_info_from_api(name)
        update_food_cache(name, food_info)
        write_food_cache()
    return food_info


def get_food_info_from_api(query: str) -> FoodInfo:
    api_response = food_info_from_api(query)
    food_info = convert_api_response_to_FoodInfo(api_response)
    return food_info


def food_info_from_api(query: str):
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

    return foods[0]


def convert_api_response_to_FoodInfo(food_info: dict) -> FoodInfo:
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


def get_nutrient(nutrient_id: int, nutrients: dict):
    for n in nutrients:
        if n['nutrientId'] == nutrient_id:
            return float(n['value'])
    raise ValueError(f'No {nutrient_id} value found.')


def get_calories_from_nutrients(nutrients: dict) -> float:
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == NUTRIENTS['calories']:
            return float(n['value'])
        elif n['nutrientId'] == NUTRIENTS['energy_atwater_specific']:
            return float(n['value'])
        elif n['nutrientId'] == NUTRIENTS['energy_atwater_general']:
            return float(n['value'])

    raise ValueError('No energy value found.')


def get_protein_from_nutrients(nutrients: dict) -> float:
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == 1003:
            return float(n['value'])
    raise ValueError('No protein value found.')


def get_carbs_from_nutrients(nutrients: dict) -> float:
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == 1005:
            return float(n['value'])
    raise ValueError('No carbs value found.')


def get_fat_from_nutrients(nutrients: dict) -> float:
    # TODO: validate
    for n in nutrients:
        if n['nutrientId'] == 1004:
            return float(n['value'])
    raise ValueError('No fat value found.')


@app.get('/logs/today')
async def get_today_logs():
    day = str(date.today())
    logger.info(f'Fetching daily panel data for {day}.')

    user_log = get_user_log()
    for log in user_log.logs:
        if log.date == day:
            logger.info('Found daily log')
            return log
    logger.info('No daily log found')
    return None


@app.delete('/logs/delete_entry/{data_id}')
async def delete_entry(data_id: str):
    logger.info(f'Removing item #{data_id} from the logs.')
    user_log = get_user_log()
    for day in user_log.logs:
        for meal in day.meals:
            for item in meal.items:
                if item.data_id == data_id:
                    meal.items.remove(item)
                    day.calculate_totals()
                    write_user_log(user_log)
                    return
