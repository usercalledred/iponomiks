import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk


class GlowTextRenderer:
    """Draws glowing text. Fonts are cached, and the expensive blurs are
    computed once (build_layers); glow pulsing afterwards is just a cheap
    re-scaling of the pre-blurred masks (compose)."""

    OUTLINE_COLOR = (5, 45, 75, 245)
    OUTLINE_OFFSETS = [
        (-3, 0), (3, 0), (0, -3), (0, 3),
        (-2, -2), (2, -2), (-2, 2), (2, 2)
    ]
    OUTER_COLOR = (70, 210, 255)
    INNER_COLOR = (100, 225, 255)

    def __init__(self, font_path, fallback_font_path=r"C:\Windows\Fonts\arial.ttf"):
        self.font_path = font_path
        self.fallback_font_path = fallback_font_path
        self._font_cache = {}

    def get_font(self, size):
        font = self._font_cache.get(size)
        if font is None:
            try:
                font = ImageFont.truetype(self.font_path, size)
            except OSError:
                font = ImageFont.truetype(self.fallback_font_path, size)
            self._font_cache[size] = font
        return font

    def build_layers(self, size, texts):
        """texts: list of ((x, y), text, font), positions relative to the region.
        Returns the blurred glow masks and the static outlined text layer."""
        mask = Image.new("L", size, 0)
        text_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        mask_draw = ImageDraw.Draw(mask)
        text_draw = ImageDraw.Draw(text_layer)

        for (x, y), text, font in texts:
            mask_draw.text((x, y), text, font=font, fill=255)
            for ox, oy in self.OUTLINE_OFFSETS:
                text_draw.text((x + ox, y + oy), text, font=font, fill=self.OUTLINE_COLOR)
            text_draw.text((x, y), text, font=font, fill=(235, 250, 255, 255))

        return {
            "outer": mask.filter(ImageFilter.GaussianBlur(18)),
            "inner": mask.filter(ImageFilter.GaussianBlur(5)),
            "text": text_layer,
        }

    @staticmethod
    def _scaled(mask, alpha):
        return mask.point([v * alpha // 255 for v in range(256)])

    def compose(self, background_region, layers, glow_amount):
        """background_region: RGB crop. Returns an RGB image with the glow."""
        image = background_region.copy()
        image.paste(self.OUTER_COLOR,
                    mask=self._scaled(layers["outer"], int(100 + 155 * glow_amount)))
        image.paste(self.INNER_COLOR,
                    mask=self._scaled(layers["inner"], int(130 + 125 * glow_amount)))
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
        window_ratio = width / height

        if image_ratio > window_ratio:
            new_height = height
            new_width = int(height * image_ratio)
        else:
            new_width = width
            new_height = int(width / image_ratio)

        resized = self.original.resize((new_width, new_height), Image.Resampling.LANCZOS)

        left = (new_width - width) // 2
        top = (new_height - height) // 2

        self._cached_image = resized.crop((left, top, left + width, top + height))
        self._cached_size = (width, height)
        return self._cached_image


class GlassButton:
    """Glass button. Normal and hover images are built once per window size;
    hovering only swaps between two cached images."""

    def __init__(self, parent, text, command, text_renderer,
                 relx, rely, relwidth, relheight, on_state_change=None):
        self.text = text
        self.command = command
        self.text_renderer = text_renderer
        self.relx = relx
        self.rely = rely
        self.relwidth = relwidth
        self.relheight = relheight
        self.on_state_change = on_state_change

        self.hovered = False
        self._photos = {}
        self._frame = None
        self._size = None

        self.label = tk.Label(parent, bd=0, highlightthickness=0, cursor="hand2")
        self.label.place(
            relx=relx, rely=rely,
            relwidth=relwidth, relheight=relheight,
            anchor="center"
        )
        self.label.bind("<Button-1>", self._on_click)
        self.label.bind("<Enter>", self._on_enter)
        self.label.bind("<Leave>", self._on_leave)

    def _on_click(self, event):
        self.command()

    def _on_enter(self, event):
        self._set_hover(True)

    def _on_leave(self, event):
        self._set_hover(False)

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
        cx = self.relx * width
        cy = self.rely * height
        w = self.relwidth * width
        h = self.relheight * height
        return (
            int(cx - w / 2), int(cy - h / 2),
            int(cx + w / 2), int(cy + h / 2)
        )

    def render(self, background_frame, width, height):
        if self._frame is background_frame and self._size == (width, height):
            self._apply()
            return

        left, top, right, bottom = self.pixel_rect(width, height)
        left = max(0, left)
        top = max(0, top)
        right = min(background_frame.width, right)
        bottom = min(background_frame.height, bottom)

        if right <= left or bottom <= top:
            return

        base = background_frame.crop((left, top, right, bottom)).convert("RGBA")
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
            base, Image.new("RGBA", base.size, (255, 255, 255, tint_alpha))
        )
        draw = ImageDraw.Draw(glass)
        draw.rectangle(
            [1, 1, glass.width - 2, glass.height - 2],
            outline=(255, 255, 255, border_alpha), width=3
        )

        box = draw.textbbox((0, 0), self.text, font=font)
        text_x = (glass.width - (box[2] - box[0])) // 2 - box[0]
        text_y = (glass.height - (box[3] - box[1])) // 2 - box[1]

        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2),
                       (-2, -2), (2, -2), (-2, 2), (2, 2)]:
            draw.text((text_x + ox, text_y + oy), self.text,
                      font=font, fill=(5, 45, 75, 245))
        draw.text((text_x, text_y), self.text, font=font, fill=(255, 255, 255, 255))
        return glass


