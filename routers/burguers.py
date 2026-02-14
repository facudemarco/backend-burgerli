from email.mime import image
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Form, Body, UploadFile, File
from pydantic import BaseModel, Field
import os
import shutil
from sqlalchemy import text
from Database.getConnection import engine
import uuid
import main
from models.users_client import UserCreate, UserUpdate, FavouriteCreate, FavouriteToggleRequest
from pathlib import Path

router = APIRouter()

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/home/iweb/burgerli/data/images"))
DOMAIN_URL = "https://burgerli.com.ar/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Burgerli/api/images"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(PROJECT_ROOT, "images")


class UpdateBurgerRequest(BaseModel):
    name : Optional[str] = None
    price : Optional[float] = None
    stock : Optional[bool] = None
    description : Optional[str] = None
    fries: Optional[str] = None
    main_image: Optional[str] = None
    size : Optional[List[str]] = None
    ingredients : Optional[List[str]] = None

class UpdateFriesRequest(BaseModel):
    name : Optional[str] = None
    stock : Optional[bool] = None
    size_list : Optional[List[str]] = None
    description_list : Optional[List[str]] = None
    price_list : Optional[List[float]] = Field(default_factory=list)
    main_image: Optional[str] = None

class UpdateDrinksRequest(BaseModel):
    name : Optional[str] = None
    price : Optional[float] = None
    stock : Optional[bool] = None
    size_list : Optional[List[str]] = None
    main_image: Optional[str] = None
    name : Optional[str] = None
    quantity : Optional[int] = None
    price : Optional[float] = None
    burgers : Optional[str] = None
    fries : Optional[str] = None
    drinks : Optional[str] = None

class UpdatePromoRequest(BaseModel):
    name : Optional[str] = None
    description : Optional[str] = None
    quantity : Optional[int] = None
    price : Optional[float] = None
    stock : Optional[bool] = None
    options : Optional[int] = None
    image: Optional[str] = None
    description_list : Optional[List[str]] = None

class ToggleProductStockRequest(BaseModel):
    has_stock: bool

class couponRequest(BaseModel):
    name : str
    amount : float
    type : Optional[str] = None
    tope : Optional[int] = None

class deliveryPriceRequest(BaseModel):
    price : float

@router.post("/burgers", tags=["Food"])
async def create_burger(
    price: str = Form(...),
    stock: bool = Form(...),
    name: str = Form(...),
    main_image: UploadFile = File(..., description="Main image"),
    size: List[str] = Form(default=[]),
    description: str = Form(...),
    ingredients: List[str] = Form(default=[]),
):
    burger_id = str(uuid.uuid4())

    normalized_size = []
    for d in size:
        if isinstance(d, str) and "," in d:
            normalized_size.extend([x.strip() for x in d.split(",") if x.strip()])
        elif d:
            normalized_size.append(d.strip())

    normalized_ingredients = []
    for d in ingredients:
        if isinstance(d, str) and "," in d:
            normalized_ingredients.extend([x.strip() for x in d.split(",") if x.strip()])
        elif d:
            normalized_ingredients.append(d.strip())

    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR, exist_ok=True)
    ext = os.path.splitext(main_image.filename or "file.jpg")[1]
    fname = f"{uuid.uuid4()}{ext}"
    path = os.path.join(IMAGES_DIR, fname)
    with open(path, "wb") as buf:
        shutil.copyfileobj(main_image.file, buf)
    url_main = f"{DOMAIN_URL}/{fname}"

    with engine.begin() as conn:
        # Burger
        conn.execute(
            text("""
                INSERT INTO burger (id_burger, name, price, stock, description)
                VALUES (:id, :name, :price, :stock, :description)
            """),
            {"id": burger_id, "name": name, "price": price, "stock": stock, "description": description},
        )

        conn.execute(
            text("""
                INSERT INTO burger_stock (id, burger_id, local_id, has_stock)
                SELECT UUID(), :burger_id, l.id, :has_stock
                FROM locals l
            """),
            {"burger_id": burger_id, "has_stock": stock},
        )
        
        # Sizes
        for s in normalized_size:
            conn.execute(
                text("INSERT INTO burger_size (id, burger_id, size) VALUES (:id, :burger_id, :size)"),
                {"id": str(uuid.uuid4()), "burger_id": burger_id, "size": s}
            )

        # Ingredients
        for ing in normalized_ingredients:
            conn.execute(
                text("INSERT INTO burger_ingredients (id, burger_id, ingredients) VALUES (:id, :burger_id, :ingredients)"),
                {"id": str(uuid.uuid4()), "burger_id": burger_id, "ingredients": ing}
            )

        # Main image
        conn.execute(
            text("INSERT INTO burger_main_imgs (id, burger_id, url) VALUES (:id, :burger_id, :url)"),
            {"id": str(uuid.uuid4()), "burger_id": burger_id, "url": url_main}
        )

    return {"message": "Burger created", "id": burger_id, "main_image_url": url_main}

