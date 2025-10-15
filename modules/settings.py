import pygame 

# Game setup
WIDTH = 1280  # Width of the virtual screen - will be scaled based on user settings
HEIGHT = 720  # Height of the virtual screen - will be scaled based on user settings
FPS = 60
WORLD_RECT = pygame.Rect(0, 0, 1, 1)  # World boundary placeholder (will be updated after loading the map image)

# Player setup
#PLAYER_START_X = WIDTH//2
#PLAYER_START_Y = HEIGHT//2
PLAYER_START_X = 600 # was 10900
PLAYER_START_Y = 380 # was 4150
PLAYER_SIZE = 0.35
PLAYER_SPEED = 8

# Colours for players
#Creating colors
RED   = (255, 0, 0)
ORANGE = (255,165,0)
BLACK = (0, 0, 0)
BLUE  = (0, 0, 255)
PINK = (255,192,203)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
YELLOW = (255,255,0)
BROWN = (150,75,0)
CYAN = (0,255,255)
PURPLE = (160,32,240)
MAGENTA = (253,61,181)
DARK_GREEN = (1,50,32)
GOLD = (255, 215, 0)
TEAL = (0, 128, 128)
LIME = (57, 255, 20)
PLAYER_COLOURS = {1:RED, 2:ORANGE, 3:BLACK, 4:BLUE, 5:PINK, 6:WHITE, 7:GREEN, 8:YELLOW, 9:BROWN, 10:CYAN, 11:PURPLE, 12:MAGENTA, 13:DARK_GREEN, 14:GOLD, 15:TEAL, 16:LIME}

# Player sprite colours for repplacement
OLD_COLOR_HIGHLIGHT = (255,0,0)
OLD_COLOR_SHADOW = (0,0,255)