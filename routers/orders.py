from typing import List, Optional
from fastapi import APIRouter, HTTPException, Form, Body, UploadFile, File
import os
import shutil
from sqlalchemy import text
from Database.getConnection import engine
import uuid
from models.order import OrderMan
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from enum import Enum
from pydantic import BaseModel
import time
from routers.testingWebSocket import manager
import json
from datetime import datetime, timezone

router = APIRouter()

IMAGES_DIR = "images/"
DOMAIN_URL = "https://burgerli.com.ar/MdpuF8KsXiRArNIHtI6pXO2XyLSJMTQ8_Burgerli/api/images"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(PROJECT_ROOT, "images")

@router.post("/createOrder", tags=["Orders"])
async def create_order(order: OrderMan):
    try:
        now = datetime.now(timezone.utc).isoformat()
        id_order = str(uuid.uuid4())
        user_client_id = None
        if order.user_client_id:
            try:
                uuid.UUID(order.user_client_id)
                user_client_id = order.user_client_id
            except (ValueError, AttributeError):
                user_client_id = None
        
        payment_method = order.payment_method
        delivery_mode = order.delivery_mode
        price = order.price
        delivery_time = order.delivery_time
        status = "confirmed"
        created_at = now
        local = order.local
        order_notes = order.order_notes
        name = order.name
        phone = order.phone
        email = order.email
        address = order.address
        products = order.products or []
        coupon = order.coupon

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO orders (id_order, id_user_client, payment_method, delivery_mode, price, delivery_time, status, order_notes, local, name, phone, email, address, coupon)
                VALUES (:id_order, :id_user_client, :payment_method, :delivery_mode, :price, :delivery_time, :status, :order_notes, :local, :name, :phone, :email, :address, :coupon)
            """), {
                "id_order": id_order,
                "id_user_client": user_client_id,
                "payment_method": payment_method,
                "delivery_mode": delivery_mode,
                "price": price,
                "delivery_time": delivery_time,
                "status": status, 
                "order_notes": order_notes,
                "local": local,
                "name": name,
                "phone": phone,
                "email": email,
                "address": address,
                "coupon": coupon
            })

             # Insert products (cada producto es un dict -> JSON string)
            for product in products:
                id_order_products = str(uuid.uuid4())

                # Si es string: convertir a dict (asumir que es JSON)
                # Si es dict: usar tal cual
                # Si es Pydantic model: usar model_dump()
                if isinstance(product, str):
                    try:
                        payload = json.loads(product)
                    except:
                        payload = {"raw": product}
                elif isinstance(product, dict):
                    payload = product
                else:
                    payload = product.model_dump()

                conn.execute(
                    text("""
                        INSERT INTO order_products (id, products, order_id)
                        VALUES (:id, :products, :order_id)
                    """),
                    {
                        "id": id_order_products,
                        "products": json.dumps(payload, ensure_ascii=False),
                        "order_id": id_order,
                    }
                )

            # ACA VA WEBSOCKET
                # 2️⃣ Notificar a dashboards
            message_dashboard = {
                "event": "new_order",
                "pedido": {
                    "id_order": id_order,
                    "user_client_id": user_client_id,
                    "payment_method": payment_method,
                    'created_at': created_at,
                    "delivery_mode": delivery_mode,
                    "price": price,
                    "delivery_time": delivery_time,
                    "status": status, 
                    "order_notes": order_notes,
                    "local": local,
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "address": address,
                    'products': products
                },
                'order_id': id_order
            }
            await manager.broadcast_to_dashboards(message_dashboard)
            
            # Transaction will auto-commit here
            return {"message": "Order created successfully", "order_id": id_order}
        
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

@router.get("/getOrders", tags=["Orders"])
async def get_orders():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM orders"))

            products = []
            for row in result.mappings().all():
                order_id = row['id_order']
                prod_result = conn.execute(text("SELECT products FROM order_products WHERE order_id = :order_id"), {"order_id": order_id})
                product_list = [prod_row['products'] for prod_row in prod_result.mappings().all()]
                row = dict(row)
                row['products'] = product_list
                products.append(row)

            return products
        
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
@router.get("/getOrderById/{id_order}", tags=["Orders"])
async def get_order_by_id(id_order: str):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM orders WHERE id_order = :id_order"), {"id_order": id_order})
            order = result.mappings().first()
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            prod_result = conn.execute(text("SELECT products FROM order_products WHERE order_id = :order_id"), {"order_id": id_order})
            product_list = [prod_row['products'] for prod_row in prod_result.mappings().all()]

            order = dict(order)
            order['products'] = product_list
            return order
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
@router.put("/updateOrderStatus/{id_order}", tags=["Orders"])
async def update_order_status_simple(id_order: str, status: str = Body(..., embed=True)):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("UPDATE orders SET status = :status WHERE id_order = :id_order"), {
                "status": status,
                "id_order": id_order
            })
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Order not found")
            
            # Coupon update logic for PUT endpoint
            if status == "delivered":
                # 1) user_client_id de la orden
                row_order = conn.execute(
                    text("SELECT id_user_client FROM orders WHERE id_order = :id_order"),
                    {"id_order": id_order},
                ).mappings().first()

                user_client_id = row_order["id_user_client"] if row_order else None

                if user_client_id:
                    # 2) obtener el coupon de la orden
                    row_coupon = conn.execute(
                        text("SELECT coupon FROM orders WHERE id_order = :id_order"),
                        {"id_order": id_order},
                    ).mappings().first()

                    coupon_code = row_coupon["coupon"] if row_coupon else None

                    if coupon_code:
                        # Resolver ID del cupon usando el nombre/código
                        row_coupon_id = conn.execute(
                            text("SELECT id FROM coupons WHERE name = :code"),
                            {"code": coupon_code}
                        ).mappings().first()

                        real_coupon_id = row_coupon_id["id"] if row_coupon_id else None

                        if real_coupon_id:
                            usage_id = str(uuid.uuid4())
                            conn.execute(
                                text("""
                                    INSERT INTO user_client_coupon_usage (id, user_client_id, coupon_id, order_id)
                                    VALUES (:id, :user_client_id, :coupon_id, :order_id)
                                    ON DUPLICATE KEY UPDATE id = id    
                                """),
                                {
                                    "id": usage_id,
                                    "user_client_id": user_client_id,
                                    "coupon_id": real_coupon_id,
                                    "order_id": id_order,
                                },
                            )

            return {"message": "Order status updated successfully"}
    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    
class OrderStatus(str, Enum):
    confirmed = "confirmed" 
    in_preparation = "in_preparation"
    on_the_way = "on_the_way"     
    delivered = "delivered"

VALID_TRANSITIONS = {
    "confirmed": {"in_preparation"},
    "in_preparation": {"on_the_way", "delivered"},
    "on_the_way": {"delivered"},
    "delivered": set(),
}

@router.get("/getOrdersByLocalStatusConfirmed/{local}", tags=["Orders"])
async def get_orders_by_local_status_confirmed(local: str):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM orders WHERE local = :local AND status = 'confirmed'"),
                {"local": local},
            )

            orders = []
            for row in result.mappings().all():
                order_id = row['id_order']
                prod_result = conn.execute(
                    text("SELECT products FROM order_products WHERE order_id = :order_id"),
                    {"order_id": order_id},
                )
                product_list = [prod_row['products'] for prod_row in prod_result.mappings().all()]
                row = dict(row)
                row['products'] = product_list
                orders.append(row)

            return orders

    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

@router.get("/getOrdersByLocalStatus/{local}/{status}", tags=["Orders"])
async def get_orders_by_local_status(local: str, status: str):
    allowed_statuses = ["confirmed", "in_preparation", "on_the_way"]
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f'El estado debe ser uno de: {", ".join(allowed_statuses)}'
        )
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM orders WHERE local = :local AND status = :status ORDER BY id_order DESC"),
                {"local": local, "status": status},
            )

            orders = []
            for row in result.mappings().all():
                order_id = row['id_order']
                prod_result = conn.execute(
                    text("SELECT products FROM order_products WHERE order_id = :order_id"),
                    {"order_id": order_id},
                )
                product_list = [prod_row['products'] for prod_row in prod_result.mappings().all()]
                row = dict(row)
                row['products'] = product_list
                orders.append(row)

            return orders

    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

class StatusUpdate(BaseModel):
    status: OrderStatus

@router.patch("/{id_order}/status", tags=["Orders"])
async def update_order_status(
    id_order: str,
    body: StatusUpdate = Body(..., embed=False),
):
    try:
        with engine.begin() as conn:
            # 1) Traer estado actual
            row = conn.execute(
                text("SELECT status FROM orders WHERE id_order = :id_order"),
                {"id_order": id_order},
            ).mappings().first()

            if not row:
                raise HTTPException(status_code=404, detail="Order not found")

            old_status: str = row["status"]
            # si StatusUpdate usa Enum, .value te deja el string
            new_status: str = body.status.value

            # 2) Validar transición
            if old_status not in VALID_TRANSITIONS:
                # si no está en el dict, dejás pasar (como ya tenías)
                pass
            else:
                if (
                    new_status not in VALID_TRANSITIONS[old_status]
                    and new_status != old_status
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=f"Invalid transition: {old_status} -> {new_status}",
                    )

            # 3) Si no cambió nada, devolvés y NO emitís eventos
            if new_status == old_status:
                return {
                    "message": "Order status unchanged",
                    "id_order": id_order,
                    "old_status": old_status,
                    "new_status": new_status,
                }

            # 4) Actualizar en la DB
            result = conn.execute(
                text(
                    """
                    UPDATE orders
                    SET status = :status
                    WHERE id_order = :id_order
                    """
                ),
                {"status": new_status, "id_order": id_order},
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Order not found")

            # Coupon update
            if new_status == "delivered":
                # 1) user_client_id de la orden
                row_order = conn.execute(
                    text("SELECT id_user_client FROM orders WHERE id_order = :id_order"),
                    {"id_order": id_order},
                ).mappings().first()

                user_client_id = row_order["id_user_client"] if row_order else None

                if user_client_id:
                    # 2) obtener el coupon de la orden
                    row_coupon = conn.execute(
                        text("SELECT coupon FROM orders WHERE id_order = :id_order"),
                        {"id_order": id_order},
                    ).mappings().first()

                    coupon_code = row_coupon["coupon"] if row_coupon else None

                    if coupon_code:
                        # Resolver ID del cupon usando el nombre/código
                        row_coupon_id = conn.execute(
                            text("SELECT id FROM coupons WHERE name = :code"),
                            {"code": coupon_code}
                        ).mappings().first()

                        real_coupon_id = row_coupon_id["id"] if row_coupon_id else None

                        if real_coupon_id:
                            usage_id = str(uuid.uuid4())
                            conn.execute(
                                text("""
                                    INSERT INTO user_client_coupon_usage (id, user_client_id, coupon_id, order_id)
                                    VALUES (:id, :user_client_id, :coupon_id, :order_id)
                                    ON DUPLICATE KEY UPDATE id = id    
                                """),
                                {
                                    "id": usage_id,
                                    "user_client_id": user_client_id,
                                    "coupon_id": real_coupon_id,
                                    "order_id": id_order,
                                },
                            )

        # 5) Armar payload común para WS
        payload = {
            "event": "status_update",
            "id_order": id_order,
            "old_status": old_status,
            "new_status": new_status,
        }

        # 6) Avisar a la TIENDA (solo esa orden)
        await manager.broadcast_order(id_order, payload)

        # 7) Avisar a TODOS los DASHBOARDS
        await manager.broadcast_to_dashboards(payload)

        print(f"[PATCH /orders/{id_order}/status] status updated successfully")
        print(f"payload: {payload}")
        # 8) Respuesta HTTP
        return {
            "message": "Order status updated successfully",
            **payload,
        }
    except HTTPException:
        # re-lanzo las HTTPException tal cual
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[PATCH /orders/{id_order}/status] error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    
@router.delete("/deleteOrder/{id_order}", tags=["Orders"])
async def delete_order(id_order: str):
    try:
        with engine.begin() as conn:
            # 1) Eliminar dependencias
            conn.execute(
                text("DELETE FROM order_products WHERE order_id = :order_id"),
                {"order_id": id_order},
            )


            # 2) Eliminar la orden
            result = conn.execute(
                text("DELETE FROM orders WHERE id_order = :id_order"),
                {"id_order": id_order},
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Order not found")

        # 3) Payload WS (igual que PATCH pero con otro event)
        payload = {
            "event": "order_deleted",
            "id_order": id_order,
        }

        # DEBUG: ver si el manager tiene conexiones
        print("[DELETE] manager id:", id(manager))
        print("[DELETE] order_connections keys:", list(manager.order_connections.keys()))
        print("[DELETE] dashboards activos:", len(manager.dashboard_connections))

        # 4) Avisar a la TIENDA (tracking de esa orden)
        await manager.broadcast_order(id_order, payload)

        # 5) Avisar a TODOS los DASHBOARDS
        await manager.broadcast_to_dashboards(payload)

        # 6) Respuesta HTTP
        return {
            "message": "Order deleted successfully",
            **payload,
        }

    except OperationalError as e:
        print(f"Database connection error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection error: {str(e)}",
        )
    except Exception as e:
        print(f"[DELETE /deleteOrder/{id_order}] error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")