@router.get("/burgers", tags=["Food"]) 
def get_burgers():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        b.id_burger,
                        b.name,
                        b.price,
                        b.stock,
                        b.description,
                        bmi.url AS main_image,
                        GROUP_CONCAT(DISTINCT bs.size) AS sizes,
                        GROUP_CONCAT(DISTINCT bi.ingredients) AS ingredients,
                        l.name AS local_name,
                        COALESCE(bst.has_stock, 1) AS local_stock
                    FROM burger b
                    LEFT JOIN burger_main_imgs bmi ON bmi.burger_id = b.id_burger
                    LEFT JOIN burger_size bs ON bs.burger_id = b.id_burger
                    LEFT JOIN burger_ingredients bi ON bi.burger_id = b.id_burger
                    LEFT JOIN burger_stock bst ON bst.burger_id = b.id_burger
                    LEFT JOIN locals l ON l.id = bst.local_id
                    GROUP BY b.id_burger, l.id
                """)
            ).mappings().all()

        burgers_map = {}

        for row in rows:
            bid = row["id_burger"]

            if bid not in burgers_map:
                burgers_map[bid] = {
                    "id_burger": bid,
                    "name": row["name"],
                    "price": row["price"],
                    "stock": bool(row["stock"]),
                    "description": row["description"],
                    "main_image": row["main_image"],
                    "size": row["sizes"].split(",") if row["sizes"] else [],
                    "ingredients": row["ingredients"].split(",") if row["ingredients"] else [],
                    "stock_by_local": {}
                }

            if row["local_name"]:
                burgers_map[bid]["stock_by_local"][row["local_name"]] = bool(row["local_stock"])

        return list(burgers_map.values())

    except Exception as e:
        print(f"Error getting burgers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update_burger/{id_burger}", tags=["Food"])
async def update_burger(
    id_burger: str,
    burger_data: UpdateBurgerRequest,
):
    try:
        with engine.begin() as conn:
            update_fields = {}
            if burger_data.price is not None:
                update_fields["price"] = burger_data.price
            if burger_data.stock is not None:
                update_fields["stock"] = burger_data.stock
            if burger_data.name is not None:
                update_fields["name"] = burger_data.name
            if burger_data.description is not None:
                update_fields["description"] = burger_data.description

            if update_fields:
                set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
                update_fields["id_burger"] = id_burger
                conn.execute(
                    text(f"UPDATE burger SET {set_clause} WHERE id_burger = :id_burger"),
                    update_fields
                )

            if burger_data.size is not None:
                conn.execute(
                    text("DELETE FROM burger_size WHERE burger_id = :id_burger"),
                    {"id_burger": id_burger}
                )
                for s in burger_data.size:
                    conn.execute(
                        text("INSERT INTO burger_size (id, burger_id, size) VALUES (:id, :burger_id, :size)"),
                        {"id": str(uuid.uuid4()), "burger_id": id_burger, "size": s}
                    )

            if burger_data.ingredients is not None:
                conn.execute(
                    text("DELETE FROM burger_ingredients WHERE burger_id = :id_burger"),
                    {"id_burger": id_burger}
                )
                for ing in burger_data.ingredients:
                    conn.execute(
                        text("INSERT INTO burger_ingredients (id, burger_id, ingredients) VALUES (:id, :burger_id, :ingredients)"),
                        {"id": str(uuid.uuid4()), "burger_id": id_burger, "ingredients": ing}
                    )

        return {"message": "Burger updated successfully", "id_burger": id_burger}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/burgers/{id_burger}/stock/{local_id}", tags=["Food"])
def toggle_burger_stock(id_burger: str, local_id: str, payload: ToggleProductStockRequest):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE burger_stock
                    SET has_stock = :has_stock
                    WHERE burger_id = :burger_id AND local_id = :local_id
                """),
                {"has_stock": payload.has_stock, "burger_id": id_burger, "local_id": local_id},
            )

            if result.rowcount == 0:
                conn.execute(
                    text("""
                        INSERT INTO burger_stock (id, burger_id, local_id, has_stock)
                        VALUES (:id, :burger_id, :local_id, :has_stock)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "burger_id": id_burger,
                        "local_id": local_id,
                        "has_stock": payload.has_stock,
                    },
                )

        return {
            "message": "Burger stock updated for local",
            "burger_id": id_burger,
            "local_id": local_id,
            "has_stock": payload.has_stock,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_burgers/{id_burger}", tags=["Food"])
def delete_burger(id_burger: str):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM burger_main_imgs WHERE burger_id = :id_burger"),
                {"id_burger": id_burger},
            )
            conn.execute(
                text("DELETE FROM burger_size WHERE burger_id = :id_burger"),
                {"id_burger": id_burger},
            )
            conn.execute(
                text("DELETE FROM burger_ingredients WHERE burger_id = :id_burger"),
                {"id_burger": id_burger},
            )
            
            conn.execute(
                text("DELETE FROM burger_stock WHERE burger_id = :id_burger"),
                {"id_burger": id_burger},
            )
            
            result = conn.execute(
                text("""
                    DELETE FROM burger
                    WHERE id_burger = :id_burger
                """),
                {"id_burger": id_burger},
            )
            if os.path.exists(IMAGES_DIR):
                for u in os.listdir(IMAGES_DIR):
                    if u.startswith(id_burger):
                        os.remove(os.path.join(IMAGES_DIR, u))
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Burger not found")

            return {"message": "Burger with your images, size and ingredients deleted succesfully", "id_burger": id_burger}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fries", tags=["Food"])
async def create_fries(
    name: str = Form(...),
    size: List[str] = Form(default=[]),
    description: List[str] = Form(default=[]),
    price: List[float] = Form(...),
    stock: bool = Form(...),
    main_image: UploadFile = File(..., description="Main image")
):
    fries_id = str(uuid.uuid4())
    
    # Insert size
    normalized_size = []
    for d in size:
        if isinstance(d, str) and "," in d:
            normalized_size.extend([item.strip() for item in d.split(",") if item.strip()])
        elif d:
            normalized_size.append(d.strip())
    
    # Insert prices
    normalized_price = []
    for p in price:
        if p:
            normalized_price.append(p)
    
    # Insert description
    normalized_description = []
    for d in description:
        if isinstance(d, str) and "," in d:
            normalized_description.extend([item.strip() for item in d.split(",") if item.strip()])
        elif d:
            normalized_description.append(d.strip())

    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR, exist_ok=True)
    ext = os.path.splitext(main_image.filename or "file.jpg")[1]
    fname = f"{uuid.uuid4()}{ext}"
    path = os.path.join(IMAGES_DIR, fname)
    with open(path, "wb") as buf:
        shutil.copyfileobj(main_image.file, buf)
    url_main = f"{DOMAIN_URL}/{fname}"
    
    # All database operations in a single transaction
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO fries (id_fries, name, stock)
                VALUES (:id, :name, :stock)
            """),
            {
                "id": fries_id,
                "name": name,
                "stock": stock,
            },
        )
        
        conn.execute(
            text("""
                INSERT INTO fries_stock (id, fries_id, local_id, has_stock)
                SELECT UUID(), :fries_id, l.id, :has_stock
                FROM locals l
            """),
            {"fries_id": fries_id, "has_stock": stock},
        )
        
        for d in normalized_size:
            if not d:
                continue
            conn.execute(
                text("""
                    INSERT INTO fries_size (id, fries_id, size)
                    VALUES (:id, :fries_id, :size)
                """),
                {"id": str(uuid.uuid4()), "fries_id": fries_id, "size": d}
            )
        
        for p in normalized_price:
            conn.execute(
                text("""
                    INSERT INTO fries_prices (id, fries_id, price)
                    VALUES (:id, :fries_id, :price)
                """),
                {"id": str(uuid.uuid4()), "fries_id": fries_id, "price": p}
            )
        
        for d in normalized_description:
            if not d:
                continue
            conn.execute(
                text("""
                    INSERT INTO fries_description (id, fries_id, description)
                    VALUES (:id, :fries_id, :description)
                """),
                {"id": str(uuid.uuid4()), "fries_id": fries_id, "description": d}
            )
        
        conn.execute(
            text("INSERT INTO fries_main_imgs (id, fries_id, url) VALUES (:id, :fries_id, :url)"),
            {"id": str(uuid.uuid4()), "fries_id": fries_id, "url": url_main}
        )
    
    return {"message": "Fries created", "id": fries_id, "main_image_url": url_main}

