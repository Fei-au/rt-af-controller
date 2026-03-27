import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import automation


class StoreCreditApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Store Credit Controller")
        self._set_window_icon()
        self.root.geometry("860x520")
        self.root.minsize(760, 460)

        self.worker_thread = None
        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()

        self.csv_path_var = tk.StringVar(value=getattr(automation, "CSV_FILE_PATH", ""))

        self._build_ui()
        self.root.after(100, self._drain_log_queue)

    def _set_window_icon(self):
        base_dir = Path(__file__).resolve().parent
        ico_path = base_dir / "images" / "app.ico"
        png_path = base_dir / "images" / "app.png"

        try:
            if ico_path.exists():
                self.root.iconbitmap(default=str(ico_path))
                return

            if png_path.exists():
                self._window_icon = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self._window_icon)
        except tk.TclError:
            # Keep app startup resilient if icon file is invalid or unsupported.
            pass

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        file_row = ttk.Frame(frame)
        file_row.pack(fill=tk.X)

        ttk.Label(file_row, text="CSV file:").pack(side=tk.LEFT, padx=(0, 8))
        self.file_entry = ttk.Entry(file_row, textvariable=self.csv_path_var)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(file_row, text="Browse", command=self._browse_file).pack(side=tk.LEFT, padx=(8, 0))

        action_row = ttk.Frame(frame)
        action_row.pack(fill=tk.X, pady=(12, 8))

        self.start_btn = ttk.Button(action_row, text="Start", command=self._start_process)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(action_row, text="Stop", command=self._stop_process, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(frame, text="Logs:").pack(anchor=tk.W)

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.csv_path_var.set(path)
            self._queue_log(f"Selected CSV file: {path}")

    def _start_process(self):
        csv_path = self.csv_path_var.get().strip()
        if not csv_path:
            messagebox.showerror("Missing file", "Please select a CSV file first.")
            return

        file_path = Path(csv_path)
        if not file_path.exists() or file_path.suffix.lower() != ".csv":
            messagebox.showerror("Invalid file", "Please choose a valid CSV file.")
            return

        if self.worker_thread and self.worker_thread.is_alive():
            self._queue_log("Process is already running.")
            return

        self.stop_event.clear()
        automation.CSV_FILE_PATH = csv_path

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self._queue_log("Starting process...")

        self.worker_thread = threading.Thread(
            target=self._run_main_process,
            args=(csv_path,),
            daemon=True,
        )
        self.worker_thread.start()

    def _stop_process(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self._queue_log("Stop requested. Waiting for current record to finish...")

    def _run_main_process(self, csv_path):
        try:
            result = automation.pre_processing(
                csv_path,
                log_fn=self._queue_log,
                should_stop_fn=self.stop_event.is_set,
            )
            self._queue_log(str(result))
        except Exception as exc:
            self._queue_log(f"Error: {exc}")
        finally:
            self.root.after(0, self._on_worker_done)

    def _on_worker_done(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.stop_event.clear()
        self._queue_log("Process finished.")

    def _queue_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def _drain_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        self.root.after(100, self._drain_log_queue)
