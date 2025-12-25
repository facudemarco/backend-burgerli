import uuid
from fastapi import APIRouter, HTTPException, Body
from sqlalchemy import text
from Database.getConnection import engine
from sqlalchemy.exc import OperationalError
from typing import Optional
import uuid

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
        