@router.put("/update_fries/{id_fries}", tags=["Food"])
async def update_fries(
    id_fries: str,
    fries_data: UpdateFriesRequest,
):
    try:
        with engine.begin() as conn:
            update_fields = {}
            if fries_data.name is not None:
                update_fields["name"] = fries_data.name
            if fries_data.stock is not None:
                update_fields["stock"] = fries_data.stock

            if update_fields:
                set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
                update_fields["id_fries"] = id_fries
                conn.execute(
                    text(f"UPDATE fries SET {set_clause} WHERE id_fries = :id_fries"),
                    update_fields
                )

            if fries_data.size_list is not None:
                conn.execute(
                    text("DELETE FROM fries_size WHERE fries_id = :id_fries"),
                    {"id_fries": id_fries}
                )
                for s in fries_data.size_list:
                    conn.execute(
                        text("INSERT INTO fries_size (id, fries_id, size) VALUES (:id, :fries_id, :size)"),
                        {"id": str(uuid.uuid4()), "fries_id": id_fries, "size": s}
                    )

            if fries_data.description_list is not None:
                conn.execute(
                    text("DELETE FROM fries_description WHERE fries_id = :id_fries"),
                    {"id_fries": id_fries}
                )
                for d in fries_data.description_list:
                    conn.execute(
                        text("INSERT INTO fries_description (id, fries_id, description) VALUES (:id, :fries_id, :description)"),
                        {"id": str(uuid.uuid4()), "fries_id": id_fries, "description": d}
                    )

            if fries_data.price_list is not None:
                conn.execute(
                    text("DELETE FROM fries_prices WHERE fries_id = :id_fries"),
                    {"id_fries": id_fries}
                )
                for p in fries_data.price_list:
                    conn.execute(
                        text("INSERT INTO fries_prices (id, fries_id, price) VALUES (:id, :fries_id, :price)"),
                        {"id": str(uuid.uuid4()), "fries_id": id_fries, "price": p}
                    )

        return {"message": "Fries updated successfully", "id_fries": id_fries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/fries/{id_fries}/stock/{local_id}", tags=["Food"])
def toggle_fries_stock(id_fries: str, local_id: str, payload: ToggleProductStockRequest):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE fries_stock SET has_stock = :has_stock WHERE fries_id = :id_fries AND local_id = :local_id"),
                {"has_stock": payload.has_stock, "id_fries": id_fries, "local_id": local_id}
            )
        return {"message": "Fries stock toggled successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_fries/{id_fries}", tags=["Food"])
