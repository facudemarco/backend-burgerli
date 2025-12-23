from typing import List, Optional
from fastapi import APIRouter, HTTPException, Form, Body, UploadFile, File
from pydantic import BaseModel
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
    size : Optional[List[str]] = None
    description : Optional[List[str]] = None
    price : Optional[List[float]] = None
    main_image: Optional[str] = None

class UpdateDrinksRequest(BaseModel):
    name : Optional[str] = None
    price : Optional[float] = None
    stock : Optional[bool] = None
    size : Optional[List[str]] = None
    main_image: Optional[str] = None

class UpdateComboRequest(BaseModel):
    name : Optional[str] = None
    quantity : Optional[int] = None
    price : Optional[float] = None
    burgers : Optional[str] = None
    fries : Optional[str] = None
    drinks : Optional[str] = None

class UpdatePromoRequest(BaseModel):
    name : Optional[str] = None
    day : Optional[str] = None
    quantity : Optional[int] = None
    price : Optional[float] = None
    image: Optional[str] = None
    description_list: Optional[List[str]] = None

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
            result = conn.execute(
                text("""
                    SELECT 
                        b.*,
                        bmi.url as main_image,
                        GROUP_CONCAT(DISTINCT bs.size) as sizes,
                        GROUP_CONCAT(DISTINCT bi.ingredients) as ingredients
                    FROM burger b
                    LEFT JOIN burger_main_imgs bmi ON bmi.burger_id = b.id_burger
                    LEFT JOIN burger_size bs ON bs.burger_id = b.id_burger 
                    LEFT JOIN burger_ingredients bi ON bi.burger_id = b.id_burger
                    GROUP BY b.id_burger
                """)
            ).mappings().all()

            if not result:
                raise HTTPException(status_code=404, detail="No burgers found.")

            burgers = []
            for row in result:
                data = dict(row)
                data["size"] = data.pop("sizes", "").split(",") if data.get("sizes") else []
                data["ingredients"] = data.pop("ingredients", "").split(",") if data.get("ingredients") else []
                burgers.append(data)

            return burgers

    except Exception as e:
        # Agregar log del error
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
    price: List[str] = Form(...),
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
        if isinstance(p, str) and "," in p:
            normalized_price.extend([float(item.strip()) for item in p.split(",") if item.strip()])
        elif p:
            normalized_price.append(float(p))
    
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

            if fries_data.size is not None:
                conn.execute(
                    text("DELETE FROM fries_size WHERE fries_id = :id_fries"),
                    {"id_fries": id_fries}
                )
                for s in fries_data.size:
                    conn.execute(
                        text("INSERT INTO fries_size (id, fries_id, size) VALUES (:id, :fries_id, :size)"),
                        {"id": str(uuid.uuid4()), "fries_id": id_fries, "size": s}
                    )

            if fries_data.description is not None:
                conn.execute(
                    text("DELETE FROM fries_description WHERE fries_id = :id_fries"),
                    {"id_fries": id_fries}
                )
                for d in fries_data.description:
                    conn.execute(
                        text("INSERT INTO fries_description (id, fries_id, description) VALUES (:id, :fries_id, :description)"),
                        {"id": str(uuid.uuid4()), "fries_id": id_fries, "description": d}
                    )

            if fries_data.price is not None:
                conn.execute(
                    text("DELETE FROM fries_prices WHERE fries_id = :id_fries"),
                    {"id_fries": id_fries}
                )
                for p in fries_data.price:
                    conn.execute(
                        text("INSERT INTO fries_prices (id, fries_id, price) VALUES (:id, :fries_id, :price)"),
                        {"id": str(uuid.uuid4()), "fries_id": id_fries, "price": p}
                    )

        return {"message": "Fries updated successfully", "id_fries": id_fries}
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
            result = conn.execute(text("SELECT * FROM fries"))
            rows = result.mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No fries found.")
            fries = []
            for fries_row in rows:
                hid = fries_row["id_fries"]
                main = conn.execute(
                    text("SELECT url FROM fries_main_imgs WHERE fries_id = :id"),
                    {"id": hid}
                ).fetchone()

                size_list = conn.execute(
                    text("SELECT size FROM fries_size WHERE fries_id = :id"),
                    {"id": hid}
                ).scalars().all()

                description_list = conn.execute(
                    text("SELECT description FROM fries_description WHERE fries_id = :id"),
                    {"id": hid}
                ).scalars().all()
                
                price_list = conn.execute(
                    text("SELECT price FROM fries_prices WHERE fries_id = :id"),
                    {"id": hid}
                ).scalars().all()

                data = dict(fries_row)
                data["main_image"] = main[0] if main else None
                data["size_list"] = size_list
                data["description_list"] = description_list
                data["price_list"] = price_list
                fries.append(data)
            return fries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dips", tags=["Food"])
