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
    # meal on a given day
    name: str
    time: Optional[str] = None
    items: list[FoodItem]
    meal_calories: float = 0
    meal_protein: float = 0
    meal_carbs: float = 0
    meal_fat: float = 0

    def compute_totals(self):
        self.meal_calories = 0
        self.meal_protein = 0
        self.meal_carbs = 0
        self.meal_fat = 0
        for item in self.items:
            for nutri in ['calories', 'protein', 'carbs', 'fat']:
                curr = getattr(self, f'meal_{nutri}')
                item_nutri = getattr(item, nutri)
                if item_nutri is not None:
                    setattr(self, f'meal_{nutri}', curr + item_nutri)


class DailyLog(BaseModel):
    # log for a given day
    date: str
    meals: list[Meal]
    total_calories: float = 0
    total_protein: float = 0
    total_carbs: float = 0
    total_fat: float = 0

    # Method to calculate the total nutritional values for the day.
    def compute_totals(self):
        self.total_calories = 0
        self.total_protein = 0
        self.total_carbs = 0
        self.total_fat = 0
        for meal in self.meals:
            meal.compute_totals()
            for nutri in ['calories', 'protein', 'carbs', 'fat']:
                curr = getattr(self, f'total_{nutri}')
                setattr(self, f'total_{nutri}', curr + getattr(meal, f'meal_{nutri}'))

        logger.info(f'Computed totals for {self.date}.')


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