def delete_fries(id_fries: str):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM fries_main_imgs WHERE fries_id = :id_fries"),
                {"id_fries": id_fries},
            )
            conn.execute(
                text("DELETE FROM fries_size WHERE fries_id = :id_fries"),
                {"id_fries": id_fries},
            )
            conn.execute(
                text("DELETE FROM fries_description WHERE fries_id = :id_fries"),
                {"id_fries": id_fries},
            )
            conn.execute(
                text("DELETE FROM fries_prices WHERE fries_id = :id_fries"),
                {"id_fries": id_fries},
            )
            
            conn.execute(
                text("DELETE FROM fries_stock WHERE fries_id = :id_fries"),
                {"id_fries": id_fries},
            )
            
            result = conn.execute(
                text("""
                    DELETE FROM fries
                    WHERE id_fries = :id_fries
                """),
                {"id_fries": id_fries},
            )
            if os.path.exists(IMAGES_DIR):
                for u in os.listdir(IMAGES_DIR):
                    if u.startswith(id_fries):
                        os.remove(os.path.join(IMAGES_DIR, u))
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Fries not found")

            return {"message": "Fries with your images, size, description and prices deleted succesfully", "id_fries": id_fries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fries", tags=["Food"])
def get_fries():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        f.*,
                        l.name AS local_name,
                        COALESCE(fs.has_stock, 1) AS local_stock
                    FROM fries f
                    LEFT JOIN fries_stock fs ON fs.fries_id = f.id_fries
                    LEFT JOIN locals l ON l.id = fs.local_id
                    ORDER BY f.id_fries
                """)
            ).mappings().all()

            if not rows:
                raise HTTPException(status_code=404, detail="No fries found.")

            fries_map = {}

            for row in rows:
                fid = row["id_fries"]

                if fid not in fries_map:
                    main = conn.execute(
                        text("SELECT url FROM fries_main_imgs WHERE fries_id = :id"),
                        {"id": fid}
                    ).fetchone()

                    size_list = conn.execute(
                        text("SELECT size FROM fries_size WHERE fries_id = :id"),
                        {"id": fid}
                    ).scalars().all()

                    description_list = conn.execute(
                        text("SELECT description FROM fries_description WHERE fries_id = :id"),
                        {"id": fid}
                    ).scalars().all()

                    price_list = conn.execute(
                        text("SELECT price FROM fries_prices WHERE fries_id = :id"),
                        {"id": fid}
                    ).scalars().all()

                    data = dict(row)
                    data.pop("local_name", None)
                    data.pop("local_stock", None)

                    data["main_image"] = main[0] if main else None
                    data["size_list"] = size_list
                    data["description_list"] = description_list
                    data["price_list"] = price_list
                    data["stock_by_local"] = {}

                    fries_map[fid] = data

                if row["local_name"]:
                    fries_map[fid]["stock_by_local"][row["local_name"]] = bool(row["local_stock"])

            return list(fries_map.values())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/drinks", tags=["Food"])
async def create_drinks(
    name: str = Form(...),
    price: str = Form(...),
    stock: bool = Form(...),
    size: List[str] = Form(default=[]),
    main_image: UploadFile = File(..., description="Main image")
):
    drinks_id = str(uuid.uuid4())
    
    # Insert size
    normalized_size = []
    for d in size:
        if isinstance(d, str) and "," in d:
            normalized_size.extend([item.strip() for item in d.split(",") if item.strip()])
        elif d:
            normalized_size.append(d.strip())

    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR, exist_ok=True)
    ext = os.path.splitext(main_image.filename or "file.jpg")[1]
    fname = f"{uuid.uuid4()}{ext}"
    path = os.path.join(IMAGES_DIR, fname)
    with open(path, "wb") as buf:
        shutil.copyfileobj(main_image.file, buf)
    url_main = f"{DOMAIN_URL}/{fname}"
    
    # All database operations in a single transaction
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO drinks (id_drinks, name, price, stock)
                VALUES (:id, :name, :price, :stock)
            """),
            {
                "id": drinks_id,
                "name": name,
                "price": price,
                "stock": stock,
            },
        )
        
        conn.execute(
            text("""
                INSERT INTO drinks_stock (id, drinks_id, local_id, has_stock)
                SELECT UUID(), :drinks_id, l.id, :has_stock
                FROM locals l
            """),
            {"drinks_id": drinks_id, "has_stock": stock},
        )
        
        for d in normalized_size:
            if not d:
                continue
            conn.execute(
                text("""
                    INSERT INTO drinks_size (id, drinks_id, size)
                    VALUES (:id, :drinks_id, :size)
                """),
                {"id": str(uuid.uuid4()), "drinks_id": drinks_id, "size": d}
            )

        conn.execute(
            text("INSERT INTO drinks_main_imgs (id, drinks_id, url) VALUES (:id, :drinks_id, :url)"),
            {"id": str(uuid.uuid4()), "drinks_id": drinks_id, "url": url_main}
        )
    
    return {"message": "Drinks created", "id": drinks_id, "main_image_url": url_main}

