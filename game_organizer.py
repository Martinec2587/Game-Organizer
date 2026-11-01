#!/usr/bin/env python3
"""
Organizador de Juegos / Game Organizer  (CustomTkinter)

Instalar dependencias:
    pip install customtkinter pillow icoextract

Funciones:
  - Idiomas: Español / English (se guarda la elección)
  - Agregar juegos (.exe sueltos) o una carpeta completa (detecta un exe por juego)
  - Organización automática por categorías (palabras clave + géneros de Steam si hay internet)
  - Logo: 1) icono del propio .exe  2) si no tiene, lo busca en internet (Steam)
          3) si no hay WiFi/Internet, lo muestra en la app (aviso + etiqueta en cada juego)
  - Seleccionar juegos con casillas: mover de categoría, quitar, etc.
  - Jugar: en Windows lanza el .exe; en Linux usa Wine si está instalado
"""

import hashlib
import html as _html
import io
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import difflib
from collections import defaultdict
import urllib.parse
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from icoextract import IconExtractor
except ImportError:  # la app funciona igual, pero sin extraer iconos de los .exe
    IconExtractor = None

# --------------------------------------------------------------------------- #
#  Rutas y constantes
# --------------------------------------------------------------------------- #
APP_DIR = Path.home() / ".game_organizer"
ICON_DIR = APP_DIR / "icons"
DB_FILE = APP_DIR / "library.json"
APP_DIR.mkdir(exist_ok=True)
ICON_DIR.mkdir(exist_ok=True)

CARD_W, CARD_H = 250, 82
ICON_PX = 54

CATS = ["action", "shooter", "rpg", "adventure", "strategy", "simulation",
        "sports", "racing", "horror", "fighting", "platformer", "puzzle",
        "emulators", "other"]

# --------------------------------------------------------------------------- #
#  Traducciones
# --------------------------------------------------------------------------- #
TR = {
    "es": {
        "title": "🎮 Organizador de Juegos",
        "add_games": "➕ Agregar juegos (.exe)",
        "add_folder": "📁 Agregar carpeta",
        "organize": "🗂 Organizar automáticamente",
        "remove": "🗑 Quitar seleccionados",
        "move_to": "Mover seleccionados a…",
        "select_all": "Seleccionar todo",
        "select_none": "Deseleccionar",
        "search": "Buscar juego…",
        "language": "Idioma",
        "lang_auto": "Automático (sistema)",
        "theme": "Tema",
        "dark": "Oscuro", "light": "Claro", "system": "Sistema",
        "online": "Conectado a internet",
        "offline": "Sin conexión WiFi",
        "offline_banner": "⚠ No hay WiFi / Internet conectado: no se pueden buscar los logos que faltan. "
                          "Se buscarán solos cuando vuelva la conexión.",
        "no_logo": "sin logo",
        "no_logo_offline": "sin logo · sin WiFi",
        "searching": "buscando logo…",
        "play": "▶",
        "empty": "Tu biblioteca está vacía.\nAgrega juegos con los botones de la izquierda.",
        "no_results": "Ningún juego coincide con la búsqueda.",
        "games": "juegos", "selected": "seleccionados",
        "confirm_remove": "¿Quitar {n} juego(s) de la biblioteca?\n(No se borran de tu disco)",
        "pick_exe": "Selecciona los ejecutables de tus juegos",
        "pick_folder": "Selecciona la carpeta que contiene tus juegos",
        "error": "Error",
        "launch_error": "No se pudo iniciar el juego:\n{e}",
        "no_wine": "No estás en Windows y no se encontró Wine.",
        "scanning": "Escaneando carpeta…",
        "set_cover": "🖼 Cambiar portada",
        "rename": "✏ Renombrar",
        "open_folder": "📂 Abrir carpeta",
        "select_one_folder": "Marca la casilla de UN solo juego para abrir su carpeta\n(o haz clic derecho sobre su imagen).",
        "folder_error": "No se pudo abrir la carpeta:\n{e}",
        "rename_title": "Renombrar juego",
        "rename_prompt": "Escribe el nombre que quieres mostrar.\nEl archivo .exe NO se renombra.\n(Déjalo vacío para volver al nombre automático.)",
        "select_one_rename": "Marca la casilla de UN solo juego para renombrarlo\n(o haz doble clic sobre su nombre).",
        "ok": "Aceptar", "cancel": "Cancelar",
        "pick_cover": "Selecciona una imagen de portada (PNG, JPG, WEBP o ICO)",
        "cover_error": "No se pudo usar esa imagen:\n{e}",
        "select_one": "Marca la casilla de UN solo juego para cambiar su portada\n(o haz clic directamente sobre su imagen).",
        "cat_action": "Acción", "cat_shooter": "Disparos / FPS", "cat_rpg": "Rol (RPG)",
        "cat_adventure": "Aventura", "cat_strategy": "Estrategia", "cat_simulation": "Simulación",
        "cat_sports": "Deportes", "cat_racing": "Carreras", "cat_horror": "Terror",
        "cat_fighting": "Lucha", "cat_platformer": "Plataformas", "cat_puzzle": "Puzzle / Casual",
        "cat_emulators": "Emuladores y launchers", "cat_other": "Otros",
    },
    "en": {
        "title": "🎮 Game Organizer",
        "add_games": "➕ Add games (.exe)",
        "add_folder": "📁 Add folder",
        "organize": "🗂 Auto-organize",
        "remove": "🗑 Remove selected",
        "move_to": "Move selected to…",
        "select_all": "Select all",
        "select_none": "Deselect",
        "search": "Search game…",
        "language": "Language",
        "lang_auto": "Automatic (system)",
        "theme": "Theme",
        "dark": "Dark", "light": "Light", "system": "System",
        "online": "Connected to the internet",
        "offline": "No WiFi connection",
        "offline_banner": "⚠ No WiFi / Internet connected: missing logos can't be searched. "
                          "They will be fetched automatically once the connection is back.",
        "no_logo": "no logo",
        "no_logo_offline": "no logo · no WiFi",
        "searching": "searching logo…",
        "play": "▶",
        "empty": "Your library is empty.\nAdd games with the buttons on the left.",
        "no_results": "No games match your search.",
        "games": "games", "selected": "selected",
        "confirm_remove": "Remove {n} game(s) from the library?\n(They are not deleted from disk)",
        "pick_exe": "Select your game executables",
        "pick_folder": "Select the folder that contains your games",
        "error": "Error",
        "launch_error": "Could not start the game:\n{e}",
        "no_wine": "You are not on Windows and Wine was not found.",
        "scanning": "Scanning folder…",
        "set_cover": "🖼 Change cover",
        "rename": "✏ Rename",
        "open_folder": "📂 Open folder",
        "select_one_folder": "Tick the checkbox of ONE game to open its folder\n(or right-click its image).",
        "folder_error": "Could not open the folder:\n{e}",
        "rename_title": "Rename game",
        "rename_prompt": "Type the name you want to display.\nThe .exe file is NOT renamed.\n(Leave empty to go back to the automatic name.)",
        "select_one_rename": "Tick the checkbox of ONE game to rename it\n(or double-click its name).",
        "ok": "OK", "cancel": "Cancel",
        "pick_cover": "Select a cover image (PNG, JPG, WEBP or ICO)",
        "cover_error": "Could not use that image:\n{e}",
        "select_one": "Tick the checkbox of ONE game to change its cover\n(or click directly on its image).",
        "cat_action": "Action", "cat_shooter": "Shooters / FPS", "cat_rpg": "RPG",
        "cat_adventure": "Adventure", "cat_strategy": "Strategy", "cat_simulation": "Simulation",
        "cat_sports": "Sports", "cat_racing": "Racing", "cat_horror": "Horror",
        "cat_fighting": "Fighting", "cat_platformer": "Platformers", "cat_puzzle": "Puzzle / Casual",
        "cat_emulators": "Emulators & launchers", "cat_other": "Other",
    },
}

