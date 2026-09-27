from fastapi import WebSocket


class Hub:
    def __init__(self): self.clients: set[WebSocket] = set(); self.redis = None
    async def connect(self, ws: WebSocket): await ws.accept(); self.clients.add(ws)
    def disconnect(self, ws: WebSocket): self.clients.discard(ws)
    async def broadcast(self, kind: str, payload: dict):
        message = {"type": kind, "payload": payload}
        dead = []
        for ws in self.clients:
            try: await ws.send_json(message)
            except Exception: dead.append(ws)
        for ws in dead: self.disconnect(ws)

hub = Hub()