@router.put("/update_drinks/{id_drinks}", tags=["Food"])
async def update_drinks(
    id_drinks: str,
    drinks_data: UpdateDrinksRequest,
):
    try:
        with engine.begin() as conn:
            update_fields = {}
            if drinks_data.name is not None:
                update_fields["name"] = drinks_data.name
            if drinks_data.price is not None:
                update_fields["price"] = drinks_data.price
            if drinks_data.stock is not None:
                update_fields["stock"] = drinks_data.stock

            if update_fields:
                set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
                update_fields["id_drinks"] = id_drinks
                conn.execute(
                    text(f"UPDATE drinks SET {set_clause} WHERE id_drinks = :id_drinks"),
                    update_fields
                )

            if drinks_data.size_list is not None:
                conn.execute(
                    text("DELETE FROM drinks_size WHERE drinks_id = :id_drinks"),
                    {"id_drinks": id_drinks}
                )
                for s in drinks_data.size_list:
                    conn.execute(
                        text("INSERT INTO drinks_size (id, drinks_id, size) VALUES (:id, :drinks_id, :size)"),
                        {"id": str(uuid.uuid4()), "drinks_id": id_drinks, "size": s}
                    )

        return {"message": "Drinks updated successfully", "id_drinks": id_drinks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/drinks/{id_drinks}/stock/{local_id}", tags=["Food"])
def toggle_drinks_stock(id_drinks: str, local_id: str, payload: ToggleProductStockRequest):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE drinks_stock SET has_stock = :has_stock WHERE drinks_id = :id_drinks AND local_id = :local_id"),
                {"has_stock": payload.has_stock, "id_drinks": id_drinks, "local_id": local_id}
            )
        return {"message": "Drinks stock toggled successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_drinks/{id_drinks}", tags=["Food"])