class MainMenu:

    TITLE = "IPONOMIKS"
    SUBTITLE = "STUDENT BUDGET AND EXPENSE TRACKER SYSTEM"

    GLOW_LEVELS = 16          # number of cached glow brightness steps
    FRAME_DELAY_MS = 40       # ~25 fps is plenty for a soft pulse
    RESIZE_DEBOUNCE_MS = 80
    GLOW_PADDING = 60         # room around the text for the blur

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

        self._frame = None
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

        self.buttons = [
            GlassButton(parent, "START TRACKING", self.on_start,
                        self.text_renderer, 0.5, 0.50, 0.42, 0.11),
            GlassButton(parent, "LOAD TRACKERS", self.on_load,
                        self.text_renderer, 0.5, 0.64, 0.42, 0.11),
            GlassButton(parent, "EXIT", self.on_exit,
                        self.text_renderer, 0.5, 0.78, 0.42, 0.11),
        ]

        self.parent.bind("<Configure>", self._on_resize)
        self._animate_glow()

    # ---------- resize handling (debounced, skipped when size is unchanged)

    def _on_resize(self, event=None):
        if event is not None and event.widget is not self.parent:
            return
        if event is not None and (event.width, event.height) == self._size:
            return
        if self._resize_job is not None:
            self.parent.after_cancel(self._resize_job)
        self._resize_job = self.parent.after(self.RESIZE_DEBOUNCE_MS, self._rebuild)

    def _rebuild(self):
        self._resize_job = None
        width = self.parent.winfo_width()
        height = self.parent.winfo_height()
        if width < 10 or height < 10 or (width, height) == self._size:
            return
        self._size = (width, height)

        frame = self.background.fit_to_size(width, height)
        self._frame = frame

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

        region_size = (right - left, bottom - top)
        self._glow_bg = frame.crop((left, top, right, bottom))
        self._glow_layers = self.text_renderer.build_layers(region_size, [
            ((title_x - left, title_y - top), self.TITLE, title_font),
            ((subtitle_x - left, subtitle_y - top), self.SUBTITLE, subtitle_font),
        ])

        self._glow_cache = {}
        self._shown_level = None
        self.canvas.coords(self._glow_item, left, top)
        self._show_glow(self._current_level())

    # ---------- glow animation (only swaps small cached images)

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
            photo = ImageTk.PhotoImage(image)
            self._glow_cache[level] = photo

        self.canvas.itemconfig(self._glow_item, image=photo)
        self._shown_level = level

    def _animate_glow(self):
        self.glow_step += 1
        # Skip all work while the menu is hidden (e.g. tracker window open).
        if self.parent.state() != "withdrawn":
            self._show_glow(self._current_level())
        self.parent.after(self.FRAME_DELAY_MS, self._animate_glow)