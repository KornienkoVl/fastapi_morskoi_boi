from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func, and_, or_
from pydantic import BaseModel
from hashlib import sha256
import random
import json
import datetime

from config_db import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
from models import Base, Player, Game
from game_logic import get_desks
from connection_manager import ConnectionManager

#Подключение к БД и создание сессии
database_url = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
engine = create_async_engine(database_url)
ASession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

#Функция получения асинхронной сессии
async def get_db():
    async with ASession() as session:
        yield session

#Модели для тел запросов
class PlayerLoginPassword(BaseModel):
    login: str
    password: str

class Players_Game(BaseModel):
    player1: int
    player2: int

app = FastAPI()

#Регистрация пользователя. Проверка уникального логина. Проверка ненулевых значений.
@app.post("/players/register")
async def register(player_info: PlayerLoginPassword, db: AsyncSession = Depends(get_db)):

    #Поля не пустые
    if(player_info.login=='' or player_info.password == ''):
        return {'status': "false",         
                'message:': "Поля не должны быть пустыми."}
    
    #Проверка уникальности логина
    request = select(Player).where(Player.login == player_info.login)
    result = await db.execute(request)

    if(result.scalar_one_or_none()):
        return {'status': "false",
                'message:': "Пользователь с таким именем уже существует."}
    
    hash_password = sha256(player_info.password.encode('utf-8')).hexdigest()

    new_player = Player(login=player_info.login, password=hash_password)
    db.add(new_player)
    await db.commit()
    await db.refresh(new_player)
    return {'status': "true",
            'message:': "Успешная регистрация."}

#Авторизация пользователя. Поиск пользователя в БД с переданным логином и паролем.
@app.post("/players/login")
async def login(player_info: PlayerLoginPassword, db: AsyncSession = Depends(get_db)):

    #Поля не пустые
    if(player_info.login=='' or player_info.password == ''):
        return {'status': "false",         
                'message:': "Поля не должны быть пустыми."}

    hash_password = sha256(player_info.password.encode('utf-8')).hexdigest()

    request = select(Player).where(Player.login == player_info.login,
                                Player.password == hash_password)
    result = await db.execute(request)

    if(result.scalar_one_or_none()):
        return {'status': "true",
            'message:': "Успешная авторизация."}
    
    return {'status': "false",
            'message:': "Некорректные данные."}


#Поучение игроков, которые не привязаны к активным играм.
@app.get("/players")
async def get_players(db: AsyncSession = Depends(get_db)):
    #Нахождение игроков в активных играх
    request = select(Game.player1_id).where(Game.date_ended.is_(None)).union(
        select(Game.player2_id).where(Game.date_ended.is_(None))
    )
    
    players_in_game = await db.execute(request)
    players_in_game = [row[0] for row in players_in_game.fetchall()]

    #Запрос всех игроков, которые не привязаны к активным играм
    request = select(Player).where(~Player.id.in_(players_in_game))
    result = await db.execute(request)
    players_free = result.scalars().all()

    return [
        {
            "id": player.id,
            "login": player.login
        }
        for player in players_free
    ]

#Получаем id двух игроков, создаем игровую доску для каждого игрока + кто ходит первым
#Создаем игру и пишем в БД
@app.post("/games/create")
async def game_create(players : Players_Game, db: AsyncSession = Depends(get_db)):

    game_desk = json.dumps(get_desks())
    new_game = Game(
        desk=game_desk,
        player1_id=players.player1,
        player2_id=players.player2,
        current_turn = random.choice([players.player1, players.player2]) #Случайно выбираем, кто ходит первым
    )
    db.add(new_game)
    await db.commit()
    await db.refresh(new_game)

    return {'status': "true",
            'message:': "Игра создана."}

#получить активные игры
@app.get("/games")
async def get_games(db: AsyncSession = Depends(get_db)):

    request = select(Game).where(Game.date_ended.is_(None))
    result = await db.execute(request)

    active_games = result.scalars().all()

    return [
        {
            "id": game.id,
            "desk": json.loads(game.desk)
        }
        for game in active_games
    ]

@app.get("/players/{player_sid}/stats")
async def get_player_stats(player_sid: int, db: AsyncSession = Depends(get_db)):

    player = await db.execute(select(Player).where(Player.id == player_sid))
    player = player.scalar_one_or_none()
    if not player:
        return {'status': "false",
            'message:': "Игрок не найден."}

    request = select(Game).where(and_(or_(Game.player1_id == player_sid, Game.player2_id == player_sid),Game.date_ended.isnot(None)))
    result = await db.execute(request)

    total_games = result.scalars().all()

    return [
        {
            "date": game.date_ended.date(),
            "winner": game.winner_id
        }
        for game in total_games
    ]


#######################################################################################

#Менеджер вебсокетов
manager = ConnectionManager()

