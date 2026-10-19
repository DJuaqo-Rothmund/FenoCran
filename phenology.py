"""
phenology.py
============
Conocimiento agronómico base de la app:

* Escala fenológica del cranberry (Vaccinium macrocarpon) del instructivo de control
  de heladas IT-AGR-006 (11 estados, con su temperatura crítica).
* Cálculo de "Semanas de Muestreo" a partir de una semana de referencia
  (por defecto: Semana 1 = semana del 1 de junio; se define en Ajustes).
* Calendario fenológico esperado (hemisferio sur, cranberry),
  usado como *prior* temporal por el clasificador.

Este módulo es puro Python (sin Kivy ni Android) para poder testearlo en PC.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Escala fenológica — cranberry (Vaccinium macrocarpon)
# ---------------------------------------------------------------------------
# Instructivo de estados fenológicos para el control de heladas (Agrícola Cran Chile,
# IT-AGR-006 v3, 01-02-2023). El código guardado es el número del estado en la ficha
# (1 = yema apretada ... 11 = fruta roja). Para ordenar, promediar, graficar y para la IA
# cada estado tiene además una posición en una escala tipo BBCH (0-99): yema 0x,
# elongación 3x, botón floral 5x, flor 6x, fruto 7x, madurez 8x.
# (código, nombre, nombre en inglés, posición BBCH, temperatura crítica °C o None,
#  descripción de la ficha, palabras clave)
CRAN_STAGES: list[tuple[int, str, str, float, float | None, str, str]] = [
    (1, "Yema apretada", "Tight bud", 0, None,
     "Reposo de la yema: cumplió dormancia y horas de frío; se activa apenas el ambiente "
     "lo permite. Brácteas apretadas, rojo oscuro o claro (sobre todo arriba en la "
     "canopia); vistas de lado las yemas son compactas, bajo las hojas superiores. "
     "No se controla temperatura: resisten hasta -7 °C.",
     "yema apretada tight bud reposo dormancia brácteas apretadas rojo oscuro compacta invierno"),
    (2, "Yema blanca", "White bud", 1, -2.0,
     "La planta comienza el cambio de coloración y la yema se torna blanca. La base de "
     "las hojas empieza a verse verde, pero la mayoría aún es rojiza clara u oscura.",
     "yema blanca white bud cambio coloración hojas rojizas base verde"),
    (3, "Repollo", "Cabbage head", 3, -2.0,
     "Hinchamiento de la yema; las brácteas no se abren. Se parece a la cabeza de un "
     "repollo. Muchas yemas ya perdieron la pigmentación rojiza.",
     "repollo cabbage head hinchamiento yema hinchada brácteas cerradas"),
    (4, "Apertura de yema", "Bud break", 7, -1.0,
     "El tejido nuevo emerge entre las brácteas: aparecen los primordios florales y ya se "
     "ve la punta de las hojas nuevas.",
     "apertura yema bud break tejido nuevo emerge brácteas primordios florales punta hojas"),
    (5, "Elongación", "Bud elongation", 31, 0.0,
     "Hojas nuevas y algunas brácteas florales emergen de la yema. Todo el crecimiento "
     "nuevo va erguido y paralelo al tallo.",
     "elongación bud elongation hojas nuevas brácteas florales erguido paralelo tallo"),
    (6, "Cuello rugoso", "Roughneck", 51, 0.0,
     "El tallo se elonga bastante. Todas las yemas florales y brácteas son visibles, "
     "pegadas al tallo; hojas nuevas paralelas al tallo; los pedicelos aún no se elongan.",
     "cuello rugoso roughneck tallo elongado yemas florales visibles pegadas pedicelos"),
    (7, "Gancho", "Hook", 55, 0.0,
     "Los pedicelos se elongan desde las flores más bajas del vertical; la flor cae y "
     "toma su forma de gancho. Las hojas nuevas se abren más perpendiculares al tallo.",
     "gancho hook pedicelos elongan flor cae forma hojas perpendiculares"),
    (8, "Inicio floración", "Early bloom", 61, 1.0,
     "Las flores se abren, comenzando por las inferiores del vertical.",
     "inicio floración early bloom flores abiertas inferiores vertical pétalos"),
    (9, "Inicio cuaja", "Fruit set", 71, 1.0,
     "Comienza la cuaja de las flores formando la fruta; parte por la zona inferior del "
     "vertical.",
     "inicio cuaja fruit set fruta cuajada formación"),
    (10, "Fruta verde", "Green fruit", 75, 0.0,
     "Comienza el llenado: la fruta crece; la fruta verde más pequeña tiene tamaño de "
     "arveja.",
     "fruta verde green fruit llenado crecimiento arveja"),
    (11, "Fruta roja", "Red fruit", 85, -1.0,
     "Fruta lista para cosecha, sobre 30 TAcy.",
     "fruta roja red fruit cosecha tacy color madura"),
]

STAGE_POS: dict[int, float] = {c: float(pos) for c, _n, _e, pos, _t, _d, _k in CRAN_STAGES}
STAGE_NAMES: dict[int, str] = {c: n for c, n, *_ in CRAN_STAGES}
# Temperatura crítica (criterio de control de heladas, °C) por estado; None = no se controla.
FROST_CRITICAL: dict[int, float | None] = {c: t for c, _n, _e, _p, t, _d, _k in CRAN_STAGES}
FROST_RESISTANCE_TIGHT_BUD = -7.0


def _cran_entry(code, name, en, _pos, temp, desc, kw):
    crit = ("Criterio de control de helada: no se controla (resiste hasta -7 °C)."
            if temp is None else f"Criterio de control de helada: {temp:g} °C.")
    return code, f"{name} ({en})", f"{desc}\n{crit}", kw


BBCH_SCALE_VERSION = 1   # sube cuando cambia la escala base (se actualiza en las bases)
# Códigos de la escala base que se corrigieron: antiguo -> nuevo (los registros se pasan solos).
BBCH_RENAMED: dict[int, int] = {}


def _scale_value(code: int) -> float:
    return STAGE_POS.get(int(code), float(code))


BBCH_CRAN: list[tuple[int, str, str, str]] = [_cran_entry(*row) for row in CRAN_STAGES]


MACRO_STAGES: dict[int, str] = {
    0: "Yema",
    3: "Elongación del brote",
    5: "Desarrollo floral",
    6: "Floración",
    7: "Cuaja y fruta verde",
    8: "Fruta roja",
}

# Colores por estadio principal (usados en reportes / chips de UI).
MACRO_COLORS: dict[int, str] = {
    0: "#7A2335",   # yema rojiza (brácteas)
    3: "#5E7F3A",   # brote verde
    5: "#9C8A4A",   # botón floral
    6: "#E9D6DA",   # flor blanco rosado
    7: "#6F9455",   # fruta verde
    8: "#8E1B2C",   # cranberry
}


def macro_of(code: int | None) -> int | None:
    """Estadio principal según la posición en la escala: 5 (elongación) -> 3; 11 -> 8."""
    if code is None:
        return None
    return int(_scale_value(int(code)) // 10)


def bbch_value(code: int | None) -> float | None:
    """Posición en la escala para ordenar, graficar y promediar: 5 (elongación) -> 31."""
    if code is None:
        return None
    return _scale_value(int(code))


def scale_pos(v) -> float | None:
    """Posición en el eje: un código (int) -> bbch_value; un promedio (float) tal cual."""
    if v is None:
        return None
    return float(v) if isinstance(v, float) else bbch_value(v)


def code_from_pos(pos: float | None) -> int | None:
    """Estado más cercano a una posición de la escala (p. ej. un promedio)."""
    if pos is None:
        return None
    return min(STAGE_POS, key=lambda c: (abs(STAGE_POS[c] - pos), c))


def code_str(code: int | None) -> str:
    """Código para mostrar: el número del estado en la ficha («5»)."""
    if code is None:
        return "—"
    return str(int(code))


def bbch_sorted(rows, key=lambda r: r["code"]):
    """Ordena estados por su posición en la escala."""
    return sorted(rows, key=lambda r: _scale_value(int(key(r))))


def bbch_label(code: int | None, catalog: dict[int, str] | None = None) -> str:
    """'Estado 5: Elongación (Bud elongation)'."""
    if code is None:
        return ""
    names = catalog or {c: n for c, n, _d, _k in BBCH_CRAN}
    name = names.get(int(code))
    if name is None:
        # Código no catalogado: devolver el estadio principal.
        name = MACRO_STAGES.get(macro_of(code), "Estado no catalogado")
    return f"Estado {code_str(code)}: {name}"


def frost_label(code: int | None) -> str:
    """«Control de helada: -2 °C» según el estado (ficha IT-AGR-006)."""
    if code is None or int(code) not in FROST_CRITICAL:
        return ""
    t = FROST_CRITICAL[int(code)]
    return ("Helada: no se controla (resiste -7 °C)" if t is None
            else f"Control de helada: {t:g} °C")


def frost_worst(codes) -> float | None:
    """Temperatura de control de helada de un conjunto de verticales: la del estado MÁS
    sensible presente (la crítica más alta). None si ninguno se controla."""
    temps = [FROST_CRITICAL.get(int(c)) for c in codes]
    temps = [t for t in temps if t is not None]
    return max(temps) if temps else None


def upright_summary(codes) -> dict | None:
    """Conteo de verticales (un estado por vertical, en el orden en que se contaron):
    total, cantidad y % por estado, estado predominante, rango y control de helada."""
    codes = [int(c) for c in codes]
    if not codes:
        return None
    counts: dict[int, int] = {}
    for c in codes:
        counts[c] = counts.get(c, 0) + 1
    order = sorted(counts, key=_scale_value)
    n = len(codes)
    # Predominante: el de más verticales; en empate, el más avanzado.
    dominant = max(order, key=lambda c: (counts[c], _scale_value(c)))
    mean = sum(_scale_value(c) for c in codes) / n
    return {"total": n,
            "rows": [{"code": c, "n": counts[c], "pct": counts[c] / n} for c in order],
            "counts": counts, "dominant": dominant,
            "least": order[0], "most": order[-1],
            "mean_pos": mean, "mean_code": code_from_pos(mean),
            "frost": frost_worst(counts), "frost_label": frost_text(frost_worst(counts), counts)}


def frost_text(temp: float | None, counts) -> str:
    if not counts:
        return ""
    if temp is None:
        return "Helada: no se controla (todas en yema apretada, resisten -7 °C)"
    return f"Control de helada del grupo: {temp:g} °C (estado más sensible presente)"


def pct(frac: float) -> str:
    """0,375 -> «38 %» (redondeo comercial, no al par)."""
    return f"{int(frac * 100 + .5)} %"


def upright_line(summary: dict | None, top: int = 3) -> str:
    """«20 verticales · E5 45 % · E6 30 % · E4 25 %» (los estados con más verticales)."""
    if not summary:
        return ""
    rows = sorted(summary["rows"], key=lambda r: (-r["n"], -_scale_value(r["code"])))[:top]
    parts = [f"E{r['code']} {pct(r['pct'])}" for r in rows]
    return f"{summary['total']} verticales · " + " · ".join(parts)


def parse_bbch_code(text: str | None) -> int | None:
    """Extrae el número de estado de textos como 'Estado 5: Elongación', 'E5' o '5'."""
    if not text:
        return None
    import re
    m = re.search(r"(?:Estado|BBCH|E)?\s*\b(\d{1,3})\b", str(text), flags=re.I)
    if not m:
        return None
    v = int(m.group(1))
    return v if 0 <= v <= 999 else None


# ---------------------------------------------------------------------------
# Semanas de muestreo
# ---------------------------------------------------------------------------
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


SEASON_MONTH = 6   # la temporada del cranberry va de junio a mayo (cosecha marzo-mayo)


def season_first_monday(season: int) -> _dt.date:
    """Lunes de la semana que contiene el 1 de junio: primera semana de la temporada."""
    d = _dt.date(season, SEASON_MONTH, 1)
    return d - _dt.timedelta(days=d.weekday())


def season_of(date: _dt.date) -> int:
    """Temporada agrícola junio-mayo («Temporada 2026-2027» = 2026). Se decide por el
    lunes de la semana, así una semana nunca queda partida entre dos temporadas:
    2026-10-16 -> 2026; 2027-04-20 -> 2026; 2027-06-02 (semana del 31-05) -> 2027."""
    monday = date - _dt.timedelta(days=date.weekday())
    return monday.year if monday >= season_first_monday(monday.year) else monday.year - 1


def season_bounds(season: int) -> tuple[_dt.date, _dt.date]:
    """(1 de junio, 31 de mayo del año siguiente)."""
    return _dt.date(season, SEASON_MONTH, 1), _dt.date(season + 1, SEASON_MONTH, 1) - _dt.timedelta(days=1)


def default_season_start(season: int) -> _dt.date:
    """Semana 1 por defecto: la semana del 1 de junio (se puede cambiar en Ajustes)."""
    return season_first_monday(season)


def legacy_season_start(season: int) -> _dt.date:
    """Semana 1 del esquema anterior (temporada julio-junio): 7 de septiembre."""
    return _dt.date(season, 9, 7)


def legacy_season_of(date: _dt.date) -> int:
    return date.year if date.month >= 7 else date.year - 1


def week_label(start: _dt.date) -> str:
    return f"Semana del {start.day} de {MESES[start.month - 1]}"


def format_date_es(d: _dt.date, with_year: bool = True) -> str:
    s = f"{d.day} de {MESES[d.month - 1]}"
    return f"{s} de {d.year}" if with_year else s


@dataclass(frozen=True)
class SamplingWeek:
    number: int
    start: _dt.date

    @property
    def end(self) -> _dt.date:
        return self.start + _dt.timedelta(days=6)

    @property
    def label(self) -> str:
        return week_label(self.start)

    @property
    def long_label(self) -> str:
        return f"{week_title(self.start)} · {self.label}"


def iso_week(start) -> tuple[int, int]:
    """(semana del año ISO-8601, año) de una fecha o «aaaa-mm-dd».
    10-08-2026 -> (33, 2026); 28-12-2026 -> (53, 2026); 04-01-2027 -> (1, 2027)."""
    d = start if isinstance(start, _dt.date) else _dt.date.fromisoformat(str(start)[:10])
    year, week, _ = d.isocalendar()
    return week, year


def _week_date(week):
    return week["start_date"] if isinstance(week, dict) else week


def week_title(week) -> str:
    """«Semana 33, año 2026» a partir de una semana de muestreo (o su fecha de inicio)."""
    w, y = iso_week(_week_date(week))
    return f"Semana {w}, año {y}"


def week_long(week) -> str:
    """«Semana 42 del año 2026»."""
    w, y = iso_week(_week_date(week))
    return f"Semana {w} del año {y}"


def week_short(week) -> str:
    """«S33»: rótulo corto (ejes de gráficos, rangos)."""
    return f"S{iso_week(_week_date(week))[0]}"


def week_of_year(week) -> int:
    return iso_week(_week_date(week))[0]


def season_title(season: int) -> str:
    """Rótulo de una temporada completa: «Temporada 2026-2027»."""
    return f"Temporada {season}-{season + 1}"


def week_start(season_start: _dt.date, number: int) -> _dt.date:
    return season_start + _dt.timedelta(days=7 * (number - 1))


def week_number_for(date: _dt.date, season_start: _dt.date) -> int:
    """Semana de muestreo que contiene `date` (1-based; <1 si es anterior a la semana 1)."""
    delta = (date - season_start).days
    return delta // 7 + 1


def generate_weeks(season_start: _dt.date, count: int) -> list[SamplingWeek]:
    return [SamplingWeek(n, week_start(season_start, n)) for n in range(1, count + 1)]


# ---------------------------------------------------------------------------
# Calendario fenológico esperado (prior temporal)
# ---------------------------------------------------------------------------
# Cranberry, zona sur de Chile, Semana 1 ≈ primera semana de septiembre (yema blanca).
# (semana, posición esperada en la escala). Se interpola linealmente entre puntos.
# Es solo un *prior* débil: la app lo combina con la visión y la historia.
EXPECTED_CALENDAR: list[tuple[int, int]] = [
    (1, 1), (3, 3), (5, 7), (7, 31), (9, 51), (11, 55),
    (14, 61), (17, 71), (20, 75), (28, 85),
]


def expected_bbch_for_week(week_number: int) -> float:
    pts = EXPECTED_CALENDAR
    if week_number <= pts[0][0]:
        return float(pts[0][1])
    if week_number >= pts[-1][0]:
        return float(pts[-1][1])
    for (w0, b0), (w1, b1) in zip(pts, pts[1:]):
        if w0 <= week_number <= w1:
            t = (week_number - w0) / (w1 - w0)
            return b0 + t * (b1 - b0)
    return float(pts[-1][1])


# ---------------------------------------------------------------------------
# Nombre de archivo de las fotos: «aaaammdd-<Ensayo>-<Variedad>[S<sector>][C<cama>]<G|D>»,
# p. ej. 20260928-NV-SteG o 20260928-AM-SteS3C45G — año-mes-día: se ordenan por fecha.
# (fecha = inicio de la semana de muestreo; G = general/canopia, D = detalle).
# legacy=True: fecha al revés (ddmmaaaa), formato antiguo heredado de FenoRubus.
# ---------------------------------------------------------------------------
PHOTO_KIND_LETTER = {"canopy": "G", "detail": "D", "attachment": "A"}   # A = adjunta a la ficha


def variety_tag(name: str, code: str | None = None) -> str:
    """Abreviatura de la variedad: su código («STE» → «Ste», «BL») o derivada del nombre."""
    import re
    import unicodedata

    def clean(t):
        t = unicodedata.normalize("NFKD", t or "")
        return re.sub(r"[^A-Za-z0-9]", "", "".join(ch for ch in t if not unicodedata.combining(ch)))

    tag = clean(code)
    if not tag:
        digits = re.findall(r"\d+", name or "")
        letters = clean(name)
        tag = (letters[:1] + digits[0]) if digits and letters else letters[:3]
    if tag.isalpha() and len(tag) >= 3:
        tag = tag.capitalize()
    return tag or "Var"


# Predio de cranberry: cada unidad es una CAMA (número correlativo del predio, 1-300 o
# más) y, opcionalmente, el sector al que pertenece (la asignación cama -> sector es
# propia de cada predio). En la base la cama se guarda en la columna `irrigation`
# (heredada de FenoRubus, donde era el equipo de riego).
SECTORS = range(1, 21)          # sector del predio (opcional)
BEDS = range(1, 301)            # número de cama (se escribe; admite más de 300)
MAX_BED = 999
IRRIGATION_UNITS = BEDS         # compatibilidad: «irrigation» = cama


def unit_name(sector, bed) -> str:
    """Nombre de una unidad de predio: «Cama 45, sector 3»."""
    parts = []
    if bed:
        parts.append(f"Cama {int(bed)}")
    if sector:
        parts.append(("sector" if parts else "Sector") + f" {int(sector)}")
    return ", ".join(parts)


def is_unit(v: dict) -> bool:
    """¿Es una unidad de predio (variedad + cama/sector)?"""
    return bool((v.get("cultivar") or "").strip() and (v.get("sector") or v.get("irrigation"))
                and not v.get("treatment"))


def unit_main(v: dict) -> str:
    """Nombre principal de una unidad de predio: «Stevens · 2019» (variedad y año de
    plantación). Para lo que no es unidad de predio, su nombre."""
    if not is_unit(v):
        return v.get("name") or ""
    return " · ".join(str(x) for x in (v["cultivar"].strip(), v.get("plant_year")) if x)


def unit_place(v: dict) -> str:
    """Ubicación de la unidad, para ir en letra chica: «Cama 45 · sector 3»."""
    return ph_unit_place(v.get("sector"), v.get("irrigation")) if is_unit(v) else ""


def ph_unit_place(sector, bed) -> str:
    return unit_name(sector, bed).replace(", ", " · ")


def unit_compact(v: dict) -> str:
    """En una sola línea (listas y celdas angostas): «Stevens 2019 · C45-S3»."""
    if not is_unit(v):
        return v.get("name") or ""
    where = "-".join(x for x in (f"C{v['irrigation']}" if v.get("irrigation") else "",
                                 f"S{v['sector']}" if v.get("sector") else "") if x)
    main = " ".join(str(x) for x in (v["cultivar"].strip(), v.get("plant_year")) if x)
    return f"{main} · {where}" if where else main


def unit_label(v: dict) -> str:
    """Variedad de una unidad de predio con su año de plantación y código:
    «Stevens · 2019 · STE»."""
    parts = [v.get("cultivar") or v.get("name") or ""]
    if v.get("plant_year"):
        parts.append(str(v["plant_year"]))
    if v.get("code"):
        parts.append(v["code"])
    return " · ".join(p for p in parts if p)


def location_tag(variety: dict) -> str:
    """«S3C45» (sector 3, cama 45); se omite lo que no esté definido."""
    out = ""
    if variety.get("sector"):
        out += f"S{int(variety['sector'])}"
    if variety.get("irrigation"):
        out += f"C{int(variety['irrigation'])}"
    return out


PHOTO_DATE_FMT, LEGACY_PHOTO_DATE_FMT = "%Y%m%d", "%d%m%Y"


def photo_date(day) -> str:
    """«20260928»: fecha para nombres de archivo (año, mes, día)."""
    import datetime as _d
    if isinstance(day, str):
        day = _d.date.fromisoformat(day[:10])
    return day.strftime(PHOTO_DATE_FMT)


def photo_basename(variety: dict, week_start, kind: str, seq: int = 1, legacy: bool = False,
                   trial: str = "") -> str:
    """trial: código del ensayo o predio («NV», «AM»…), va después de la fecha."""
    import datetime as _d
    if isinstance(week_start, str):
        week_start = _d.date.fromisoformat(week_start[:10])
    date = week_start.strftime(LEGACY_PHOTO_DATE_FMT if legacy else PHOTO_DATE_FMT)
    if trial:
        date = f"{date}-{trial}"
    # Predio: la unidad se llama «Cama 45, sector 3»; la foto lleva la variedad.
    base = f"{date}-{variety_tag(variety.get('cultivar') or variety.get('name', ''), variety.get('code'))}" \
           f"{location_tag(variety)}{PHOTO_KIND_LETTER.get(kind, 'X')}"
    return base if seq <= 1 else f"{base}-{seq}"
