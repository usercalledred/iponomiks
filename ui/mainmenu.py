import math
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

import database
from logic.budget import Budget, BudgetStatus, format_money
from logic.expenses import CATEGORIES, ExpenseLog
from ui.widgets import FontLoader

OUTLINE_COLOR = (5, 45, 75, 245)
THIN_OUTLINE = [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)]


def draw_outlined_text(draw, x, y, text, font, fill, offsets=THIN_OUTLINE):
    for ox, oy in offsets:
        draw.text((x + ox, y + oy), text, font=font, fill=OUTLINE_COLOR)
    draw.text((x, y), text, font=font, fill=fill)


def paste_glass(target, source, box, darken_alpha=90, tint_alpha=60):
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return

    glass = source.crop(box).convert("RGBA").filter(ImageFilter.GaussianBlur(8))
    glass = Image.alpha_composite(glass, Image.new("RGBA", glass.size, (0, 0, 0, darken_alpha)))
    glass = Image.alpha_composite(glass, Image.new("RGBA", glass.size, (255, 255, 255, tint_alpha)))

    draw = ImageDraw.Draw(glass)
    draw.rectangle([0, 0, glass.width - 1, glass.height - 1], outline=(11, 13, 16, 255), width=1)
    draw.rectangle([1, 1, glass.width - 2, glass.height - 2], outline=(255, 255, 255, 220), width=3)
    target.paste(glass.convert("RGB"), (left, top))


def shift_color(color, amount):
    r, g, b = (max(0, min(255, int(color[i:i + 2], 16) + amount)) for i in (1, 3, 5))
    return f"#{r:02x}{g:02x}{b:02x}"


class GlowTextRenderer:

    OUTLINE_OFFSETS = [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)]
    OUTER_COLOR = (70, 210, 255)
    INNER_COLOR = (100, 225, 255)

    def __init__(self, font_path, fallback_font_path=r"C:\Windows\Fonts\arial.ttf"):
        self.font_path = font_path
        self.fallback_font_path = fallback_font_path
        self._font_cache = {}

    def get_font(self, size):
        if size not in self._font_cache:
            try:
                self._font_cache[size] = ImageFont.truetype(self.font_path, size)
            except OSError:
                self._font_cache[size] = ImageFont.truetype(self.fallback_font_path, size)
        return self._font_cache[size]

    def build_layers(self, size, texts):
        mask = Image.new("L", size, 0)
        text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        mask_draw = ImageDraw.Draw(mask)
        text_draw = ImageDraw.Draw(text_layer)

        for (x, y), text, font in texts:
            mask_draw.text((x, y), text, font=font, fill=255)
            draw_outlined_text(text_draw, x, y, text, font, (235, 250, 255, 255),
                               self.OUTLINE_OFFSETS)

        return {
            "outer": mask.filter(ImageFilter.GaussianBlur(18)),
            "inner": mask.filter(ImageFilter.GaussianBlur(5)),
            "text": text_layer,
        }

    @staticmethod
    def _scaled(mask, alpha):
        return mask.point([v * alpha // 255 for v in range(256)])

    def compose(self, background_region, layers, glow_amount):
        image = background_region.copy()
        glows = (("outer", self.OUTER_COLOR, 100, 155), ("inner", self.INNER_COLOR, 130, 125))
        for name, color, base, span in glows:
            image.paste(color, mask=self._scaled(layers[name], int(base + span * glow_amount)))
        image.paste(layers["text"], (0, 0), layers["text"])
        return image


class ImageBackground:

    def __init__(self, path):
        self.original = Image.open(path).convert("RGB")
        self._cached_size = None
        self._cached_image = None

    def fit_to_size(self, width, height):
        if self._cached_size == (width, height):
            return self._cached_image

        image_ratio = self.original.width / self.original.height
        if image_ratio > width / height:
            new_width, new_height = int(height * image_ratio), height
        else:
            new_width, new_height = width, int(width / image_ratio)

        resized = self.original.resize((new_width, new_height), Image.Resampling.LANCZOS)
        left, top = (new_width - width) // 2, (new_height - height) // 2

        self._cached_image = resized.crop((left, top, left + width, top + height))
        self._cached_size = (width, height)
        return self._cached_image


class GlassButton:

    def __init__(self, parent, text, command, text_renderer,
                 relx, rely, relwidth, relheight, on_state_change=None):
        self.text = text
        self.command = command
        self.text_renderer = text_renderer
        self.relx, self.rely = relx, rely
        self.relwidth, self.relheight = relwidth, relheight
        self.on_state_change = on_state_change

        self.hovered = False
        self._photos = {}
        self._frame = None
        self._size = None

        self.label = tk.Label(parent, bd=0, highlightthickness=0, cursor="hand2")
        self.label.place(relx=relx, rely=rely, relwidth=relwidth, relheight=relheight,
                         anchor="center")
        self.label.bind("<Button-1>", lambda event: self.command())
        self.label.bind("<Enter>", lambda event: self._set_hover(True))
        self.label.bind("<Leave>", lambda event: self._set_hover(False))

    def _set_hover(self, hovered):
        self.hovered = hovered
        self._apply()
        if self.on_state_change:
            self.on_state_change(self)

    def _apply(self):
        photo = self._photos.get(self.hovered)
        if photo is not None:
            self.label.configure(image=photo)

    def pixel_rect(self, width, height):
        cx, cy = self.relx * width, self.rely * height
        half_w, half_h = self.relwidth * width / 2, self.relheight * height / 2
        return int(cx - half_w), int(cy - half_h), int(cx + half_w), int(cy + half_h)

    def _fit_font(self, base):
        size = max(20, int(base.height * 0.5))
        measure = ImageDraw.Draw(Image.new("L", (1, 1)))
        while True:
            font = self.text_renderer.get_font(size)
            box = measure.textbbox((0, 0), self.text, font=font)
            if box[2] - box[0] <= base.width * 0.88 or size <= 12:
                return font
            size -= 2

    def render(self, background_frame, width, height):
        if self._frame is background_frame and self._size == (width, height):
            self._apply()
            return

        left, top, right, bottom = self.pixel_rect(width, height)
        box = (max(0, left), max(0, top),
               min(background_frame.width, right), min(background_frame.height, bottom))
        if box[2] <= box[0] or box[3] <= box[1]:
            return

        base = background_frame.crop(box).convert("RGBA")
        base = base.filter(ImageFilter.GaussianBlur(8))
        base = Image.alpha_composite(base, Image.new("RGBA", base.size, (0, 0, 0, 60)))

        font = self._fit_font(base)

        self._photos = {
            False: ImageTk.PhotoImage(self._compose(base, font, 105, 210)),
            True: ImageTk.PhotoImage(self._compose(base, font, 150, 255)),
        }
        self._frame = background_frame
        self._size = (width, height)
        self._apply()

    def _compose(self, base, font, tint_alpha, border_alpha):
        glass = Image.alpha_composite(
            base, Image.new("RGBA", base.size, (255, 255, 255, tint_alpha)))
        draw = ImageDraw.Draw(glass)
        draw.rectangle([1, 1, glass.width - 2, glass.height - 2],
                       outline=(255, 255, 255, border_alpha), width=3)

        box = draw.textbbox((0, 0), self.text, font=font)
        text_x = (glass.width - (box[2] - box[0])) // 2 - box[0]
        text_y = (glass.height - (box[3] - box[1])) // 2 - box[1]
        draw_outlined_text(draw, text_x, text_y, self.text, font, (255, 255, 255, 255))
        return glass


class Palette:
   

    PANEL_OUTER, PANEL_EDGE = "#0b0d10", "#5d6673"
    FIELD_BG = "#15181d"
    TEXT, MUTED, GOLD, LINE, SHADOW = "#ffffff", "#c8d0d8", "#ffd24a", "#aab4c0", "#052d4b"
    GREEN, ORANGE, RED = "#4cc65a", "#f39c2f", "#e04848"

    STATUS_COLORS = {BudgetStatus.SAFE: GREEN, BudgetStatus.WARNING: ORANGE,
                     BudgetStatus.OVER: RED}
    CATEGORY_COLORS = dict(zip(CATEGORIES, [
        "#e8a23a", "#4aa3df", "#9b6fd6", "#d65a8a", "#c98a5a", "#3fd0c9",
        "#e6d94a", "#e26a6a", "#7bd35a", "#f07fb0", "#5ad6a0", "#9aa5b1"]))


class MainDashboard:

    TITLE = "IPONOMIKS"
    SUBTITLE = "STUDENT BUDGET AND EXPENSE TRACKER SYSTEM"

    TITLE_PLAQUE = (0.18, 0.025, 0.64, 0.185)
    MENU_PANEL = (0.04, 0.25, 0.24, 0.70)
    OVERVIEW_PANEL = (0.30, 0.25, 0.38, 0.70)
    RECENT_PANEL = (0.70, 0.25, 0.26, 0.70)

    FONT_PX = {"menu_title": (48, 26), "heading": (30, 16), "stat": (24, 13), "body": (21, 12), "small": (17, 10)}
    MAX_RECENT = 5
    MAX_CATEGORIES = 4

    GLOW_LEVELS = 16
    FRAME_DELAY_MS = 40
    RESIZE_DEBOUNCE_MS = 80
    GLOW_PADDING = 30

    def __init__(self, parent, background_path, font_path,
                 on_create=None, on_load=None, on_exit=None, on_open_tracker=None):
        self.parent = parent
        self.on_create = on_create or (lambda: None)
        self.on_load = on_load or (lambda: None)
        self.on_exit = on_exit or self.parent.destroy
        self.on_open_tracker = on_open_tracker or (lambda tracker_id: None)

        self.background = ImageBackground(background_path)
        self.text_renderer = GlowTextRenderer(font_path)
        family = FontLoader.load(font_path)
        self.fonts = {key: tkfont.Font(family=family, size=-px[0])
                      for key, px in self.FONT_PX.items()}

        self.background_photo = None
        self.glow_step = 0
        self.data = {}

        self._size = (0, 0)
        self._resize_job = None
        self._boxes = {}
        self._hits = []

        self._composite = None
        self._row_photos = []

        self._glow_bg = None
        self._glow_layers = None
        self._glow_cache = {}
        self._shown_level = None

        self.canvas = tk.Canvas(parent, bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_item = self.canvas.create_image(0, 0, anchor="nw")
        self._glow_item = self.canvas.create_image(0, 0, anchor="nw")
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)

        menu_x = self.MENU_PANEL[0] + self.MENU_PANEL[2] / 2
        menu_y, menu_h = self.MENU_PANEL[1], self.MENU_PANEL[3]
        menu = (("CREATE TRACKER", self.on_create, 0.30),
                ("LOAD TRACKER", self.on_load, 0.46),
                ("EXIT", self.on_exit, 0.62))
        self.buttons = [GlassButton(parent, text, command, self.text_renderer,
                                    menu_x, menu_y + menu_h * frac,
                                    self.MENU_PANEL[2] * 0.84, 0.08)
                        for text, command, frac in menu]

        self._load_data()

        self.parent.bind("<Configure>", self._on_resize)
        self.parent.bind("<Control-n>", lambda event: self.on_create())
        self.parent.bind("<Control-l>", lambda event: self.on_load())
        self._animate_glow()

    
    def _load_data(self):
        try:
            rows = list(database.get_tracker_overview())
        except Exception:
            rows = []
        rows.sort(key=lambda row: row[0], reverse=True)

        total_budget = sum(row[3] for row in rows)
        total_spent = sum(row[5] for row in rows)
        entries = sum(row[6] for row in rows)
        over_count = sum(1 for row in rows
                         if Budget(row[3]).status(row[5]) == BudgetStatus.OVER)

        categories = {}
        for row in rows:
            try:
                items = ExpenseLog(database.get_tracker_expenses(row[0])).items
            except Exception:
                continue
            for item in items:
                categories[item.category] = categories.get(item.category, 0) + item.amount

        if total_budget > 0:
            plan = Budget(total_budget)
            status_color = Palette.STATUS_COLORS[plan.status(total_spent)]
            fraction = plan.bar_fraction(total_spent)
            message = plan.message(total_spent)
            percent = total_spent / total_budget * 100
        else:
            status_color, fraction, percent = Palette.MUTED, 0, 0
            message = "NO TRACKERS YET. CREATE ONE TO BEGIN."

        self.data = {
            "trackers": rows,
            "budget": total_budget,
            "spent": total_spent,
            "entries": entries,
            "over_count": over_count,
            "categories": sorted(categories.items(), key=lambda pair: pair[1], reverse=True),
            "color": status_color,
            "fraction": fraction,
            "percent": percent,
            "message": message,
        }

    def refresh(self):
        self._load_data()
        self._draw_content()


    def _on_resize(self, event=None):
        if event is not None and (event.widget is not self.parent
                                  or (event.width, event.height) == self._size):
            return
        if self._resize_job is not None:
            self.parent.after_cancel(self._resize_job)
        self._resize_job = self.parent.after(self.RESIZE_DEBOUNCE_MS, self._rebuild)

    def _box(self, rect, width, height):
        x, y, w, h = rect
        return int(x * width), int(y * height), int((x + w) * width), int((y + h) * height)

    def _rebuild(self):
        self._resize_job = None
        width, height = self.parent.winfo_width(), self.parent.winfo_height()
        if width < 10 or height < 10 or (width, height) == self._size:
            return
        self._size = (width, height)

        for key, (base, minimum) in self.FONT_PX.items():
            self.fonts[key].configure(size=-max(minimum, int(base * height / 1080)))

        frame = self.background.fit_to_size(width, height)
        self._boxes = {
            "title": self._box(self.TITLE_PLAQUE, width, height),
            "menu": self._box(self.MENU_PANEL, width, height),
            "overview": self._box(self.OVERVIEW_PANEL, width, height),
            "recent": self._box(self.RECENT_PANEL, width, height),
        }

        composite = frame.copy()
        for box in self._boxes.values():
            paste_glass(composite, frame, box)

        self._composite = composite
        self.background_photo = ImageTk.PhotoImage(composite)
        self.canvas.itemconfig(self._bg_item, image=self.background_photo)

        self._build_glow(composite, width, height)
        self._draw_content()
        for button in self.buttons:
            button.render(composite, width, height)


    def _fit_font(self, measure, text, size, max_width):
        while True:
            font = self.text_renderer.get_font(size)
            box = measure.textbbox((0, 0), text, font=font)
            if box[2] - box[0] <= max_width or size <= 12:
                return font
            size -= 2

    def _build_glow(self, frame, width, height):
        plaque_left, plaque_top, plaque_right, plaque_bottom = self._boxes["title"]
        plaque_w, plaque_h = plaque_right - plaque_left, plaque_bottom - plaque_top

        measure = ImageDraw.Draw(Image.new("L", (1, 1)))
        title_font = self._fit_font(measure, self.TITLE, max(48, int(height * 0.105)),
                                    int(plaque_w * 0.9))
        subtitle_font = self._fit_font(measure, self.SUBTITLE, max(16, int(height * 0.03)),
                                       int(plaque_w * 0.92))

        title_box = measure.textbbox((0, 0), self.TITLE, font=title_font)
        sub_box = measure.textbbox((0, 0), self.SUBTITLE, font=subtitle_font)
        title_w, title_h = title_box[2] - title_box[0], title_box[3] - title_box[1]
        sub_w, sub_h = sub_box[2] - sub_box[0], sub_box[3] - sub_box[1]

        gap = int(height * 0.02)
        block_top = plaque_top + (plaque_h - (title_h + gap + sub_h)) // 2
        center_x = (plaque_left + plaque_right) // 2

        title_x = center_x - title_w // 2 - title_box[0]
        title_y = block_top - title_box[1]
        subtitle_x = center_x - sub_w // 2 - sub_box[0]
        subtitle_y = block_top + title_h + gap - sub_box[1]

        pad = self.GLOW_PADDING
        left, top = max(0, plaque_left - pad), max(0, plaque_top - pad)
        right, bottom = min(width, plaque_right + pad), min(height, plaque_bottom + pad)

        self._glow_bg = frame.crop((left, top, right, bottom))
        self._glow_layers = self.text_renderer.build_layers((right - left, bottom - top), [
            ((title_x - left, title_y - top), self.TITLE, title_font),
            ((subtitle_x - left, subtitle_y - top), self.SUBTITLE, subtitle_font),
        ])

        self._glow_cache = {}
        self._shown_level = None
        self.canvas.coords(self._glow_item, left, top)
        self._show_glow(self._current_level())

    def _current_level(self):
        amount = (math.sin(self.glow_step * 0.08) + 1) / 2
        return round(amount * (self.GLOW_LEVELS - 1))

    def _show_glow(self, level):
        if level == self._shown_level or self._glow_layers is None:
            return

        photo = self._glow_cache.get(level)
        if photo is None:
            amount = level / (self.GLOW_LEVELS - 1)
            image = self.text_renderer.compose(self._glow_bg, self._glow_layers, amount)
            photo = self._glow_cache[level] = ImageTk.PhotoImage(image)

        self.canvas.itemconfig(self._glow_item, image=photo)
        self._shown_level = level

    def _animate_glow(self):
        self.glow_step += 1
        if self.parent.state() != "withdrawn":
            self._show_glow(self._current_level())
        self.parent.after(self.FRAME_DELAY_MS, self._animate_glow)

    @staticmethod
    def _fit(text, font, max_width):
        if font.measure(text) <= max_width:
            return text
        while text and font.measure(text + "...") > max_width:
            text = text[:-1]
        return text + "..."

    def _text(self, x, y, text, color, font, anchor="nw", **options):
        for dx, dy, fill in ((2, 2, Palette.SHADOW), (0, 0, color)):
            self.canvas.create_text(x + dx, y + dy, text=text, fill=fill, font=font,
                                    anchor=anchor, tags="content", **options)

    def _heading(self, text, font_key, x0, x1, y):
        font = self.fonts[font_key]
        self._text(x0, y, self._fit(text, font, x1 - x0), Palette.GOLD, font)
        y += font.metrics("linespace") + 6
        self.canvas.create_line(x0, y, x1, y, fill=Palette.LINE, width=2, tags="content")
        return y + 12

    def _centered_heading(self, text, font_key, x0, x1, y):
        font = self.fonts[font_key]
        self._text((x0 + x1) // 2, y, self._fit(text, font, x1 - x0), Palette.GOLD, font,
                   anchor="n")
        y += font.metrics("linespace") + 6
        self.canvas.create_line(x0, y, x1, y, fill=Palette.LINE, width=2, tags="content")
        return y + 12

    def _glass_row(self, x0, y0, x1, y1):
        """Frosted-glass row (instead of a solid black box) that stays readable."""
        if self._composite is None:
            return
        box = (max(0, int(x0)), max(0, int(y0)),
               min(self._composite.width, int(x1)), min(self._composite.height, int(y1)))
        if box[2] <= box[0] or box[3] <= box[1]:
            return
        glass = self._composite.crop(box).convert("RGBA")
        glass = Image.alpha_composite(glass, Image.new("RGBA", glass.size, (0, 0, 0, 80)))
        glass = Image.alpha_composite(glass, Image.new("RGBA", glass.size, (255, 255, 255, 38)))
        ImageDraw.Draw(glass).rectangle([0, 0, glass.width - 1, glass.height - 1],
                                        outline=(255, 255, 255, 190), width=2)
        photo = ImageTk.PhotoImage(glass)
        self._row_photos.append(photo)
        self.canvas.create_image(box[0], box[1], image=photo, anchor="nw", tags="content")

    def _draw_bar(self, x0, y0, x1, y1, fraction, color):
        canvas = self.canvas
        canvas.create_rectangle(x0, y0, x1, y1, fill=Palette.FIELD_BG, outline="", tags="content")

        fill_x = x0 + (x1 - x0) * max(0, min(1, fraction))
        if fill_x > x0:
            band = max(2, int((y1 - y0) * 0.18))
            canvas.create_rectangle(x0, y0, fill_x, y1, fill=color, outline="", tags="content")
            canvas.create_rectangle(x0, y0, fill_x, y0 + band,
                                    fill=shift_color(color, 45), outline="", tags="content")
            canvas.create_rectangle(x0, y1 - band, fill_x, y1,
                                    fill=shift_color(color, -55), outline="", tags="content")

        for i in range(1, 10):
            x = x0 + (x1 - x0) * i / 10
            canvas.create_line(x, y0, x, y1, fill=Palette.PANEL_OUTER, width=2, tags="content")
        canvas.create_rectangle(x0, y0, x1, y1, outline=Palette.PANEL_OUTER, width=3,
                                tags="content")

    def _draw_content(self):
        self.canvas.delete("content")
        self._row_photos = []
        self._hits = []
        if not self._boxes:
            return
        self._draw_menu(self._boxes["menu"])
        self._draw_overview(self._boxes["overview"])
        self._draw_recent(self._boxes["recent"])

    def _draw_menu(self, box):
        left, top, right, bottom = box
        pad = int((right - left) * 0.08)
        x0, x1 = left + pad, right - pad
        self._centered_heading("MENU", "menu_title", x0, x1, top + int((bottom - top) * 0.03))

        small = self.fonts["small"]
        line = small.metrics("linespace") + 6
        center = (left + right) // 2
        y = bottom - pad - line * 3
        today = datetime.now().strftime("%a, %d %b %Y").upper()
        for text, color in ((today, Palette.TEXT), ("CTRL+N = CREATE", Palette.MUTED),
                            ("CTRL+L = LOAD", Palette.MUTED)):
            self._text(center, y, self._fit(text, small, x1 - x0), color, small, anchor="n")
            y += line

    def _draw_overview(self, box):
        left, top, right, bottom = box
        data = self.data
        pad = int((right - left) * 0.06)
        x0, x1 = left + pad, right - pad
        stat, small = self.fonts["stat"], self.fonts["small"]
        stat_h, small_h = stat.metrics("linespace"), small.metrics("linespace")
        color = data["color"]

        y = self._heading("OVERVIEW", "heading", x0, x1, top + int((bottom - top) * 0.03))

        over = data["over_count"]
        rows = [
            ("TRACKERS", str(len(data["trackers"])), Palette.TEXT),
            ("TOTAL BUDGET", format_money(data["budget"]), Palette.TEXT),
            ("TOTAL SPENT", format_money(data["spent"]), Palette.TEXT),
            ("REMAINING", format_money(data["budget"] - data["spent"]), color),
            ("USED", f"{data['percent']:.1f}%", color),
            ("ENTRIES", str(data["entries"]), Palette.TEXT),
            ("OVER BUDGET", f"{over} TRACKER{'' if over == 1 else 'S'}",
             Palette.RED if over else Palette.TEXT),
        ]
        for label, value, fg in rows:
            self._text(x0, y + stat_h - small_h, label, Palette.MUTED, small)
            self._text(x1, y, value, fg, stat, anchor="ne")
            y += stat_h + 8

        y += 6
        self._text(x0, y, "OVERALL BUDGET USED", Palette.MUTED, small)
        self._text(x1, y, f"{data['percent']:.0f}%", color, small, anchor="ne")
        y += small_h + 4
        bar_h = max(18, int((bottom - top) * 0.05))
        self._draw_bar(x0, y, x1, y + bar_h, data["fraction"], color)
        y += bar_h + 8
        self._text(x0, y, data["message"], color, small, width=x1 - x0)
        y += small_h * 2 + 10

        y = self._heading("TOP CATEGORIES", "stat", x0, x1, y)
        self._draw_categories(x0, x1, y, bottom - pad)

    def _draw_categories(self, x0, x1, y, limit):
        small = self.fonts["small"]
        categories = self.data["categories"]
        if not categories:
            self._text((x0 + x1) // 2, y, "NO EXPENSES YET", Palette.MUTED, small, anchor="n")
            return

        line = small.metrics("linespace")
        bar_h = max(8, int(line * 0.6))
        row_h = line + bar_h + 14
        count = min(self.MAX_CATEGORIES, len(categories), max(0, int(limit - y) // row_h))
        grand_total = sum(total for _, total in categories) or 1

        for category, total in categories[:count]:
            share = total / grand_total * 100
            color = Palette.CATEGORY_COLORS.get(category, Palette.CATEGORY_COLORS["Others"])
            self._text(x0, y, category.upper(), Palette.TEXT, small)
            self._text(x1, y, f"{total:,.2f}  {share:.0f}%", Palette.MUTED, small, anchor="ne")
            top = y + line + 4
            self._draw_bar(x0, top, x1, top + bar_h, share / 100, color)
            y += row_h

    def _draw_recent(self, box):
        left, top, right, bottom = box
        pad = int((right - left) * 0.08)
        x0, x1 = left + pad, right - pad
        body, small = self.fonts["body"], self.fonts["small"]
        body_h, small_h = body.metrics("linespace"), small.metrics("linespace")

        y = self._heading("RECENT TRACKERS", "heading", x0, x1,
                          top + int((bottom - top) * 0.03))
        trackers = self.data["trackers"]
        footer_y = bottom - pad - small_h

        if not trackers:
            center = (left + right) // 2
            self._text(center, (y + footer_y) // 2 - small_h, "NO TRACKERS YET",
                       Palette.MUTED, small, anchor="n")
            self._text(center, (y + footer_y) // 2 + small_h // 2, "PRESS CREATE TRACKER",
                       Palette.MUTED, small, anchor="n")
            return

        bar_h = max(8, int(small_h * 0.6))
        row_h = body_h + small_h + bar_h + 24
        gap = 10
        count = min(self.MAX_RECENT, len(trackers),
                    max(1, int(footer_y - y - 6) // (row_h + gap)))

        for tracker_id, name, month, budget, _created, spent, _entries in trackers[:count]:
            plan = Budget(budget)
            color = Palette.STATUS_COLORS[plan.status(spent)]
            self._glass_row(x0, y, x1, y + row_h)
            inner0, inner1 = x0 + 10, x1 - 10
            self._text(inner0, y + 6, self._fit(name.upper(), body, inner1 - inner0),
                       Palette.TEXT, body)
            info = f"{month}  {format_money(spent)} / {format_money(budget)}"
            self._text(inner0, y + 6 + body_h, self._fit(info, small, inner1 - inner0),
                       Palette.MUTED, small)
            bar_top = y + row_h - bar_h - 8
            self._draw_bar(inner0, bar_top, inner1, bar_top + bar_h,
                           spent / budget if budget else 0, color)
            self._hits.append((x0, y, x1, y + row_h, tracker_id))
            y += row_h + gap

        hidden = len(trackers) - count
        note = f"+{hidden} MORE IN LOAD TRACKER" if hidden else "CLICK A TRACKER TO OPEN"
        self._text((left + right) // 2, footer_y,
                   self._fit(note, small, x1 - x0), Palette.MUTED, small, anchor="n")

    def _hit(self, x, y):
        for left, top, right, bottom, tracker_id in self._hits:
            if left <= x <= right and top <= y <= bottom:
                return tracker_id
        return None

    def _on_motion(self, event):
        self.canvas.configure(cursor="hand2" if self._hit(event.x, event.y) else "")

    def _on_click(self, event):
        tracker_id = self._hit(event.x, event.y)
        if tracker_id is not None:
            self.on_open_tracker(tracker_id)
