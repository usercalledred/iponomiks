import ctypes
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from logic.validation import ValidationError, parse_money
from ui.mainmenu import GlassButton, GlowTextRenderer, ImageBackground


class FontLoader:

    FR_PRIVATE = 0x10

    @classmethod
    def load(cls, font_path, fallback_family="Arial"):
        try:
            family = ImageFont.truetype(font_path, 10).getname()[0]
        except OSError:
            return fallback_family

        if sys.platform == "win32":
            try:
                ctypes.windll.gdi32.AddFontResourceExW(font_path, cls.FR_PRIVATE, 0)
            except Exception:
                pass

        return family


class GlassPanel:

    OUTLINE_OFFSETS = [
        (-2, 0), (2, 0), (0, -2), (0, 2),
        (-2, -2), (2, -2), (-2, 2), (2, 2)
    ]

    def __init__(self, parent, text_renderer, left, top, width, height, items,
                 darken_alpha=90, tint_alpha=60):
        self.text_renderer = text_renderer
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.items = items
        self.darken_alpha = darken_alpha
        self.tint_alpha = tint_alpha

        self.photo = None
        self._frame = None
        self._size = None

        self.label = tk.Label(parent, bd=0, highlightthickness=0)
        self.label.place(
            relx=left, rely=top,
            relwidth=width, relheight=height,
            anchor="nw"
        )

    def render(self, background_frame, width, height):
        if self._frame is background_frame and self._size == (width, height):
            return

        left = max(0, int(self.left * width))
        top = max(0, int(self.top * height))
        right = min(background_frame.width, int((self.left + self.width) * width))
        bottom = min(background_frame.height, int((self.top + self.height) * height))

        if right <= left or bottom <= top:
            return

        crop = background_frame.crop((left, top, right, bottom)).convert("RGBA")
        crop = crop.filter(ImageFilter.GaussianBlur(8))
        darken = Image.new("RGBA", crop.size, (0, 0, 0, self.darken_alpha))
        crop = Image.alpha_composite(crop, darken)
        tint = Image.new("RGBA", crop.size, (255, 255, 255, self.tint_alpha))
        glass = Image.alpha_composite(crop, tint)

        draw = ImageDraw.Draw(glass)
        draw.rectangle(
            [1, 1, glass.width - 2, glass.height - 2],
            outline=(255, 255, 255, 220),
            width=3
        )

        for item in self.items:
            self._draw_item(draw, glass, item)

        self.photo = ImageTk.PhotoImage(glass)
        self.label.configure(image=self.photo)
        self._frame = background_frame
        self._size = (width, height)

    def _draw_item(self, draw, glass, item):
        max_width = int(glass.width * 0.84)
        size = max(12, int(glass.height * item["size"]))

        font = self.text_renderer.get_font(size)
        box = draw.textbbox((0, 0), item["text"], font=font)

        while box[2] - box[0] > max_width and size > 12:
            size -= 2
            font = self.text_renderer.get_font(size)
            box = draw.textbbox((0, 0), item["text"], font=font)

        text_width = box[2] - box[0]

        if item["align"] == "center":
            x = (glass.width - text_width) // 2 - box[0]
        else:
            x = int(glass.width * 0.08) - box[0]

        y = int(glass.height * item["rely"]) - box[1]

        for offset_x, offset_y in self.OUTLINE_OFFSETS:
            draw.text(
                (x + offset_x, y + offset_y), item["text"],
                font=font, fill=(5, 45, 75, 245)
            )
        draw.text((x, y), item["text"], font=font, fill=(255, 255, 255, 255))


