import uuid
from fastapi import APIRouter, HTTPException, Body
from sqlalchemy import text
from Database.getConnection import engine
from sqlalchemy.exc import OperationalError
from typing import Optional, Dict, List 

from models.locals import OpeningHoursPayload
import json

router = APIRouter()

@router.put("/updateLocalStatus/{name}", tags=["Locals"])
async def update_local_status(name: str, status: bool = Body(..., embed=True)):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("UPDATE locals SET is_open = :status WHERE name = :name"), {
                "status": status,
                "name": name
            })
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Local not found")
            return {"message": "Local status updated successfully"}
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
@router.post("/addLocal", tags=["Locals"])
async def add_local(name: str = Body(...), is_open: bool = Body(...)):
    id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            result = conn.execute(text("INSERT INTO locals (id, name, is_open) VALUES (:id, :name, :is_open)"), {
                "id": id,
                "name": name,
                "is_open": is_open
            })
            return {"message": "Local added successfully", "id": id}
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
@router.get("/getLocals", tags=["Locals"])
async def get_locals():
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM locals"))
            locals_list = [dict(row) for row in result.mappings()]
            return {"locals": locals_list}
    
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

@router.delete("/deleteLocal/{name}", tags=["Locals"])
async def delete_local(name: str):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("DELETE FROM locals WHERE name = :name"), {
                "name": name
            })
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Local not found")
            return {"message": "Local deleted successfully"}
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
@router.put("/renameLocal/{old_name}", tags=["Locals"])
async def rename_local(old_name: str, new_name: str = Body(..., embed=True)):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("UPDATE locals SET name = :new_name WHERE name = :old_name"), {
                "new_name": new_name,
                "old_name": old_name
            })
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Local not found")
            return {"message": "Local renamed successfully"}
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

@router.get("/getLocal/{name}", tags=["Locals"])
def get_local(name: str):
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM locals WHERE name = :name"),
                {"name": name},
            ).mappings().one_or_none()
            if not row:
                raise HTTPException(status_code=404, detail="Local not found")
            return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/updateLocalOpeningHours/{name}")
def update_local_opening_hours(name: str, payload: OpeningHoursPayload):
    hours_dict = {
        day: [r.model_dump() for r in ranges]
        for day, ranges in payload.opening_hours.items()
    }

    valid_days = {str(i) for i in range(7)}
    if not set(hours_dict.keys()).issubset(valid_days):
        raise HTTPException(status_code=400, detail="opening_hours keys must be '0'..'6'")

    opening_hours_json = json.dumps(hours_dict, ensure_ascii=False)

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE locals
                SET opening_hours = :opening_hours
                WHERE name = :name
            """),
            {"name": name, "opening_hours": opening_hours_json}
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Local '{name}' not found")

        saved = conn.execute(
            text("SELECT id, name, opening_hours FROM locals WHERE name = :name"),
            {"name": name}
        ).mappings().one()

    return {"ok": True, "local": {k: v for k, v in saved.items()}}  