import logging
from typing import Optional

from pydantic import BaseModel, field_validator

logger = logging.getLogger('uvicorn')


class FoodItem(BaseModel):
    # food instance for a given meal in logs
    name: str
    weight: Optional[float] = None
    quantity: Optional[int] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    data_id: str

    @field_validator('name', mode='before')
    @classmethod
    def standardize_name(cls, v: str) -> str:
        return v.lower()


class Meal(BaseModel):
    name: str  # The name of the meal (e.g., "Breakfast", "Lunch", "Snack").
    time: Optional[str] = None  # The time the meal was consumed (e.g., "08:00").
    items: list[FoodItem]  # A list of FoodItem objects included in this meal.


class DailyLog(BaseModel):
    # log for a given day
    date: str
    meals: list[Meal]
    total_calories: float = 0
    total_protein: float = 0
    total_carbs: float = 0
    total_fat: float = 0

    # Method to calculate the total nutritional values for the day.
    def calculate_totals(self):
        # Sums up calories from all items across all meals, ignoring None values.
        self.total_calories = sum(
            item.calories
            for meal in self.meals
            for item in meal.items
            if item.calories is not None
        )
        # Sums up protein from all items across all meals, ignoring None values.
        self.total_protein = sum(
            item.protein
            for meal in self.meals
            for item in meal.items
            if item.protein is not None
        )
        # Sums up carbohydrates from all items across all meals, ignoring None values.
        self.total_carbs = sum(
            item.carbs
            for meal in self.meals
            for item in meal.items
            if item.carbs is not None
        )
        # Sums up fat from all items across all meals, ignoring None values.
        self.total_fat = sum(
            item.fat
            for meal in self.meals
            for item in meal.items
            if item.fat is not None
        )


# UserLog model represents the entire collection of daily logs for a user.
class UserLog(BaseModel):
    # all daily logs
    user: str  # The name or ID of the user.
    logs: list[DailyLog]  # A list of DailyLog objects for the user.


class FoodEntry(BaseModel):
    # data structure for form entry
    date: str
    meal: str
    food_name: str
    weight: Optional[float] = None
    quantity: Optional[int] = None
    calories: Optional[float] = None


class FoodInfo(BaseModel):
    # data structure for USDA API response and cache
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float


FoodCache = dict[str, FoodInfo]
