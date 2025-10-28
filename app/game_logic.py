import random

#Создание матрицы игрового поля 10 на 10
def create_empty_desk():
    return [[0 for _ in range(10)] for _ in range(10)]

#Проверка возможность разместить корабль
def can_place_ship(desk, ship_length, row, col, horizontal):
    if horizontal:
        #Нельзя выходить за пределы поля
        if col + ship_length > 10:
            return False
        #Проверка места размещения корабля
        for i in range(ship_length):
            if desk[row][col + i] != 0:
                return False
            #Проверка клеток вокруг корабля
            for dr in [-1, 0, 1]: # верх, ряд клетки, низ
                for dc in [-1, 0, 1]: # лево, столбец клетки, право
                    if 0 <= row + dr < 10 and 0 <= col + i + dc < 10: #проверяемая клетка должна быть в пределах поля
                        if desk[row + dr][col + i + dc] != 0 and not (dr == 0 and dc == 0): #проверка занятости соседней клетки
                            return False
    else:
        #Нельзя выходить за пределы поля
        if row + ship_length > 10:
            return False
        #Проверка места размещения корабля
        for i in range(ship_length):
            if desk[row + i][col] != 0:
                return False
            #Проверка клеток вокруг корабля
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if 0 <= row + i + dr < 10 and 0 <= col + dc < 10:
                        if desk[row + i + dr][col + dc] != 0 and not (dr == 0 and dc == 0):
                            return False
        return True

#размещение корабля
def place_ship(desk, ship_length, ship_number, horizontal):
        attempts = 0
        while attempts < 100:  #Выбор случайной клетки на поле до ограничителя
            row = random.randint(0, 9)
            col = random.randint(0, 9)
            
            if can_place_ship(desk, ship_length, row, col, horizontal):
                if horizontal:
                    for i in range(ship_length):
                        desk[row][col + i] = ship_number
                else:
                    for i in range(ship_length):
                        desk[row + i][col] = ship_number
                return True
            attempts += 1
        return False


#создание доски
#корабли пронумерованы от 1 до 10 начиная с самого крупного корабля (4 клетки)
#на игровой доске клетки кораблей будут отмечены их индексом
#попадание проверяется по содержанию клетки, значение клетки меняется на -1, кораблю с нужным индексом снимается одна жизнь
#1 корабль длиной 4
#2 корабля длиной 3
#3 корабля длиной 2
#4 корабля длиной 1
def desk_create():       
    player_desk = create_empty_desk()
    
    ships = {
        4: 1,
        3: 2,
        2: 3,  
        1: 4   
    }
    
    ship_number = 1
    
    #Размещаем корабли для первого игрока
    for ship_length, count in ships.items():
        for _ in range(count):
            placed = False
            attempts = 0
            while not placed and attempts < 100:
                horizontal = random.choice([True, False]) #направление корабля
                placed = place_ship(player_desk, ship_length, ship_number, horizontal)
                attempts += 1
            if placed:
                ship_number += 1

    return player_desk

#упаковка двух досок
def get_desks():
    player1_desk = desk_create()
    player2_desk = desk_create()
    return {
        "player1": player1_desk,
        "player2": player2_desk
    }
