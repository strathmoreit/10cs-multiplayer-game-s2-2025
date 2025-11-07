import pygame
import math
from modules.settings import *
import os

# functions to check for collisions between a rect and a polygon
def line_intersection(a, b, c, d):
    # check for division by zero
    if ((a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])) == 0:
        return False
    t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / ((a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0]))
    u = ((a[0] - c[0]) * (a[1] - b[1]) - (a[1] - c[1]) * (a[0] - b[0])) / ((a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0]))
    # check if line actually intersect
    if (0 <= t and t <= 1 and 0 <= u and u <= 1):
        return True
    else: 
        return False

def colideRectLine(rect, p1, p2):
    return (line_intersection(p1, p2, rect.topleft, rect.bottomleft) or
            line_intersection(p1, p2, rect.bottomleft, rect.bottomright) or
            line_intersection(p1, p2, rect.bottomright, rect.topright) or
            line_intersection(p1, p2, rect.topright, rect.topleft))

def collideRectPolygon(rect, polygon):
    for i in range(len(polygon)-1):
        if colideRectLine(rect, polygon[i], polygon[i+1]):
            return True
    return False

def pallete_swap(image, old_color, new_color):
    image_copy = pygame.Surface(image.get_size())
    image_copy.fill((236,0,140))
    image_copy.blit(image, (0,0))
    image_copy2 = pygame.Surface(image.get_size())
    image_copy2.fill(new_color)
    image_copy.set_colorkey(old_color)
    image_copy2.blit(image_copy, (0,0))
    image_copy2.set_colorkey((236,0,140))
    return image_copy2

def load_frames_grid(
    sheet_path, *, cols, count, pad=0, origin=(0, 0), frame_w=None, frame_h=None):
    """
    Slice a uniform grid sheet into frames (no JSON).
    - cols: number of columns in the sheet
    - count: total frames to extract
    - pad: pixels between cells
    - origin: top-left offset where the first cell starts
    - frame_w/frame_h: override cell size (if None, derive from sheet)
    """
    sheet = pygame.image.load(sheet_path).convert_alpha()
    sw, sh = sheet.get_size()

    rows = math.ceil(count / cols)

    # Derive sizes unless overridden
    fw = frame_w if frame_w is not None else (sw - origin[0] - (cols - 1) * pad) // cols
    fh = frame_h if frame_h is not None else (sh - origin[1] - (rows - 1) * pad) // rows

    frames = []
    y = origin[1]
    for r in range(rows):
        x = origin[0]
        for c in range(cols):
            if len(frames) >= count:
                break
            rect = pygame.Rect(x, y, fw, fh)
            frames.append(sheet.subsurface(rect).copy())
            x += fw + pad
        y += fh + pad
    return frames



# When drawing to the screen everything is offset in relation to how far the player has moved.
def offset_xcoord(x_coord, player_x): 
    return x_coord - player_x + PLAYER_START_X
def offset_ycoord(y_coord, player_y):
    return y_coord - player_y + PLAYER_START_Y