def delete_drinks(id_drinks: str):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM drinks_main_imgs WHERE drinks_id = :id_drinks"),
                {"id_drinks": id_drinks},
            )
            conn.execute(
                text("DELETE FROM drinks_size WHERE drinks_id = :id_drinks"),
                {"id_drinks": id_drinks},
            )
            
            result = conn.execute(
                text("""
                    DELETE FROM drinks
                    WHERE id_drinks = :id_drinks
                """),
                {"id_drinks": id_drinks},
            )
            if os.path.exists(IMAGES_DIR):
                for u in os.listdir(IMAGES_DIR):
                    if u.startswith(id_drinks):
                        os.remove(os.path.join(IMAGES_DIR, u))
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Drinks not found")

            return {"message": "Drinks with your images and size deleted succesfully", "id_drinks": id_drinks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drinks", tags=["Food"])
def get_drinks():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        f.*,
                        l.name AS local_name,
                        COALESCE(fs.has_stock, 1) AS local_stock
                    FROM drinks f
                    LEFT JOIN drinks_stock fs ON fs.drinks_id = f.id_drinks
                    LEFT JOIN locals l ON l.id = fs.local_id
                    ORDER BY f.id_drinks
                """)
            ).mappings().all()

            if not rows:
                raise HTTPException(status_code=404, detail="No drinks found.")

            drinks_map = {}

            for row in rows:
                fid = row["id_drinks"]

                if fid not in drinks_map:
                    main = conn.execute(
                        text("SELECT url FROM drinks_main_imgs WHERE drinks_id = :id"),
                        {"id": fid}
                    ).fetchone()

                    size_list = conn.execute(
                        text("SELECT size FROM drinks_size WHERE drinks_id = :id"),
                        {"id": fid}
                    ).scalars().all()

                    data = dict(row)
                    data.pop("local_name", None)
                    data.pop("local_stock", None)

                    data["main_image"] = main[0] if main else None
                    data["size_list"] = size_list
                    data["stock_by_local"] = {}

                    drinks_map[fid] = data

                if row["local_name"]:
                    drinks_map[fid]["stock_by_local"][row["local_name"]] = bool(row["local_stock"])

            return list(drinks_map.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/promos", tags=["Promos"])
async def create_promo(
    name: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
    stock: bool = Form(...),
    options: int = Form(...),
    image: UploadFile = File(..., description="Promo image"),
    description_list: List[str] = Form(default=[]),  
):
    promo_id = str(uuid.uuid4())

    # Insert description_list
    normalized_description = []
    for d in description_list:
        if isinstance(d, str) and "," in d:
            normalized_description.extend([item.strip() for item in d.split(",") if item.strip()])
        elif d:
            normalized_description.append(d.strip())

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO promos (id_promos, name, description, quantity, price, stock, options)
                VALUES (:id, :name, :description, :quantity, :price, :stock, :options)
            """),
            {"id": promo_id, "name": name, "description": description, "quantity": quantity, "price": price, "stock": stock, "options": options},
        )
        
        conn.execute(
            text("""
                INSERT INTO promos_stock (id, promo_id, local_id, has_stock)
                SELECT UUID(), :promo_id, l.id, :has_stock
                FROM locals l
            """),
            {"promo_id": promo_id, "has_stock": stock}
        )

        for desc in normalized_description:
            if not desc:
                continue
            conn.execute(
                text("""
                    INSERT INTO promos_description (id, promo_id, description)
                    VALUES (:id, :promo_id, :description)
                """),
                {"id": str(uuid.uuid4()), "promo_id": promo_id, "description": desc}
            )

    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR, exist_ok=True)
    ext = os.path.splitext(image.filename or "file.jpg")[1]
    fname = f"{uuid.uuid4()}{ext}"
    path = os.path.join(IMAGES_DIR, fname)
    with open(path, "wb") as buf:
        shutil.copyfileobj(image.file, buf)
    url_image = f"{DOMAIN_URL}/{fname}"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO promos_imgs (id, promo_id, url) VALUES (:id, :promo_id, :url)"),
            {"id": str(uuid.uuid4()), "promo_id": promo_id, "url": url_image}
        )
    
    

    return {"message": "Promo created", "id": promo_id}

