import tkinter as tk
from dotenv import load_dotenv




def main_app():
    root = tk.Tk()
    load_dotenv(".env")
    from tkinter_gui import StoreCreditApp
    StoreCreditApp(root)
    root.mainloop()


if __name__ == "__main__":
    main_app()
