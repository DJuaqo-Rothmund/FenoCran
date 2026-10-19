"""
Estética «cranberry»: verdes oscuros de hoja + burdeos/rojo arándano sobre un fondo
claro difuminado, con tarjetas translúcidas tipo vidrio (glassmorphism).

KivyMD 1.2 solo acepta paletas con nombre; se re-definen las rampas «Green»
(-> verde hoja oscuro) y «Pink» (-> burdeos cranberry) antes de construir la app.
"""
from kivy.utils import get_color_from_hex

from platform_utils import resource_path

# --- Verdes (hoja) --------------------------------------------------------
LEAF_DARK = "#123326"     # tinta principal / trazos
LEAF = "#1F4D3A"
LEAF_LIGHT = "#4F7F5A"
LEAF_SOFT = "#D6E6D9"
# --- Rojos (fruto) --------------------------------------------------------
BERRY = "#8E1B2C"         # acción principal / estado activo (burdeos cranberry)
BERRY_DARK = "#5E0F1C"
BERRY_LIGHT = "#C4566A"
BERRY_SOFT = "#F2D9DD"
# --- Neutros y vidrio -----------------------------------------------------
INK = "#18241E"
INK_2 = "#3A4A42"
MUTED = "#66756C"
WARN = "#B7791F"
GLASS = "#FFFFFFA8"       # tarjetas translúcidas (~66 %)
GLASS_STRONG = "#FFFFFFD9"
GLASS_EDGE = "#FFFFFFE6"  # borde luminoso del vidrio
LINE = "#1233262E"        # líneas finas verdes translúcidas
CLEAR = "#00000000"

# --- «Mente del sistema» (módulo de IA): negros/azules con grises -------------
MIND_BG = resource_path("assets", "ui", "mind_bg.jpg")
MIND_CARD = "#0F1A2CC7"      # vidrio oscuro
MIND_CARD_2 = "#16233ACC"
MIND_EDGE = "#4FC3F740"      # borde cian tenue
MIND_TEXT = "#DCE6F2"
MIND_MUTED = "#8C9BB3"
MIND_ACCENT = "#4FC3F7"      # cian
MIND_ACCENT_2 = "#7C8CFF"    # índigo
MIND_INK = "#06121F"         # texto sobre botones cian
MIND_OK = "#34D399"
MIND_BAD = "#F87171"
MIND_FIRE = "#FFB454"

BACKGROUND = resource_path("assets", "ui", "background.jpg")
LOGO = resource_path("assets", "ui", "logo.png")
WORDMARK = resource_path("assets", "ui", "wordmark.png")
# Cranberries ilustrados (vista previa): color = semana con registro; gris = sin registro.
BERRY_KEYS = ("stevens", "ben_lear", "pilgrim", "mullica_queen")


def berry_art(*names: str, gray: bool = False) -> str:
    """Dibujo de la variedad (por nombre o variedad del sector); si no tiene uno propio,
    siempre el mismo de los 4 (según el nombre) para que cada una se reconozca."""
    import unicodedata
    import zlib

    def slug(t):
        t = unicodedata.normalize("NFKD", t or "")
        t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
        t = t.replace("n°", "").replace("nº", "").replace("no.", "")
        return "_".join(w for w in "".join(ch if ch.isalnum() else " " for ch in t).split())

    keys = [slug(n) for n in names if n]
    key = next((k for k in keys if k in BERRY_KEYS), None)
    if key is None:
        base = keys[0] if keys else ""
        key = BERRY_KEYS[zlib.crc32(base.encode()) % len(BERRY_KEYS)]
    return resource_path("assets", "ui", "berries", f"{key}{'_gris' if gray else ''}.png")
   # letra «FenoCran App»
# Pantalla de inicio: botones circulares e ícono de la IA (cerebro delineado)
START_ID = resource_path("assets", "ui", "start_id.png")           # trazo burdeos
START_PREDIO = resource_path("assets", "ui", "start_predio.png")   # trazo verde
START_AI = resource_path("assets", "ui", "start_ai.png")           # azul estelar
LOGO_LINE = resource_path("assets", "ui", "logo_line.png")         # logo a línea
START_BG = resource_path("assets", "ui", "start_bg.jpg")           # degradado + trazos tenues
BLOB_ID = resource_path("assets", "ui", "blob_id.png")
BLOB_PREDIO = resource_path("assets", "ui", "blob_predio.png")
BLOB_AI = resource_path("assets", "ui", "blob_ai.png")             # burbuja nocturna con estrellas
START_AI_NIGHT = resource_path("assets", "ui", "start_ai_night.png")
AI_GLOW = resource_path("assets", "ui", "ai_glow.png")
AI_BAR = resource_path("assets", "ui", "ai_bar.png")               # cerebro azul (barra)
DRIVE_UP = resource_path("assets", "ui", "drive_up.png")           # hay algo por subir
DRIVE_OK = resource_path("assets", "ui", "drive_ok.png")           # todo al día
DRIVE_OFF = resource_path("assets", "ui", "drive_off.png")         # sin cuenta conectada
DRIVE_SPIN = [resource_path("assets", "ui", f"spin_{k}.png") for k in range(8)]
AI_ICON = resource_path("assets", "ui", "ai_outline.png")
GOOGLE_G = resource_path("assets", "ui", "google_g.png")
# Fondo liso de la pantalla de inicio: el MISMO color que el presplash de Android
# (buildozer.spec › android.presplash_color) para que ambas se vean como una sola.
SPLASH_BG = "#F2F4EE"