@router.put("/update_promos/{id_promos}", tags=["Promos"])
async def update_promos(
    promo_id: str,
    promo_data: UpdatePromoRequest,
):
    try:
        with engine.begin() as conn:
            update_fields = {}
            if promo_data.name is not None:
                update_fields["name"] = promo_data.name
            if promo_data.description is not None:
                update_fields["description"] = promo_data.description
            if promo_data.quantity is not None:
                update_fields["quantity"] = promo_data.quantity
            if promo_data.price is not None:
                update_fields["price"] = promo_data.price
            if promo_data.options is not None:
                update_fields["options"] = promo_data.options

            if promo_data.description_list is not None:
                conn.execute(
                    text("DELETE FROM promos_description WHERE promo_id = :promo_id"),
                    {"promo_id": promo_id}
                )
                for d in promo_data.description_list:
                    conn.execute(
                        text("INSERT INTO promos_description (id, promo_id, description) VALUES (:id, :promo_id, :description)"),
                        {"id": str(uuid.uuid4()), "promo_id": promo_id, "description": d}
                    )

            if update_fields:
                set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
                update_fields["id_promos"] = promo_id
                conn.execute(
                    text(f"UPDATE promos SET {set_clause} WHERE id_promos = :id_promos"),
                    update_fields
                )

        return {"message": "Promo updated successfully", "id_promos": promo_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/promos/{id_promos}/stock/{local_id}", tags=["Promos"])
def toggle_promo_stock(id_promos: str, local_id: str, payload: ToggleProductStockRequest):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE promos_stock SET has_stock = :has_stock WHERE promo_id = :id_promos AND local_id = :local_id"),
                {"has_stock": payload.has_stock, "id_promos": id_promos, "local_id": local_id}
            )
        return {"message": "Promo stock toggled successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/promos", tags=["Promos"])