class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, direction, owner, screen):
        super().__init__()
        self.x = x  # World position
        self.y = y  # World position
        self.image = pygame.Surface((60, 20))
        self.image.fill((255, 255, 0))
        self.rect = self.image.get_rect(center=(x, y))
        self.velocity = direction
        self.owner = owner
        self.screen = screen

    def update(self, player_x, player_y):
        self.x += self.velocity[0]
        self.y += self.velocity[1]
        self.rect.center = (self.x, self.y)
        self.rect = self.image.get_rect(center=(self.x-player_x+(WIDTH//2),self.y-player_y+(HEIGHT//2)))
        # Kill if out of world bounds
        if not WORLD_RECT.collidepoint((self.x, self.y)):
            self.kill()


class Player(pygame.sprite.Sprite):
    def __init__(self, colour, projectiles, screen):
        super().__init__()
        self.projectiles = projectiles
        self.screen = screen

        # world position (authoritative)
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self.prev_x = self.x
        self.prev_y = self.y

        self.speed = PLAYER_SPEED
        self.player_num = 0
        self.facing = "right"
        self.animation_state = "idle_right"
        self.input_enabled = True
        self.cooldown = 0

        # velocity set in user_input()
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        # 1) load frames from spritesheet (Surfaces, not paths)
        #    (packed with --cols 9 --pad 1; already scaled during packing)
        self.base_frames = load_frames_grid("assets/player_sheet.png", cols=9, count=9, pad=1)

        # 2) build colourised frames (copies) and set initial frame
                # animation counters
        self.current_frame = 0
        self.frame_count   = 0
        self.anim_speed    = 5  # frames between animation steps
        self.color_highlight = tuple(colour)
        self.color_shadow    = tuple(colour)
        self.images = []  # colourised frames
        self.set_colour(colour)

        # local player is camera-locked: rect stays at screen centre
        self.image = self.images[self.current_frame]
        self.rect  = self.image.get_rect(center=(WIDTH // 2, HEIGHT // 2))

        # hit_rect should represent world collision box around (x, y)
        self.hit_rect = pygame.Rect(0, 0, 40, 40)
        self.hit_rect.center = (WIDTH // 2, HEIGHT // 2)


    # ----- appearance -----

    def set_colour(self, colour):
        """Rebuild colourised frames from base_frames (no re-loading from disk)."""
        self.color_highlight = tuple(colour)
        self.color_shadow    = tuple(colour)

        new_images = []
        for base in self.base_frames:
            img = base.copy()  # don’t mutate the base
            img = pallete_swap(img, OLD_COLOR_HIGHLIGHT, self.color_highlight)
            img = pallete_swap(img, OLD_COLOR_SHADOW,    self.color_shadow)
            new_images.append(img)
        self.images = new_images

        # keep current frame valid
        self.current_frame = min(self.current_frame, len(self.images) - 1)
        self.image = self.images[self.current_frame]

    def _step_animation(self, moving: bool):
        """Advance current_frame based on moving/idle state."""
        if not moving:
            self.current_frame = 0
            self.frame_count = 0
            self.animation_state = "idle_left" if self.facing == "left" else "idle_right"
            return

        # moving:
        self.animation_state = "walk_left" if self.facing == "left" else "walk_right"
        if self.current_frame == 0:   # just started moving → enter walk cycle at frame 1
            self.current_frame = 1
            self.frame_count = 0
        else:
            self.frame_count += 1
            if self.frame_count > self.anim_speed:
                self.current_frame += 1
                self.frame_count = 0
                if self.current_frame > len(self.images) - 1:
                    self.current_frame = 1  # loop walk frames 1..end

    def _compose_image(self):
        frame = self.images[self.current_frame]
        if self.animation_state in ("idle_left", "walk_left"):
            frame = pygame.transform.flip(frame, True, False)
        self.image = frame

    # ----- controls & movement -----

    def user_input(self):
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        if not self.input_enabled:
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.velocity_y = -self.speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.velocity_y =  self.speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.velocity_x = -self.speed
            self.facing = "left"
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.velocity_x =  self.speed
            self.facing = "right"
        if keys[pygame.K_SPACE]:
            self.shoot()

        # normalise diagonal
        if self.velocity_x != 0 and self.velocity_y != 0:
            inv = 1.0 / math.sqrt(2)
            self.velocity_x *= inv
            self.velocity_y *= inv

    def move(self):
        # remember previous position for collision rollback
        self.prev_x, self.prev_y = self.x, self.y
        self.x += self.velocity_x
        self.y += self.velocity_y

    def move_back(self):
        # called by your room collision logic
        self.x, self.y = self.prev_x, self.prev_y

    # ----- gameplay bits you kept -----

    def shoot(self):
        # kept as placeholder for your future use (networked bullets, etc.)
        if self.cooldown == 0:
            dx = 10 if self.facing == "right" else -10
            self.cooldown = 50
            self.last_shot_position = (self.x, self.y)
            self.last_shot_direction = dx

    # ----- per-frame update -----

    def update(self):
        # timers
        if self.cooldown > 0:
            self.cooldown -= 1

        # input → velocity
        self.user_input()

        # animation step (uses velocities)
        moving = (abs(self.velocity_x) > 0.01) or (abs(self.velocity_y) > 0.01)
        self._step_animation(moving)
        self._compose_image()

        # move in world
        self.move()

        # keep rect (draw position) at screen centre; hit_rect on world coords
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.hit_rect.center = (WIDTH // 2, HEIGHT // 2)

class Player_V7(pygame.sprite.Sprite):
    def __init__(self, colour, projectiles, screen):
        super().__init__()
        self.projectiles = projectiles
        self.screen = screen
        #self.image = pygame.image.load("sprites/player_idle.png").convert_alpha()
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self.speed = PLAYER_SPEED
        self.player_num = 0
        #self.color_highlight = (21,129,48)
        #self.color_shadow = (15,82,51)
        self.color_highlight = (colour)
        self.color_shadow = (colour)
        #self.frames = ["sprites/player_idle.png", "sprites/player_move_1.png", "sprites/player_move_2.png", "sprites/player_move_3.png", "sprites/player_move_4.png", "sprites/player_move_5.png", "sprites/player_move_6.png", "sprites/player_move_7.png", "sprites/player_move_8.png"]
        self.frames = load_frames_grid("assets/player_sheet.png", cols=9, count=9, pad=1)
        self.set_colour(colour)
        #self.network = network
        #self.images = []
        # for fra in self.frames:
        #     new_image = (pygame.image.load(fra).convert_alpha())
        #     new_image = pygame.transform.scale(new_image, (new_image.get_width()*.66, new_image.get_height()*.66))
        #     new_image = pallete_swap(new_image, OLD_COLOR_HIGHLIGHT, self.color_highlight)
        #     new_image = pallete_swap(new_image, OLD_COLOR_SHADOW, self.color_shadow)
        #     self.images.append(new_image)
        self.current_frame = 0 # which frame is currently shown
        self.frame_count = 0   # how long has the current frame been shown for
        self.anim_speed = 5  # how often we change the frame when animating
        self.facing = "right"
        self.animation_state = "idle_right"  # added animation state V4.2 to manage animation of network players
        self.image = self.images[self.current_frame]
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.hit_rect = pygame.Rect(620, 360, 40, 40)
        self.input_enabled = True
        self.cooldown = 0
    
    def shoot(self):
        if self.cooldown == 0:
            if self.facing == "right":
                dx = 10
            else:
                dx = -10
            # removed below... don't make a projectile until told to by the network... won't work on single-player game??
            #bullet = Projectile(self.x, self.y, (dx * 3, 0), self, self.screen)
            #self.projectiles.add(bullet)
            self.cooldown = 50  # Cooldown in frames
            self.last_shot_position = (self.x, self.y)
            self.last_shot_direction = dx

    def set_colour(self, colour):
        self.color_highlight = (colour)
        self.color_shadow = (colour)
        self.images = []
        for fra in self.frames:
            new_image = (pygame.image.load(fra).convert_alpha())
            new_image = pygame.transform.scale(new_image, (new_image.get_width()*.66, new_image.get_height()*.66))
            new_image = pallete_swap(new_image, OLD_COLOR_HIGHLIGHT, self.color_highlight)
            new_image = pallete_swap(new_image, OLD_COLOR_SHADOW, self.color_shadow)
            self.images.append(new_image)
            
    def get_image(self):
        next_frame = self.current_frame
        if not(abs(self.velocity_x) > 0.01 or abs(self.velocity_y) > 0.01):
            # handle player being stationary
        #if (self.velocity_x + self.velocity_y) == 0: # this failed as some velocities were rounding to zero
            next_frame = 0
            self.frame_count = 0
            if self.facing == "left":
                self.animation_state = "idle_left"
            else:
                self.animation_state = "idle_right"
        else:
            # handle player is moving
            if self.facing == "right":
                self.animation_state = "walk_right"
            else:
                self.animation_state = "walk_left"
            if self.current_frame == 0: # we have just started moving
                next_frame = 1
                self.frame_count = 0
            else:  # we are continuing to move, change the frame if we have waited long enough
                self.frame_count += 1
                if self.frame_count > self.anim_speed:
                    next_frame = self.current_frame + 1
                    self.frame_count = 0
                    if next_frame > len(self.frames) -1:
                        next_frame = 1
        self.current_frame = next_frame
        self.image = self.images[self.current_frame]
        if self.facing == "left":
            self.image = pygame.transform.flip(self.image,True,False)

    
    def user_input(self):
        self.velocity_x = 0
        self.velocity_y = 0
        
        keys = pygame.key.get_pressed()
        
        if keys[pygame.K_w]:
            self.velocity_y = -self.speed
        if keys[pygame.K_s]:
            self.velocity_y = self.speed
        if keys[pygame.K_a]:
            self.velocity_x = -self.speed
            self.facing = "left"
        if keys[pygame.K_d]:
            self.velocity_x = self.speed
            self.facing = "right"
        if keys[pygame.K_SPACE]:
            self.shoot()
            
        if self.velocity_x != 0 and self.velocity_y != 0:  # moving diagonally
            self.velocity_x /= math.sqrt(2)
            self.velocity_y /= math.sqrt(2)
    
    def move(self):
        self.x += self.velocity_x
        self.y += self.velocity_y
        #self.rect = self.image.get_rect(center=(WIDTH//2,HEIGHT//2)) # keep the rect up to date as it's used by the build in draw method of the sprite
        #self.rect = self.image.get_rect(center=(self.x,self.y)) 
    
    def move_back(self):
        self.x -= self.velocity_x
        self.y -= self.velocity_y
        #self.rect = self.image.get_rect(center=(WIDTH//2,HEIGHT//2)) # keep the rect up to date as it's used by the build in draw method of the sprite

    def update(self):
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.input_enabled == True:
            self.user_input()
        self.get_image()
        self.move()    


class BasePlayer(pygame.sprite.Sprite):
    # --- Students set only these two ---
    SHEET       = None          # e.g. "assets/my_character.png"
    SHEET_COUNT = 1             # total frames; 1 = no animation

    # --- Defaults students rarely touch ---
    SHEET_COLS  = None          # None = single-row strip split into SHEET_COUNT
    SHEET_PAD   = 0             # only used by grid loader
    SHEET_SCALE = 1.0
    ANIM_SPEED  = 5             # frames between steps (bigger = slower)

    def __init__(self, colour, projectiles_group, screen, x=PLAYER_START_X, y=PLAYER_START_Y, playable=True, speed=PLAYER_SPEED):
        super().__init__()
        self.projectiles = projectiles_group
        self.screen = screen

        # world position & movement (students usually manipulate these)
        self.x = float(x)
        self.y = float(y)
        self.prev_x = self.x
        self.prev_y = self.y
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.speed = float(speed)

        self.playable = playable
        self.input_enabled = True

        # facing & animation state (mirrors your original behaviour)
        self.facing = "right"           # "left" or "right"
        self.current_frame = 0          # 0 = idle; walking loops 1..end
        self.frame_count   = 0          # counts ticks up to ANIM_SPEED

        # load frames or fallback square
        self.frames = self._load_frames_or_square(colour)
        self.image  = self.frames[self.current_frame]

        # camera-locked draw rect and a simple hit rect
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.hit_rect = pygame.Rect(0, 0, 40, 40)
        self.hit_rect.center = (WIDTH // 2, HEIGHT // 2)

    # Intentionally empty so students can own update() logic safely.
    def update(self):
        return

    # Animation happens here so students never have to call super().update()
    def draw(self, surface):
        # Work out deltas since the last frame (supports "set x/y directly" style)
        dx = float(self.x) - float(self.prev_x)
        dy = float(self.y) - float(self.prev_y)

        # If velocities exist, we can also consider them (but position deltas are enough)
        vx = getattr(self, "velocity_x", 0.0)
        vy = getattr(self, "velocity_y", 0.0)

        # Moving if either position changed or velocity is non-zero
        moving = (abs(dx) > 0.01) or (abs(dy) > 0.01) or (abs(vx) > 0.01) or (abs(vy) > 0.01)

        # Facing: prefer horizontal delta; fall back to velocity if no delta
        if dx < -0.01 or vx < -0.01:
            self.facing = "left"
        elif dx > 0.01 or vx > 0.01:
            self.facing = "right"

        # Step animation (idle → frame 0; walking loops 1..end)
        if len(self.frames) > 1:
            if not moving:
                self.current_frame = 0
                self.frame_count = 0
            else:
                if self.current_frame == 0:
                    self.current_frame = 1
                    self.frame_count = 0
                else:
                    self.frame_count = self.frame_count + 1
                    if self.frame_count > int(self.ANIM_SPEED):
                        self.current_frame = self.current_frame + 1
                        self.frame_count = 0
                        if self.current_frame > (len(self.frames) - 1):
                            self.current_frame = 1

        # Compose frame with left/right flip
        frame = self.frames[self.current_frame]
        if self.facing == "left":
            frame = pygame.transform.flip(frame, True, False)
        self.image = frame

        # Camera-locked draw + collision rects
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.hit_rect.center = (WIDTH // 2, HEIGHT // 2)

        # Draw
        surface.blit(self.image, self.rect)

        # IMPORTANT: update previous position AFTER drawing so next frame sees deltas
        self.prev_x, self.prev_y = float(self.x), float(self.y)


    # ---------------- helpers for students/engine ----------------
    def move_back(self):
        self.x, self.y = self.prev_x, self.prev_y

    def get_frame(self, idx, *, flip=False):
        if not self.frames:
            return self.image
        if idx < 0:
            idx = 0
        if idx > len(self.frames) - 1:
            idx = len(self.frames) - 1
        frame = self.frames[int(idx)]
        if flip:
            frame = pygame.transform.flip(frame, True, False)
        return frame

    # ---------------- internal: load frames or fallback ----------------
    def _load_frames_or_square(self, colour):
        try:
            if self.SHEET and os.path.exists(self.SHEET) and int(self.SHEET_COUNT) > 0:
                if self.SHEET_COLS is None:
                    frames = self._load_sprite_strip(self.SHEET, int(self.SHEET_COUNT))
                else:
                    frames = self._load_frames_grid(self.SHEET, int(self.SHEET_COLS), int(self.SHEET_COUNT), int(self.SHEET_PAD))
                if frames:
                    if float(self.SHEET_SCALE) != 1.0:
                        scaled = []
                        i = 0
                        while i < len(frames):
                            f = frames[i]
                            w, h = f.get_size()
                            nw = int(w * float(self.SHEET_SCALE))
                            nh = int(h * float(self.SHEET_SCALE))
                            scaled.append(pygame.transform.scale(f, (nw, nh)))
                            i = i + 1
                        frames = scaled
                    return frames
        except Exception:
            pass

        # Fallback single-frame so game still runs
        surf = pygame.Surface((20, 20), pygame.SRCALPHA)
        surf.fill(colour)
        self.SHEET_COUNT = 1
        return [surf]

    # 1-row strip: width split into frame_count equal parts
    def _load_sprite_strip(self, path, frame_count):
        sheet = pygame.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        #fw = sw // int(frame_count)
        fw = 60
        frames = []
        x = 0
        i = 0
        while i < frame_count:
            rect = pygame.Rect(x, 0, fw, sh)
            frames.append(sheet.subsurface(rect).copy())
            x = x + fw
            i = i + 1
        return frames

    # This wraps the global load_frames_grid function. Added this after accidentally creating a second version of it here
    def _load_frames_grid(self, path, cols, count, pad):
        # Fix frame width at 60px; height still derived from rows
        return load_frames_grid(path, cols=cols, count=count, pad=pad, frame_w=60)

class Other_Player_V7(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        #self.image = pygame.image.load("sprites/player_idle.png").convert_alpha()
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self.speed = PLAYER_SPEED
        self.color_highlight = (21,129,48)
        self.color_shadow = (15,82,51)
        #self.frames = ["sprites/player_idle.png", "sprites/player_move_1.png", "sprites/player_move_2.png", "sprites/player_move_3.png", "sprites/player_move_4.png", "sprites/player_move_5.png", "sprites/player_move_6.png", "sprites/player_move_7.png", "sprites/player_move_8.png"]
        self.frames = load_frames_grid("assets/player_sheet.png", cols=9, count=9, pad=1)
        self.images = []
        for fra in self.frames:
            new_image = (pygame.image.load(fra).convert_alpha())
            new_image = pygame.transform.scale(new_image, (new_image.get_width()*.66, new_image.get_height()*.66))
            self.images.append(new_image)
        self.current_frame = 0 # which frame is currently shown
        self.frame_count = 0   # how long has the current frame been shown for
        self.anim_speed = 5  # how often we change the frame when animating
        self.facing = "right"
        self.animation_state = "idle_right"  # added animation state V4.2 to manage animation of network players
        self.image = self.images[self.current_frame]
        self.rect = self.image.get_rect(center=(self.x,self.y))
        self.hit_rect = pygame.Rect(620, 360, 40, 40)
    
    def set_colour(self, colour):
        self.color_highlight = (colour)
        self.color_shadow = (colour)
        self.images = []
        for fra in self.frames:
            new_image = (pygame.image.load(fra).convert_alpha())
            new_image = pygame.transform.scale(new_image, (new_image.get_width()*.66, new_image.get_height()*.66))
            new_image = pallete_swap(new_image, OLD_COLOR_HIGHLIGHT, self.color_highlight)
            new_image = pallete_swap(new_image, OLD_COLOR_SHADOW, self.color_shadow)
            self.images.append(new_image)
    
    def get_image(self):
        next_frame = self.current_frame
        if self.animation_state == "idle_right" or self.animation_state == "idle_left":
            next_frame = 0
            self.frame_count = 0
        else:
            if self.current_frame == 0: # we have just started moving
                next_frame = 1
                self.frame_count = 0
            else:  # we are continuing to move, change the frame if we have waited long enough
                self.frame_count += 1
                if self.frame_count > self.anim_speed:
                    next_frame = self.current_frame + 1
                    self.frame_count = 0
                    if next_frame > len(self.frames) -1:
                        next_frame = 1
        self.current_frame = next_frame
        
        try: # the following code is returning errors now and then. Could try top work out why, but we'll just use a try for now (V4.2)
            #if self.current_frame <= len(self.images):  # added this check in V4.2. I seem to get an index error sometimes where it tries to use image 1 when there is only one image. Might be happening when I first connect a client... maybe I am moving before all the images are loaded?
                self.image = self.images[self.current_frame]            
        except:
            pass
                
        if self.animation_state == "idle_left" or self.animation_state == "walk_left":
            self.image = pygame.transform.flip(self.image,True,False)

    def update(self, player_x, player_y):
        self.get_image()
        #print("Other Player animation state is " + self.animation_state)
        self.rect = self.image.get_rect(center=(self.x-player_x+(WIDTH//2),self.y-player_y+(HEIGHT//2)))


class Other_Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self.speed = PLAYER_SPEED

        # colours
        self.color_highlight = (21,129,48)
        self.color_shadow    = (15,82,51)

        # 1) Load frames from spritesheet -> list of Surfaces
        #    (sheet was packed with --cols 9 --pad 1 --scale 0.66)
        self.base_frames = load_frames_grid("assets/player_sheet.png", cols=9, count=9, pad=1)

        # 2) Working frames we actually render (start as copies of base)
        self.images = [frm.copy() for frm in self.base_frames]

        # anim state
        self.current_frame = 0
        self.frame_count   = 0
        self.anim_speed    = 5
        self.facing = "right"
        self.animation_state = "idle_right"

        # sprite surfaces/rects
        self.image = self.images[self.current_frame]
        self.rect  = self.image.get_rect(center=(self.x, self.y))
        self.hit_rect = pygame.Rect(0, 0, 40, 40)
        self.hit_rect.center = (self.x, self.y)

    def set_colour(self, colour):
        """Rebuild self.images by palette-swapping copies of base frames."""
        self.color_highlight = colour
        self.color_shadow    = colour
        new_images = []
        for base in self.base_frames:
            img = base.copy()
            # apply your palette swaps onto the copy
            img = pallete_swap(img, OLD_COLOR_HIGHLIGHT, self.color_highlight)
            img = pallete_swap(img, OLD_COLOR_SHADOW,    self.color_shadow)
            new_images.append(img)
        self.images = new_images
        # keep current frame valid
        self.current_frame = min(self.current_frame, len(self.images) - 1)
        self.image = self.images[self.current_frame]

    def get_image(self):
        # choose next frame index
        if self.animation_state in ("idle_right", "idle_left"):
            self.current_frame = 0
            self.frame_count = 0
        else:
            if self.current_frame == 0:
                self.current_frame = 1
                self.frame_count = 0
            else:
                self.frame_count += 1
                if self.frame_count > self.anim_speed:
                    self.current_frame += 1
                    self.frame_count = 0
                    if self.current_frame > len(self.images) - 1:
                        self.current_frame = 1

        # fetch frame safely
        frame = self.images[self.current_frame]

        # flip for facing without mutating the source frame
        if self.animation_state in ("idle_left", "walk_left"):
            frame = pygame.transform.flip(frame, True, False)

        self.image = frame

    def update(self, player_x, player_y):
        self.get_image()
        # camera-relative draw position
        self.rect = self.image.get_rect(
            center=(self.x - player_x + (WIDTH // 2), self.y - player_y + (HEIGHT // 2))
        )
        # keep hit_rect centered on world coords (not camera)
        self.hit_rect.center = (self.x, self.y)

    def apply_frames(self, frames):
        self.base_frames = frames
        self.images = [f.copy() for f in self.base_frames]
        self.current_frame = 0
        self.frame_count = 0
        self.image = self.images[0]

    def ensure_sheet(self, sheet_hash, client, meta):
        """Ensure frames for a given hash exist locally; request if not."""
        if sheet_hash in client.sheet_cache:
            self.apply_frames(client.sheet_cache[sheet_hash]["frames"])
            return
        # mark pending and request once
        client._pending_ops[self.sid] = sheet_hash   # store sid on creation
        client.sio.emit("sheet_get", {"hash": sheet_hash})


class GameEntity(pygame.sprite.Sprite):
    def __init__(self, x, y, player, anim_speed=5, scale=0.15):
        super().__init__()
        self.x = x
        self.y = y
        self.frames = []   # filenames
        self.images = []   # loaded images
        self.scale = scale
        self.anim_speed = anim_speed
        self.current_frame = 0
        self.frame_count = 0
        self.facing = "right"
        self.image = pygame.Surface((32, 32))  # placeholder
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.player = player

    def hit_test(self, rect):
        return False

    def add_frame(self, frame_path):
        """Add an animation frame and immediately load and scale the image."""
        self.frames.append(frame_path)
        img = pygame.image.load(frame_path).convert_alpha()
        img = pygame.transform.scale(img, (img.get_width() * self.scale, img.get_height() * self.scale))
        self.images.append(img)
        # Automatically set image for first frame added
        if len(self.images) == 1:
            self.image = self.images[0]

    def animate(self, is_moving):
        if not is_moving:
            self.current_frame = 0
            self.frame_count = 0
        else:
            self.frame_count += 1
            if self.frame_count > self.anim_speed:
                self.current_frame += 1
                self.frame_count = 0
                if self.current_frame >= len(self.images):
                    self.current_frame = 1
        self.image = self.images[self.current_frame]
        if self.facing == "left":
            self.image = pygame.transform.flip(self.image, True, False)

    def update_position(self, velocity_x, velocity_y):
        self.x += velocity_x
        self.y += velocity_y
        self.rect.center = (self.x, self.y)
    
    def update(self):
        self.rect = self.image.get_rect(center=(self.x-self.player.x+(WIDTH//2),self.y-self.player.y+(HEIGHT//2)))


class Cafeteria(pygame.sprite.Sprite):
    def __init__(self, x, y, player):
        super().__init__()
        self.image = pygame.image.load("maps/cafeteria.png").convert_alpha()
        self.x = x      # this is the starting location that will be offset when the player moves
        self.y = y   # this is the starting location that will be offset when the player moves
        self.rect = self.image.get_rect(center=(self.x,self.y))
        self.hitboxes = []
        self.player = player # need a reference to the player so we can offset the map as the player moves
        #self.hitboxes.append([(365,415),(363,587),(591,587),(591,415),(365,415)]) # debug code - simple hitbox for testing
        self.hitboxes.append([(33,238), (197,76), (722,76), (962,316), (964,379), (987,382), (989,369), (973,370), (971,248), (727,4), (194,3), (23,170), (22,369), (5,369), (5,380), (34,381), (33,238)])
        self.hitboxes.append([(147,285), (168,339), (207,367), (242,377), (270,354), (301,377), (346,358), (376,329), (387,283), (361,282), (385,270), (366,234), (338,213), (294,197), (286,210), (254,210), (249,194), (209,205), (174,228), (149,270), (173,280), (147,285)])
        self.hitboxes.append([(358,502), (365,537), (383,564), (414,586), (454,599), (467,574), (499,573), (513,597), (557,578), (589,545), (599,502), (574,499), (597,490), (584,458), (556,433), (505,415), (496,429), (467,429), (460,414), (427,420), (397,438), (373,461), (361,492), (387,499), (358,502)])
        self.hitboxes.append([(561,279), (570,322), (593,347), (625,366), (657,375), (671,343), (699,342), (716,374), (755,358), (785,332), (801,300), (802,279), (775,277), (800,265), (787,234), (759,210), (727,196), (708,191), (700,206), (669,204), (663,189), (628,198), (595,218), (573,242), (564,269), (589,276), (561,279)])
        self.hitboxes.append([(990,538), (963,538), (963,730), (750,943), (555,943), (555,993), (565,993), (566,954), (754,954), (973,733), (974,548), (990,548), (990,538)])
        self.hitboxes.append([(5,538), (33,538), (33,738), (240,944), (430,944), (429,993), (418,993), (419,955), (233,954), (22,743), (22,548), (5,548), (5,538)])
        self.hitboxes.append([(561,716), (568,751), (586,778), (617,800), (657,813), (670,788), (702,787), (716,811), (760,792), (792,759), (802,716), (777,713), (800,704), (787,672), (759,647), (708,629), (699,643), (670,643), (663,628), (630,634), (600,652), (576,675), (564,706), (590,713), (561,716)])
        self.hitboxes.append([(146,715), (153,750), (171,777), (202,799), (242,812), (255,787), (287,786), (301,810), (345,791), (377,758), (387,715), (362,712), (385,703), (372,671), (344,646), (293,628), (284,642), (255,642), (248,627), (215,633), (185,651), (161,674), (149,705), (175,712), (146,715)])        
        self.draw_hitboxes = False   # Debugging tool

    def hit_test(self, rect):
        # before we can test for collisions we have to work out where the hitboxes are located on the screen.
        for hitbox in self.hitboxes:
            new_poly = []
            for point in hitbox: 
                new_x = self.rect.topleft[0] + point[0]
                new_y = self.rect.topleft[1] + point[1]
                new_poly.append([new_x,new_y])
            result = collideRectPolygon(rect, new_poly)
        #print(f"Player x: {player.x}, Player y: {player.y}, Collision: {result}")  # debug code
        #print(f"Map TopLeft: {self.rect.topleft}, Hitbox coords:{new_poly}")  # debug code
            if result == True:
                return result

    def update(self):
        self.rect = self.image.get_rect(center=(self.x-self.player.x+(WIDTH//2),self.y-self.player.y+(HEIGHT//2)))
        if self.draw_hitboxes == True:
            for hitbox in self.hitboxes:
                pygame.draw.polygon(self.image, (255,0,0), hitbox)

