import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from PIL import ImageTk

import database
import records
from logic.budget import Budget, BudgetStatus, format_money
from logic.expenses import CATEGORIES, ExpenseLog
from logic.summary import build_summary
from logic.validation import ValidationError
from ui.mainmenu import GlassButton, GlowTextRenderer, ImageBackground
from ui.start import FontLoader


class Theme:

    PANEL_OUTER, PANEL_EDGE, PANEL_BG = "#0b0d10", "#5d6673", "#252a31"
    FIELD_BG, ROW_ALT = "#15181d", "#1d2127"
    TEXT, MUTED, GOLD, SELECT = "#ffffff", "#b7c0cc", "#ffd24a", "#3f7d4a"
    GREEN, ORANGE, RED = "#4cc65a", "#f39c2f", "#e04848"
    BTN, BTN_HOVER = "#6d7580", "#8894a3"
    ADD, ADD_HOVER = "#3f8f3a", "#54ac4d"
    DANGER, DANGER_HOVER = "#94403f", "#b45654"

    STATUS_COLORS = {BudgetStatus.SAFE: GREEN, BudgetStatus.WARNING: ORANGE,
                     BudgetStatus.OVER: RED}
    CATEGORY_COLORS = dict(zip(CATEGORIES, [
        "#e8a23a", "#4aa3df", "#9b6fd6", "#d65a8a", "#c98a5a", "#3fd0c9",
        "#e6d94a", "#e26a6a", "#7bd35a", "#f07fb0", "#5ad6a0", "#9aa5b1"]))


def shift_color(color, amount):
    """Lighten (+) or darken (-) a #rrggbb color."""
    r, g, b = (max(0, min(255, int(color[i:i + 2], 16) + amount)) for i in (1, 3, 5))
    return f"#{r:02x}{g:02x}{b:02x}"


class MinecraftButton(tk.Button):

    def __init__(self, parent, text, command, font, color=Theme.BTN, hover=Theme.BTN_HOVER):
        super().__init__(parent, text=text, command=command, font=font, bg=color,
                         fg=Theme.TEXT, activebackground=hover, activeforeground=Theme.TEXT,
                         relief="raised", bd=4, highlightthickness=0, cursor="hand2")
        self.bind("<Enter>", lambda e: self.configure(bg=hover))
        self.bind("<Leave>", lambda e: self.configure(bg=color))


