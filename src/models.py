from typing import Optional

from pydantic import BaseModel, field_validator


# FoodItem model represents a single food item in the logs with its nutritional details.
class FoodItem(BaseModel):
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


# Meal model represents a collection of FoodItems consumed at a specific time.
class Meal(BaseModel):
    name: str  # The name of the meal (e.g., "Breakfast", "Lunch", "Snack").
    time: Optional[str] = None  # The time the meal was consumed (e.g., "08:00").
    items: list[FoodItem]  # A list of FoodItem objects included in this meal.


# DailyLog model represents all meals and their nutritional totals for a specific date.
class DailyLog(BaseModel):
    date: str  # The date for which the log is recorded (e.g., "2023-10-27").
    meals: list[Meal]  # A list of Meal objects for that day.
    # Sum of calories from all food items in all meals for the day.v
    total_calories: float = 0
    # Sum of protein from all food items in all meals for the day.
    total_protein: float = 0
    # Sum of carbohydrates from all food items in all meals for the day.
    total_carbs: float = 0
    # Sum of fat from all food items in all meals for the day.
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
    user: str  # The name or ID of the user.
    logs: list[DailyLog]  # A list of DailyLog objects for the user.


# FoodEntry model defines the expected structure of data when a user adds a new food item.
class FoodEntry(BaseModel):
    date: str  # The date for the new entry.
    meal: str  # The meal type for the new entry (e.g., "breakfast").
    # The name of the food item. Field(alias="food-name") maps incoming JSON field "food-name" to Python attribute "food_name".
    food_name: str
    weight: Optional[float] = None  # Optional weight in grams.
    quantity: Optional[int] = None  # Optional quantity.
    calories: Optional[float] = None  # Optional direct calorie input.


class FoodInfo(BaseModel):
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float


FoodCache = dict[str, FoodInfo]
