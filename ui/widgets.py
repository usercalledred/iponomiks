import ctypes
import sys
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk


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