async def create_dip(
    name: str = Form(...),
    image: UploadFile = File(..., description="Dip image"),
    stock: bool = Form(...),
    price: float = Form(...)
):
    dip_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO dips (id_dips, name, stock, price)
                VALUES (:id, :name, :stock, :price)
            """),
            {
                "id": dip_id,
                "name": name,
                "stock": stock,
                "price": price
            }
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
            text("INSERT INTO dips_imgs (id, dips_id, url) VALUES (:id, :dips_id, :url)"),
            {"id": str(uuid.uuid4()), "dips_id": dip_id, "url": url_image}
        )
    return {"message": "Dip created", "id": dip_id}

@router.get("/dips", tags=["Food"])
def get_dips():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM dips"))
            rows = result.mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No dips found.")
            dips = []
            for dip in rows:
                hid = dip["id_dips"]
                images = conn.execute(
                    text("SELECT url FROM dips_imgs WHERE dips_id = :id"),
                    {"id": hid}
                ).scalars().all()
                data = dict(dip)
                data["images"] = images
                dips.append(data)
            return dips
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

            if drinks_data.size is not None:
                conn.execute(
                    text("DELETE FROM drinks_size WHERE drinks_id = :id_drinks"),
                    {"id_drinks": id_drinks}
                )
                for s in drinks_data.size:
                    conn.execute(
                        text("INSERT INTO drinks_size (id, drinks_id, size) VALUES (:id, :drinks_id, :size)"),
                        {"id": str(uuid.uuid4()), "drinks_id": id_drinks, "size": s}
                    )

        return {"message": "Drinks updated successfully", "id_drinks": id_drinks}
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
            result = conn.execute(text("SELECT * FROM drinks"))
            rows = result.mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No drinks found.")
            drinks = []
            for drinks_row in rows:
                hid = drinks_row["id_drinks"]
                main = conn.execute(
                    text("SELECT url FROM drinks_main_imgs WHERE drinks_id = :id"),
                    {"id": hid}
                ).fetchone()

                size_list = conn.execute(
                    text("SELECT size FROM drinks_size WHERE drinks_id = :id"),
                    {"id": hid}
                ).scalars().all()

                data = dict(drinks_row)
                data["main_image"] = main[0] if main else None
                data["size_list"] = size_list
                drinks.append(data)
            return drinks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/combos", tags=["Combos & Promos"])
async def create_combo(
    name: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
    burgers: str = Form(...),
    fries: str = Form(...),
    drinks: str = Form(...)
):
    combo_id = str(uuid.uuid4())

    def _split_csv(value: str):
        return [x.strip() for x in value.split(",") if x.strip()]

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO combos (id_combos, name, quantity, price)
                VALUES (:id, :name, :quantity, :price)
            """),
            {"id": combo_id, "name": name, "quantity": quantity, "price": price},
        )

        for b in _split_csv(burgers):
            conn.execute(
                text("""
                    INSERT INTO combo_burger (id_combo_burger, id_combo, id_burger)
                    VALUES (:id, :combo, :burger)
                """),
                {"id": str(uuid.uuid4()), "combo": combo_id, "burger": b},
            )

        for f in _split_csv(fries):
            conn.execute(
                text("""
                    INSERT INTO combo_fries (id_combo_fries, id_combo, id_fries)
                    VALUES (:id, :combo, :fries)
                """),
                {"id": str(uuid.uuid4()), "combo": combo_id, "fries": f},
            )

        for d in _split_csv(drinks):
            conn.execute(
                text("""
                    INSERT INTO combo_drinks (id_combo_drinks, id_combo, id_drinks)
                    VALUES (:id, :combo, :drinks)
                """),
                {"id": str(uuid.uuid4()), "combo": combo_id, "drinks": d},
            )

    return {"message": "Combo created", "id": combo_id}

