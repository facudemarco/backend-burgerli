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

@router.post("/add_home_image", tags=["Home"])
def add_home_image(image: UploadFile = File(...)):
    try:
        id = str(uuid.uuid4())
        if not image.filename:
            raise HTTPException(status_code=400, detail="No image file provided")
        
        # Generate a unique filename
        file_extension = image.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(IMAGES_DIR, unique_filename)
        
        # Save the image
        os.makedirs(IMAGES_DIR, exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        # Get the URL
        image_url = f"{DOMAIN_URL}/{unique_filename}"
        
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO imgs_home (id, url) VALUES (:id, :url)"),
                {"id": id, "url": image_url},
            )
        
        return {"message": "Image added successfully", "id": id, "image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_home_images", tags=["Home"])
def get_home_images():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT id, url FROM imgs_home")
            )
            images = [{"id": row[0], "url": row[1]} for row in rows]
        return {"images": images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_home_image", tags=["Home"])
def delete_home_image(id: str):
    try:
        image_url = None
        with engine.begin() as conn:
            # Get the image URL first
            result = conn.execute(
                text("SELECT url FROM imgs_home WHERE id = :id"),
                {"id": id}
            ).fetchone()
            
            if result:
                image_url = result[0]
                conn.execute(
                    text("DELETE FROM imgs_home WHERE id = :id"),
                    {"id": id},
                )
        
        if image_url:
            filename = image_url.split("/")[-1]
            file_path = os.path.join(IMAGES_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                
        return {"message": "Image deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))