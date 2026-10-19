"""
ui/marking.py
=============
Conteo de verticales desde una foto: la IA propone un recuadro por vertical con su
estado y el evaluador corrige.

* Tocar un recuadro lo selecciona; tocar un estado de la franja inferior se lo asigna
  (y queda como estado «pincel» para los siguientes).
* Tocar fuera de los recuadros agrega un vertical con el estado pincel; arrastrar dibuja
  el recuadro a medida.
* «Aceptar» guarda los recuadros, pasa el conteo al registro y la IA aprende de la foto.
"""
from __future__ import annotations

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

import phenology as ph
from ui import theme
from ui.theme import c


def app():
    return MDApp.get_running_app()


def order(marks: list[dict]) -> list[int]:
    """Índices de los recuadros en el orden V1, V2… (izquierda a derecha, arriba abajo)."""
    return sorted(range(len(marks)), key=lambda i: (round(marks[i]["x"] + marks[i]["w"] / 2, 2),
                                                    marks[i]["y"]))


class MarkCanvas(Widget):
    """Foto con los recuadros de los verticales (coordenadas 0-1, y hacia abajo)."""
    source = StringProperty("")
    marks = ListProperty([])
    selected = NumericProperty(-1)
    brush = NumericProperty(5)
    default_box = ListProperty([.07, .32])

    def __init__(self, on_change=None, **kw):
        super().__init__(**kw)
        self.on_change = on_change
        self._tex = None
        self._labels: dict[str, object] = {}
        self._drag = None
        self.bind(pos=self.redraw, size=self.redraw, marks=self.redraw, selected=self.redraw)

    def on_source(self, *_):
        try:
            self._tex = CoreImage(self.source).texture if self.source else None
        except Exception:  # noqa: BLE001
            self._tex = None
        self.redraw()

    # -------------------------------------------------------------- geometría
    def img_rect(self):
        if self._tex is None or self.width < 2 or self.height < 2:
            return self.x, self.y, self.width, self.height
        tw, th = self._tex.size
        k = min(self.width / tw, self.height / th)
        w, h = tw * k, th * k
        return self.x + (self.width - w) / 2, self.y + (self.height - h) / 2, w, h

    def to_norm(self, x, y):
        rx, ry, rw, rh = self.img_rect()
        return (x - rx) / rw, 1 - (y - ry) / rh

    def to_px(self, m):
        rx, ry, rw, rh = self.img_rect()
        return rx + m["x"] * rw, ry + (1 - m["y"] - m["h"]) * rh, m["w"] * rw, m["h"] * rh

    def _label(self, text, size):
        key = f"{text}|{size}"
        if key not in self._labels:
            lab = CoreLabel(text=text, font_size=size, bold=True)
            lab.refresh()
            self._labels[key] = lab.texture
        return self._labels[key]

    # ------------------------------------------------------------- dibujo
    def redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            rx, ry, rw, rh = self.img_rect()
            if self._tex is not None:
                Color(1, 1, 1, 1)
                Rectangle(texture=self._tex, pos=(rx, ry), size=(rw, rh))
            numbers = {i: n for n, i in enumerate(order(self.marks), 1)}
            for i, m in enumerate(self.marks):
                x, y, w, h = self.to_px(m)
                col = c(ph.MACRO_COLORS.get(ph.macro_of(m["code"]), "#888888"))
                sel = i == self.selected
                Color(1, 1, 1, .9)
                Line(rectangle=(x, y, w, h), width=dp(3.2 if sel else 2.2))
                Color(*(c(theme.BERRY) if sel else col))
                Line(rectangle=(x, y, w, h), width=dp(2.2 if sel else 1.4))
                tex = self._label(f"V{numbers[i]}·E{m['code']}", dp(11))
                lx, ly = x, min(y + h + dp(1), ry + rh - tex.height - dp(2))
                if ly < y + h:
                    ly = y + h - tex.height - dp(2)
                Color(*(c(theme.BERRY) if sel else col)[:3], .92)
                Rectangle(pos=(lx, ly), size=(tex.width + dp(6), tex.height + dp(2)))
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(lx + dp(3), ly + dp(1)), size=tex.size)
            if self._drag and self._drag.get("moved"):
                (x0, y0), (x1, y1) = self._drag["start"], self._drag["now"]
                Color(*c(theme.BERRY))
                Line(rectangle=(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)),
                     width=dp(1.6), dash_length=dp(4), dash_offset=dp(3))

    # ------------------------------------------------------------- toques
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        self._drag = {"start": touch.pos, "now": touch.pos, "moved": False}
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self or not self._drag:
            return super().on_touch_move(touch)
        self._drag["now"] = touch.pos
        sx, sy = self._drag["start"]
        if abs(touch.x - sx) + abs(touch.y - sy) > dp(14):
            self._drag["moved"] = True
        self.redraw()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        drag, self._drag = self._drag, None
        if drag is None:
            return True
        if drag["moved"]:
            (x0, y0), (x1, y1) = (self.to_norm(*drag["start"]), self.to_norm(*drag["now"]))
            box = {"x": min(x0, x1), "y": min(y0, y1), "w": abs(x1 - x0), "h": abs(y1 - y0)}
            if box["w"] > .01 and box["h"] > .01:
                self._add(box)
            else:
                self.redraw()
            return True
        nx, ny = self.to_norm(*touch.pos)
        hit = [i for i, m in enumerate(self.marks)
               if m["x"] <= nx <= m["x"] + m["w"] and m["y"] <= ny <= m["y"] + m["h"]]
        if hit:
            self.selected = min(hit, key=lambda i: self.marks[i]["w"] * self.marks[i]["h"])
            self._changed()
        elif 0 <= nx <= 1 and 0 <= ny <= 1:
            w, h = self.default_box
            self._add({"x": nx - w / 2, "y": ny - h / 2, "w": w, "h": h})
        return True

    def _add(self, box):
        box = {k: min(max(v, 0.0), 1.0) for k, v in box.items()}
        box["w"] = min(box["w"], 1 - box["x"])
        box["h"] = min(box["h"], 1 - box["y"])
        self.marks = self.marks + [dict(box, code=int(self.brush), origin="user")]
        self.selected = len(self.marks) - 1
        self._changed(edit=True)

    def set_code(self, code: int):
        self.brush = code
        if 0 <= self.selected < len(self.marks):
            marks = [dict(m) for m in self.marks]
            marks[self.selected].update(code=int(code), origin="user")
            self.marks = marks
            self._changed(edit=True)

    def remove_selected(self):
        if 0 <= self.selected < len(self.marks):
            self.marks = [m for i, m in enumerate(self.marks) if i != self.selected]
            self.selected = -1
            self._changed(edit=True)

    def _changed(self, edit=False):
        self.redraw()
        if self.on_change:
            self.on_change(edit)