class TrackerDashboard(tk.Toplevel):

    PLAQUE = (0.34, 0.02, 0.32, 0.115)
    BAR = (0.04, 0.155, 0.92, 0.10)
    FORM = (0.04, 0.28, 0.27, 0.68)
    LIST = (0.325, 0.28, 0.355, 0.68)
    SUMMARY = (0.695, 0.28, 0.265, 0.68)

    FONT_PX = {"title": (44, 22), "heading": (24, 14), "body": (19, 12),
               "small": (15, 10), "stat": (22, 13), "bar": (28, 14)}
    RESIZE_DEBOUNCE_MS = 80

    def __init__(self, parent, background_path, font_path, name, month, budget,
                 expenses=None, tracker_id=None, on_close=None, on_exit=None):
        super().__init__(parent)
        self.on_close = on_close
        self.on_exit = on_exit or parent.destroy

        self.tracker_name, self.month = name, month
        self.budget = Budget(budget)
        self.log = ExpenseLog(expenses)
        self.tracker_id = tracker_id
        self.saved = tracker_id is not None  

        self.title("IPONOMIKS - Dashboard")
        self.attributes("-fullscreen", True)

        self.background = ImageBackground(background_path)
        self.text_renderer = GlowTextRenderer(font_path)
        self.background_photo = None

        family = FontLoader.load(font_path)
        self.fonts = {key: tkfont.Font(family=family, size=-px[0])
                      for key, px in self.FONT_PX.items()}

        self._size = (0, 0)
        self._resize_job = None
        self.summary = build_summary(self.budget, self.log)
        self._was_over = self.summary.status == BudgetStatus.OVER

        self._setup_styles()
        self.background_label = tk.Label(self, bd=0, highlightthickness=0)
        self.background_label.place(x=0, y=0, relwidth=1, relheight=1)

        self._build_plaque()
        self._build_bar()
        self._build_form()
        self._build_list()
        self._build_summary()

        self.glass_buttons = [
            GlassButton(self, "BACK", self._handle_back, self.text_renderer,
                        0.12, 0.08, 0.16, 0.08),
            GlassButton(self, "SAVE", self.save, self.text_renderer,
                        0.74, 0.08, 0.14, 0.08),
            GlassButton(self, "EXIT", self._handle_exit, self.text_renderer,
                        0.89, 0.08, 0.14, 0.08),
        ]

        self.bind("<Configure>", self._on_resize)
        self.bind("<Control-s>", lambda event: self.save())
        self.protocol("WM_DELETE_WINDOW", self._handle_back)

        self._refresh()
        self.description_entry.focus_set()


    def _setup_styles(self):
        T, style = Theme, ttk.Style(self)
        style.theme_use("clam")
        self.style = style

        style.configure("MC.Treeview", background=T.FIELD_BG, fieldbackground=T.FIELD_BG,
                        foreground=T.TEXT, borderwidth=0, bordercolor=T.PANEL_BG,
                        lightcolor=T.PANEL_BG, darkcolor=T.PANEL_BG, font=self.fonts["body"])
        style.map("MC.Treeview", background=[("selected", T.SELECT)],
                  foreground=[("selected", T.TEXT)])
        style.configure("MC.Treeview.Heading", background="#3a414b", foreground=T.GOLD,
                        relief="flat", font=self.fonts["small"])
        style.map("MC.Treeview.Heading", background=[("active", "#4a535f")])

        style.configure("MC.Vertical.TScrollbar", background=T.BTN, troughcolor=T.FIELD_BG,
                        bordercolor=T.PANEL_OUTER, arrowcolor=T.TEXT,
                        lightcolor=T.BTN, darkcolor=T.BTN)
        style.map("MC.Vertical.TScrollbar", background=[("active", T.BTN_HOVER)])

        style.configure("MC.TCombobox", fieldbackground=T.FIELD_BG, background=T.BTN,
                        foreground=T.TEXT, arrowcolor=T.TEXT, bordercolor=T.TEXT,
                        lightcolor=T.FIELD_BG, darkcolor=T.FIELD_BG,
                        selectbackground=T.FIELD_BG, selectforeground=T.TEXT)
        readonly = lambda value: [("readonly", value)]
        style.map("MC.TCombobox", fieldbackground=readonly(T.FIELD_BG),
                  foreground=readonly(T.TEXT), selectbackground=readonly(T.FIELD_BG),
                  selectforeground=readonly(T.TEXT))

        
        for option, value in {"background": T.FIELD_BG, "foreground": T.TEXT,
                              "selectBackground": T.SELECT, "selectForeground": T.TEXT,
                              "font": str(self.fonts["body"])}.items():
            self.option_add(f"*TCombobox*Listbox.{option}", value)


    def _make_panel(self, geometry):
        relx, rely, relw, relh = geometry
        outer = tk.Frame(self, bg=Theme.PANEL_OUTER)
        outer.place(relx=relx, rely=rely, relwidth=relw, relheight=relh, anchor="nw")
        edge = tk.Frame(outer, bg=Theme.PANEL_EDGE)
        edge.pack(fill="both", expand=True, padx=2, pady=2)
        body = tk.Frame(edge, bg=Theme.PANEL_BG)
        body.pack(fill="both", expand=True, padx=3, pady=3)
        return body

    def _label(self, parent, text="", font="small", fg=Theme.MUTED, **kwargs):
        return tk.Label(parent, text=text, font=self.fonts[font], fg=fg,
                        bg=Theme.PANEL_BG, **kwargs)

    def _make_entry(self, parent):
        return tk.Entry(parent, font=self.fonts["body"], bg=Theme.FIELD_BG, fg=Theme.TEXT,
                        insertbackground=Theme.TEXT, relief="flat", bd=6,
                        highlightthickness=2, highlightbackground=Theme.TEXT,
                        highlightcolor="#46d2ff")

    def _heading(self, parent, text, **grid):
        self._label(parent, text, "heading", Theme.GOLD).grid(sticky="w", padx=16, **grid)

    def _build_plaque(self):
        body = self._make_panel(self.PLAQUE)
        self.title_label = tk.Label(body, text=self.tracker_name.upper(),
                                    font=self.fonts["title"], fg=Theme.GOLD, bg=Theme.PANEL_BG)
        self.title_label.pack(fill="x", expand=True)

        info = tk.Frame(body, bg=Theme.PANEL_BG)
        info.pack(side="bottom", pady=(0, 4))
        self._label(info, f"{self.month.upper()} - BUDGET "
                          f"{format_money(self.budget.total)}").pack(side="left")
        self.saved_label = self._label(info)
        self.saved_label.pack(side="left", padx=(16, 0))

    def _build_bar(self):
        self.bar_canvas = tk.Canvas(self._make_panel(self.BAR), bg=Theme.PANEL_BG,
                                    highlightthickness=0, bd=0)
        self.bar_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.bar_canvas.bind("<Configure>", lambda event: self._draw_bar())

    def _build_form(self):
        body = self._make_panel(self.FORM)
        body.columnconfigure(0, weight=1)
        self._heading(body, "ADD EXPENSE", row=0, column=0, pady=(14, 8))

        self.category_var = tk.StringVar(value=CATEGORIES[0])
        self.category_box = ttk.Combobox(body, textvariable=self.category_var,
                                         values=CATEGORIES, state="readonly",
                                         style="MC.TCombobox", font=self.fonts["body"])
        self.description_entry = self._make_entry(body)
        self.amount_entry = self._make_entry(body)
        self._entry_widgets = [self.description_entry, self.amount_entry]

        for row, (text, widget) in enumerate([("CATEGORY", self.category_box),
                                              ("DESCRIPTION", self.description_entry),
                                              ("AMOUNT", self.amount_entry)]):
            self._label(body, text).grid(row=row * 2 + 1, column=0, sticky="w",
                                         padx=16, pady=(12, 2))
            widget.grid(row=row * 2 + 2, column=0, padx=16, sticky="ew")

        self.description_entry.bind("<Return>", lambda e: self.amount_entry.focus_set())
        self.amount_entry.bind("<Return>", lambda e: self._add_expense())

        font, T = self.fonts["body"], Theme
        buttons = [  # row, text, command, colors, pady, ipady
            (7, "ADD EXPENSE", self._add_expense, (T.ADD, T.ADD_HOVER), (20, 6), 8),
            (9, "DELETE SELECTED", self._delete_selected, (T.DANGER, T.DANGER_HOVER), (6, 6), 4),
            (10, "CLEAR ALL", self._clear_all, (T.BTN, T.BTN_HOVER), (0, 10), 4),
        ]
        for row, text, command, colors, pady, ipady in buttons:
            MinecraftButton(body, text, command, font, *colors).grid(
                row=row, column=0, padx=16, pady=pady, sticky="ew", ipady=ipady)
        body.rowconfigure(8, weight=1)  # flexible spacer

        self.hint_label = self._label(body, "ENTER = ADD    DEL = REMOVE    CTRL+S = SAVE",
                                      justify="center")
        self.hint_label.grid(row=11, column=0, padx=10, pady=(0, 12))

    def _build_list(self):
        body = self._make_panel(self.LIST)
        header = tk.Frame(body, bg=Theme.PANEL_BG)
        header.pack(fill="x", padx=16, pady=(14, 8))
        self._label(header, "EXPENSES", "heading", Theme.GOLD).pack(side="left")
        self.count_label = self._label(header)
        self.count_label.pack(side="right")

        frame = tk.Frame(body, bg=Theme.PANEL_BG)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(frame, columns=("no", "category", "description", "amount"),
                                 show="headings", style="MC.Treeview", selectmode="extended")
        for column, text, anchor in (("no", "#", "center"), ("category", "CATEGORY", "w"),
                                     ("description", "DESCRIPTION", "w"),
                                     ("amount", "AMOUNT", "e")):
            self.tree.heading(column, text=text, anchor=anchor)
            self.tree.column(column, anchor=anchor, stretch=False)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview,
                                  style="MC.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("even", background=Theme.FIELD_BG)
        self.tree.tag_configure("odd", background=Theme.ROW_ALT)
        self.tree.bind("<Configure>", self._fit_columns)
        self.tree.bind("<Delete>", lambda event: self._delete_selected())

    def _build_summary(self):
        body = self._make_panel(self.SUMMARY)
        body.columnconfigure(1, weight=1)
        self._heading(body, "SUMMARY", row=0, column=0, columnspan=2, pady=(14, 8))

        rows = [("budget", "BUDGET", "stat"), ("spent", "SPENT", "stat"),
                ("remaining", "REMAINING", "stat"), ("used", "USED", "body"),
                ("entries", "ENTRIES", "body"), ("average", "AVERAGE", "body"),
                ("highest", "HIGHEST", "body"), ("top", "TOP CATEGORY", "body")]
        self.stat_labels = {}
        for index, (key, title, font) in enumerate(rows, start=1):
            self._label(body, title).grid(row=index, column=0, sticky="w", padx=(16, 6), pady=3)
            self.stat_labels[key] = self._label(body, "", font, Theme.TEXT)
            self.stat_labels[key].grid(row=index, column=1, sticky="e", padx=(6, 16), pady=3)

        row = len(rows) + 1
        self.message_label = self._label(body, "", "small", Theme.TEXT, justify="left", anchor="w")
        self.message_label.grid(row=row, column=0, columnspan=2, sticky="ew",
                                padx=16, pady=(12, 8))
        self._heading(body, "BY CATEGORY", row=row + 1, column=0, columnspan=2, pady=(6, 4))

        self.category_canvas = tk.Canvas(body, bg=Theme.PANEL_BG, highlightthickness=0, bd=0)
        self.category_canvas.grid(row=row + 2, column=0, columnspan=2, sticky="nsew",
                                  padx=12, pady=(0, 12))
        body.rowconfigure(row + 2, weight=1)
        self.category_canvas.bind("<Configure>", lambda event: self._draw_categories())


    def _on_resize(self, event=None):
        if event is not None and (event.widget is not self
                                  or (event.width, event.height) == self._size):
            return
        self._cancel_jobs()
        self._resize_job = self.after(self.RESIZE_DEBOUNCE_MS, self._render)

    def _render(self):
        self._resize_job = None
        width, height = self.winfo_width(), self.winfo_height()
        if width < 10 or height < 10 or (width, height) == self._size:
            return
        self._size = (width, height)

        frame = self.background.fit_to_size(width, height)
        self.background_photo = ImageTk.PhotoImage(frame)
        self.background_label.configure(image=self.background_photo)

        self._apply_scale(width, height)
        for button in self.glass_buttons:
            button.render(frame, width, height)

    def _apply_scale(self, width, height):
        for key, (base, minimum) in self.FONT_PX.items():
            self.fonts[key].configure(size=-max(minimum, int(base * height / 1080)))
        self.style.configure("MC.Treeview", rowheight=max(22, int(height * 0.045)))

        pad = max(4, int(height * 0.007))
        for widget in (*self._entry_widgets, self.category_box):
            widget.grid_configure(ipady=pad)

        self.message_label.configure(wraplength=max(120, int(width * self.SUMMARY[2]) - 44))
        self.hint_label.configure(wraplength=max(120, int(width * self.FORM[2]) - 30))

        # Shrink long tracker names until they fit the title plaque
        font, text = self.fonts["title"], self.title_label.cget("text")
        available = int(width * self.PLAQUE[2]) - 40
        while font.measure(text) > available and abs(font.cget("size")) > 16:
            font.configure(size=font.cget("size") + 2)  # sizes are negative pixels

        self.after_idle(lambda: (self._draw_bar(), self._draw_categories()))

    def _fit_columns(self, event):
        for column, share in {"no": 0.08, "category": 0.31,
                              "description": 0.34, "amount": 0.27}.items():
            self.tree.column(column, width=int(max(event.width, 100) * share))


    def _draw_bar(self):
        canvas = self.bar_canvas
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 20 or height < 10:
            return
        canvas.delete("all")

        summary = self.summary
        color = Theme.STATUS_COLORS[summary.status]
        x0, y0, x1, y1 = 3, 3, width - 3, height - 3
        canvas.create_rectangle(x0, y0, x1, y1, fill=Theme.FIELD_BG, outline="")

        fill_x = x0 + (x1 - x0) * self.budget.bar_fraction(summary.spent)
        if fill_x > x0:
            band = max(2, int((y1 - y0) * 0.18))
            canvas.create_rectangle(x0, y0, fill_x, y1, fill=color, outline="")
            canvas.create_rectangle(x0, y0, fill_x, y0 + band, fill=shift_color(color, 45), outline="")
            canvas.create_rectangle(x0, y1 - band, fill_x, y1, fill=shift_color(color, -55), outline="")

        for i in range(1, 10):  # ten pixel-style segments, like a Minecraft XP bar
            x = x0 + (x1 - x0) * i / 10
            canvas.create_line(x, y0, x, y1, fill=Theme.PANEL_OUTER, width=2)
        canvas.create_rectangle(x0, y0, x1, y1, outline=Theme.PANEL_OUTER, width=3)

        if summary.status == BudgetStatus.OVER:
            first = f"OVER BUDGET BY {format_money(self.budget.overspent_by(summary.spent))}"
        else:
            first = f"{format_money(summary.spent)} / {format_money(summary.budget)}"
        text = f"{first}  -  {summary.percent_used:.0f}% USED"

        font, cx, cy = self.fonts["bar"], width // 2, height // 2
        half_w, half_h = font.measure(text) / 2 + 22, font.metrics("linespace") / 2 + 4
        canvas.create_rectangle(cx - half_w, cy - half_h, cx + half_w, cy + half_h,
                                fill=Theme.PANEL_OUTER, outline=Theme.PANEL_EDGE, width=2)
        canvas.create_text(cx, cy, text=text, font=font, fill=Theme.TEXT)

    def _draw_categories(self):
        canvas = self.category_canvas
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 40 or height < 20:
            return
        canvas.delete("all")

        rows, font = self.summary.by_category, self.fonts["small"]
        if not rows:
            canvas.create_text(width / 2, height / 2, text="NO EXPENSES YET",
                               font=font, fill=Theme.MUTED)
            return

        line = font.metrics("linespace")
        bar_h = max(8, int(line * 0.6))
        row_h = line + bar_h + 14
        capacity = max(1, height // row_h)
        shown = rows if len(rows) <= capacity else rows[:max(1, capacity - 1)]

        y = 4
        for category, total, share in shown:
            color = Theme.CATEGORY_COLORS.get(category, Theme.CATEGORY_COLORS["Others"])
            canvas.create_text(4, y, text=category.upper(), anchor="nw", font=font, fill=Theme.TEXT)
            canvas.create_text(width - 4, y, text=f"{total:,.2f}  {share:.0f}%",
                               anchor="ne", font=font, fill=Theme.MUTED)
            top = y + line + 4
            canvas.create_rectangle(4, top, width - 4, top + bar_h, fill=Theme.FIELD_BG, outline="")
            canvas.create_rectangle(4, top, 4 + (width - 8) * share / 100, top + bar_h,
                                    fill=color, outline="")
            canvas.create_rectangle(4, top, width - 4, top + bar_h,
                                    outline=Theme.PANEL_OUTER, width=2)
            y += row_h

        if len(rows) > len(shown):
            canvas.create_text(4, y, text=f"+{len(rows) - len(shown)} MORE", anchor="nw",
                               font=font, fill=Theme.MUTED)


    def _refresh(self):
        self.summary = s = build_summary(self.budget, self.log)
        color = Theme.STATUS_COLORS[s.status]

        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(self.log.items):
            self.tree.insert("", "end", iid=str(index), tags=("odd" if index % 2 else "even",),
                             values=(index + 1, item.category, item.description or "-",
                                     f"{item.amount:,.2f}"))
        self.count_label.configure(text=f"{s.count} ITEM{'' if s.count == 1 else 'S'}")

        values = {
            "budget": format_money(s.budget), "spent": format_money(s.spent),
            "remaining": format_money(s.remaining), "used": f"{s.percent_used:.1f}%",
            "entries": str(s.count), "average": format_money(s.average),
            "highest": format_money(s.highest.amount) if s.highest else "-",
            "top": s.top_category.upper() if s.top_category else "-",
        }
        for key, text in values.items():
            self.stat_labels[key].configure(text=text)
        for key in ("remaining", "used"):
            self.stat_labels[key].configure(fg=color)
        self.message_label.configure(text=s.message, fg=color)

        self._update_saved_label()
        self._draw_bar()
        self._draw_categories()

    def _update_saved_label(self):
        text, color = ("[SAVED]", Theme.GREEN) if self.saved else ("[UNSAVED]", Theme.ORANGE)
        self.saved_label.configure(text=text, fg=color)


    def _add_expense(self):
        try:
            self.log.add(self.category_var.get(), self.description_entry.get(),
                         self.amount_entry.get())
        except ValidationError as error:
            messagebox.showerror("Invalid expense", str(error), parent=self)
            {"category": self.category_box, "description": self.description_entry
             }.get(error.field, self.amount_entry).focus_set()
            return

        self.saved = False
        self.description_entry.delete(0, "end")
        self.amount_entry.delete(0, "end")
        self.description_entry.focus_set()
        self._refresh()
        self.tree.see(str(len(self.log) - 1))

        now_over = self.summary.status == BudgetStatus.OVER
        if now_over and not self._was_over:
            over = format_money(self.budget.overspent_by(self.summary.spent))
            messagebox.showwarning("Over budget!", f"You are over your budget by {over}.",
                                   parent=self)
        self._was_over = now_over

    def _remove(self, indexes=None):
        """Remove the given expenses (or all of them) and update the screen."""
        self.log.remove(indexes) if indexes is not None else self.log.clear()
        self.saved = False
        self._refresh()
        self._was_over = self.summary.status == BudgetStatus.OVER

    def _delete_selected(self):
        selected = [int(iid) for iid in self.tree.selection()]
        if selected:
            self._remove(selected)
        else:
            messagebox.showinfo("Nothing selected", "Click an expense in the list first.",
                                parent=self)

    def _clear_all(self):
        if len(self.log) and messagebox.askyesno(
                "Clear all expenses", "Remove every expense from this tracker?", parent=self):
            self._remove()


    def save(self):
        """Save to the database and to records. Returns True on success."""
        items, total = self.log.as_tuples(), self.budget.total
        try:
            if self.tracker_id is None:
                self.tracker_id = database.save_tracker(
                    self.tracker_name, self.month, total, items)
            else:
                database.update_tracker(
                    self.tracker_id, self.tracker_name, self.month, total, items)
        except Exception as error:
            messagebox.showerror("Save failed",
                                 f"The tracker could not be saved:\n{error}", parent=self)
            return False

        try:
            records.save_record(self.tracker_id, self.tracker_name, self.month, total, items)
        except Exception as error:
            messagebox.showwarning(
                "Records not updated",
                f"Saved to the database, but the records file failed:\n{error}", parent=self)

        self.saved = True
        self._update_saved_label()
        return True

    def _confirm_leave(self):
        """True if it is fine to leave (saved, or the user chose not to save)."""
        if self.saved:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved tracker",
            f'"{self.tracker_name}" has not been saved.\n\n'
            "Do you want to save it before leaving?", parent=self)
        if answer is None:      # Cancel: stay on the dashboard
            return False
        return self.save() if answer else True   # Yes: leave only if saved; No: just leave

    def _cancel_jobs(self):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None

    def _handle_back(self):
        if self._confirm_leave():
            self._cancel_jobs()
            self.destroy()
            if self.on_close:
                self.on_close()

    def _handle_exit(self):
        if self._confirm_leave():
            self._cancel_jobs()
            self.on_exit()