@router.put("/update_combos/{id_combos}", tags=["Combos & Promos"])
async def update_combos(
    combo_id: str,
    combo_data: UpdateComboRequest,
):
    try:
        with engine.begin() as conn:
            update_fields = {}
            if combo_data.name is not None:
                update_fields["name"] = combo_data.name
            if combo_data.quantity is not None:
                update_fields["quantity"] = combo_data.quantity
            if combo_data.price is not None:
                update_fields["price"] = combo_data.price

            if update_fields:
                set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
                update_fields["id_combos"] = combo_id
                conn.execute(
                    text(f"UPDATE combos SET {set_clause} WHERE id_combos = :id_combos"),
                    update_fields
                )

            if combo_data.burgers is not None:
                conn.execute(
                    text("DELETE FROM combo_burger WHERE id_combo = :id_combos"),
                    {"id_combos": combo_id}
                )
                for b in combo_data.burgers.split(","):
                    conn.execute(
                        text("INSERT INTO combo_burger (id_combo_burger, id_combo, id_burger) VALUES (:id, :combo, :burger)"),
                        {"id": str(uuid.uuid4()), "combo": combo_id, "burger": b.strip()}
                    )

            if combo_data.fries is not None:
                conn.execute(
                    text("DELETE FROM combo_fries WHERE id_combo = :id_combos"),
                    {"id_combos": combo_id}
                )
                for f in combo_data.fries.split(","):
                    conn.execute(
                        text("INSERT INTO combo_fries (id_combo_fries, id_combo, id_fries) VALUES (:id, :combo, :fries)"),
                        {"id": str(uuid.uuid4()), "combo": combo_id, "fries": f.strip()}
                    )

            if combo_data.drinks is not None:
                conn.execute(
                    text("DELETE FROM combo_drinks WHERE id_combo = :id_combos"),
                    {"id_combos": combo_id}
                )
                for d in combo_data.drinks.split(","):
                    conn.execute(
                        text("INSERT INTO combo_drinks (id_combo_drinks, id_combo, id_drinks) VALUES (:id, :combo, :drinks)"),
                        {"id": str(uuid.uuid4()), "combo": combo_id, "drinks": d.strip()}
                    )

        return {"message": "Combo updated successfully", "id_combos": combo_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_combos/{id_combos}", tags=["Combos & Promos"])
def delete_combo(id_combos: str):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM combo_burger WHERE id_combo = :id_combos"),
                {"id_combos": id_combos},
            )
            conn.execute(
                text("DELETE FROM combo_fries WHERE id_combo = :id_combos"),
                {"id_combos": id_combos},
            )
            conn.execute(
                text("DELETE FROM combo_drinks WHERE id_combo = :id_combos"),
                {"id_combos": id_combos},
            )
            
            result = conn.execute(
                text("""
                    DELETE FROM combos
                    WHERE id_combos = :id_combos
                """),
                {"id_combos": id_combos},
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Combo not found")

            return {"message": "Combo deleted succesfully", "id_combos": id_combos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/combos", tags=["Combos & Promos"])
def get_combos():
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT c.*, cb.id_burger, cf.id_fries, cd.id_drinks
                    FROM combos c
                    LEFT JOIN combo_burger cb ON cb.id_combo = c.id_combos
                    LEFT JOIN combo_fries cf ON cf.id_combo = c.id_combos
                    LEFT JOIN combo_drinks cd ON cd.id_combo = c.id_combos
                """)
            ).mappings().all()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/promos", tags=["Combos & Promos"])
async def create_promo(
    name: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
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
                INSERT INTO promos (id_promos, name, description, quantity, price)
                VALUES (:id, :name, :description, :quantity, :price)
            """),
            {"id": promo_id, "name": name, "description": description, "quantity": quantity, "price": price},
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

@router.put("/update_promos/{id_promos}", tags=["Combos & Promos"])
async def update_promos(
    promo_id: str,
    promo_data: UpdatePromoRequest,
):
    try:
        with engine.begin() as conn:
            update_fields = {}
            if promo_data.name is not None:
                update_fields["name"] = promo_data.name
            if promo_data.day is not None:
                update_fields["day"] = promo_data.day
            if promo_data.quantity is not None:
                update_fields["quantity"] = promo_data.quantity
            if promo_data.price is not None:
                update_fields["price"] = promo_data.price
            if promo_data.description_list is not None:
                conn.execute(
                    text("DELETE FROM promos_description WHERE promo_id = :promo_id"),
                    {"promo_id": promo_id}
                )
                for desc in promo_data.description_list:
                    if not desc:
                        continue
                    conn.execute(
                        text("INSERT INTO promos_description (id, promo_id, description) VALUES (:id, :promo_id, :description)"),
                        {"id": str(uuid.uuid4()), "promo_id": promo_id, "description": desc}
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

@router.get("/promos", tags=["Combos & Promos"])
def get_promos():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM promos"))
            rows = result.mappings().all()
            if not rows:
                raise HTTPException(status_code=404, detail="No promos found.")
            promos = []
            for promo in rows:
                hid = promo["id_promos"]
                images = conn.execute(
                    text("SELECT url FROM promos_imgs WHERE promo_id = :id"),
                    {"id": hid}
                ).scalars().all()
                
                description_list = conn.execute(
                    text("SELECT description FROM promos_description WHERE promo_id = :id"),
                    {"id": hid}
                ).scalars().all()
                
                data = dict(promo)
                data["images"] = images
                data["description_list"] = description_list
                promos.append(data)
            return promos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/delete_promos/{id_promos}", tags=["Combos & Promos"])
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