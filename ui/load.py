import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageFilter, ImageTk

import database
from logic.budget import Budget, BudgetStatus, format_money
from logic.validation import ValidationError, parse_money
from ui.mainmenu import GlassButton, GlowTextRenderer, ImageBackground
from ui.widgets import FontLoader, GlassPanel

WHITE = "#ffffff"
MUTED = "#c8d0d8"

STATUS_COLORS = {
    BudgetStatus.SAFE: "#55ff55",
    BudgetStatus.WARNING: "#ffaa00",
    BudgetStatus.OVER: "#ff5555",
}


class TrackerList(tk.Canvas):

    DARKEN_ALPHA = 110
    TINT_ALPHA = 28
    CARD_ALPHA = 22
    HIGHLIGHT_ALPHA = 55
    BORDER_COLOR = "#aab4c0"
    PADDING = 10
    GAP = 8
    ROW_PADDING = 10
    SCROLL_STEP = 70
    SHADOW = "#052d4b"

    def __init__(self, parent, name_font, detail_font, on_open):
        super().__init__(parent, bd=0, highlightthickness=0, bg="#0c0c10",
                         cursor="hand2")
        self.name_font = name_font
        self.detail_font = detail_font
        self.on_open = on_open

        self._trackers = {}
        self._order = []
        self._selected_id = None
        self._offset = 0

        self._glass_photo = None
        self._fills = {}
        self._glass_item = self.create_image(0, 0, anchor="nw")

        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<Double-Button-1>", self._on_double_click)

    @property
    def selected(self):
        return self._trackers.get(self._selected_id)

    def set_backdrop(self, frame):
        self.update_idletasks()
        left, top = self.winfo_x(), self.winfo_y()
        right = min(frame.width, left + self.winfo_width())
        bottom = min(frame.height, top + self.winfo_height())
        if right <= left or bottom <= top:
            return

        glass = frame.crop((left, top, right, bottom)).convert("RGBA")
        glass = glass.filter(ImageFilter.GaussianBlur(8))
        glass = Image.alpha_composite(
            glass, Image.new("RGBA", glass.size, (0, 0, 0, self.DARKEN_ALPHA)))
        glass = Image.alpha_composite(
            glass, Image.new("RGBA", glass.size, (255, 255, 255, self.TINT_ALPHA)))
        ImageDraw.Draw(glass).rectangle(
            [1, 1, glass.width - 2, glass.height - 2],
            outline=(255, 255, 255, 220), width=3)

        self._glass_photo = ImageTk.PhotoImage(glass)
        self.itemconfigure(self._glass_item, image=self._glass_photo)
        self._draw()

    def set_trackers(self, trackers, select_id=None):
        self._trackers = {row[0]: row for row in trackers}
        self._order = [row[0] for row in trackers]
        self._selected_id = None
        self._offset = 0
        if select_id in self._trackers:
            self.select(select_id)
        else:
            self._draw()

    def select(self, tracker_id):
        if tracker_id not in self._trackers:
            return
        self._selected_id = tracker_id
        self._scroll_to(self._order.index(tracker_id))
        self._draw()

    def move_selection(self, step):
        if not self._order:
            return
        if self._selected_id is None:
            index = 0 if step > 0 else len(self._order) - 1
        else:
            index = self._order.index(self._selected_id) + step
            index = max(0, min(len(self._order) - 1, index))
        self.select(self._order[index])

    def scroll(self, event):
        direction = -1 if event.delta > 0 else 1
        self._offset = self._clamp(self._offset + direction * self.SCROLL_STEP)
        self._draw()

    def _row_height(self):
        return (self.ROW_PADDING * 2 + 3
                + self.name_font.metrics("linespace")
                + 2 * self.detail_font.metrics("linespace"))

    def _max_offset(self):
        count = len(self._order)
        content = self.PADDING * 2 + count * self._row_height() + (count - 1) * self.GAP
        return max(0, content - self.winfo_height())

    def _clamp(self, offset):
        return max(0, min(offset, self._max_offset()))

    def _scroll_to(self, index):
        step = self._row_height() + self.GAP
        top = self.PADDING + index * step
        bottom = top + self._row_height()
        view = self.winfo_height()
        if top - self.PADDING < self._offset:
            self._offset = top - self.PADDING
        elif bottom + self.PADDING > self._offset + view:
            self._offset = bottom + self.PADDING - view
        self._offset = self._clamp(self._offset)

    def _index_at(self, y):
        step = self._row_height() + self.GAP
        position = y + self._offset - self.PADDING
        if position < 0:
            return None
        index, within = divmod(position, step)
        if within >= step - self.GAP or index >= len(self._order):
            return None
        return int(index)

    def _on_click(self, event):
        index = self._index_at(event.y)
        if index is not None:
            self.select(self._order[index])

    def _on_double_click(self, event):
        index = self._index_at(event.y)
        if index is not None:
            self.select(self._order[index])
            self.on_open()

    def _draw(self):
        self.delete("content")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 40 or height < 40:
            return

        if not self._order:
            self._text(width // 2, height // 2,
                       "No trackers yet.\nCreate one with START TRACKING.",
                       MUTED, self.detail_font, anchor="center", justify="center")
            return

        self._offset = self._clamp(self._offset)
        step = self._row_height() + self.GAP
        first = max(0, self._offset // step)
        last = min(len(self._order), (self._offset + height) // step + 1)
        for index in range(first, last):
            top = self.PADDING + index * step - self._offset
            self._draw_row(self._trackers[self._order[index]], top, width)

    def _draw_row(self, tracker, top, width):
        tracker_id, name, month, budget, created_at, spent, _count = tracker
        plan = Budget(budget)
        left, right = self.PADDING, width - self.PADDING
        row_height = self._row_height()

        selected = tracker_id == self._selected_id
        self.create_image(
            left, top, anchor="nw", tags="content",
            image=self._card_fill(right - left, row_height,
                                  self.HIGHLIGHT_ALPHA if selected else self.CARD_ALPHA))
        self.create_rectangle(
            left, top, right, top + row_height, tags="content",
            outline=WHITE if selected else self.BORDER_COLOR,
            width=3 if selected else 2)

        text_left, text_right = left + 14, right - 14
        name_h = self.name_font.metrics("linespace")
        detail_h = self.detail_font.metrics("linespace")
        y = top + self.ROW_PADDING

        self._text(text_right, y + name_h - detail_h, created_at, MUTED,
                   self.detail_font, anchor="ne")
        title_room = text_right - text_left - self.detail_font.measure(created_at) - 20
        self._text(text_left, y, self._fit(name, self.name_font, title_room),
                   WHITE, self.name_font)

        y += name_h + 3
        info = f"{month}  |  Budget: {format_money(budget)}  |  Spent: {format_money(spent)}"
        room = text_right - text_left
        self._text(text_left, y, self._fit(info, self.detail_font, room),
                   MUTED, self.detail_font)

        y += detail_h
        self._text(text_left, y, self._fit(plan.message(spent), self.detail_font, room),
                   STATUS_COLORS[plan.status(spent)], self.detail_font)

    def _text(self, x, y, text, color, font, anchor="nw", **options):
        for dx, dy, fill in ((2, 2, self.SHADOW), (0, 0, color)):
            self.create_text(x + dx, y + dy, text=text, fill=fill, font=font,
                             anchor=anchor, tags="content", **options)

    def _card_fill(self, width, height, alpha):
        key = (width, height, alpha)
        if key not in self._fills:
            self._fills[key] = ImageTk.PhotoImage(
                Image.new("RGBA", (width, height), (255, 255, 255, alpha)))
        return self._fills[key]

    @staticmethod
    def _fit(text, font, max_width):
        if font.measure(text) <= max_width:
            return text
        while text and font.measure(text + "...") > max_width:
            text = text[:-1]
        return text + "..."


class EditTrackerDialog(tk.Toplevel):

    BG = "#0b1620"
    WIDTH = 560

    def __init__(self, parent, font_family, tracker, on_saved):
        super().__init__(parent, bg=self.BG)
        self.tracker_id, name, month, budget, _created, self.spent, _count = tracker
        self.on_saved = on_saved

        self.title("Edit Tracker")
        self.resizable(False, False)
        self.transient(parent)

        self._fonts = {
            "title": tkfont.Font(family=font_family, size=-34),
            "label": tkfont.Font(family=font_family, size=-22),
            "entry": tkfont.Font(family=font_family, size=-24),
            "button": tkfont.Font(family=font_family, size=-24),
        }

        tk.Label(self, text="EDIT TRACKER", font=self._fonts["title"],
                 fg=WHITE, bg=self.BG).pack(pady=(22, 8))

        self.entries = {}
        fields = (
            ("name", "TRACKER NAME", name),
            ("month", "MONTH", month),
            ("budget", "BUDGET", f"{budget:.2f}"),
        )
        for key, label, value in fields:
            self.entries[key] = self._add_field(label, value)

        buttons = tk.Frame(self, bg=self.BG)
        buttons.pack(pady=24)
        for text, command in (("SAVE", self._save), ("CANCEL", self.destroy)):
            tk.Button(
                buttons, text=text, command=command, font=self._fonts["button"],
                fg=WHITE, bg="#1d4f6e", activebackground="#46d2ff",
                activeforeground="#05202e", relief="flat", bd=0,
                padx=30, pady=8, cursor="hand2"
            ).pack(side="left", padx=10)

        self.bind("<Escape>", lambda event: self.destroy())
        self._center()
        self.wait_visibility()
        self.grab_set()
        self.entries["name"].focus_set()
        self.entries["name"].select_range(0, "end")

    def _add_field(self, label, value):
        tk.Label(self, text=label, font=self._fonts["label"], fg=WHITE,
                 bg=self.BG, anchor="w").pack(fill="x", padx=30, pady=(10, 0))
        entry = tk.Entry(
            self, font=self._fonts["entry"], bg="#0f1e2b", fg=WHITE,
            insertbackground=WHITE, relief="flat", bd=8, highlightthickness=2,
            highlightbackground=WHITE, highlightcolor="#46d2ff"
        )
        entry.insert(0, value)
        entry.pack(fill="x", padx=30)
        entry.bind("<Return>", lambda event: self._save())
        return entry

    def _center(self):
        self.update_idletasks()
        height = self.winfo_reqheight()
        x = (self.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{self.WIDTH}x{height}+{x}+{y}")

    def _save(self):
        name = self.entries["name"].get().strip()
        month = self.entries["month"].get().strip()

        if not name or not month:
            messagebox.showerror("Missing information",
                                 "Please fill in the name and month.", parent=self)
            return

        try:
            budget = parse_money(self.entries["budget"].get(), "budget")
        except ValidationError as error:
            messagebox.showerror("Invalid budget", str(error), parent=self)
            return

        over = Budget(budget).overspent_by(self.spent)
        if over > 0 and not messagebox.askyesno(
            "Budget below spending",
            f"{format_money(self.spent)} is already spent, so this tracker "
            f"will be over budget by {format_money(over)}.\n\nSave anyway?",
            parent=self,
        ):
            return

        database.update_tracker_details(self.tracker_id, name, month, budget)
        self.destroy()
        self.on_saved(self.tracker_id)


class LoadTrackerWindow(tk.Toplevel):

    TITLE_BOX = (0.30, 0.04, 0.40, 0.11)
    LIST_BOX = (0.25, 0.18, 0.50, 0.52)

    RESIZE_DEBOUNCE_MS = 80

    def __init__(self, parent, background_path, font_path,
                 on_close=None, on_open=None):
        super().__init__(parent)
        self.on_close = on_close
        self.on_open = on_open or (lambda tracker_id: None)

        self.title("IPONOMIKS - Load Trackers")
        self.attributes("-fullscreen", True)

        self.background = ImageBackground(background_path)
        self.text_renderer = GlowTextRenderer(font_path)
        self.font_family = FontLoader.load(font_path)
        self.name_font = tkfont.Font(family="Arial", weight="bold", size=-30)
        self.detail_font = tkfont.Font(family="Arial", weight="bold", size=-21)

        self.background_photo = None
        self._last_size = (0, 0)
        self._resize_job = None

        self.background_label = tk.Label(self, bd=0, highlightthickness=0)
        self.background_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.title_panel = GlassPanel(
            self, self.text_renderer, *self.TITLE_BOX,
            [{"text": "SELECT TRACKER", "rely": 0.34, "size": 0.45, "align": "center"}]
        )

        self.tracker_list = TrackerList(
            self, self.name_font, self.detail_font, on_open=self._open_selected
        )
        left, top, width, height = self.LIST_BOX
        self.tracker_list.place(relx=left, rely=top, relwidth=width, relheight=height)

        self.back_button = GlassButton(
            self, "BACK", self._handle_close, self.text_renderer,
            0.12, 0.08, 0.16, 0.08
        )
        self.open_button = GlassButton(
            self, "OPEN TRACKER", self._open_selected, self.text_renderer,
            0.500, 0.77, 0.500, 0.07
        )
        self.edit_button = GlassButton(
            self, "EDIT TRACKER", self._edit_selected, self.text_renderer,
            0.375, 0.86, 0.245, 0.07
        )
        self.delete_button = GlassButton(
            self, "DELETE", self._delete_selected, self.text_renderer,
            0.625, 0.86, 0.245, 0.07
        )

        self._reload()

        self.bind("<Configure>", self._on_resize)
        self.bind("<MouseWheel>", self.tracker_list.scroll)
        self.bind("<Up>", lambda event: self.tracker_list.move_selection(-1))
        self.bind("<Down>", lambda event: self.tracker_list.move_selection(1))
        self.bind("<Return>", lambda event: self._open_selected())
        self.bind("<Delete>", lambda event: self._delete_selected())
        self.bind("<Escape>", lambda event: self._handle_close())
        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.focus_set()

    def _on_resize(self, event=None):
        if event is not None and event.widget is not self:
            return
        if event is not None and (event.width, event.height) == self._last_size:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(self.RESIZE_DEBOUNCE_MS, self._render)

    def _render(self):
        self._resize_job = None
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 10 or height < 10 or (width, height) == self._last_size:
            return
        self._last_size = (width, height)

        frame = self.background.fit_to_size(width, height)
        self.background_photo = ImageTk.PhotoImage(frame)
        self.background_label.configure(image=self.background_photo)

        self.name_font.configure(size=-max(16, int(height * 0.030)))
        self.detail_font.configure(size=-max(12, int(height * 0.021)))

        self.title_panel.render(frame, width, height)
        self.tracker_list.set_backdrop(frame)
        for button in (self.back_button, self.open_button,
                       self.edit_button, self.delete_button):
            button.render(frame, width, height)

    def _reload(self, select_id=None):
        self.tracker_list.set_trackers(database.get_tracker_overview(), select_id)

    def _require_selection(self):
        tracker = self.tracker_list.selected
        if tracker is None:
            messagebox.showinfo("No tracker selected",
                                "Please select a tracker from the list first.",
                                parent=self)
        return tracker

    def _open_selected(self):
        tracker = self._require_selection()
        if tracker is not None:
            self.on_open(tracker[0])

    def _edit_selected(self):
        tracker = self._require_selection()
        if tracker is not None:
            EditTrackerDialog(self, self.font_family, tracker, on_saved=self._reload)

    def _delete_selected(self):
        tracker = self._require_selection()
        if tracker is None:
            return

        tracker_id, name, *_, count = tracker
        confirmed = messagebox.askyesno(
            "Delete tracker",
            f'Delete "{name}"?\n\nIts {count} expense(s) will be deleted too. '
            "This cannot be undone.",
            icon="warning", default="no", parent=self,
        )
        if confirmed:
            database.delete_tracker(tracker_id)
            self._reload()

    def _handle_close(self):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None
        self.destroy()
        if self.on_close:
            self.on_close()