def get_promos():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        p.*,
                        l.name AS local_name,
                        COALESCE(ps.has_stock, 1) AS local_stock
                    FROM promos p
                    LEFT JOIN promos_stock ps ON ps.promo_id = p.id_promos
                    LEFT JOIN locals l ON l.id = ps.local_id
                    ORDER BY p.id_promos
                """)
            ).mappings().all()

            if not rows:
                raise HTTPException(status_code=404, detail="No promos found.")

            promos_map = {}

            for row in rows:
                pid = row["id_promos"]

                if pid not in promos_map:
                    img = conn.execute(
                        text("SELECT url FROM promos_imgs WHERE promo_id = :id"),
                        {"id": pid}
                    ).fetchone()

                    description_list = conn.execute(
                        text("SELECT description FROM promos_description WHERE promo_id = :id"),
                        {"id": pid}
                    ).scalars().all()

                    data = dict(row)
                    data.pop("local_name", None)
                    data.pop("local_stock", None)

                    data["image"] = img[0] if img else None
                    data["description_list"] = description_list
                    data["stock_by_local"] = {}

                    promos_map[pid] = data

                if row["local_name"]:
                    promos_map[pid]["stock_by_local"][row["local_name"]] = bool(row["local_stock"])

            return list(promos_map.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/delete_promos/{id_promos}", tags=["Promos"])
def delete_promo(id_promos: str):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM promos_imgs WHERE promo_id = :id_promos"),
                {"id_promos": id_promos},
            )
            conn.execute(
                text("DELETE FROM promos_description WHERE promo_id = :promo_id"),
                {"promo_id": id_promos}
            )
            conn.execute(
                text("DELETE FROM promos_stock WHERE promo_id = :id_promos"),
                {"id_promos": id_promos},
            )
            result = conn.execute(
                text("""
                    DELETE FROM promos
                    WHERE id_promos = :id_promos
                """),
                {"id_promos": id_promos},
            )
            if os.path.exists(IMAGES_DIR):
                for u in os.listdir(IMAGES_DIR):
                    if u.startswith(id_promos):
                        os.remove(os.path.join(IMAGES_DIR, u))
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Promo not found")

            return {"message": "Promo with your images deleted succesfully", "id_promos": id_promos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/create_coupon", tags=["Coupons"])
async def create_coupon(coupon_data: couponRequest):
    try:
        coupon_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO coupons (id, name, amount, type, tope) VALUES (:id, :name, :amount, :type, :tope)"),
                {"id": coupon_id, "name": coupon_data.name, "amount": coupon_data.amount, "type": coupon_data.type, "tope": coupon_data.tope},
            )
        return {"message": "Coupon created", "id": coupon_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coupons", tags=["Coupons"])
def get_coupons():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT * FROM coupons")
            ).mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No coupons found.")
            return list(rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coupon/{name}", tags=["Coupons"])
def get_coupon(name: str):
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM coupons WHERE name = :name"),
                {"name": name},
            ).mappings().one_or_none()
            if not row:
                raise HTTPException(status_code=404, detail="Coupon not found")
            return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update_coupon/{id}", tags=["Coupons"])
def update_coupon(id: str, coupon_data: couponRequest):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE coupons SET name = :name, amount = :amount, type = :type, tope = :tope WHERE id = :id"),
                {"id": id, "name": coupon_data.name, "amount": coupon_data.amount, "type": coupon_data.type, "tope": coupon_data.tope},
            )
        return {"message": "Coupon updated successfully", "id": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_coupon/{id}", tags=["Coupons"])
def delete_coupon(id: str):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM coupons WHERE id = :id"),
                {"id": id},
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Coupon not found")
            return {"message": "Coupon deleted successfully", "id": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/create_delivery_price", tags=["Delivery Price"])
def create_delivery_price(delivery_price_data: deliveryPriceRequest):
    try:
        delivery_price_id = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO delivery_price (id, price) VALUES (:id, :price)"),
                {"id": delivery_price_id, "price": delivery_price_data.price},
            )
        return {"message": "Delivery price created", "id": delivery_price_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/delivery_price", tags=["Delivery Price"])
def get_delivery_price():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT * FROM delivery_price")
            ).mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No delivery prices found.")
            return list(rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_delivery_price/{id}", tags=["Delivery Price"])
def delete_delivery_price(id: str):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM delivery_price WHERE id = :id"),
                {"id": id},
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Delivery price not found")
            return {"message": "Delivery price deleted successfully", "id": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/update_delivery_price/{id}", tags=["Delivery Price"])
def update_delivery_price(id: str, delivery_price_data: deliveryPriceRequest):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE delivery_price SET price = :price WHERE id = :id"),
                {"id": id, "price": delivery_price_data.price},
            )
        return {"message": "Delivery price updated successfully", "id": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))