class TrackerWindow(tk.Toplevel):

    PANEL_LEFT = 0.30
    PANEL_TOP = 0.14
    PANEL_WIDTH = 0.40
    PANEL_HEIGHT = 0.72

    TITLE_RELY = 0.05

    FIELDS = [
        ("name", "TRACKER NAME", 0.20),
        ("month", "MONTH", 0.40),
        ("budget", "BUDGET", 0.60),
    ]

    ENTRY_OFFSET = 0.075
    ENTRY_HEIGHT = 0.085

    PROCEED_RELY_IN_PANEL = 0.88
    PROCEED_RELHEIGHT = 0.09
    PROCEED_WIDTH_IN_PANEL = 0.50

    RESIZE_DEBOUNCE_MS = 80

    def __init__(self, parent, background_path, font_path,
                 on_close=None, on_proceed=None):
        super().__init__(parent)
        self.on_close = on_close
        self.on_proceed = on_proceed or self._default_proceed

        self.title("IPONOMIKS - Tracker")
        self.attributes("-fullscreen", True)

        self.background = ImageBackground(background_path)
        self.text_renderer = GlowTextRenderer(font_path)
        self.entry_font = tkfont.Font(family=FontLoader.load(font_path), size=16)

        self.background_photo = None
        self._last_width = 0
        self._last_height = 0
        self._resize_job = None

        self.background_label = tk.Label(self, bd=0, highlightthickness=0)
        self.background_label.place(x=0, y=0, relwidth=1, relheight=1)

        panel_items = [
            {"text": "CREATE TRACKER", "rely": self.TITLE_RELY, "size": 0.075, "align": "center"}
        ]
        for _, label, rely in self.FIELDS:
            panel_items.append({"text": label, "rely": rely, "size": 0.045, "align": "left"})

        self.panel = GlassPanel(
            self, self.text_renderer,
            self.PANEL_LEFT, self.PANEL_TOP, self.PANEL_WIDTH, self.PANEL_HEIGHT,
            panel_items
        )

        self.back_button = GlassButton(
            self, "BACK", self._handle_close, self.text_renderer,
            0.12, 0.08, 0.16, 0.08
        )

        self.proceed_button = GlassButton(
            self, "PROCEED", self._handle_proceed, self.text_renderer,
            self.PANEL_LEFT + self.PANEL_WIDTH / 2,
            self.PANEL_TOP + self.PANEL_HEIGHT * self.PROCEED_RELY_IN_PANEL,
            self.PANEL_WIDTH * self.PROCEED_WIDTH_IN_PANEL,
            self.PROCEED_RELHEIGHT
        )

        self.entries = {}
        for key, _, label_rely in self.FIELDS:
            self.entries[key] = self._create_entry(label_rely)

        self.entries["name"].focus_set()

        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _create_entry(self, label_rely):
        entry = tk.Entry(
            self,
            font=self.entry_font,
            bg="#0f1e2b",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            bd=8,
            highlightthickness=2,
            highlightbackground="#ffffff",
            highlightcolor="#46d2ff"
        )
        entry.place(
            relx=self.PANEL_LEFT + self.PANEL_WIDTH * 0.08,
            rely=self.PANEL_TOP + self.PANEL_HEIGHT * (label_rely + self.ENTRY_OFFSET),
            relwidth=self.PANEL_WIDTH * 0.84,
            relheight=self.PANEL_HEIGHT * self.ENTRY_HEIGHT
        )
        entry.bind("<Return>", lambda event: self._handle_proceed())
        return entry

    def _on_resize(self, event=None):
        if event is not None and event.widget is not self:
            return
        if event is not None and (event.width, event.height) == (self._last_width, self._last_height):
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(self.RESIZE_DEBOUNCE_MS, self._render)

    def _render(self):
        self._resize_job = None
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 10 or height < 10:
            return
        if (width, height) == (self._last_width, self._last_height):
            return

        self._last_width = width
        self._last_height = height

        frame = self.background.fit_to_size(width, height)

        self.background_photo = ImageTk.PhotoImage(frame)
        self.background_label.configure(image=self.background_photo)

        self.entry_font.configure(size=max(12, int(height * 0.026)))

        self.panel.render(frame, width, height)
        self.back_button.render(frame, width, height)
        self.proceed_button.render(frame, width, height)

    def _handle_proceed(self):
        name = self.entries["name"].get().strip()
        month = self.entries["month"].get().strip()
        budget_text = self.entries["budget"].get().strip()

        if not name or not month or not budget_text:
            messagebox.showerror("Missing information", "Please fill in all fields.", parent=self)
            return

        try:
            budget = parse_money(budget_text, "budget")
        except ValidationError as error:
            messagebox.showerror("Invalid budget", str(error), parent=self)
            return

        self.on_proceed(name, month, budget)

    def _default_proceed(self, name, month, budget):
        print(f"Tracker: {name} | Month: {month} | Budget: {budget}")

    def _handle_close(self):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None
        self.destroy()
        if self.on_close:
            self.on_close()