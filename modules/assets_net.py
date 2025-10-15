# assets_net.py
import base64, hashlib, io, pygame, math

MAX_SHEET_BYTES = 512 * 1024  # 512 KB safety cap

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def is_png(b: bytes) -> bool:
    return len(b) > 8 and b[:8] == b"\x89PNG\r\n\x1a\n"

def b64encode_bytes(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def b64decode_bytes(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

def load_surface_from_png_bytes(b: bytes) -> pygame.Surface:
    return pygame.image.load(io.BytesIO(b)).convert_alpha()

def frames_from_surface(sheet: pygame.Surface, *, cols: int, count: int, pad: int = 0, scale: float = 1.0):
    if scale != 1.0:
        w, h = sheet.get_size()
        sheet = pygame.transform.smoothscale(sheet, (int(w*scale), int(h*scale)))
    sw, sh = sheet.get_size()
    rows = math.ceil(count / cols)
    fw = (sw - (cols - 1) * pad) // cols
    fh = (sh - (rows - 1) * pad) // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            if len(frames) >= count: break
            x = c * (fw + pad); y = r * (fh + pad)
            frames.append(sheet.subsurface(pygame.Rect(x, y, fw, fh)).copy())
    return frames
