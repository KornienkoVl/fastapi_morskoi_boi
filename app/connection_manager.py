from fastapi import WebSocket

#На один id игры два сокета пользователей
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}
    
    #Создаем подключечение, если его не было
    async def connect(self, websocket: WebSocket, game_id: int):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)
    
    #Убираем сокет игрока при отключении. Если отключились два игрока, удаляем соединение
    def disconnect(self, websocket: WebSocket, game_id: int):
        if game_id in self.active_connections:
            try:
                self.active_connections[game_id].remove(websocket)
                if len(self.active_connections[game_id]) == 0:
                    del self.active_connections[game_id]
            except ValueError:
                pass
    
    #Личное сообщение
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    #бродкаст сообщения всем игрокам
    async def broadcast(self, message: str, game_id: int):
        if game_id in self.active_connections:
            for connection in self.active_connections[game_id]:
                await connection.send_text(message)