class MarkScreen(MDScreen):
    """Pantalla de conteo sobre una foto (una foto de conteo del registro abierto)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        from kivy.factory import Factory
        self.cp = None
        self._history: list[list[dict]] = []
        root = BoxLayout(orientation="vertical")
        self.bar = Factory.TopBar(title="Verticales en la foto")
        self.bar.left_action_items = [["arrow-left", lambda x: app().back()]]
        self.bar.right_action_items = [["check", lambda x: self.accept()]]
        root.add_widget(self.bar)
        self.info = MDLabel(text="", font_style="Caption", adaptive_height=True, padding=(dp(12), dp(4)),
                            theme_text_color="Custom", text_color=c(theme.INK))
        root.add_widget(self.info)
        self.canvas_w = MarkCanvas(on_change=self._changed)
        root.add_widget(self.canvas_w)
        # Estados: franja horizontal (el elegido es el «pincel»).
        strip_sv = ScrollView(size_hint_y=None, height=dp(52), do_scroll_y=False, bar_width=dp(2))
        self.strip = MDBoxLayout(adaptive_width=True, spacing=dp(6), padding=(dp(8), dp(6)))
        self.chips = {}
        from ui.screens import PillButton
        for code in sorted(ph.STAGE_NAMES):
            bg, fg = theme.stage_colors(code)
            btn = PillButton(text=f"E{code}", bold=True, font_size="15sp", size_hint=(None, None),
                             height=dp(40), width=dp(54), bg_off=bg, fg_off=fg,
                             bg_on=c(theme.BERRY), fg_on=c("#FFFFFF"))
            btn.bind(on_release=lambda w, code=code: self.pick_code(code))
            self.chips[code] = btn
            self.strip.add_widget(btn)
        strip_sv.add_widget(self.strip)
        root.add_widget(strip_sv)
        self.stage_name = MDLabel(text="", font_style="Caption", adaptive_height=True,
                                  padding=(dp(12), 0), theme_text_color="Custom",
                                  text_color=c(theme.LEAF_DARK))
        root.add_widget(self.stage_name)
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6), padding=(dp(8), dp(6)))
        for text, cb in (("IA", self.run_ai), ("Quitar", self.canvas_w.remove_selected),
                         ("Deshacer", self.undo)):
            row.add_widget(Factory.GhostButton(text=text, on_release=lambda *_, cb=cb: cb(),
                                               icon={"IA": "auto-fix", "Quitar": "delete-outline",
                                                     "Deshacer": "undo"}[text]))
        self.accept_btn = MDRaisedButton(text="ACEPTAR", md_bg_color=c(theme.BERRY),
                                         size_hint_x=None, width=dp(118), elevation=0)
        self.accept_btn.bind(on_release=lambda *_: self.accept())
        row.add_widget(self.accept_btn)
        root.add_widget(row)
        self.add_widget(root)

    # ------------------------------------------------------------- abrir
    def open(self, count_photo_id: int, suggest: bool = True):
        import upright_ai as ua
        a = app()
        self.cp = a.db.get_count_photo(count_photo_id)
        mode = self.cp["mode"]
        self.bar.title = f"Verticales · {ua.MODES[mode][0]}"
        self.canvas_w.source = self.cp["path"]
        self.canvas_w.default_box = list(ua.DEFAULT_BOX[mode])
        marks = [dict(m) for m in a.db.list_marks(count_photo_id)]
        if marks:
            ws = sorted(m["w"] for m in marks)
            hs = sorted(m["h"] for m in marks)
            self.canvas_w.default_box = [ws[len(ws) // 2], hs[len(hs) // 2]]
        self._history = []
        self.canvas_w.selected = -1
        self.canvas_w.marks = marks
        self.pick_code(self.canvas_w.brush, apply=False)
        self._msg = ("Toque un recuadro y luego su estado · toque fuera para agregar un "
                     "vertical · arrastre para dibujarlo.")
        self._changed()
        if suggest and not marks:
            Clock.schedule_once(lambda *_: self.run_ai(), .2)

    def run_ai(self):
        a = app()
        cp = self.cp
        if cp is None:
            return
        self._msg = "Buscando verticales…"
        self._changed()
        week = a.observation.week["week_number"] if getattr(a.observation, "week", None) else None

        def work():
            try:
                det = a.upright_ai.suggest(cp["path"], cp["mode"], week)
                res = ([b.as_dict() for b in det.boxes], det.message, None)
            except Exception as exc:  # noqa: BLE001
                res = (None, "", exc)
            Clock.schedule_once(lambda *_: done(*res))

        def done(boxes, message, error):
            if self.cp is None or self.cp["id"] != cp["id"]:
                return
            if error:
                self._msg = f"La IA no pudo analizar la foto: {error}"
            else:
                self._push()
                keep = [m for m in self.canvas_w.marks if m.get("origin") == "user"]
                new = [b for b in boxes if not any(_overlap(b, k) for k in keep)]
                self.canvas_w.marks = keep + new
                self.canvas_w.selected = -1
                self._msg = message
            self._changed()

        a.workers.submit(work)

    # ----------------------------------------------------------- edición
    def _push(self):
        self._history.append([dict(m) for m in self.canvas_w.marks])
        self._history = self._history[-30:]

    def _changed(self, edit=False):
        if edit:
            self._history.append(getattr(self, "_last", []))
        self._last = [dict(m) for m in self.canvas_w.marks]
        marks = self.canvas_w.marks
        s = ph.upright_summary([m["code"] for m in marks])
        head = (f"{len(marks)} verticales · predominante E{s['dominant']} "
                f"{ph.STAGE_NAMES.get(s['dominant'], '')}" if s else "Sin verticales marcados")
        self.info.text = f"[b]{head}[/b]\n{getattr(self, '_msg', '')}"
        self.info.markup = True
        self.accept_btn.text = f"ACEPTAR ({len(marks)})"
        sel = self.canvas_w.selected
        if 0 <= sel < len(marks):
            self.pick_code(marks[sel]["code"], apply=False)

    def pick_code(self, code: int, apply: bool = True):
        for k, btn in self.chips.items():
            btn.selected = k == code
        self.stage_name.text = f"Estado E{code}: {ph.STAGE_NAMES.get(code, '')}  ·  " + ph.frost_label(code)
        if apply:
            self.canvas_w.set_code(code)
        else:
            self.canvas_w.brush = code

    def undo(self):
        if self._history:
            self.canvas_w.marks = self._history.pop()
            self.canvas_w.selected = -1
            self._last = [dict(m) for m in self.canvas_w.marks]
            self._changed()

    # ----------------------------------------------------------- aceptar
    def accept(self):
        a = app()
        cp = self.cp
        if cp is None:
            return
        marks = [dict(m) for m in self.canvas_w.marks]
        a.db.set_marks(cp["id"], marks)
        n = a.db.accept_count_photo(cp["id"])
        a.workers.submit(lambda: a.upright_ai.learn(cp["path"], cp["mode"], marks))
        a.toast(f"{n} verticales pasan al registro · la IA aprende de esta foto")
        self.cp = None
        a.back()
        obs = a.observation
        if getattr(obs, "obs", None):
            obs.update_uprights()
            obs.load_count_photos()


def _overlap(a: dict, b: dict) -> bool:
    x0, y0 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x1, y1 = min(a["x"] + a["w"], b["x"] + b["w"]), min(a["y"] + a["h"], b["y"] + b["h"])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return inter > .3 * min(a["w"] * a["h"], b["w"] * b["h"])
