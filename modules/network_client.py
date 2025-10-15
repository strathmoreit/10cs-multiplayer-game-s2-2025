# network_client.py
import time
import socketio
from modules.entities import Other_Player  # <-- use your class
from modules.settings import PLAYER_START_X, PLAYER_START_Y
from modules.assets_net import *  # functions to manage client sprite sheets

def hex_to_rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c*2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def get_xy(player):
    # adjust to how your Player stores coords
    if hasattr(player, "x") and hasattr(player, "y"):
        return player.x, player.y
    return player.rect.x, player.rect.y

class NetClient:
    def __init__(self, state, server_url, name="Player", color="#64b5f6"):
        self.state = state
        self.url = server_url
        self.name = name
        self.color = color
        self.sio = socketio.Client()
        self.my_sid = None
        self.connected = False
        self.last_emit = 0.0
        self.emit_interval = 1 / 30.0
        self._last_pos = None          # for local movement deltas
        self._prev_remote_pos = {}     # sid -> (x,y) to drive other players' animation
        self.sheet_cache = {}   # hash -> {"frames": [Surfaces], "meta": {...}}
        self._pending_ops = {}  # sid -> sheet_hash waiting to apply

        # --- handlers ---
        def on_connect():
            self.my_sid = self.sio.get_sid()
            self.connected = True
            print("connected:", self.my_sid)

        def on_chat(msg):
            # msg: {"from": "...", "sid": "...", "text": "..."}
            msg = f'{msg.get("from", "")}: {msg.get("text", "")}'
            if state.message_list == "":
                self.state.message_list = msg 
            else:
                self.state.message_list = self.state.message_list  + "\n" + msg 

        def on_world(world):
            # world: { sid: {"x","y","name","color"} }
            self.state.player_data.clear()

            # Add/update sprites for others
            for sid, pdata in world.items():
                x, y = int(pdata["x"]), int(pdata["y"])
                name = pdata.get("name", sid[:5])
                color_hex = pdata.get("color", "#64b5f6")
                self.state.player_data[sid] = {"x": x, "y": y, "name": name, "color": color_hex}

                # --- treat *either* SID as "me" ---
                is_self = (sid == self.sio.sid) or (sid == self.my_sid)
                if is_self:
                    # lock local player to server (prevents camera/world drift)
                    if self.state.player is not None:
                        self.state.player.x = x
                        self.state.player.y = y
                        self._last_pos = (x, y)   # keep delta baseline aligned
                    continue

                # ensure a sprite exists for remote players
                if sid not in self.state.players_group:
                    op = Other_Player()
                    # set initial colour once (convert hex -> (r,g,b))
                    try:
                        op.set_colour(hex_to_rgb(color_hex))
                    except Exception:
                        pass  # fallback to default colours if anything odd
                    # set initial world position
                    op.x, op.y = x, y
                    
                    # below added to handle client sprite sheets V7.2
                    op.sid = sid  # so ensure_sheet can reference it
                    app = pdata.get("appearance", {})
                    sheet_hash = app.get("hash", "")
                    meta = {"count": int(app.get("count", 1)), "cols": int(app.get("cols", 9)),
                            "pad": int(app.get("pad", 0)), "scale": float(app.get("scale", 1.0))}
                    op.ensure_sheet(sheet_hash, self, meta)  

                    # orient based on first update
                    op.facing = "right"
                    op.animation_state = "idle_right"
                    self.state.players_group[sid] = op
                    self._prev_remote_pos[sid] = (x, y)
                else:
                    op = self.state.players_group[sid]
                    # compute delta to drive animation/facing
                    px, py = self._prev_remote_pos.get(sid, (op.x, op.y))
                    dx, dy = x - px, y - py

                    # update animation state
                    if dx == 0 and dy == 0:
                        # idle maintains facing
                        if op.facing == "left":
                            op.animation_state = "idle_left"
                        else:
                            op.animation_state = "idle_right"
                    else:
                        # moving: face by x if possible, else keep last facing
                        if dx < 0:
                            op.facing = "left"
                            op.animation_state = "walk_left"
                        elif dx > 0:
                            op.facing = "right"
                            op.animation_state = "walk_right"
                        else:
                            # vertical only movement; keep facing, set walk_
                            op.animation_state = "walk_left" if op.facing == "left" else "walk_right"

                    # apply new absolute position
                    op.x, op.y = x, y
                    self._prev_remote_pos[sid] = (x, y)

            # Remove sprites for players no longer present
            for sid in list(self.state.players_group.keys()):
                if sid not in world:
                    spr = self.state.players_group.pop(sid, None)
                    if spr and hasattr(spr, "kill"):
                        spr.kill()
                    self._prev_remote_pos.pop(sid, None)

            # --- explicit prune: never keep a self-sprite, even if created earlier ---
            for self_sid in (self.sio.sid, self.my_sid):
                if self_sid and (self_sid in self.state.players_group):
                    spr = self.state.players_group.pop(self_sid, None)
                    if spr and hasattr(spr, "kill"):
                        spr.kill()

        def on_sheet_bytes(payload):
            # payload: {"hash","meta","png_b64"}
            h = payload.get("hash", "")
            if not h or h in self.sheet_cache:
                return
            png = b64decode_bytes(payload.get("png_b64", ""))
            if not is_png(png):
                return
            meta = payload.get("meta", {}) or {}
            surf = load_surface_from_png_bytes(png)
            frames = frames_from_surface(
                surf,
                cols=int(meta.get("cols", 9)),
                count=int(meta.get("count", 1)),
                pad=int(meta.get("pad", 0)),
                scale=float(meta.get("scale", 1.0)),
            )
            self.sheet_cache[h] = {"frames": frames, "meta": meta}

            # apply to any remote players waiting on this hash
            for sid, pending_hash in list(self._pending_ops.items()):
                if pending_hash == h and sid in self.state.players_group:
                    op = self.state.players_group[sid]
                    op.apply_frames(frames)
                    del self._pending_ops[sid]

        def on_disconnect():
            self.connected = False
            print("disconnected")

        self.sio.on("connect", on_connect)
        self.sio.on("world", on_world)
        self.sio.on("disconnect", on_disconnect)
        self.sio.on("chat", on_chat)
        self.sio.on("sheet_bytes", on_sheet_bytes)
    
    def send_chat(self, text: str):
        self.sio.emit("chat", {"text": text})

    def _get_spawn_xy(self):
        p = self.state.player
        if p is None:
            return (PLAYER_START_X, PLAYER_START_Y)
        # Prefer explicit attributes if they exist and are not None
        if getattr(p, "x", None) is not None and getattr(p, "y", None) is not None:
            return int(p.x), int(p.y)
        # Fallback to sprite rect center
        if hasattr(p, "rect"):
            return int(p.rect.centerx), int(p.rect.centery)
        return (PLAYER_START_X, PLAYER_START_Y)

    # def connect(self, timeout=0.6) -> bool:
    #     app = self._my_appearance()
    #     x0, y0 = self._get_spawn_xy()
    #     try:
    #         # Short timout to avoid blocking the game start
    #         self.sio.connect(
    #             self.url, 
    #             auth={"name": self.name, "color": self.color, "x": x0, "y": y0},
    #             wait=True,
    #             wait_timeout=timeout,
    #             transports=["websocket"], # Speeds up failure if no server
    #         )
    #         # return True
    #     except Exception as e:
    #         print(f"No server at {self.url}; running offline. ({e})")
    #         self.connected = False
    #         return False

    #     # send bytes for png sprite sheet (if we have them) as a separate event
    #     if app.get("hash") and app.get("register_b64"):
    #         self.sio.emit("sheet_register", {
    #             "hash": app["hash"],
    #             "meta": {"count": app["count"], "cols": app["cols"], "pad": app["pad"], "scale": app["scale"]},
    #             "png_b64": app["register_b64"],
    #         })
    #     print("[APP] sheet_register sent:", app["hash"]) # debug code: working out why custom sprite sheet isn't being applied over the network 29/9/2025
    #     return True

    def connect(self, timeout=0.6) -> bool:
        # new connect routine to fix sprite_sheets not sending over network. Delete the above commented out one if this works
        app = self._my_appearance()  # {"hash","count","cols","pad","scale","register_b64"}
        auth_app = {k: app[k] for k in ("hash","count","cols","pad","scale")}  # strip register_b64

        x0, y0 = self._get_spawn_xy()
        try:
            self.sio.connect(
                self.url,
                auth={
                    "name": self.name,
                    "color": self.color,
                    "x": x0, "y": y0,
                    "appearance": auth_app,                  # ← send metadata here
                },
                wait=True,
                wait_timeout=timeout,
                transports=["websocket"],
            )
        except Exception as e:
            print(f"No server at {self.url}; running offline. ({e})")
            self.connected = False
            return False

        # Upload the PNG bytes after we’re connected (if available)
        if app.get("hash") and app.get("register_b64"):
            self.sio.emit("sheet_register", {
                "hash": app["hash"],
                "meta": {"count": app["count"], "cols": app["cols"], "pad": app["pad"], "scale": app["scale"]},
                "png_b64": app["register_b64"],
            })
            # Nudge peers to re-check (handles race where they asked before bytes existed)
            self.sio.emit("set_appearance", {"hash": app["hash"]})

        return True


    def tick_send_move(self):
        if not self.connected or self.my_sid is None or self.state.player is None:
            return
        now = time.time()
        if now - self.last_emit < self.emit_interval:
            return
        x, y = get_xy(self.state.player)
        if self._last_pos is None:
            self._last_pos = (x, y)
            return
        dx, dy = x - self._last_pos[0], y - self._last_pos[1]
        if dx or dy:
            try:
                self.sio.emit("move", {"dx": int(dx), "dy": int(dy)})
                self._last_pos = (x, y)
                self.last_emit = now
            except Exception as e:
                print("emit failed:", e)

    def close(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass
    
    def _my_appearance(self):
        P = self.state.player.__class__
        cols  = int(getattr(P, "SHEET_COLS", 9))
        count = int(getattr(P, "SHEET_COUNT", 1))
        pad   = int(getattr(P, "SHEET_PAD", 0))
        scale = float(getattr(P, "SHEET_SCALE", 1.0))
        # compute hash/bytes if possible
        sheet_path = getattr(P, "SHEET", None)
        h = ""; b64 = ""
        try:
            if sheet_path:
                with open(sheet_path, "rb") as f:
                    b = f.read()
                if len(b) <= MAX_SHEET_BYTES and is_png(b):
                    h = sha256_hex(b)
                    b64 = b64encode_bytes(b)
                    # cache our own frames locally now
                    if h not in self.sheet_cache:
                        surf = load_surface_from_png_bytes(b)
                        frames = frames_from_surface(surf, cols=cols, count=count, pad=pad, scale=scale)
                        self.sheet_cache[h] = {"frames": frames, "meta": {"cols": cols, "count": count, "pad": pad, "scale": scale}}
        except Exception:
            pass

        return {
            "hash": h, "count": count, "cols": cols, "pad": pad, "scale": scale,
            "register_b64": b64,   # empty if not available/too big
        }