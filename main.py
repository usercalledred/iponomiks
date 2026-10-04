import tkinter as tk

import database
from ui.mainmenu import MainMenu
from ui.start import TrackerWindow
from ui.tracker import TrackerDashboard

MENU_BACKGROUND = r"C:\Iponomiks\backgrounds\mainmenubg.jpg"
TRACKER_BACKGROUND = r"C:\Iponomiks\backgrounds\trackerbg.jpg"
DASHBOARD_BACKGROUND = TRACKER_BACKGROUND  # change this to use a different image
FONT_PATH = r"C:\Users\User\AppData\Local\Microsoft\Windows\Fonts\MINECRAFT.TTF"

class App:

    def __init__(self):
        database.init_db()

        self.root = tk.Tk()
        self.root.title("IPONOMIKS")
        self.root.attributes("-fullscreen", True)

        self.create_window = None

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

    def _show_menu(self):
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)

    def open_saved_trackers(self):
        print("Load Trackers clicked")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()