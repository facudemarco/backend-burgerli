from sqlalchemy import Column, Integer, String, Enum, UniqueConstraint, TIMESTAMP, text
from enum import Enum as PyEnum
from Database.getConnection import Base

class ProductType(str, PyEnum):
    burger = "burger"
    drink = "drink"
    fries = "fries"
    combo = "combo"       

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False)
    product_type = Column(Enum(ProductType), nullable=False)
    product_id = Column(String(36), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("user_id", "product_type", "product_id", name="uniq_user_product"),
    )