@app.websocket("/games/{game_sid}/play")
async def game_ws(websocket: WebSocket, game_sid: int, db: AsyncSession = Depends(get_db), connected_player_id : int = None):

    #Проверка id игры
    request = select(Game).where(Game.id == game_sid)   
    game = await db.execute(request)
    game = game.scalar_one_or_none()

    if not game:
        await websocket.close(code=1002)
        return
    
    #Проверка id игрока
    if (connected_player_id != game.player1_id) and (connected_player_id != game.player2_id):
        await websocket.close(code=1002)
        return

    request1 = select(Player).where(Player.id == game.player1_id)  
    request2 = select(Player).where(Player.id == game.player2_id)  

    player1 = await db.execute(request1)
    player2 = await db.execute(request2)

    player1 = player1.scalar_one_or_none()
    player2 = player2.scalar_one_or_none()

    # Подключаем WebSocket
    await manager.connect(websocket, game.id)
    
    try:
        #Отправляем информацию об игре
        initial_data = {
            "type": "game_info",
            "player1": player1.login,
            "player2": player2.login,
            "turn": game.current_turn
        }
        #Получение досок игроков
        player1_board, player2_board = await process_game_data(game.id, db)

        #передаю обе доски, чтобы игроки могли видеть попадания по доске врага
        initial_data["board1"] = player1_board
        initial_data["board2"] = player2_board

        await manager.send_personal_message(json.dumps(initial_data), websocket)
        
        #Ожидаем сообщения от клиента
        while True:
            message = await websocket.receive_text()
                     
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                await manager.send_personal_message(json.dumps({
                    "type": "error",
                    "message": "Wrong message format"
                }), websocket)
                continue

            #Обработка сообщений  
            #Каждый ход достаем доски из базы и обновляем + изменяем ход    
            if message["type"] == "move":
                await move(websocket, game.id, connected_player_id, message, db)
                
            elif message["type"] == "start_game":
                await start_game(websocket, game.id)
                
            elif message["type"] == "game_over":
                await end_game(websocket, game.id, db)

    except WebSocketDisconnect:
        #Отправляем уведомление об отключении игрока
        manager.disconnect(websocket, game.id)
        disconnect_message = {
            "type": "player_disconnect",
            "message": "Player disconnected"
        }
        await manager.broadcast(json.dumps(disconnect_message), game.id)

    except Exception as e:
        print(f"Websocket error: {e}")
    finally:
        manager.disconnect(websocket, game.id)

#Функция для получения данных игровых досок из БД
async def get_game_desk(game_id: int, db: AsyncSession):
 
    request = select(Game).where(Game.id == game_id)   
    result = await db.execute(request)
    game = result.scalar_one_or_none()   

    desk_data = json.loads(game.desk)
    return desk_data
            

#Разделяем доски игроков
async def process_game_data(game_id: int, db: AsyncSession):

    game_desk = await get_game_desk(game_id, db)
       
    player1_data = game_desk["player1"]
    player2_data = game_desk["player2"]
            
    return player1_data, player2_data

async def move(websocket: WebSocket, game_id: int, player_id: int, message: dict, db: AsyncSession):
    #в сообщении получаем координаты, проверяем попадание, проверяем завершение игры, меняем ход   
    #получаем актуальную информацию об игре
    request = select(Game).where(Game.id == game_id)   
    result = await db.execute(request)
    game = result.scalar_one_or_none()  

    #проверка хода. Если не ход игрока, отправляем сообщение и выходим
    if (player_id != game.current_turn):
        message = {
            "type": "move_false",
            "message": "Not your turn."
        }
        await manager.send_personal_message(json.dumps(message), websocket) 
        return

    #Получить доски
    player1_board, player2_board = await process_game_data(game.id, db)

    #координаты выстрела
    X = message["col"]
    Y = message["row"]
    #По какой доске стреляем
    cur_board = [[]]
    p1 = False
    if(player_id == game.player1_id): cur_board = player2_board
    else: 
        cur_board = player1_board
        p1 = True

    #Получаем значение в месте попадания
    hit_place = cur_board[X][Y]

    #Отмечаем выстрел
    cur_board[X][Y] = -1

    #проверка попадания
    is_hit = False
    if(hit_place >0 ): is_hit = True
    #проверка уничтожения корабля и окончания игры
    kill = False
    game_over = False
    #Если на доске больше нет клеток с индексом корабля, то он уничтожен
    if(is_hit):
        counthit = 0
        countships = 0
        for row in cur_board:
            for index in row:
                if index == hit_place:
                    counthit +=1
                if index > 0:
                    countships +=1
        if(counthit == 0): kill = True
        if(countships == 0): game_over = True       
    #Если промах, то происходит смена хода. Если игра закончена, то ход не меняется (Получаем победителя из game.current_turn)
    else:
        if not(game_over):
            if(game.current_turn == game.player1_id): game.current_turn = game.player2_id
            else: game.current_turn = game.player1_id

    #Сохранение изменений в базу данных
    if(p1):
        desk = {
            "player1": cur_board,
            "player2": player2_board
        }
    else:
        desk = {
            "player1": player1_board,
            "player2": cur_board
        }

    game.desk = json.dumps(desk)

    await db.commit()
    await db.refresh(game)

    #Посылаем сообщение
    message = {
        "type": "move_result",
        "hit": is_hit,
        "kill": kill,
        "game_over": game_over
    }

    await manager.broadcast(json.dumps(message), game_id)
    return


async def start_game(websocket: WebSocket, game_id: int):
    #проверка двух подключений + бродкаст сообщения о начале
    if len(manager.active_connections[game_id]) != 2:
        message = {
            "type": "start_game_false",
            "message": "Wait for second player!"
        }
    else:
        message = {
            "type": "start_game_true",
            "message": "Game start!"
        }
    await manager.broadcast(json.dumps(message), game_id)
    return

async def end_game(websocket: WebSocket, game_id: int, db: AsyncSession):
    #заканчиваем игру. Записываем в базу дату окончания и победителя

    #получаем актуальную информацию об игре
    request = select(Game).where(Game.id == game_id)   
    result = await db.execute(request)
    game = result.scalar_one_or_none() 

    game.date_ended = datetime.datetime.utcnow()
    game.winner_id = game.current_turn

    await db.commit()

    message = {
            "type": "end_game_true",
            "message": f"Game over! Winner: {game.winner_id}"          
        }
    
    await manager.broadcast(json.dumps(message), game_id)

    return


