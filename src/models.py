from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# FoodItem model represents a single food item with its nutritional details.
class FoodItem(BaseModel):
    name: str  # The name of the food item (e.g., "Apple", "Chicken Breast").
    weight: Optional[float] = (
        None  # The weight of the food item in grams, if applicable.
    )
    cal: Optional[float] = None  # Direct calorie input, if provided by the user.
    quantity: Optional[int] = (
        None  # The quantity of the food item (e.g., 1 apple, 2 slices).
    )
    calories: Optional[float] = None  # Calculated total calories for the item.
    protein: Optional[float] = None  # Calculated total protein in grams for the item.
    carbs: Optional[float] = (
        None  # Calculated total carbohydrates in grams for the item.
    )
    fat: Optional[float] = None  # Calculated total fat in grams for the item.

    @field_validator('name', mode='before')
    @classmethod
    def standardize_name(cls, v: str) -> str:
        return v.lower()


# Meal model represents a collection of FoodItems consumed at a specific time.
class Meal(BaseModel):
    name: str  # The name of the meal (e.g., "Breakfast", "Lunch", "Snack").
    time: Optional[str] = None  # The time the meal was consumed (e.g., "08:00").
    items: List[FoodItem]  # A list of FoodItem objects included in this meal.


# DailyLog model represents all meals and their nutritional totals for a specific date.
class DailyLog(BaseModel):
    date: str  # The date for which the log is recorded (e.g., "2023-10-27").
    meals: List[Meal]  # A list of Meal objects for that day.
    total_calories: float = (
        0  # Sum of calories from all food items in all meals for the day.
    )
    total_protein: float = (
        0  # Sum of protein from all food items in all meals for the day.
    )
    total_carbs: float = (
        0  # Sum of carbohydrates from all food items in all meals for the day.
    )
    total_fat: float = 0  # Sum of fat from all food items in all meals for the day.

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
    logs: List[DailyLog]  # A list of DailyLog objects for the user.


# NewFoodEntry model defines the expected structure of data when a user adds a new food item.
class NewFoodEntry(BaseModel):
    date: str  # The date for the new entry.
    meal: str  # The meal type for the new entry (e.g., "breakfast").
    # The name of the food item. Field(alias="food-name") maps incoming JSON field "food-name" to Python attribute "food_name".
    food_name: str = Field(alias='food-name')
    weight: Optional[float] = None  # Optional weight in grams.
    quantity: Optional[int] = None  # Optional quantity.
    calories: Optional[float] = None  # Optional direct calorie input.
