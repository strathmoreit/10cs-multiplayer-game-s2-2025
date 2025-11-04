# Strathmore multiplayer game for Y10 Computing
# By N Stebbing September/October 2025
# v7.0 implements socket.io using aiohttp as a server to manage network communication
# Implemented multiplayer and chat.
# v7.1 started 28/9/25 allows the game to run as local only if a server is not found
# Also implements a student_code.py module where students write their Player class and later other classes such as objects and NPCs
# v7.2 student sprite sheet pngs shared by uploading to the server

import pygame
from modules.entities import *
from modules.settings import *
from modules.ui import *
from modules.network_client import NetClient
from modules.player_loader import make_player

SERVER_URL = "http://localhost:8000"  # or "http://<host-lan-ip>:8000" on students' PCs

# Set up the game window
pygame.init()

# Game State Class to store variables - makes it easier to pass them around
class GameState:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
        pygame.display.set_caption("Strathmore Game")
        self.clock = pygame.time.Clock()
        self.background = pygame.image.load("assets/starfield720.png").convert()
        self.mode = "auto" #accepts menu, offline, server or client, added auto in 7.1 to connect to a server if there is one or run offline
        self.player = None
        self.client = None
        self.server = None
        self.message_cache = []  # list of surfaces containing rendered messages ready to blit
        self.message_list = "" # new messages read from network ready to be put in the cache
        self.chat_font = pygame.font.Font('assets\FreeSans.ttf', 16)
        self.menu_font = pygame.font.Font('assets\FreeSans.ttf', 100) # used when showing the menu, define here as globals to avoid repeating code in the game loop
        self.menu_text = self.menu_font.render("Strathmore Game", True, (128,128,255)) # used when showing the menu, define here as globals to avoid repeating code in the game loop
        self.player_data = {} # hold the data on network player sprites to be broadcast
        self.players_group = {} # holds the Other_Player sprite objects to be displayed
        self.projectiles_group = pygame.sprite.Group()
        self.player_group = pygame.sprite.GroupSingle() # the current player of the local client, stored in a group for some reason that I forget now
        self.rooms_group = pygame.sprite.Group()
        self.chat_box = None

state = GameState()

# Message Caching and Drawing
def update_message_cache(state):
    #message_cache = []  # Clear cache and re-render messages
    for line in state.message_list.splitlines():
        text_surface = state.chat_font.render(line, True, (0, 0, 0), (255, 255, 255))
        state.message_cache.append(text_surface)
        if len(state.message_cache) > 50:
            state.message_cache.pop(0)
    state.message_list = "" # rather than clearing the message cache and re-renedering the whols list when there is one change, I will addd new lines to the cache without clearing it so the message-list only contains new lines to be added now

def draw_messages(state):
    h = state.message_cache[0].get_height() if state.message_cache else 16
    y = HEIGHT - (h * len(state.message_cache)) - 10
    for text_surface in state.message_cache:
        state.screen.blit(text_surface, (10, y))
        y += h

# Game Logic (Called in the game loop)
def handle_events(state):
    for event in pygame.event.get():
        if state.chat_box.handle_event(event) == "submit":
            if state.mode == "client":   # don't try to send a message if we are offline
                if state.chat_box.text.strip():
                    state.client.send_chat(state.chat_box.text.strip())
            state.chat_box.text = ""
            state.chat_box.active = False
            state.player.input_enabled = True
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_t:
                state.chat_box.active = True
                state.player.input_enabled = False    

def update_game_state(state):
    # --- snapshot player position BEFORE any updates this frame ---
    if state.player is not None:
        state.player.prev_x, state.player.prev_y = state.player.x, state.player.y

    '''applies data recieved from the network in the last game loop'''
    state.player_group.update()
    state.projectiles_group.update()
    state.rooms_group.update()

    # Handle player-room collisions
    for map in state.rooms_group:
        if map.hit_test(state.player.hit_rect):
            state.player.move_back()
            state.rooms_group.update()

def draw_group(surface, group):
    for spr in group.sprites():
        if hasattr(spr, "draw"):
            spr.draw(surface)          # lets BasePlayer run facing/idle/animation
        else:
            surface.blit(spr.image, spr.rect)

def draw_game(state):
    '''draws all elements to the screen'''
    state.screen.blit(state.background, (0,0))
    state.rooms_group.draw(state.screen) 
    #state.player_group.draw(state.screen) # the player group only contains the local player
    draw_group(state.screen, state.player_group)
    
    for op in state.players_group.values():
        op.update(state.player.x, state.player.y)  # draw relative to camera
        state.screen.blit(op.image, op.rect)
    state.projectiles_group.draw(state.screen)
    state.chat_box.draw(state.screen)
    draw_messages(state)

# Set up the game
state.player = make_player(RED, state.projectiles_group, state.screen, PLAYER_START_X, PLAYER_START_Y)
#state.player = Player(RED, state.projectiles_group,state.screen)  #Debug code - revert to the player class from entities instead of a student written Player class
state.player_group.add(state.player) # I created a group with just the player so I can call the draw method on the group
state.chat_box = TextBox(WIDTH - 410,HEIGHT - 35,400,20)
state.chat_box.active=False 

# Set up network client
if state.mode in ("client","auto"):
    nc = NetClient(state, SERVER_URL, name="Player1", color="#ffcc66")
    if nc.connect(timeout=0.6):
        state.client = nc
        state.mode = "client"
    else:
        state.client = None
        state.mode = "offline"

# Set up Rooms
cafeteria = Cafeteria(WIDTH//2,HEIGHT//2+200, state.player)
state.rooms_group.add(cafeteria)

# GAME LOOP
while True:
    handle_events(state)

    # if state.mode == "menu":
    #     update_menu(state)

    if state.mode in ("server", "client", "offline"):
        update_game_state(state)

        # --- network tick (client only) ---
        if state.mode == "client" and state.client is not None:
            state.client.tick_send_move()
        update_message_cache(state)
        draw_game(state)
        
        # draw OTHER players (kept in a dict of sprites) -DEBUG CODE: generated by chatgpt - doesn't seem to integrate with gamestate 
        for sid, spr in state.players_group.items():
            # if your Other_Player needs per-frame update, do it here:
            # spr.update(state.player.x, state.player.y)  # e.g., camera-relative
            state.screen.blit(spr.image, spr.rect)
    
    pygame.display.flip() 
    #print(state.clock.get_fps())
    state.clock.tick(FPS)