# server.py
import random
import socketio
from aiohttp import web
from settings import WIDTH, HEIGHT, PLAYER_START_X, PLAYER_START_Y 
import base64
from assets_net import MAX_SHEET_BYTES, is_png  # used by sheet_register

W, H = WIDTH, HEIGHT
SIZE = 20
WORLD = {}
SHEETS = {}  # hash -> {"meta": {...}, "png": bytes}

def clamp(n, lo, hi): return max(lo, min(hi, n))

# Async Socket.IO server hosted by aiohttp
sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
app = web.Application()
sio.attach(app)

# Authoritative world state: { sid: {"x": int, "y": int, "name": str, "color": str} }
WORLD = {}

async def on_connect(sid, environ, auth=None):
    name  = (auth or {}).get("name")  or sid[:5]
    color = (auth or {}).get("color") or "#64b5f6"

    # If you kept Fix A's constants, ignore them for now
    # Use the client's spawn if provided; else fall back to your game defaults
    x = int((auth or {}).get("x", PLAYER_START_X))
    y = int((auth or {}).get("y", PLAYER_START_Y))

    # pull appearance meta from auth (added v7.2 to manage client sprite sheets)
    app_in = auth.get("appearance", {}) or {}
    appearance = {
        "hash":  str(app_in.get("hash", "")),
        "count": int(app_in.get("count", 1)),
        "cols":  int(app_in.get("cols", 9)),
        "pad":   int(app_in.get("pad", 0)),
        "scale": float(app_in.get("scale", 1.0)),
    }

    WORLD[sid] = {"x": x, "y": y, "name": name, "color": color, "appearance": appearance}
    await sio.emit("world", WORLD)

    print("APPEAR:", WORLD[sid]["appearance"]) #debug code - checking that appearance is passed

async def on_move(sid, data):
    p = WORLD.get(sid)
    if not p: return
    p["x"] += int(data.get("dx", 0))
    p["y"] += int(data.get("dy", 0))
    await sio.emit("world", WORLD)

async def on_disconnect(sid):
    if sid in WORLD:
        del WORLD[sid]
        await sio.emit("world", WORLD)

async def on_chat(sid, data):
    text = str(data.get("text", ""))[:200]
    if not text:
        return
    # include a display name if you track one in WORLD; fallback to sid
    name = WORLD.get(sid, {}).get("name", sid[:5])
    await sio.emit("chat", {"from": name, "sid": sid, "text": text})

sio.on("chat", on_chat)
sio.on("connect", on_connect)
sio.on("move", on_move)
sio.on("disconnect", on_disconnect)

# --- HANDLE CLIENT SPRITE SHEETS ---
SHEETS = {}  # hash -> {"meta": {...}, "png": bytes}

async def on_sheet_register(sid, data):
    """
    data: { "hash": str, "meta": {count, cols, pad, scale}, "png_b64": str }
    """
    try:
        h = str(data.get("hash", ""))
        meta = data.get("meta", {}) or {}
        b64 = data.get("png_b64", "")
        if not h or not b64:
            return
        if h in SHEETS:
            return  # already have it
        png = base64.b64decode(b64.encode("ascii"))
        if len(png) > MAX_SHEET_BYTES or not is_png(png):
            return  # reject oversize/non-png
        SHEETS[h] = {"meta": {
            "count": int(meta.get("count", 1)),
            "cols":  int(meta.get("cols", 9)),
            "pad":   int(meta.get("pad", 0)),
            "scale": float(meta.get("scale", 1.0)),
        }, "png": png}
        # (optional) nothing to broadcast; clients will request when needed
    except Exception:
        pass

async def on_sheet_get(sid, data):
    """
    data: { "hash": str }
    Reply only to requester: { "hash": str, "meta": {...}, "png_b64": str }
    """
    h = str((data or {}).get("hash", ""))
    rec = SHEETS.get(h)
    if not rec:
        return
    payload = {
        "hash": h,
        "meta": rec["meta"],
        "png_b64": base64.b64encode(rec["png"]).decode("ascii"),
    }
    await sio.emit("sheet_bytes", payload, to=sid)

sio.on("sheet_register", on_sheet_register)
sio.on("sheet_get", on_sheet_get)

async def on_set_appearance(sid, data): 
    ''' Allows student to change spritesheet mid-game)'''
    p = WORLD.get(sid); 
    if not p: return
    app = p["appearance"]
    app.update({
        "hash":  str(data.get("hash",  app.get("hash", ""))),
        "count": int(data.get("count", app.get("count", 1))),
        "cols":  int(data.get("cols",  app.get("cols", 9))),
        "pad":   int(data.get("pad",   app.get("pad", 0))),
        "scale": float(data.get("scale",app.get("scale", 1.0))),
    })
    await sio.emit("world", WORLD)

sio.on("set_appearance", on_set_appearance)

if __name__ == "__main__":
    print("Serving on 0.0.0.0:8000")
    web.run_app(app, host="0.0.0.0", port=8000)