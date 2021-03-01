import pygame
from pygame.locals import *
from pygame.math import Vector2
from math import cos
import os


def load_image(name, colorkey=None):
    fullname = os.path.join('data', name)
    # если файл не существует, то выходим
    if not os.path.isfile(fullname):
        print(f"Файл с изображением '{fullname}' не найден")
        raise SystemExit
    image = pygame.image.load(fullname)
    if colorkey is not None:
        image = image.convert()
        if colorkey == -1:
            colorkey = image.get_at((0, 0))
        image.set_colorkey(colorkey)
    else:
        image = image.convert_alpha()
    return image


# класс машинки
class Car(pygame.sprite.Sprite):
    cars = set()
    # метки на поле по мере прохождения поля для корректной проверки прохождения круга
    mark = [pygame.Rect(25, 180, 150, 20), pygame.Rect(1000, 350, 200, 50), pygame.Rect(620, 550, 50, 150)]

    def __init__(self, n, buttons, position):
        super().__init__(all_sprites)
        self.add(all_sprites)
        # количество пройденных меток
        self.progress = 1
        # количество пройденных кругов
        self.lap = "1/3"
        Car.cars.add(self)

        self.original_image = load_image("car{}.png".format(n))
        x, y = self.original_image.get_width(), self.original_image.get_height()
        self.original_image = pygame.transform.scale(self.original_image, (x // 16, y // 16))
        self.image = self.original_image
        self.mask = pygame.mask.from_surface(self.original_image)

        # среди входных параметров машинки есть набор кнопок для её управления
        self.front = buttons[0]
        self.left = buttons[1]
        self.back = buttons[2]
        self.right = buttons[3]

        # позиция машинки будет определяться радиус-вектором из начала координат
        self.position = Vector2(position)
        # скорость машинки при нормальной езде
        self.speed = 0
        # скорость машинки после удара. до остановки управление невозможно
        self.nspeed = 0
        # скорость машинки ровно перед ударом, определяется перед каждым столкновением
        self.crash_speed = self.nspeed
        # угол от вертикали на который повёрнута машинка
        self.angle = 0
        # угол направления скорости машинки при нормальной езде
        self.direction = Vector2(0, -1)
        # угол направления скорости после удара
        self.ndirection = Vector2(0, -1)
        # угол направления скорости непосредственно перед ударом
        self.crash_direction = self.ndirection
        self.rect = pygame.Rect(self.position, self.image.get_size())

    def update(self):
        # обработка столкновений
        self.update_crash()
        if self.nspeed:
            # то есть машинка попала в столкновение
            self.update_broken()
        else:
            # то есть машинка едет в нормальном состоянии
            self.update_normal()
        screen.blit(self.image, self.rect)

    def update_crash(self):
        # обработка меток на поле для учёта прогресса в гонке
        for i in range(3):
            # если машинка заезжает в пространство метки
            if Car.mark[i].collidepoint(self.rect.center):
                # если это следующая метка
                if self.progress % 3 == i:
                    self.progress += 1
                # если это предыдущая метка
                elif (self.progress + 1) % 3 == i:
                    self.progress -= 1
                # если пройден круг
                if self.progress > 9:
                    self.lap = "win"
                elif self.progress > 6:
                    self.lap = "3/3"
                elif self.progress > 3:
                    self.lap = "2/3"
        # обработка ударов о стену
        for wall in Wall.walls:
            if pygame.sprite.collide_mask(self, wall):
                # удар происходит по закону отражения
                # скорость не меняется по модулю
                # направление скорости отражается симметрично от стенки
                self.crash_speed = self.nspeed + self.speed * (self.nspeed == 0)
                self.crash_direction = self.ndirection * (self.nspeed != 0) + self.direction * (self.nspeed == 0)
                self.nspeed, self.speed = self.crash_speed, 0
                self.ndirection = self.crash_direction.reflect(wall.normal)
        # обработка столкновений машинок
        for car in Car.cars - {self}:
            if pygame.sprite.collide_mask(self, car):
                # определяем скорости и их направления перед ударом
                self.crash_speed = self.nspeed + self.speed * (self.nspeed == 0)
                car.crash_speed = car.nspeed + car.speed * (car.nspeed == 0)
                self.crash_direction = self.ndirection * (self.nspeed != 0) + self.direction * (self.nspeed == 0)
                car.crash_direction = car.ndirection * (car.nspeed != 0) + car.direction * (car.nspeed == 0)
                # используется упрощенная модель столкновений
                # определяется, какая из машинок врезается в другую с помощью функции is_predator
                # если только одна машинка True, то осуществляется вариант "хищник - жертва"
                # если обе машинки True, то осуществляется вариант "лобовое столкновение"
                if self.is_predator(car) and not car.is_predator(self):
                    self.crash_predator(car)
                    car.crash_prey(self)
                if car.is_predator(self) and not self.is_predator(car):
                    car.crash_predator(self)
                    self.crash_prey(car)
                else:
                    self.head_on_crash(car)
                    car.head_on_crash(self)
                # обнуление первоначальных скоростей
                self.speed = 0
                car.speed = 0

    # проверка, является ли машинка нападающей
    def is_predator(self, car):
        # если машинка не едет, то она не хищник
        if not self.crash_speed:
            return False
        # преобразование пространства к удобному виду
        vec, vec1 = self.transform(car, self.crash_speed * self.crash_direction)
        # если краевые удары
        if min(vec1, key=lambda v: v.x).x > max(vec, key=lambda v: v.x).x:
            return False
        if min(vec, key=lambda v: v.x).x > max(vec1, key=lambda v: v.x).x:
            return False
        # если изучаемая машинка отдаляется от другой (но тогда её догоняла вторая машинка - хищник)
        if min(vec, key=lambda v: v.y).y > max(vec1, key=lambda v: v.y).y:
            return False
        return True

    # столкновения
    def head_on_crash(self, car):
        # машинки обмениваются скоростями
        self.ndirection = car.crash_direction * car.crash_speed
        self.nspeed = self.ndirection.magnitude()
        try:
            self.ndirection.normalize_ip()
        except ValueError:
            self.ndirection = self.crash_direction

    def crash_predator(self, car):
        angle = self.crash_direction.angle_to(car.crash_direction)
        self.nspeed = int(car.crash_speed * cos(angle))
        self.ndirection = car.crash_direction * (cos(angle) >= 0 - cos(angle) < 0)

    def crash_prey(self, car):
        car.crash_predator(self)
        self.ndirection *= self.nspeed
        self.ndirection += car.crash_speed * car.crash_direction
        self.ndirection -= car.nspeed * car.ndirection
        self.nspeed = self.ndirection.magnitude()
        try:
            self.ndirection.normalize_ip()
        except ValueError:
            self.ndirection = self.crash_direction

    # если не было столкновений
    def update_normal(self):
        # управление машинкой
        keys = pygame.key.get_pressed()
        if keys[self.front] and not self.nspeed:
            self.speed += 3
        if keys[self.back] and not self.nspeed:
            self.speed -= 3
        if (keys[self.left] or keys[self.right]) and not self.nspeed:
            d_angle = self.speed / fps * (keys[self.right] - keys[self.left])
            self.direction.rotate_ip(d_angle)
            self.angle += d_angle
            self.image = pygame.transform.rotate(self.original_image, -self.angle)
            self.rect = self.image.get_rect(center=self.rect.center)
            self.mask = pygame.mask.from_surface(self.image)
        # замедление машинки при бездействии
        self.speed = abs(self.speed) * 99 // 100 * ((self.speed > 0) - (self.speed < 0))
        self.position += self.direction * self.speed / fps
        self.rect.center = self.position

    def update_broken(self):
        # машинка движется после столкновения
        self.nspeed = abs(self.nspeed) * 99 // 100 * ((self.nspeed > 0) - (self.nspeed < 0))
        self.position += self.ndirection * self.nspeed / fps
        self.rect.center = self.position

    # преобразование пространства для определения типа столкновения
    def transform(self, car, speed):
        vec, vec1 = [], []
        vec += [Vector2(- self.image.get_height() // 2, - self.image.get_width())]
        vec += [Vector2(- self.image.get_height() // 2, self.image.get_width())]
        vec += [Vector2(self.image.get_height() // 2, self.image.get_width())]
        vec += [Vector2(self.image.get_height() // 2, - self.image.get_width())]
        vec1 += [Vector2(- car.image.get_height() // 2, - car.image.get_width())]
        vec1 += [Vector2(- car.image.get_height() // 2, car.image.get_width())]
        vec1 += [Vector2(car.image.get_height() // 2, car.image.get_width())]
        vec1 += [Vector2(car.image.get_height() // 2, - car.image.get_width())]
        angle = Vector2(0, -1).angle_to(speed)
        for i in range(4):
            vec[i] = vec[i].rotate(self.angle) + Vector2(self.rect.center)
            vec1[i] = vec1[i].rotate(car.angle) + Vector2(car.rect.center)
            vec[i].rotate_ip(-angle)
            vec1[i].rotate_ip(-angle)
        return vec, vec1


class Wall(pygame.sprite.Sprite):
    walls = []
    # цвет стен
    colors = ["red", "pink", "yellow", "green", "blue", "purple"]

    def __init__(self, p1, p2):
        super().__init__(all_sprites)
        self.add(all_sprites)
        Wall.walls.append(self)
        x1, y1 = p1
        x2, y2 = p2
        self.normal = Vector2(x2 - x1, y2 - y1)
        # угол, на который повёрнута стена
        angle = Vector2.angle_to(self.normal, Vector2(0, 1))
        # вектор нормали к стене
        self.normal = Vector2(y2 - y1, x1 - x2)
        # выбор цвета стены
        color = Wall.colors.pop(0)
        Wall.colors += [color]
        self.image = load_image("{}.png".format(color))
        self.image = pygame.transform.scale(self.image, (10, int(self.normal.length()) + 5))
        self.image = pygame.transform.rotate(self.image, angle)
        self.mask = pygame.mask.from_surface(self.image)
        x, y = min(x1, x2), min(y1, y2)
        w, h = self.image.get_width(), self.image.get_height()
        self.rect = pygame.Rect((x, y), (w, h))

    def update(self):
        screen.blit(self.image, self.rect)


# отрисовка главного меню
def menu_view():
    screen.fill((0, 0, 0))
    screen.blit(full_background, (0, 0))
    font = pygame.font.Font(None, 100)

    title = font.render("Cars crusaders", True, pygame.color.Color("cyan"))
    title_x = width // 2 - title.get_width() // 2
    title_y = height // 4 - title.get_height() // 2
    title_w = title.get_width()
    title_h = title.get_height()
    screen.blit(title, (title_x, title_y))
    pygame.draw.rect(screen, (0, 255, 0), (title_x - 10, title_y - 10,
                                           title_w + 20, title_h + 20), 1)

    race_button = font.render("Race", True, pygame.color.Color("cyan"))
    race_x = width // 2 - race_button.get_width() // 2
    race_y = 2 * height // 4 - race_button.get_height() // 2
    race_w = race_button.get_width()
    race_h = race_button.get_height()
    screen.blit(race_button, (race_x, race_y))
    race_rect = (race_x - 10, race_y - 10, race_w + 20, race_h + 20)
    pygame.draw.rect(screen, (0, 255, 0), race_rect, 1)

    hunt_button = font.render("Hunt", True, pygame.color.Color("cyan"))
    hunt_x = width // 2 - hunt_button.get_width() // 2
    hunt_y = 3 * height // 4 - hunt_button.get_height() // 2
    hunt_w = hunt_button.get_width()
    hunt_h = hunt_button.get_height()
    screen.blit(hunt_button, (hunt_x, hunt_y))
    hunt_rect = pygame.Rect(hunt_x - 10, hunt_y - 10, hunt_w + 20, hunt_h + 20)
    pygame.draw.rect(screen, (0, 255, 0), hunt_rect, 1)
    return pygame.Rect(race_rect), pygame.Rect(hunt_rect)


# отрисовка окна выбора машинок
def draw_choose(cars, mode=1, p=1, n1=1, n2=0):
    screen.fill((0, 0, 0))
    screen.blit(full_background, (0, 0))

    for i in range(6):
        for j in range(3):
            if n1 == 3 * i + j + 1:
                pygame.draw.rect(screen, "red", (265 + i * 150, 110 + j * 150, 120, 120))
            if n2 == 3 * i + j + 1:
                pygame.draw.rect(screen, "blue", (265 + i * 150, 110 + j * 150, 120, 120))
            screen.blit(cars[3 * i + j], (275 + i * 150, 120 + j * 150))

    font = pygame.font.Font(None, 50)

    button1 = font.render("1 Player", True, (0, 355 - 100 * mode, 355 - 100 * mode))
    b1x = 500 - button1.get_width() // 2
    b1y = 570 - button1.get_height() // 2
    b1w = button1.get_width()
    b1h = button1.get_height()
    screen.blit(button1, (b1x, b1y))
    b1_rect = (b1x - 10, b1y - 10, b1w + 20, b1h + 20)
    pygame.draw.rect(screen, (0, 255, 0), b1_rect, 1 + 5 * (mode == 1))

    button2 = font.render("2 Players", True, (0, 55 + 100 * p, 55 + 100 * p))
    b2x = 900 - button2.get_width() // 2
    b2y = 570 - button2.get_height() // 2
    b2w = button2.get_width()
    b2h = button2.get_height()
    screen.blit(button2, (b2x, b2y))
    b2_rect = (b2x - 10, b2y - 10, b2w + 20, b2h + 20)
    pygame.draw.rect(screen, (0, 255, 0), b2_rect, 1 + 5 * (mode == 2))

    player1 = font.render("P1", True, (455 - 200 * p, 0, 0))
    p1x = 650 - player1.get_width() // 2
    p1y = 570 - player1.get_height() // 2
    p1w = player1.get_width()
    p1h = player1.get_height()
    screen.blit(player1, (p1x, p1y))
    p1_rect = (p1x - 10, p1y - 10, p1w + 20, p1h + 20)
    pygame.draw.rect(screen, (255, 0, 0), p1_rect, 1 + 5 * (p == 1))

    player2 = font.render("P2", True, (0, 0, -145 + 200 * p))
    p2x = 750 - player2.get_width() // 2
    p2y = 570 - player2.get_height() // 2
    p2w = player2.get_width()
    p2h = player2.get_height()
    screen.blit(player2, (p2x, p2y))
    p2_rect = (p2x - 10, p2y - 10, p2w + 20, p2h + 20)
    pygame.draw.rect(screen, (0, 0, 255), p2_rect, 1 + 5 * (p == 2))

    play = font.render("Play", True, pygame.color.Color("cyan"))
    px = 700 - play.get_width() // 2
    py = 660 - play.get_height() // 2
    pw = play.get_width()
    ph = play.get_height()
    screen.blit(play, (px, py))
    p_rect = (px - 10, py - 10, pw + 20, ph + 20)
    pygame.draw.rect(screen, (0, 255, 0), p_rect, 1)
    return pygame.Rect(b1_rect), pygame.Rect(b2_rect), pygame.Rect(p1_rect), pygame.Rect(p2_rect), pygame.Rect(p_rect)


# окно выбора машинок
def choose_player():
    cars = []
    for i in range(6):
        for j in range(1, 4):
            image = load_image("car{}.png".format(3 * i + j))
            x, y = image.get_size()
            image = pygame.transform.scale(image, (x // 8, y // 8))
            plate = pygame.Surface((100, 100))
            rect = pygame.Rect((0, 0), image.get_size())
            rect.center = (50, 50)
            plate.blit(image, rect)
            cars += [plate]

    # прямоугольники кнопок
    button1, button2, player1, player2, play = draw_choose(cars)
    # mode - количество игроков
    # p - какой игрок сейчас выбирает автомобиль
    # n1 и n2 - выборы игроков
    # если mode == 1, то p = 1 и n2 = 0
    mode, p, n1, n2 = 1, 1, 1, 0
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                raise SystemExit
            if event.type == pygame.MOUSEBUTTONDOWN:
                for i in range(6):
                    for j in range(3):
                        # если игрок кликнул на одну из машинок
                        # то он может её выбрать, если она не выбрана другим игроком
                        if pygame.Rect(275 + i * 150, 120 + j * 150, 100, 100).collidepoint(event.pos):
                            n = 3 * i + j + 1
                            if p == 1:
                                if n2 != n:
                                    n1 = n
                            else:
                                if n1 != n:
                                    n2 = n
                # если изменили режим на 2 игрока
                # то по умолчанию выбирается первая или вторая машинка для второго игрока
                if button2.collidepoint(event.pos):
                    mode, n2 = 2, 1 + (n1 == 1)
                # при выборе режима 1 игрока выбор второго убирается
                if button1.collidepoint(event.pos):
                    mode, n2, p = 1, 0, 1
                # выбор авто для первого игрока
                if player1.collidepoint(event.pos):
                    p = 1
                # выбор авто для второго, если режим 2 игрока
                if player2.collidepoint(event.pos):
                    p = mode
                # запуск игры
                if play.collidepoint(event.pos):
                    running = False
        # отрисовка экрана
        draw_choose(cars, mode, p, n1, n2)
        clock.tick(fps)
        pygame.display.flip()
    race(n1, n2)


# гравное меню
def menu():
    running = True
    # прямоугольники кнопок
    race_rect, hunt_rect = menu_view()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                raise SystemExit
            if event.type == pygame.MOUSEBUTTONDOWN:
                if race_rect.collidepoint(event.pos):
                    p = choose_player()
                    race(p)
                if hunt_rect.collidepoint(event.pos):
                    pass
        clock.tick(fps)
        pygame.display.flip()


# отрисовка информационного табло во время игры
def print_result(t0, p1, p2=None):
    font = pygame.font.Font(None, 40)

    if t0 == -1:
        time = 0.000
    else:
        # время от старта
        time = (pygame.time.get_ticks() - t0) / 1000.0
    time = font.render("time: {}".format(time), True, pygame.color.Color("cyan"))
    screen.blit(time, (700, 50))

    lap1 = font.render("Lap", True, pygame.color.Color("cyan"))
    screen.blit(lap1, (700, 100))

    # номер круга каждого игрока
    lap1 = font.render("Player 1: {}".format(p1.lap), True, pygame.color.Color("cyan"))
    screen.blit(lap1, (700, 150))

    if p2:
        lap2 = font.render("Player 2: {}".format(p2.lap), True, pygame.color.Color("cyan"))
        screen.blit(lap2, (700, 200))


# старт игры
# до него нельзя поехать
# и на экране обратный отсчёт
def start_race(finish, p1, p2, n2):
    for i in range(3, 0, -1):
        screen.fill((0, 0, 0))
        screen.blit(full_background, (0, 0))
        screen.blit(finish, (25, 180))
        pygame.draw.rect(screen, "green", (690, 40, 180, 200), 2)
        all_sprites.update()
        if n2:
            print_result(-1, p1, p2)
        else:
            print_result(-1, p1)
        font = pygame.font.Font(None, 400)
        num = font.render(str(i), True, pygame.color.Color("cyan"))
        screen.blit(num, (650, 200))
        pygame.display.flip()
        clock.tick(1)


# игровой процесс
def race(n1, n2=0):
    # машинка первого игрока
    p1 = Car(n1, [K_w, K_a, K_s, K_d], (100, 220))
    p2 = None
    if n2:
        # если режим 2 игрока, то это машинка второго игрока
        p2 = Car(n2, [K_UP, K_LEFT, K_DOWN, K_RIGHT], (130, 220))

    # создание стен
    for i in range(len(wall1) - 1):
        Wall(wall1[i], wall1[i + 1])
    for i in range(len(wall2) - 1):
        Wall(wall2[i], wall2[i + 1])

    # создание финишной полосы
    finish = pygame.Surface((150, 20))
    for i in range(19):
        for j in range(2):
            if (i + j) % 2:
                pygame.draw.rect(finish, "white", (10 * i, 10 * j, 10, 10))

    running = True
    # функция старта игры
    start_race(finish, p1, p2, n2)
    # время начала гонки
    t0 = pygame.time.get_ticks()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                raise SystemExit

        # отрисовка фона
        screen.fill((0, 0, 0))
        screen.blit(full_background, (0, 0))
        screen.blit(finish, (25, 180))

        # отрисовка информации
        pygame.draw.rect(screen, "green", (690, 40, 180, 200), 2)
        if n2:
            print_result(t0, p1, p2)
        else:
            print_result(t0, p1)

        # после прохождения 3 кругов игра заканчивается
        if p1.lap == "win":
            running = False
            time = (pygame.time.get_ticks() - t0) / 1000.0
            table, button = win(winner=1, time=time)
        if n2:
            if p2.lap == "win":
                running = False
                time = (pygame.time.get_ticks() - t0) / 1000.0
                table, button = win(winner=2, time=time)

        all_sprites.update()
        clock.tick(fps)
        pygame.display.flip()

    # отображение итогов игры
    screen.blit(table, (400, 200))
    button = pygame.Rect((button.x + 400, button.y + 200, button.w, button.h))
    pygame.display.flip()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                raise SystemExit
            if event.type == MOUSEBUTTONDOWN:
                # при нажатии на кнопку выхода переходим в главное меню
                if button.collidepoint(event.pos):
                    all_sprites.empty()
                    Car.cars = set()
                    menu()


# отрисовка итогов игры
def win(winner=1, time=0.0, score=-1):
    table = pygame.Surface((600, 300))
    table.blit(full_background, (0, 0))
    pygame.draw.rect(table, "green", (5, 5, 590, 290), 2)

    font = pygame.font.Font(None, 50)
    title = font.render("Player {} won".format(winner), True, pygame.color.Color("cyan"))
    table.blit(title, (300 - title.get_width() // 2, 100 - title.get_height() // 2))
    
    if time:
        time = font.render("Time: {}".format(time), True, pygame.color.Color("cyan"))
        table.blit(time, (300 - time.get_width() // 2, 180 - time.get_height() // 2))
    
    if score + 1:
        # отображения количества набранных очков для будущего режима игры hunt
        score = font.render("Score: {}".format(score), True, pygame.color.Color("cyan"))
        table.blit(score, (300 - score.get_width() // 2, 180 - score.get_height() // 2))
    
    button = font.render("back", True, pygame.color.Color("cyan"))
    button_x = 300 - button.get_width() // 2
    button_y = 250 - button.get_height() // 2
    button_w = button.get_width()
    button_h = button.get_height()
    table.blit(button, (button_x, button_y))
    button_rect = pygame.Rect(button_x - 10, button_y - 10, button_w + 20, button_h + 20)
    pygame.draw.rect(table, (0, 255, 0), button_rect, 1)
    return table, button_rect


# режим игры охота, будет добавлен позже
def hunt():
    pass


if __name__ == '__main__':
    pygame.init()
    pygame.display.set_caption("Машинки")
    size = width, height = 1400, 700
    screen = pygame.display.set_mode(size)
    fps = 90
    # размер клеток на фоне
    bgs = 100
    # список точек ломанных, являющихся стенами
    wall1 = [(1034, 661), (829, 666), (552, 657), (378, 656), (188, 654), (79, 649), (43, 611), (25, 521), (43, 454),
             (81, 406), (121, 375), (161, 379), (216, 408), (271, 426), (329, 438), (389, 432), (388, 405), (353, 392),
             (257, 361), (203, 344), (136, 333), (66, 314), (14, 211), (23, 125), (49, 62), (92, 31), (161, 24),
             (222, 25), (295, 28), (380, 36), (438, 39), (486, 40), (556, 52), (626, 80), (661, 108), (676, 162),
             (675, 200), (675, 239), (673, 285), (676, 340), (693, 379), (725, 397), (801, 367), (838, 318), (875, 243),
             (896, 193), (925, 141), (962, 92), (1007, 51), (1073, 31), (1134, 28), (1204, 26), (1204, 26), (1282, 32),
             (1343, 53), (1345, 55), (1359, 107), (1347, 174), (1322, 233), (1257, 261), (1194, 276), (1166, 322),
             (1146, 355), (1146, 384), (1180, 432), (1252, 467), (1320, 511), (1352, 592), (1241, 654), (1128, 661),
             (1016, 662)]
    wall2 = [(818, 564), (714, 562), (645, 560), (559, 562), (484, 569), (390, 571), (320, 566), (231, 552), (180, 526),
             (255, 518), (281, 522), (349, 529), (394, 530), (460, 528), (517, 515), (546, 492), (550, 449), (544, 389),
             (529, 359), (497, 323), (442, 293), (375, 265), (303, 237), (240, 211), (174, 179), (251, 176), (328, 183),
             (380, 174), (429, 173), (472, 205), (505, 254), (540, 312), (548, 353), (564, 391), (581, 440), (615, 477),
             (671, 493), (731, 492), (829, 477), (893, 422), (946, 360), (959, 281), (996, 224), (1027, 191),
             (1077, 158), (1136, 128), (1218, 122), (1209, 140), (1170, 148), (1131, 165), (1095, 176), (1069, 213),
             (1054, 243), (1045, 273), (1043, 312), (1030, 339), (994, 372), (999, 446), (1028, 488), (1084, 513),
             (1143, 534), (1191, 548), (1127, 550), (1013, 558), (876, 566), (789, 562)]
    # фоновая картинка
    background = pygame.transform.scale(load_image("background.png"), (bgs, bgs))
    full_background = pygame.Surface(size)
    all_sprites = pygame.sprite.Group()
    clock = pygame.time.Clock()
    for i in range(width // bgs + 1):
        for j in range(height // bgs + 1):
            full_background.blit(background, (bgs * i, bgs * j))
    # запуск игры
    menu()