def nav_icon(name: str, active: bool) -> str:
    return resource_path("assets", "ui", f"nav_{name}_{'active' if active else 'idle'}.png")


def c(hex_color: str, alpha: float | None = None):
    """Color Kivy desde hex (#RRGGBB o #RRGGBBAA); `alpha` lo sobrescribe."""
    rgba = get_color_from_hex(hex_color)
    if len(rgba) == 3:
        rgba.append(1.0)
    if alpha is not None:
        rgba[3] = alpha
    return rgba


# Colores de etiqueta por estadio principal: del verde vegetativo al rojo
# de maduración (fondo, texto).
STAGE_COLORS = {
    0: ("#EBD7DA", "#5E0F1C"),   # yema (brácteas rojizas)
    3: ("#C9DDCB", "#123326"),   # elongación
    5: ("#E6E8D0", "#4A5A1E"),   # cuello rugoso / gancho
    6: ("#FFFFFF", "#1F4D3A"),   # floración (pétalo blanco rosado)
    7: ("#B7D3B9", "#123326"),   # cuaja / fruta verde
    8: ("#F0CDD3", "#8E1B2C"),   # fruta roja
}


def stage_colors(code):
    if code is None:
        return c("#FFFFFF", .55), c(MUTED)
    import phenology as ph
    bg, fg = STAGE_COLORS.get(ph.macro_of(code), ("#FFFFFF", INK))
    return c(bg, .92), c(fg)


LEAF_RAMP = {
    "50": "EAF2EC", "100": "D6E6D9", "200": "AFCDB5", "300": "84AE8E", "400": "4F7F5A",
    "500": "1F4D3A", "600": "1B4434", "700": "173B2D", "800": "123326", "900": "0B2219",
    "A100": "BFE0C6", "A200": "8CC499", "A400": "5FA06E", "A700": "3F7F4F",
}
BERRY_RAMP = {
    "50": "F9ECEE", "100": "F2D9DD", "200": "E3AEB7", "300": "D08391", "400": "C4566A",
    "500": "8E1B2C", "600": "7C1726", "700": "6A1320", "800": "5E0F1C", "900": "420A13",
    "A100": "FF9AA8", "A200": "F0607A", "A400": "D42F4C", "A700": "B01E38",
}


def install_palette() -> None:
    from kivymd.color_definitions import colors
    colors["Green"].update(LEAF_RAMP)
    colors["Pink"].update(BERRY_RAMP)
    colors["Light"].update({"StatusBar": "123326", "AppBar": "1F4D3A",
                            "Background": "F4F5F2", "CardsDialogs": "FCFCFB"})


def apply(theme_cls) -> None:
    theme_cls.theme_style = "Light"
    theme_cls.primary_palette = "Green"
    theme_cls.primary_hue = "500"
    theme_cls.accent_palette = "Pink"
    theme_cls.material_style = "M2"


# ---------------------------------------------------------------------------
# Rendimiento: KivyMD 1.2 registra CADA widget en el tema con `theme_cls.bind(...)`.
# `bind` de Kivy compara contra todos los registros anteriores (también los de widgets
# ya destruidos), así que crear una pantalla se volvía más lento cuanto más se usaba
# la app. `fbind(..., ref=True)` registra lo mismo (referencia débil) sin esa búsqueda,
# y `purge_theme_observers` borra cada tanto los registros de widgets que ya no existen.
# ---------------------------------------------------------------------------
def speed_up_theme_bindings() -> None:
    from kivymd.theming import ThemeManager
    if getattr(ThemeManager, "_fast_bind", False):
        return

    def bind(self, **kwargs):
        for name, callback in kwargs.items():
            if self.fbind(name, callback, ref=True) == 0:   # nombre desconocido: como antes
                raise KeyError(name)

    ThemeManager.bind = bind
    ThemeManager._fast_bind = True


def purge_theme_observers(theme_cls) -> int:
    """Quita los observadores muertos (widgets destruidos) de las propiedades del tema."""
    removed = 0
    for name in theme_cls.properties():
        try:
            observers = theme_cls.get_property_observers(name, args=True)
        except Exception:  # noqa: BLE001
            continue
        for callback, _largs, _kwargs, is_ref, uid in observers:
            if is_ref and getattr(callback, "is_dead", lambda: False)():
                theme_cls.unbind_uid(name, uid)
                removed += 1
    return removed