# --------------------------------------------------------------------------- #
#  Categorización automática
# --------------------------------------------------------------------------- #
# El orden importa: la primera categoría que coincida gana.
KEYWORDS = {
    "emulators": ["steam", "epic games launcher", "gog galaxy", "retroarch", "dolphin", "pcsx2",
                  "rpcs3", "yuzu", "ryujinx", "cemu", "ppsspp", "duckstation", "citra", "mgba",
                  "bsnes", "snes9x", "project64", "xemu", "xenia", "launcher", "emulator"],
    "horror": ["resident evil", "silent hill", "outlast", "amnesia", "dead space", "five nights",
               "fnaf", "horror", "phasmophobia", "alien isolation", "evil within", "layers of fear",
               "dying light", "until dawn", "little nightmares", "granny", "poppy playtime"],
    "fighting": ["street fighter", "mortal kombat", "tekken", "smash", "guilty gear", "injustice",
                 "soulcalibur", "fighter", "brawl", "king of fighters", "blazblue", "fighterz"],
    "racing": ["racing", "need for speed", "nfs", "forza", "gran turismo", "assetto", "dirt",
               "rally", "burnout", "kart", "wrc", "f1", "race", "trackmania", "beamng"],
    "sports": ["fifa", "fc 24", "fc 25", "fc 26", "pes", "efootball", "nba", "nfl", "nhl", "madden",
               "football", "soccer", "golf", "tennis", "wwe", "ufc", "rugby", "basketball",
               "skate", "tony hawk", "pga", "mlb", "rocket league"],
    "shooter": ["counter strike", "counter-strike", "cs2", "csgo", "valorant", "call of duty",
                "doom", "quake", "halo", "battlefield", "half life", "half-life", "far cry",
                "apex", "overwatch", "fps", "sniper", "warzone", "wolfenstein", "bioshock",
                "titanfall", "payday", "left 4 dead", "rainbow six", "borderlands", "fortnite",
                "pubg", "destiny", "crysis", "metro", "shooter", "unreal tournament", "cod"],
    "strategy": ["age of", "civilization", "total war", "starcraft", "warcraft", "command and conquer",
                 "xcom", "stronghold", "anno", "stellaris", "europa universalis", "hearts of iron",
                 "crusader kings", "tower defense", "rts", "empire", "company of heroes",
                 "humankind", "banished", "frostpunk", "they are billions", "heroes of might"],
    "rpg": ["witcher", "skyrim", "elder scrolls", "fallout", "diablo", "dark souls", "elden ring",
            "final fantasy", "dragon age", "mass effect", "baldur", "cyberpunk", "pathfinder",
            "persona", "rpg", "path of exile", "kingdom come", "pillars of eternity", "divinity",
            "torchlight", "bloodborne", "sekiro", "dragon quest", "pokemon", "oblivion", "morrowind"],
    "simulation": ["simulator", "simulation", "sims", "farming", "cities skylines", "planet zoo",
                   "planet coaster", "tycoon", "flight", "euro truck", "american truck", "kerbal",
                   "rimworld", "factorio", "satisfactory", "stardew", "house flipper", "cooking",
                   "powerwash", "football manager"],
    "platformer": ["mario", "sonic", "rayman", "celeste", "hollow knight", "ori and", "cuphead",
                   "super meat boy", "platformer", "crash bandicoot", "spyro", "terraria", "geometry dash"],
    "puzzle": ["puzzle", "portal", "tetris", "candy", "bejeweled", "sudoku", "chess", "solitaire",
               "the witness", "talos principle", "baba is you", "mahjong", "match", "among us",
               "minesweeper", "jigsaw", "cut the rope"],
    "adventure": ["tomb raider", "uncharted", "assassin", "zelda", "life is strange", "telltale",
                  "adventure", "walking dead", "monkey island", "grand theft auto", "gta",
                  "red dead", "minecraft", "spider-man", "spiderman", "batman", "god of war",
                  "hitman", "just cause", "watch dogs", "sleeping dogs", "mafia", "max payne",
                  "far cry primal", "lego", "journey", "firewatch", "subnautica", "the forest"],
}
def _nk(s: str) -> str:
    """Normaliza: minúsculas y todo lo que no sea letra/número -> un espacio."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


_KW_RE = {}
for _cat, _kws in KEYWORDS.items():
    _norm = sorted({_nk(k) for k in _kws if _nk(k)}, key=len, reverse=True)
    _KW_RE[_cat] = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in _norm) + r")(?![a-z0-9])")

LOOKUP_V = 2  # versión del algoritmo de búsqueda online (si cambia, se vuelve a buscar)

# Etiquetas/géneros de internet -> puntos por categoría.
# Se acumulan TODAS las reglas que coincidan con una etiqueta, y luego se multiplica por el
# peso de la etiqueta (votos relativos en SteamSpy, 1.0 para géneros de Steam, 1.5 Wikidata).
_TAG_RULES = [
    (r"\bfps\b|shooter|shoot ?'?em ?up|shmup|battle royale|bullet hell|gunplay", {"shooter": 3}),
    (r"bullet hell|shoot ?'?em ?up|shmup", {"action": 1}),
    (r"horror", {"horror": 3}),
    (r"zombie|lovecraft|jump scare|creepy", {"horror": 1}),
    (r"fighting|\bfighters?\b", {"fighting": 3}),
    (r"beat ?'?em ?up", {"fighting": 2, "action": 1.5}),
    (r"racing|driving|motorsport|\bracer\b|\bkart\b|formula|drifting|\brally\b", {"racing": 3}),
    (r"automobile", {"racing": 2, "simulation": 1}),
    (r"\bsports?\b|football|soccer|basketball|baseball|\bgolf\b|tennis|wrestling|hockey|rugby|"
     r"cricket|skateboard|snowboard|boxing|e-?sports|\bmma\b", {"sports": 3}),
    (r"strategy|\brts\b|\b4x\b|tower defense|tactics|wargame|real-time with pause", {"strategy": 3}),
    (r"\bmoba\b", {"strategy": 2}),
    (r"turn-based", {"strategy": 1}),
    (r"city[- ]build|colony", {"simulation": 2.5, "strategy": 1}),
    (r"management|tycoon|automation|farming|life sim|economy", {"simulation": 2.5}),
    (r"(?<!walking )simulat|\bsim\b", {"simulation": 3}),
    (r"sandbox|crafting|base building|\bbuilding\b", {"simulation": 1}),
    (r"survival", {"adventure": 1, "simulation": 0.5}),
    (r"\brpg\b|role-?playing|jrpg|crpg|party-based", {"rpg": 3}),
    (r"dungeon crawler", {"rpg": 2, "action": 0.5}),
    (r"roguelike|roguelite|rogue-like|rogue-lite", {"action": 1.5, "rpg": 1}),
    (r"souls-?like", {"rpg": 1.5, "action": 1.5}),
    (r"\bmmo|massively multiplayer", {"rpg": 2}),
    (r"adventure|point\W*(?:&|and)?\W*click|visual novel|walking simulator|interactive fiction|text-based",
     {"adventure": 3}),
    (r"action[- ]adventure", {"action": 1}),
    (r"story rich|narrative|choices matter|detective|mystery|exploration|cinematic", {"adventure": 1.5}),
    (r"open[- ]world", {"adventure": 1.5, "action": 0.5}),
    (r"\bplatform(?:er|ing)?\b|platform game|metroidvania", {"platformer": 3}),
    (r"metroidvania", {"adventure": 0.5}),
    (r"side[- ]scroll", {"platformer": 0.8}),
    (r"puzzle|match[- ]3|hidden object|\blogic\b|trivia|word game|solitaire|\bchess\b|mahjong|brain",
     {"puzzle": 2.5}),
    (r"casual", {"puzzle": 1.5}),
    (r"board game|card game|card battler|deck-?build|collectible card", {"puzzle": 1.5, "strategy": 1}),
    (r"\baction\b", {"action": 1.5}),
    (r"hack and slash|hack 'n' slash|hack-and-slash|character action|spectacle fighter|\bbrawler\b",
     {"action": 3}),
    (r"stealth", {"action": 1.5}),
]
TAG_PATTERNS = [(re.compile(p), w) for p, w in _TAG_RULES]


def tag_scores(tag: str) -> dict:
    t = _html.unescape(str(tag)).lower().strip()
    out = defaultdict(float)
    for rx, weights in TAG_PATTERNS:
        if rx.search(t):
            for cat, v in weights.items():
                out[cat] += v
    return out


def score_categories(name: str, path: str = "", tags=None) -> dict:
    """Suma puntos de varias señales: palabras clave del título, ruta del archivo y
    etiquetas/géneros encontrados en internet."""
    s = defaultdict(float)
    padded = " " + _nk(name) + " "
    for cat, rx in _KW_RE.items():
        total = sum(3.0 + (1.0 if " " in m else 0.0) for m in set(rx.findall(padded)))
        if total:
            s[cat] += min(total, 5.0) * (2.0 if cat == "emulators" else 1.0)
    if re.search(r"emulat|retroarch", path.lower()):
        s["emulators"] += 2.0
    for tag, weight in (tags or []):
        for cat, v in tag_scores(tag).items():
            s[cat] += float(weight) * v
    return s


def categorize(name: str, path: str = "", tags=None) -> str:
    s = score_categories(name, path, tags)
    # reversed: en empates gana la categoría más específica ("Acción" es la más genérica)
    best = max(reversed(CATS), key=lambda c: s.get(c, 0.0))
    return best if s.get(best, 0.0) >= 1.5 else "other"


# --------------------------------------------------------------------------- #
#  Nombres e iconos
# --------------------------------------------------------------------------- #
GENERIC = {"game", "launcher", "start", "run", "play", "bin", "main", "app", "client", "shipping",
           "binaries", "bin32", "bin64", "retail", "release", "start_protected_game", "windows",
           "windowsnoeditor", "game_release", "exe", "common", "steamapps"}
IGNORE_EXE = re.compile(r"(unins|setup|install|redist|dxsetup|crash(handler|report|pad)|helper|"
                        r"updater|dotnet|prereq|easyanticheat|battleye|benchmark)", re.I)


def clean_name(s: str) -> str:
    s = re.sub(r"(?i)(?<![a-z0-9])(win64|win32|shipping|x64|x86)(?![a-z0-9])", " ", s)
    s = re.sub(r"(?i)[-_.]?(win64|win32|shipping)$", " ", s)
    s = re.sub(r"[_\-.]+", " ", s)
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def guess_name(path: str) -> str:
    p = Path(path)
    candidates = [p.stem] + [x.name for x in list(p.parents)[:4]]
    for c in candidates:
        cc = clean_name(c)
        if len(cc) > 1 and cc.lower().replace(" ", "") not in GENERIC and cc.lower() not in GENERIC:
            return cc
    return p.stem


def fit_square(img: Image.Image, size=128) -> Image.Image:
    img = ImageOps.contain(img.convert("RGBA"), (size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def extract_exe_icon(exe_path: str, out_png: Path) -> bool:
    """Devuelve True si el .exe tenía un icono y se guardó como PNG."""
    if IconExtractor is None:
        return False
    try:
        data = IconExtractor(exe_path).get_icon()
        img = Image.open(data)
        try:
            sizes = img.ico.sizes()
            img.size = max(sizes, key=lambda s: s[0])
        except Exception:
            pass
        img.load()
        fit_square(img).save(out_png, "PNG")
        return True
    except Exception:
        return False


def placeholder(name: str, size=128) -> Image.Image:
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    color = (60 + (h >> 16) % 140, 60 + (h >> 8 & 255) % 140, 60 + (h & 255) % 140, 255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, size - 4, size - 4), radius=24, fill=color)
    letter = (name.strip()[:1] or "?").upper()
    try:
        font = ImageFont.load_default(size=72)
    except TypeError:
        font = ImageFont.load_default()
    bb = d.textbbox((0, 0), letter, font=font)
    d.text(((size - (bb[2] - bb[0])) / 2 - bb[0], (size - (bb[3] - bb[1])) / 2 - bb[1]),
           letter, fill="white", font=font)
    return img


# --------------------------------------------------------------------------- #
#  Red
# --------------------------------------------------------------------------- #
def is_online(timeout=2.0) -> bool:
    for host in (("1.1.1.1", 53), ("8.8.8.8", 53)):
        try:
            socket.create_connection(host, timeout=timeout).close()
            return True
        except OSError:
            continue
    return False


def http_get(url: str, timeout=8) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "GameOrganizer/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


_EDITION_RE = re.compile(r"\b(definitive|complete|enhanced|ultimate|deluxe|gold|anniversary|special|"
                         r"remastered|remaster|goty|game of the year|director s cut|edition|hd)\b")


def norm_title(s: str) -> str:
    s = re.sub(r"^the ", "", _nk(s))
    return re.sub(r"\s+", " ", _EDITION_RE.sub(" ", s)).strip()


def title_sim(a: str, b: str) -> float:
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if len(a) >= 5 and (b.startswith(a + " ") or a.startswith(b + " ")):
        r = max(r, 0.85)  # "witcher 3" ~ "witcher 3 wild hunt"
    return r


def steam_find(name: str):
    """Busca el juego en Steam (prueba el nombre tal cual y una versión simplificada).
    Lanza OSError si hay problemas de red."""
    for q in dict.fromkeys([name, norm_title(name)]):
        if not q:
            continue
        data = json.loads(http_get(
            f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(q)}&l=english&cc=us"))
        best, score = None, 0.0
        for it in data.get("items", []):
            if it.get("type", "app") != "app":
                continue
            r = title_sim(name, it.get("name", ""))
            if r > score:
                best, score = it, r
        if best and score >= 0.62:
            return best
    return None


def steam_details(appid):
    d = json.loads(http_get(f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"))
    info = d.get(str(appid), {})
    if not info.get("success"):
        return None, []
    data = info["data"]
    return data.get("header_image"), [g["description"] for g in data.get("genres", [])]


def steamspy_tags(appid):
    """Etiquetas de la comunidad con su peso relativo (0-1), ej. [('FPS', 1.0), ('Shooter', 0.93)]."""
    d = json.loads(http_get(f"https://steamspy.com/api.php?request=appdetails&appid={appid}"))
    tags = d.get("tags")
    if not isinstance(tags, dict) or not tags:
        return []
    top = sorted(tags.items(), key=lambda kv: kv[1], reverse=True)[:12]
    mx = top[0][1] or 1
    return [(k, v / mx) for k, v in top if v / mx >= 0.15]


def wikidata_genres(name: str):
    """Géneros del videojuego según Wikidata (para juegos que no están en Steam)."""
    base = "https://www.wikidata.org/w/api.php?format=json&"
    data = json.loads(http_get(
        base + "action=wbsearchentities&language=en&uselang=en&type=item&limit=8&search="
        + urllib.parse.quote(name)))
    best, score = None, 0.0
    for it in data.get("search", []):
        desc = (it.get("description") or "").lower()
        if "video game" not in desc and "computer game" not in desc:
            continue
        r = title_sim(name, it.get("label", "")) - (0.05 if "series" in desc else 0.0)
        if r > score:
            best, score = it, r
    if not best or score < 0.7:
        return []
    ent = json.loads(http_get(base + f"action=wbgetentities&props=claims&ids={best['id']}"))
    claims = ent["entities"][best["id"]].get("claims", {}).get("P136", [])
    ids = [c["mainsnak"]["datavalue"]["value"]["id"] for c in claims
           if c.get("mainsnak", {}).get("datavalue")]
    if not ids:
        return []
    labs = json.loads(http_get(base + "action=wbgetentities&props=labels&languages=en&ids="
                               + "|".join(ids[:10])))
    return [v["labels"]["en"]["value"] for v in labs["entities"].values() if "en" in v.get("labels", {})]


def online_lookup(name: str):
    """Busca portada + categorías en internet: Steam (géneros + etiquetas SteamSpy) y, si el juego
    no está en Steam, Wikidata. Devuelve {'image', 'tags': [[etiqueta, peso], ...]} o None.
    Lanza OSError si no hay red."""
    tags, image, found = [], None, False
    hit = steam_find(name)
    if hit:
        found = True
        image = hit.get("tiny_image")
        try:
            hdr, genres = steam_details(hit["id"])
            image = hdr or image
            tags += [[g, 1.0] for g in genres]
        except Exception:
            pass
        try:
            tags += [[k, w] for k, w in steamspy_tags(hit["id"])]
        except Exception:
            pass
    if not tags:
        try:
            wd = wikidata_genres(name)
        except Exception:
            wd = []
        if wd:
            found = True
            tags += [[g, 1.5] for g in wd]
    return {"image": image, "tags": tags} if found else None


# --------------------------------------------------------------------------- #
#  Biblioteca
# --------------------------------------------------------------------------- #
def new_game(path: str) -> dict:
    path = os.path.abspath(path)
    name = guess_name(path)
    return {
        "id": hashlib.md5(path.lower().encode()).hexdigest()[:12],
        "path": path, "name": name, "category": categorize(name, path), "tags": [], "lookup_v": 0,
        "icon": None, "icon_src": None, "manual": False, "name_manual": False,
        "exe_icon_tried": False, "looked_up": False,
    }


def load_db():
    try:
        data = json.loads(DB_FILE.read_text(encoding="utf-8"))
        settings, games = data.get("settings", {}), data.get("games", [])
    except Exception:
        return {}, []
    for g in games:
        for k, v in new_game(g.get("path", "x")).items():
            g.setdefault(k, v)
        if not g["tags"] and g.get("genres"):          # migración de versiones anteriores
            g["tags"] = [[x, 1.0] for x in g["genres"]]
        if g.get("lookup_v") != LOOKUP_V:              # algoritmo nuevo -> volver a buscar online
            g["looked_up"] = False
        if g.get("icon") and not os.path.exists(g["icon"]):
            g.update(icon=None, icon_src=None, exe_icon_tried=False, looked_up=False)
    return settings, games


def scan_folder(root: str):
    """Encuentra un .exe (el más grande) por cada subcarpeta, hasta 3 niveles."""
    root = Path(root)
    found = []

    def best_exe(folder: Path):
        best, size = None, -1
        base = len(folder.parts)
        for dp, dn, fn in os.walk(folder):
            if len(Path(dp).parts) - base >= 3:
                dn[:] = []
            for f in fn:
                if f.lower().endswith(".exe") and not IGNORE_EXE.search(f):
                    p = os.path.join(dp, f)
                    try:
                        s = os.path.getsize(p)
                    except OSError:
                        continue
                    if s > size:
                        best, size = p, s
        return best

    try:
        entries = sorted(root.iterdir())
    except OSError:
        return found
    for e in entries:
        if e.is_dir():
            b = best_exe(e)
            if b:
                found.append(b)
        elif e.suffix.lower() == ".exe" and not IGNORE_EXE.search(e.name):
            found.append(str(e))
    return found


def detect_system_lang() -> str:
    """Idioma del sistema: 'es' si es español, 'en' si es inglés y 'en' para cualquier otro."""
    if os.name == "nt":
        try:
            import ctypes
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return "es" if primary == 0x0A else "en"
        except Exception:
            pass
    candidates = [os.environ.get(k, "") for k in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        import locale
        candidates.append(locale.getlocale()[0] or "")
    except Exception:
        pass
    for v in candidates:
        v = v.split(":")[0].strip().lower()
        if not v or v in ("c", "posix") or v.startswith("c."):
            continue
        return "es" if v.startswith("es") else "en"
    return "en"


# --------------------------------------------------------------------------- #
#  Aplicación
# --------------------------------------------------------------------------- #
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings, self.games = load_db()
        mode = self.settings.get("lang_mode") or self.settings.get("lang") or "auto"
        self.lang_mode = mode if mode in ("auto", "es", "en") else "auto"
        self.lang = detect_system_lang() if self.lang_mode == "auto" else self.lang_mode
        self.settings.setdefault("theme", "dark")
        ctk.set_appearance_mode(self.settings["theme"])
        ctk.set_default_color_theme("blue")

        self.online = None            # None = aún no comprobado
        self.selected = set()
        self.collapsed = set()
        self.img_cache = {}
        self.q = queue.Queue()
        self.worker_running = False
        self.rerun = False
        self._cols = None
        self._resize_job = None
        self._search_job = None

        self.geometry("1150x720")
        self.minsize(820, 520)
        self.build_ui()
        self.refresh_texts()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Configure>", self.on_resize)

        self.after(250, self.render)
        self.after(50, self.poll)
        self.conn_loop()
        self.start_worker()

    # ---------------- utilidades ---------------- #
    def t(self, key, **kw):
        s = TR[self.lang][key]
        return s.format(**kw) if kw else s

    def save(self):
        self.settings["lang_mode"] = self.lang_mode
        try:
            DB_FILE.write_text(json.dumps({"settings": self.settings, "games": self.games},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def on_close(self):
        self.save()
        self.destroy()

    # ---------------- interfaz ---------------- #
    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self, width=240, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        self.title_lbl = ctk.CTkLabel(side, font=ctk.CTkFont(size=20, weight="bold"), wraplength=210)
        self.title_lbl.pack(padx=15, pady=(20, 15))

        self.btn_add = ctk.CTkButton(side, command=self.add_games)
        self.btn_add.pack(padx=15, pady=5, fill="x")
        self.btn_folder = ctk.CTkButton(side, command=self.add_folder)
        self.btn_folder.pack(padx=15, pady=5, fill="x")
        self.btn_org = ctk.CTkButton(side, command=self.organize, fg_color="#2e8b57", hover_color="#236b43")
        self.btn_org.pack(padx=15, pady=5, fill="x")

        sep = ctk.CTkFrame(side, height=2, fg_color=("gray75", "gray30"))
        sep.pack(fill="x", padx=15, pady=12)

        self.btn_all = ctk.CTkButton(side, command=self.select_all, fg_color="transparent",
                                     border_width=1, text_color=("gray10", "gray90"))
        self.btn_all.pack(padx=15, pady=3, fill="x")
        self.btn_none = ctk.CTkButton(side, command=self.select_none, fg_color="transparent",
                                      border_width=1, text_color=("gray10", "gray90"))
        self.btn_none.pack(padx=15, pady=3, fill="x")
        self.btn_cover = ctk.CTkButton(side, command=self.cover_selected)
        self.btn_cover.pack(padx=15, pady=(10, 3), fill="x")
        self.btn_rename = ctk.CTkButton(side, command=self.rename_selected)
        self.btn_rename.pack(padx=15, pady=3, fill="x")
        self.btn_folder_open = ctk.CTkButton(side, command=self.open_folder_selected)
        self.btn_folder_open.pack(padx=15, pady=3, fill="x")
        self.move_menu = ctk.CTkOptionMenu(side, values=["-"], command=self.move_selected)
        self.move_menu.pack(padx=15, pady=(10, 3), fill="x")
        self.btn_remove = ctk.CTkButton(side, command=self.remove_selected,
                                        fg_color="#b23b3b", hover_color="#8a2d2d")
        self.btn_remove.pack(padx=15, pady=3, fill="x")

        # parte baja de la barra lateral
        self.status_lbl = ctk.CTkLabel(side, font=ctk.CTkFont(size=12))
        self.status_lbl.pack(side="bottom", padx=15, pady=(5, 15))
        self.theme_menu = ctk.CTkOptionMenu(side, values=["-"], command=self.set_theme)
        self.theme_menu.pack(side="bottom", padx=15, pady=3, fill="x")
        self.theme_lbl = ctk.CTkLabel(side, anchor="w")
        self.theme_lbl.pack(side="bottom", padx=15, fill="x")
        self.lang_menu = ctk.CTkOptionMenu(side, values=["Español", "English"], command=self.set_lang)
        self.lang_menu.pack(side="bottom", padx=15, pady=3, fill="x")
        self.lang_lbl = ctk.CTkLabel(side, anchor="w")
        self.lang_lbl.pack(side="bottom", padx=15, fill="x")

        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        self.banner = ctk.CTkFrame(main, fg_color="#a83232", corner_radius=8)
        self.banner.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 0))
        self.banner_lbl = ctk.CTkLabel(self.banner, text_color="white", wraplength=800, justify="left")
        self.banner_lbl.pack(padx=12, pady=8, anchor="w")
        self.banner.grid_remove()

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=15, pady=12)
        top.grid_columnconfigure(0, weight=1)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        self.search = ctk.CTkEntry(top, textvariable=self.search_var, height=36)
        self.search.grid(row=0, column=0, sticky="ew")
        self.count_lbl = ctk.CTkLabel(top, text_color=("gray30", "gray70"))
        self.count_lbl.grid(row=0, column=1, padx=(15, 0))

        self.scroll = ctk.CTkScrollableFrame(main, corner_radius=10)
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 15))

    def refresh_texts(self):
        self.title(self.t("title").replace("🎮 ", ""))
        self.title_lbl.configure(text=self.t("title"))
        self.btn_add.configure(text=self.t("add_games"))
        self.btn_folder.configure(text=self.t("add_folder"))
        self.btn_org.configure(text=self.t("organize"))
        self.btn_all.configure(text=self.t("select_all"))
        self.btn_none.configure(text=self.t("select_none"))
        self.btn_remove.configure(text=self.t("remove"))
        self.btn_cover.configure(text=self.t("set_cover"))
        self.btn_rename.configure(text=self.t("rename"))
        self.btn_folder_open.configure(text=self.t("open_folder"))
        self.move_menu.configure(values=[self.t("cat_" + c) for c in CATS])
        self.move_menu.set(self.t("move_to"))
        self.search.configure(placeholder_text=self.t("search"))
        self.lang_lbl.configure(text=self.t("language"))
        self.theme_lbl.configure(text=self.t("theme"))
        labels = self.lang_labels()
        self.lang_menu.configure(values=list(labels.values()))
        self.lang_menu.set(labels[self.lang_mode])
        self.theme_menu.configure(values=self.theme_values())
        self.theme_menu.set(self.theme_values()[["dark", "light", "system"].index(self.settings["theme"])])
        self.banner_lbl.configure(text=self.t("offline_banner"))
        self.update_status()
        self.update_counts()

    def theme_values(self):
        return [self.t("dark"), self.t("light"), self.t("system")]

    def lang_labels(self):
        return {"auto": self.t("lang_auto"), "es": "Español", "en": "English"}

    def set_lang(self, choice):
        inv = {v: k for k, v in self.lang_labels().items()}
        self.lang_mode = inv.get(choice, "auto")
        self.lang = detect_system_lang() if self.lang_mode == "auto" else self.lang_mode
        self.save()
        self.refresh_texts()
        self.render()

    def set_theme(self, choice):
        mode = dict(zip(self.theme_values(), ["dark", "light", "system"]))[choice]
        self.settings["theme"] = mode
        ctk.set_appearance_mode(mode)
        self.save()

    def update_status(self):
        if self.online is None:
            self.status_lbl.configure(text="…", text_color="gray")
        elif self.online:
            self.status_lbl.configure(text="● " + self.t("online"), text_color="#3cb371")
            self.banner.grid_remove()
        else:
            self.status_lbl.configure(text="● " + self.t("offline"), text_color="#e05555")
            self.banner.grid()

    def update_counts(self):
        self.count_lbl.configure(
            text=f"{len(self.games)} {self.t('games')}  ·  {len(self.selected)} {self.t('selected')}")

    # ---------------- conexión ---------------- #
    def conn_loop(self):
        threading.Thread(target=lambda: self.q.put(("online", is_online())), daemon=True).start()
        self.after(8000, self.conn_loop)

    def set_online(self, state: bool):
        if state == self.online:
            return
        self.online = state
        self.update_status()
        self.render()
        if state:
            self.start_worker()

    def poll(self):
        changed = False
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "update":
                    changed = True
                elif msg[0] == "online":
                    self.set_online(msg[1])
                elif msg[0] == "add":
                    self.add_paths(msg[1])
        except queue.Empty:
            pass
        if changed:
            self.save()
            self.render()
        self.after(400, self.poll)

    # ---------------- trabajo en segundo plano ---------------- #
    def start_worker(self):
        if self.worker_running:
            self.rerun = True
            return
        self.worker_running = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            while True:
                self.rerun = False
                self._process()
                if not self.rerun:
                    break
        finally:
            self.worker_running = False
            self.q.put(("update",))

    def _process(self):
        # 1) icono del propio .exe (local, no necesita internet)
        for g in list(self.games):
            if not g.get("exe_icon_tried"):
                g["exe_icon_tried"] = True
                out = ICON_DIR / f"{g['id']}.png"
                if extract_exe_icon(g["path"], out) and g.get("icon_src") != "custom":
                    g["icon"], g["icon_src"] = str(out), "exe"
                self.q.put(("update",))

        # 2) si no tiene icono (o categoría) -> buscar en internet
        for g in list(self.games):
            need = (not g.get("icon")) or (not g.get("manual"))
            if not need or g.get("looked_up"):
                continue
            if not self.online:
                return  # sin WiFi: se reintenta cuando vuelva la conexión
            try:
                nm = g["name"]
                info = online_lookup(nm)
                if g["name"] != nm:  # lo renombraron mientras se buscaba: se repite con el nombre nuevo
                    continue
                g["looked_up"] = True
                g["lookup_v"] = LOOKUP_V
                if info:
                    g["tags"] = info["tags"]
                    if not g.get("icon") and info.get("image"):
                        try:
                            img = Image.open(io.BytesIO(http_get(info["image"])))
                            out = ICON_DIR / f"{g['id']}.png"
                            fit_square(img).save(out, "PNG")
                            if g.get("icon_src") != "custom":
                                g["icon"], g["icon_src"] = str(out), "web"
                        except Exception:
                            pass
                    if not g.get("manual"):
                        g["category"] = categorize(g["name"], g["path"], g["tags"])
            except OSError:
                self.q.put(("online", False))
                return
            except Exception:
                g["looked_up"] = True
            self.q.put(("update",))
            time.sleep(0.8)  # no saturar las APIs (SteamSpy limita ~1 petición/s)

    # ---------------- acciones ---------------- #
    def add_games(self):
        paths = filedialog.askopenfilenames(
            title=self.t("pick_exe"),
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")])
        if paths:
            self.add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title=self.t("pick_folder"))
        if not folder:
            return
        self.count_lbl.configure(text=self.t("scanning"))
        threading.Thread(target=lambda: self.q.put(("add", scan_folder(folder))), daemon=True).start()

    def add_paths(self, paths):
        known = {g["id"] for g in self.games}
        for p in paths:
            g = new_game(p)
            if g["id"] not in known:
                self.games.append(g)
                known.add(g["id"])
        self.save()
        self.render()
        self.start_worker()

    def organize(self):
        for g in self.games:
            if not g.get("manual"):
                g["category"] = categorize(g["name"], g["path"], g.get("tags"))
            if not g.get("icon") or not g.get("tags"):
                g["looked_up"] = False
        self.save()
        self.render()
        self.start_worker()

    def visible_games(self):
        q = self.search_var.get().strip().lower()
        return [g for g in self.games if q in g["name"].lower()]

    def select_all(self):
        self.selected |= {g["id"] for g in self.visible_games()}
        self.render()

    def select_none(self):
        self.selected.clear()
        self.render()

    def on_select(self, gid, value):
        (self.selected.add if value else self.selected.discard)(gid)
        self.update_counts()

    def move_selected(self, choice):
        inv = {self.t("cat_" + c): c for c in CATS}
        cat = inv.get(choice)
        self.move_menu.set(self.t("move_to"))
        if not cat or not self.selected:
            return
        for g in self.games:
            if g["id"] in self.selected:
                g["category"], g["manual"] = cat, True
        self.save()
        self.render()

    def remove_selected(self):
        if not self.selected:
            return
        if not messagebox.askyesno(self.t("title"), self.t("confirm_remove", n=len(self.selected))):
            return
        for g in self.games:
            if g["id"] in self.selected and g.get("icon"):
                try:
                    os.remove(g["icon"])
                except OSError:
                    pass
        self.games = [g for g in self.games if g["id"] not in self.selected]
        self.selected.clear()
        self.save()
        self.render()

    def ask_name(self, current):
        """Diálogo con el nombre actual ya escrito. Devuelve el texto, o None si se cancela."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(self.t("rename_title"))
        dlg.geometry("430x230")
        dlg.resizable(False, False)
        dlg.transient(self)
        result = {"v": None}
        ctk.CTkLabel(dlg, text=self.t("rename_prompt"), justify="left", wraplength=390
                     ).pack(padx=20, pady=(18, 8), anchor="w")
        var = ctk.StringVar(value=current)
        entry = ctk.CTkEntry(dlg, textvariable=var, width=390)
        entry.pack(padx=20)

        def ok(*_):
            result["v"] = var.get()
            dlg.destroy()

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(pady=16)
        ctk.CTkButton(row, text=self.t("ok"), width=120, command=ok).pack(side="left", padx=6)
        ctk.CTkButton(row, text=self.t("cancel"), width=120, fg_color="gray40",
                      hover_color="gray30", command=dlg.destroy).pack(side="left", padx=6)
        entry.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        def focus():
            try:
                dlg.grab_set()
            except Exception:
                pass
            entry.focus()
            entry.select_range(0, "end")

        dlg.after(150, focus)
        self.wait_window(dlg)
        return result["v"]

    def rename_selected(self):
        ids = list(self.selected)
        if len(ids) != 1:
            messagebox.showinfo(self.t("title"), self.t("select_one_rename"))
            return
        g = next((x for x in self.games if x["id"] == ids[0]), None)
        if g:
            self.rename_game(g)

    def rename_game(self, g):
        """Cambia SOLO el nombre que se muestra en la app; el archivo .exe no se toca."""
        new = self.ask_name(g["name"])
        if new is None:
            return
        new = re.sub(r"\s+", " ", new).strip()[:80]
        if new:
            g["name_manual"] = True
        else:  # vacío -> volver al nombre automático
            new = guess_name(g["path"])
            g["name_manual"] = False
        if new == g["name"]:
            return
        g["name"] = new
        # con otro nombre, lo buscado en internet ya no sirve: se vuelve a buscar
        g["tags"] = []
        g["looked_up"] = False
        if g.get("icon_src") == "web":  # un logo descargado con el nombre viejo puede ser de otro juego
            try:
                os.remove(g["icon"])
            except OSError:
                pass
            g["icon"], g["icon_src"] = None, None
        if not g.get("manual"):
            g["category"] = categorize(new, g["path"])
        self.save()
        self.render()
        self.start_worker()

    def open_folder_selected(self):
        ids = list(self.selected)
        if len(ids) != 1:
            messagebox.showinfo(self.t("title"), self.t("select_one_folder"))
            return
        g = next((x for x in self.games if x["id"] == ids[0]), None)
        if g:
            self.open_folder(g)

    def open_folder(self, g):
        """Abre la carpeta del juego en el explorador de archivos (en Windows deja el .exe resaltado)."""
        path = g["path"]
        folder = os.path.dirname(path)
        try:
            if not os.path.isdir(folder):
                raise FileNotFoundError(folder)
            if os.name == "nt":
                if os.path.exists(path):
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
                else:
                    os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror(self.t("error"), self.t("folder_error", e=e))

    def cover_selected(self):
        ids = list(self.selected)
        if len(ids) != 1:
            messagebox.showinfo(self.t("title"), self.t("select_one"))
            return
        g = next((x for x in self.games if x["id"] == ids[0]), None)
        if g:
            self.set_cover(g)

    def set_cover(self, g, path=None):
        """Portada manual (PNG/JPG/WEBP). Se procesa y se GUARDA como PNG dentro de la carpeta
        de iconos, así el juego conserva su portada aunque el archivo original se borre o se corrompa."""
        if path is None:
            path = filedialog.askopenfilename(
                title=self.t("pick_cover"),
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.ico"), ("All files", "*.*")])
        if not path:
            return
        out = ICON_DIR / f"{g['id']}_custom.png"
        tmp = ICON_DIR / f"{g['id']}_custom.tmp"
        try:
            with Image.open(path) as im:
                try:  # .ico con varios tamaños: usar el más grande
                    im.size = max(im.ico.sizes(), key=lambda sz: sz[0])
                except Exception:
                    pass
                im.load()
                img = fit_square(ImageOps.exif_transpose(im), 256)
            img.save(tmp, "PNG")
            os.replace(tmp, out)  # escritura atómica: nunca queda un icono a medias
        except Exception as e:
            try:
                tmp.unlink()
            except OSError:
                pass
            messagebox.showerror(self.t("error"), self.t("cover_error", e=e))
            return
        old = g.get("icon")
        if old and old != str(out) and Path(old).parent == ICON_DIR:
            try:
                os.remove(old)  # quita el icono automático anterior
            except OSError:
                pass
        g["icon"], g["icon_src"] = str(out), "custom"
        self.save()
        self.render()

    def launch(self, g):
        path = g["path"]
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            cwd = os.path.dirname(path)
            if os.name == "nt" or not path.lower().endswith(".exe"):
                subprocess.Popen([path], cwd=cwd)
            else:
                wine = shutil.which("wine")
                if not wine:
                    raise RuntimeError(self.t("no_wine"))
                subprocess.Popen([wine, path], cwd=cwd)
        except Exception as e:
            messagebox.showerror(self.t("error"), self.t("launch_error", e=e))

    # ---------------- render ---------------- #
    def on_search(self, *_):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(200, self.render)

    def on_resize(self, e):
        if e.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(250, lambda: self.calc_cols() != self._cols and self.render())

    def calc_cols(self):
        w = self.scroll.winfo_width()
        if w < 100:
            w = 800
        return max(1, (w - 40) // (CARD_W + 14))

    def get_image(self, g):
        ip = g.get("icon")
        if ip and os.path.exists(ip):
            key = ("f", ip, os.path.getmtime(ip))
            if key not in self.img_cache:
                try:
                    pil = Image.open(ip).convert("RGBA")
                except Exception:
                    pil = placeholder(g["name"])
                self.img_cache[key] = ctk.CTkImage(light_image=pil, size=(ICON_PX, ICON_PX))
            return self.img_cache[key]
        key = ("p", g["name"])
        if key not in self.img_cache:
            self.img_cache[key] = ctk.CTkImage(light_image=placeholder(g["name"]), size=(ICON_PX, ICON_PX))
        return self.img_cache[key]

    def sub_text(self, g):
        if g.get("icon"):
            return ""
        if not self.online:                       # sin WiFi -> se muestra en el juego
            return "📡 " + self.t("no_logo_offline")
        if not g.get("looked_up"):
            return self.t("searching")
        return self.t("no_logo")

    def render(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._cols = cols = self.calc_cols()
        games = self.visible_games()

        if not games:
            msg = self.t("empty") if not self.games else self.t("no_results")
            ctk.CTkLabel(self.scroll, text=msg, font=ctk.CTkFont(size=15),
                         text_color=("gray40", "gray60")).pack(pady=80)
            self.update_counts()
            return

        for cat in CATS:
            items = sorted((g for g in games if g["category"] == cat), key=lambda g: g["name"].lower())
            if not items:
                continue
            opened = cat not in self.collapsed
            ctk.CTkButton(
                self.scroll, text=f"{'▼' if opened else '▶'}  {self.t('cat_' + cat)}  ({len(items)})",
                anchor="w", height=34, font=ctk.CTkFont(size=15, weight="bold"),
                fg_color=("gray80", "gray25"), hover_color=("gray70", "gray30"),
                text_color=("gray10", "gray95"),
                command=lambda c=cat: self.toggle_cat(c)).pack(fill="x", padx=4, pady=(10, 4))
            if not opened:
                continue
            grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
            grid.pack(fill="x", padx=4)
            for i, g in enumerate(items):
                self.make_card(grid, g).grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nw")
        self.update_counts()

    def toggle_cat(self, cat):
        self.collapsed ^= {cat}
        self.render()

    def make_card(self, parent, g):
        card = ctk.CTkFrame(parent, width=CARD_W, height=CARD_H, corner_radius=10)
        card.grid_propagate(False)
        card.grid_columnconfigure(2, weight=1)
        card.grid_rowconfigure((0, 1), weight=1)

        var = ctk.BooleanVar(value=g["id"] in self.selected)
        ctk.CTkCheckBox(card, text="", width=24, checkbox_width=20, checkbox_height=20, variable=var,
                        command=lambda gid=g["id"], v=var: self.on_select(gid, v.get())
                        ).grid(row=0, column=0, rowspan=2, padx=(10, 2))
        img_lbl = ctk.CTkLabel(card, text="", image=self.get_image(g))
        img_lbl.grid(row=0, column=1, rowspan=2, padx=4)
        img_lbl.bind("<Button-1>", lambda e, gg=g: self.set_cover(gg))
        img_lbl.bind("<Button-3>", lambda e, gg=g: self.open_folder(gg))
        try:
            img_lbl.configure(cursor="hand2")
        except Exception:
            pass

        name = g["name"] if len(g["name"]) <= 38 else g["name"][:36] + "…"
        name_lbl = ctk.CTkLabel(card, text=name, anchor="sw", justify="left", wraplength=100,
                                font=ctk.CTkFont(size=13, weight="bold"))
        name_lbl.grid(row=0, column=2, sticky="sw", padx=(4, 0))
        name_lbl.bind("<Double-Button-1>", lambda e, gg=g: self.rename_game(gg))
        name_lbl.bind("<Button-3>", lambda e, gg=g: self.open_folder(gg))
        sub = self.sub_text(g)
        offline_warn = sub.startswith("📡")
        ctk.CTkLabel(card, text=sub, anchor="nw", wraplength=105, justify="left",
                     font=ctk.CTkFont(size=10),
                     text_color="#e05555" if offline_warn else ("gray40", "gray65")
                     ).grid(row=1, column=2, sticky="nw", padx=(4, 0))

        ctk.CTkButton(card, text=self.t("play"), width=34, height=34,
                      command=lambda gg=g: self.launch(gg)).grid(row=0, column=3, rowspan=2, padx=(2, 10))
        return card


if __name__ == "__main__":
    App().mainloop()
