# player_loader.py
# Nstebbing 28/9/25 (ChatGPT Assisting)
# Supports running a game where students have to write their own Player class.
# If the Player class is not written yet a NullPlayer object will be substituted.

import importlib, importlib.util, sys
from pathlib import Path
from modules.entities import BasePlayer
from modules.settings import PLAYER_START_X, PLAYER_START_Y

def _load_student_module():
    # 1) Try normal top-level import
    try:
        return importlib.import_module("student_code")
    except ModuleNotFoundError:
        pass

    # 2) Try by file path: parent of this file is the project root
    root = Path(__file__).resolve().parents[1]
    cand = root / "student_code.py"
    if cand.exists():
        spec = importlib.util.spec_from_file_location("student_code", str(cand))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return None

def make_player(color, projectiles_group, screen, x=PLAYER_START_X, y=PLAYER_START_Y):
    mod = _load_student_module()
    if mod and hasattr(mod, "Player"):
        try:
            return mod.Player(color, projectiles_group, screen, x, y)
        except Exception as e:
            print(f"[player_loader] student Player failed: {e!r}")
    # fallback
    from engine_base import BasePlayer
    return BasePlayer(color, projectiles_group, screen, x, y, playable=True)


# import importlib
# from modules.entities import BasePlayer  # optional: use as fallback too

# def make_player(color, projectiles_group, screen, x, y):
#     try:
#         student_mod = importlib.import_module("student_code")
#         StudentPlayer = getattr(student_mod, "Player")
#         return StudentPlayer(color, projectiles_group, screen, x, y)
#     except Exception as e:
#         print(f"[player_loader] Using BasePlayer ({e})")
#         return BasePlayer(color, projectiles_group, screen, x, y)
