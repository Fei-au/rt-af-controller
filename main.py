import sys
import tkinter as tk
from pathlib import Path

from dotenv import load_dotenv


def _load_env_file():
    candidates = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / ".env")

    candidates.append(Path(__file__).resolve().parent / ".env")
    candidates.append(Path.cwd() / ".env")

    for env_path in candidates:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            return

    load_dotenv()


def main_app():
    _load_env_file()
    root = tk.Tk()
    from tkinter_gui import StoreCreditApp
    StoreCreditApp(root)
    root.mainloop()


if __name__ == "__main__":
    main_app()
