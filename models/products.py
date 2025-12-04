from pydantic import BaseModel
from enum import Enum

class Burger(BaseModel):
    burger_id: str
    price: float
    stock: bool
    name: str
    size: str
    description: str
    ingredients: str

class Drink(BaseModel):
    drink_id: str
    name: str
    price: float
    stock: bool
    size: str

class Fries(BaseModel):
    fries_id: str
    name: str
    size: str
    description: str
    price: float
    stock: bool

class Combo(BaseModel):
    combo_id: str
    name: str
    quantity: int
    price: float
    burgers: str
    fries: str
    drinks: str