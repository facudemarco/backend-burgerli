import os
from typing import Dict, List, Optional
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Verificador WS y excepción custom (como ya tenías)
from auth.authentication import get_current_user_ws, WSAuthError

router = APIRouter()




class OrderConnectionManager:
    """
    Maneja dos tipos de conexiones:
    - order_connections: conexiones de TIENDA, una o más pestañas escuchando UNA order_id
    - dashboard_connections: conexiones de DASHBOARD, escuchan TODOS los eventos
    """

    def __init__(self) -> None:
        # {order_id: [WebSocket, WebSocket, ...]}
        self.order_connections: Dict[str, List[WebSocket]] = {}
        # [WebSocket, WebSocket, ...]
        self.dashboard_connections: List[WebSocket] = []
        # {local_id: [WebSocket, WebSocket, ...]}
        self.local_connections: Dict[str, List[WebSocket]] = {}

    # ---------- TIENDA (por order_id) ----------

    async def connect_order(self, order_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.order_connections.setdefault(order_id, []).append(websocket)
        print(f"[WS] conectado seguimiento order_id={order_id}")

    def disconnect_order(self, order_id: str, websocket: WebSocket) -> None:
        conns = self.order_connections.get(order_id)
        if not conns:
            return

        if websocket in conns:
            conns.remove(websocket)

        if not conns:
            # si no quedan conexiones para esa orden, la sacamos del dict
            self.order_connections.pop(order_id, None)

        print(f"[WS] desconectado seguimiento order_id={order_id}")

    async def broadcast_order(self, order_id: str, message: dict) -> None:
        """
        Envía un mensaje solo a las conexiones de tienda que estén
        escuchando esa order_id.
        """
        conns = self.order_connections.get(order_id)
        print(f"[BROADCAST_ORDER] order_id={order_id}, conexiones={len(conns) if conns else 0}, total_orders={len(self.order_connections)}")
        if not conns:
            print(f"[BROADCAST_ORDER] No hay conexiones para order_id={order_id}")
            return

        text = json.dumps(message)
        for ws in list(conns):
            try:
                await ws.send_text(text)
            except Exception as e:
                print(f"[WS] error al enviar a order_id={order_id}: {e}")
                self.disconnect_order(order_id, ws)

    # ---------- DASHBOARD (todas las órdenes) ----------

    async def connect_dashboard(self, websocket: WebSocket, user_id: Optional[str] = None) -> None:
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        print(f"[WS] dashboard conectado: {user_id or id(websocket)}")

    def disconnect_dashboard(self, websocket: WebSocket) -> None:
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
            print("[WS] dashboard desconectado")

    async def broadcast_to_dashboards(self, message: dict) -> None:
        """
        Envía un mensaje a TODOS los dashboards conectados.
        """
        print(f"[DEBUG] Dashboards activos: {len(self.dashboard_connections)}")
        print(f"[BROADCAST DASHBOARDS] manager={id(self)} dashboards={len(self.dashboard_connections)}")
        print(f"[BROADCAST DASHBOARDS] message={message}")
        text = json.dumps(message)

        for ws in list(self.dashboard_connections):
            try:
                await ws.send_text(text)
            except Exception as e:
                print(f"[WS] error broadcast dashboard: {e}")
                try:
                    await ws.close()
                except Exception:
                    pass
                self.disconnect_dashboard(ws)

    # ---------- LOCAL (dashboards por local) ----------

    async def connect_local(self, local_id: str, websocket: WebSocket) -> None:
        """Conectar dashboard de un local específico"""
        await websocket.accept()
        self.local_connections.setdefault(local_id, []).append(websocket)
        print(f"[WS] Local '{local_id}' conectado")

    def disconnect_local(self, local_id: str, websocket: WebSocket) -> None:
        """Desconectar dashboard de un local"""
        conns = self.local_connections.get(local_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                self.local_connections.pop(local_id, None)
        print(f"[WS] Local '{local_id}' desconectado")

    async def broadcast_to_local(self, local_id: str, message: dict) -> None:
        """Enviar evento solo a un local específico"""
        conns = self.local_connections.get(local_id)
        print(f"[BROADCAST_LOCAL] local_id={local_id}, conexiones={len(conns) if conns else 0}")
        if not conns:
            print(f"[BROADCAST_LOCAL] No hay conexiones para local={local_id}")
            return
        
        text = json.dumps(message)
        for ws in list(conns):
            try:
                await ws.send_text(text)
            except Exception as e:
                print(f"[WS] error broadcast local {local_id}: {e}")
                self.disconnect_local(local_id, ws)


manager = OrderConnectionManager()

@router.websocket("/ws/orders/{order_id}")
async def websocket_order_tracking(websocket: WebSocket, order_id: str):
    """
    Conexión de la TIENDA (cliente final), para seguir una orden específica.

    URL: ws://.../ws/orders/{order_id}?token=...
    - order_id: id de la orden (string)
    - token: opcional, se valida con get_current_user_ws
    """

    token = websocket.cookies.get("Authorization")


    # Opcional: validar token (si lo mandás desde la tienda)
    if token:
        try:
            user_id = await get_current_user_ws(token)
            print(f"[WS TRACKING] user_id={user_id} escuchando order_id={order_id}")
        except WSAuthError as e:
            print(f"[WS TRACKING AUTH] rechazo: {e}")
            try:
                await websocket.close(code=e.code)
            except Exception:
                pass
            return
        except Exception as e:
            print(f"[WS TRACKING AUTH ERROR] {e}")
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            return

    await manager.connect_order(order_id, websocket)
    print(f"[WS] TRACKING conectado. manager id={id(manager)}  order_id={order_id}  total_conns={len(manager.order_connections)}")
    try:
        # En este caso no esperamos mensajes de la tienda,
        # solo mantenemos viva la conexión.
        while True:
            # si querés soportar ping del cliente, podés hacer un parse del mensaje acá
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_order(order_id, websocket)
    except Exception as e:
        print(f"[WS TRACKING LOOP ERROR] {e}")
        manager.disconnect_order(order_id, websocket)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


# =====================================================
#   WS Dashboard: escucha TODAS las órdenes
#   wss://tu-dominio.com/ws/orders
# =====================================================
@router.websocket("/ws/orders")
async def websocket_dashboard(websocket: WebSocket):
    """
    Conexión del DASHBOARD.

    URL: ws://.../ws/orders?token=...

    Si hay token:
      - lo validamos y usamos el user_id solo para logs.
    Si no hay token:
      - se conecta como dashboard anónimo (útil para testeo).
    """

    token = websocket.cookies.get("Authorization")

    user_id: Optional[str] = None
    print(f"[WS CONNECT REAL] manager id={id(manager)}")
    print(f"[WS CONNECT REAL] dashboards={len(manager.dashboard_connections)}")
    print(f"[WS CONNECT REAL] orders={list(manager.order_connections.keys())}")
    print(f"[WS CONNECT] pid={os.getpid()} manager id={id(manager)}")
    print(f"[WS CONNECT] dashboards={len(manager.dashboard_connections)}")
    print(f"[WS CONNECT] orders={list(manager.order_connections.keys())}")
    # Autenticación/identidad durante el handshake
    try:
        if token:
            user_id = await get_current_user_ws(token)
        else:
            user_id = f"dashboard_{id(websocket)}"

        await manager.connect_dashboard(websocket, user_id)
        print(f"[WS] DASHBOARD conectado. manager id={id(manager)}  total_dash={len(manager.dashboard_connections)}")
    except WSAuthError as e:
        try:
            await websocket.close(code=e.code)
        except Exception:
            pass    
        print(f"[WS DASHBOARD AUTH] rechazo: {e}")
        return
    except Exception as e:
        print(f"[WS DASHBOARD AUTH ERROR] {e}")
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
        return

    print(f"[WS] Nueva conexión dashboard desde: {websocket.client.host} user_id={user_id}")

    try:
        while True:
            data_raw = await websocket.receive_text()
            print(f"[WS DASHBOARD] Recibido: {data_raw}")

            # Si querés, acá podés manejar pings o futuros comandos del dashboard
            try:
                data = json.loads(data_raw)
            except Exception:
                # mensaje no JSON -> lo ignoramos
                continue

            event = data.get("event")

            # Ejemplo: ping/pong
            if event == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))

            # Si en el futuro querés manejar otras cosas por WS, lo agregás acá
            # (pero para cambio de estado es más prolijo usar HTTP PATCH)
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
    except Exception as e:
        print(f"[WS DASHBOARD LOOP ERROR] {e}")
        manager.disconnect_dashboard(websocket)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

@router.websocket("/ws/local/{local_id}")
async def websocket_local_dashboard(websocket: WebSocket, local_id: str):
    """
    Conexión del dashboard de un LOCAL específico.
    Recibe eventos solo de órdenes transferidas a ese local.
    
    URL: ws://.../ws/local/{local_id}
    """
    await manager.connect_local(local_id, websocket)
    print(f"[WS LOCAL] conectado para local_id={local_id}")
    
    try:
        while True:
            # Mantener viva la conexión, sin esperar mensajes del cliente
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_local(local_id, websocket)
    except Exception as e:
        print(f"[WS LOCAL LOOP ERROR] {e}")
        manager.disconnect_local(local_id, websocket)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass