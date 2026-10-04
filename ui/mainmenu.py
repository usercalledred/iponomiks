import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

OUTLINE_COLOR = (5, 45, 75, 245)
THIN_OUTLINE = [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)]


def draw_outlined_text(draw, x, y, text, font, fill, offsets=THIN_OUTLINE):
    for ox, oy in offsets:
        draw.text((x + ox, y + oy), text, font=font, fill=OUTLINE_COLOR)
    draw.text((x, y), text, font=font, fill=fill)


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

        font = self.text_renderer.get_font(max(20, int(base.height * 0.5)))

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


class MainMenu:

    TITLE = "IPONOMIKS"
    SUBTITLE = "STUDENT BUDGET AND EXPENSE TRACKER SYSTEM"

    GLOW_LEVELS = 16
    FRAME_DELAY_MS = 40
    RESIZE_DEBOUNCE_MS = 80
    GLOW_PADDING = 60

    def __init__(self, parent, background_path, font_path,
                 on_start=None, on_load=None, on_exit=None):
        self.parent = parent
        self.on_start = on_start or (lambda: None)
        self.on_load = on_load or (lambda: None)
        self.on_exit = on_exit or self.parent.destroy

        self.background = ImageBackground(background_path)
        self.text_renderer = GlowTextRenderer(font_path)

        self.background_photo = None
        self.glow_step = 0

        self._size = (0, 0)
        self._resize_job = None

        self._glow_bg = None
        self._glow_layers = None
        self._glow_cache = {}
        self._shown_level = None

        self.canvas = tk.Canvas(parent, bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_item = self.canvas.create_image(0, 0, anchor="nw")
        self._glow_item = self.canvas.create_image(0, 0, anchor="nw")

        menu = (("START TRACKING", self.on_start, 0.50),
                ("LOAD TRACKERS", self.on_load, 0.64),
                ("EXIT", self.on_exit, 0.78))
        self.buttons = [GlassButton(parent, text, command, self.text_renderer,
                                    0.5, rely, 0.42, 0.11)
                        for text, command, rely in menu]

        self.parent.bind("<Configure>", self._on_resize)
        self._animate_glow()

    def _on_resize(self, event=None):
        if event is not None and (event.widget is not self.parent
                                  or (event.width, event.height) == self._size):
            return
        if self._resize_job is not None:
            self.parent.after_cancel(self._resize_job)
        self._resize_job = self.parent.after(self.RESIZE_DEBOUNCE_MS, self._rebuild)

    def _rebuild(self):
        self._resize_job = None
        width, height = self.parent.winfo_width(), self.parent.winfo_height()
        if width < 10 or height < 10 or (width, height) == self._size:
            return
        self._size = (width, height)

        frame = self.background.fit_to_size(width, height)
        self.background_photo = ImageTk.PhotoImage(frame)
        self.canvas.itemconfig(self._bg_item, image=self.background_photo)

        self._build_glow(frame, width, height)
        for button in self.buttons:
            button.render(frame, width, height)

    def _build_glow(self, frame, width, height):
        measure = ImageDraw.Draw(Image.new("L", (1, 1)))

        title_font = self.text_renderer.get_font(max(110, int(height * 0.17)))
        subtitle_font = self.text_renderer.get_font(max(32, int(height * 0.05)))

        title_box = measure.textbbox((0, 0), self.TITLE, font=title_font)
        title_x = (width - (title_box[2] - title_box[0])) // 2
        title_y = int(height * 0.10)

        sub_box = measure.textbbox((0, 0), self.SUBTITLE, font=subtitle_font)
        subtitle_x = (width - (sub_box[2] - sub_box[0])) // 2
        subtitle_y = title_y + (title_box[3] - title_box[1]) + int(height * 0.025)

        pad = self.GLOW_PADDING
        left = max(0, min(title_x, subtitle_x) - pad)
        top = max(0, title_y + title_box[1] - pad)
        right = min(width, max(title_x + title_box[2], subtitle_x + sub_box[2]) + pad)
        bottom = min(height, subtitle_y + sub_box[3] + pad)

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