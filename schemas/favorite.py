from pydantic import BaseModel
from models.favorites import ProductType
from datetime import datetime

class FavoriteCreate(BaseModel):
    product_type: ProductType
    product_id: str

class FavoriteOut(BaseModel):
    id: int
    user_id: str
    product_type: ProductType
    product_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class FavoriteProductOut(BaseModel):
    favorite_id: int
    product_type: ProductType
    product_id: str
    name: str
    price: float
    stock: int

    class Config:
        from_attributes = True