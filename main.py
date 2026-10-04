import os
import tkinter as tk
from pathlib import Path

import database
from ui.dashboard import TrackerDashboard
from ui.load import LoadTrackerWindow
from ui.mainmenu import MainMenu
from ui.start import TrackerWindow

BASE_DIR = Path(__file__).resolve().parent
BACKGROUND_DIR = BASE_DIR / "backgrounds"

MENU_BACKGROUND = str(BACKGROUND_DIR / "mainmenubg.jpg")
TRACKER_BACKGROUND = str(BACKGROUND_DIR / "trackerbg.jpg")
LOAD_BACKGROUND = str(BACKGROUND_DIR / "loadbg.png")
DASHBOARD_BACKGROUND = TRACKER_BACKGROUND


def find_font():
    folders = [
        BASE_DIR / "fonts",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    ]
    for folder in folders:
        if folder.is_dir():
            for file in sorted(folder.iterdir()):
                if "minecraft" in file.name.lower() and file.suffix.lower() in (".ttf", ".otf"):
                    return str(file)

    print("WARNING: Minecraft font not found. Put MINECRAFT.TTF in "
          f"{folders[0]} to use it. Falling back to Arial.")
    return str(folders[0] / "MINECRAFT.TTF")


FONT_PATH = find_font()


class App:

    def __init__(self):
        database.init_db()

        self.root = tk.Tk()
        self.root.title("IPONOMIKS")
        self.root.attributes("-fullscreen", True)

        self.create_window = None
        self.load_window = None

        self.menu = MainMenu(
            self.root,
            background_path=MENU_BACKGROUND,
            font_path=FONT_PATH,
            on_start=self.open_tracker,
            on_load=self.open_saved_trackers,
            on_exit=self.root.destroy
        )

    def open_tracker(self):
        self.root.withdraw()
        self.create_window = TrackerWindow(
            self.root,
            background_path=TRACKER_BACKGROUND,
            font_path=FONT_PATH,
            on_close=self._show_menu,
            on_proceed=self.open_dashboard
        )

    def open_dashboard(self, name, month, budget):
        if self.create_window is not None:
            self.create_window.destroy()
            self.create_window = None

        TrackerDashboard(
            self.root,
            background_path=DASHBOARD_BACKGROUND,
            font_path=FONT_PATH,
            name=name,
            month=month,
            budget=budget,
            on_close=self._show_menu,
            on_exit=self.root.destroy
        )

    def open_saved_trackers(self):
        self.root.withdraw()
        self.load_window = LoadTrackerWindow(
            self.root,
            background_path=LOAD_BACKGROUND,
            font_path=FONT_PATH,
            on_close=self._show_menu,
            on_open=self.open_saved_dashboard
        )

    def open_saved_dashboard(self, tracker_id):
        tracker = database.get_tracker(tracker_id)
        if tracker is None:
            return

        if self.load_window is not None:
            self.load_window.destroy()
            self.load_window = None

        _, name, month, budget, _ = tracker
        TrackerDashboard(
            self.root,
            background_path=DASHBOARD_BACKGROUND,
            font_path=FONT_PATH,
            name=name,
            month=month,
            budget=budget,
            tracker_id=tracker_id,
            expenses=database.get_tracker_expenses(tracker_id),
            on_close=self.open_saved_trackers,
            on_exit=self.root.destroy
        )

    def _show_menu(self):
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()