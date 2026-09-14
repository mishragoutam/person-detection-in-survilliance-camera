import os
import sys
import subprocess
from pathlib import Path

# Prepare dependency paths before importing UI libs
_PROJECT_DIR = Path(__file__).parent
def _prepare_dependency_paths():
    candidates = [
        _PROJECT_DIR / ".venv312" / "Lib" / "site-packages",
        Path(sys.prefix) / "Lib" / "site-packages",
    ]
    python_root = Path.home() / "AppData" / "Local" / "Programs" / "Python"
    if python_root.exists():
        candidates.extend(python_root.glob("Python*/Lib/site-packages"))

    for candidate in candidates:
        if (candidate / "customtkinter").exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))

_prepare_dependency_paths()

try:
    import customtkinter as ctk
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "CustomTkinter is installed, but this Python interpreter cannot see it. "
        "Select the Python 3.12 interpreter that contains customtkinter in VS Code."
    ) from exc

# Import extracted UI components and pages
from ui.theme import COLORS
from ui.widgets import Sidebar
from ui.dashboard import DashboardPage
from ui.cameras import LiveSurveillancePage
from ui.analytics import AnalyzeVideoPage, TrainingMetricsPage, AnalyticsPage
from ui.personnel import WhitelistPage
from ui.alerts import EvidencePage
from ui.events import EventsPage
from ui.settings import ConfigPage
from ui.system import SystemPage
from ui.login import LoginPage
from ui.records import LoginRecordsPage
from storage.database import EventStore

# ======================================================================
# main.py (entry point)
# ======================================================================
PAGE_REGISTRY = {
    "dashboard": DashboardPage,
    "cameras": LiveSurveillancePage,
    "analyze": AnalyzeVideoPage,
    "personnel": WhitelistPage,
    "alerts": EvidencePage,
    "events": EventsPage,
    "analytics": AnalyticsPage,
    "settings": ConfigPage,
    "system": SystemPage,
    "login": LoginPage,
    "records": LoginRecordsPage,
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SIH26187 — Border Surveillance Command Center")
        self.geometry("1280x800")
        self.minsize(1024, 680)
        self.configure(fg_color=COLORS["bg_base"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, on_navigate=self.navigate, app=self)
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg_base"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)

        self.event_store = EventStore(_PROJECT_DIR / "events.db")
        self.current_user = None
        self.login_time = None

        self._pages = {}
        self._current_key = None
        self.navigate("login")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_timer()

    def update_timer(self):
        import time
        if self.login_time is not None:
            elapsed = int(time.time() - self.login_time)
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                timer_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            else:
                timer_str = f"{mins:02d}:{secs:02d}"
            if hasattr(self.sidebar, 'timer_label'):
                self.sidebar.timer_label.configure(text=timer_str)
        self.after(1000, self.update_timer)

    def on_login_success(self):
        import time
        self.login_time = time.time()
        self.sidebar.update_visibility()
        self.navigate("dashboard")

    def on_closing(self):
        try:
            if "cameras" in self._pages:
                self._pages["cameras"]._stop_stream()
        except Exception:
            pass
        for page in self._pages.values():
            store = getattr(page, "store", None)
            if store is not None:
                try:
                    store.close()
                except Exception:
                    pass
        self.destroy()

    def navigate(self, key: str):
        if key not in PAGE_REGISTRY:
            return
            
        if key == "login":
            self.sidebar.grid_forget()
            self.content.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)
        else:
            self.sidebar.grid(row=0, column=0, sticky="nsw")
            self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)

        if self._current_key is not None:
            self._pages[self._current_key].pack_forget()

        if key not in self._pages:
            page_cls = PAGE_REGISTRY[key]
            self._pages[key] = page_cls(self.content, app=self)

        self._pages[key].pack(fill="both", expand=True)
        self._current_key = key
        
        if key != "login":
            self.sidebar.set_active(key)
        
        if key == "records":
            self._pages[key].refresh_records()


if __name__ == "__main__":
    app = App()
    app.mainloop()
