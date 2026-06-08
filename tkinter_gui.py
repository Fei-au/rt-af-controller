import queue
import threading
import tkinter as tk
import winsound
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import auto_add_credit
import auto_deduct_credit
from auto_common import IS_ONLINE, APP_VERSION
from service import upload_file_to_s3
from tools import _resolve_resource_path


class StoreCreditApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Store Credit Controller")
        self._set_window_icon()
        self.root.geometry("860x520")
        self.root.minsize(560, 460)

        self.add_worker_thread = None
        self.add_stop_event = threading.Event()
        self.deduct_worker_thread = None
        self.deduct_stop_event = threading.Event()
        self.log_queue = queue.Queue()

        self.add_csv_path_var = tk.StringVar(value=getattr(auto_add_credit, "CSV_FILE_PATH", ""))
        self.deduct_csv_path_var = tk.StringVar(value=getattr(auto_deduct_credit, "CSV_FILE_PATH", ""))

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

        add_file_row = ttk.Frame(frame)
        add_file_row.pack(fill=tk.X)

        ttk.Label(add_file_row, text="Store credit adding file:").pack(side=tk.LEFT, padx=(0, 8))
        self.add_file_entry = ttk.Entry(add_file_row, textvariable=self.add_csv_path_var)
        self.add_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            add_file_row,
            text="Browse",
            command=lambda: self._browse_file(self.add_csv_path_var, "Store credit adding file"),
        ).pack(side=tk.LEFT, padx=(8, 0))

        add_action_row = ttk.Frame(frame)
        add_action_row.pack(fill=tk.X, pady=(10, 0))

        self.add_start_btn = ttk.Button(add_action_row, text="Start Add", command=self._start_add_process)
        self.add_start_btn.pack(side=tk.LEFT)

        self.add_stop_btn = ttk.Button(add_action_row, text="Stop Add", command=self._stop_add_process, state=tk.DISABLED)
        self.add_stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 14))

        deduct_file_row = ttk.Frame(frame)
        deduct_file_row.pack(fill=tk.X)

        ttk.Label(deduct_file_row, text="Store credit deducting file:").pack(side=tk.LEFT, padx=(0, 8))
        self.deduct_file_entry = ttk.Entry(deduct_file_row, textvariable=self.deduct_csv_path_var)
        self.deduct_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            deduct_file_row,
            text="Browse",
            command=lambda: self._browse_file(self.deduct_csv_path_var, "Store credit deducting file"),
        ).pack(side=tk.LEFT, padx=(8, 0))

        deduct_action_row = ttk.Frame(frame)
        deduct_action_row.pack(fill=tk.X, pady=(10, 0))

        self.deduct_start_btn = ttk.Button(deduct_action_row, text="Start Deduct", command=self._start_deduct_process)
        self.deduct_start_btn.pack(side=tk.LEFT)

        self.deduct_stop_btn = ttk.Button(deduct_action_row, text="Stop Deduct", command=self._stop_deduct_process, state=tk.DISABLED)
        self.deduct_stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 14))

        log_header_row = ttk.Frame(frame)
        log_header_row.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(log_header_row, text="Logs:").pack(side=tk.LEFT)
        self.stop_alarm_btn = ttk.Button(
            log_header_row,
            text="Stop Alarm",
            command=self._stop_alarm,
            state=tk.DISABLED,
        )
        self.stop_alarm_btn.pack(side=tk.RIGHT)

        log_frame = ttk.Frame(frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _browse_file(self, target_var, label):
        path = filedialog.askopenfilename(
            title=f"Select {label}",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            target_var.set(path)
            if target_var is self.add_csv_path_var:
                self._queue_add_log(f"Selected {label}: {path}")
            else:
                self._queue_deduct_log(f"Selected {label}: {path}")

    def _start_add_process(self):
        if self.deduct_worker_thread and self.deduct_worker_thread.is_alive():
            messagebox.showwarning(
                "Process already running",
                "Deduct process is currently running. Please wait for it to finish first.",
            )
            self._queue_add_log("Cannot start add process while deduct process is running.")
            return

        csv_path = self.add_csv_path_var.get().strip()
        if not csv_path:
            messagebox.showerror("Missing file", "Please select the store credit adding file first.")
            return

        file_path = Path(csv_path)
        if not file_path.exists() or file_path.suffix.lower() != ".csv":
            messagebox.showerror("Invalid file", "Please choose a valid CSV file.")
            return

        if self.add_worker_thread and self.add_worker_thread.is_alive():
            self._queue_add_log("Process is already running.")
            return

        self._stop_alarm()
        self.add_stop_event.clear()
        auto_add_credit.CSV_FILE_PATH = csv_path

        self.add_start_btn.configure(state=tk.DISABLED)
        self.add_stop_btn.configure(state=tk.NORMAL)
        self.deduct_start_btn.configure(state=tk.DISABLED)
        self._queue_add_log("Starting process...")

        self.add_worker_thread = threading.Thread(
            target=self._run_add_process,
            args=(csv_path,),
            daemon=True,
        )
        self.add_worker_thread.start()

    def _stop_add_process(self):
        if self.add_worker_thread and self.add_worker_thread.is_alive():
            self.add_stop_event.set()
            self.add_stop_btn.configure(state=tk.DISABLED)
            self._queue_add_log("Stop requested. Attempting to stop immediately...")

    def _start_deduct_process(self):
        if self.add_worker_thread and self.add_worker_thread.is_alive():
            messagebox.showwarning(
                "Process already running",
                "Add process is currently running. Please wait for it to finish first.",
            )
            self._queue_deduct_log("Cannot start deduct process while add process is running.")
            return

        csv_path = self.deduct_csv_path_var.get().strip()
        if not csv_path:
            messagebox.showerror("Missing file", "Please select the store credit deducting file first.")
            return

        file_path = Path(csv_path)
        if not file_path.exists() or file_path.suffix.lower() != ".csv":
            messagebox.showerror("Invalid file", "Please choose a valid CSV file.")
            return

        if self.deduct_worker_thread and self.deduct_worker_thread.is_alive():
            self._queue_deduct_log("Deduct process is already running.")
            return
        
        self._stop_alarm()
        self.deduct_stop_event.clear()
        auto_deduct_credit.CSV_FILE_PATH = csv_path

        self.deduct_start_btn.configure(state=tk.DISABLED)
        self.deduct_stop_btn.configure(state=tk.NORMAL)
        self.add_start_btn.configure(state=tk.DISABLED)
        self._queue_deduct_log("Starting deduct process...")

        self.deduct_worker_thread = threading.Thread(
            target=self._run_deduct_process,
            args=(csv_path,),
            daemon=True,
        )
        self.deduct_worker_thread.start()

    def _stop_deduct_process(self):
        if self.deduct_worker_thread and self.deduct_worker_thread.is_alive():
            self.deduct_stop_event.set()
            self.deduct_stop_btn.configure(state=tk.DISABLED)
            self._queue_deduct_log("Deduct stop requested. Attempting to stop immediately...")

    def _run_add_process(self, csv_path):
        try:
            result = auto_add_credit.pre_processing(
                csv_path,
                log_fn=self._queue_add_log,
                should_stop_fn=self.add_stop_event.is_set,
            )
            self._queue_add_log(str(result))
        except Exception as exc:
            self._queue_add_log(f"Error: {exc}")
        finally:
            self.root.after(0, self._on_worker_done)

    def _run_deduct_process(self, csv_path):
        try:
            result = auto_deduct_credit.processing(
                csv_path,
                log_fn=self._queue_deduct_log,
                should_stop_fn=self.deduct_stop_event.is_set,
            )
            self._queue_deduct_log(str(result))
        except Exception as exc:
            self._queue_deduct_log(f"Error: {exc}")
        finally:
            self.root.after(0, self._on_deduct_worker_done)

    def _on_worker_done(self):
        was_stopped = self.add_stop_event.is_set()
        self.add_start_btn.configure(state=tk.NORMAL)
        self.add_stop_btn.configure(state=tk.DISABLED)
        if not (self.deduct_worker_thread and self.deduct_worker_thread.is_alive()):
            self.deduct_start_btn.configure(state=tk.NORMAL)
        self.add_stop_event.clear()
        self._queue_add_log("Process finished.")
        self._save_and_upload_logs(self.add_csv_path_var.get(), prefix="add")
        if not was_stopped:
            self._start_alarm()

    def _on_deduct_worker_done(self):
        was_stopped = self.deduct_stop_event.is_set()
        self.deduct_start_btn.configure(state=tk.NORMAL)
        self.deduct_stop_btn.configure(state=tk.DISABLED)
        if not (self.add_worker_thread and self.add_worker_thread.is_alive()):
            self.add_start_btn.configure(state=tk.NORMAL)
        self.deduct_stop_event.clear()
        self._queue_deduct_log("Deduct process finished.")
        self._save_and_upload_logs(self.deduct_csv_path_var.get(), prefix="deduct")
        if not was_stopped:
            self._start_alarm()

    def _start_alarm(self):
        alarm_path = _resolve_resource_path("sounds/alarm.wav")
        try:
            winsound.PlaySound(
                str(alarm_path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
        except Exception:
            pass
        self.stop_alarm_btn.configure(state=tk.NORMAL)

    def _stop_alarm(self):
        """Stop the looping alarm sound and disable the 'Stop Alarm' button."""
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        self.stop_alarm_btn.configure(state=tk.DISABLED)

    def _save_and_upload_logs(self, csv_path, prefix):
        """
        Persist the current log widget contents to a timestamped .log file and
        (when IS_ONLINE) upload both the log file and the processed CSV to S3
        on a background thread. Runs on the Tkinter main thread; drains pending
        log queue first so the file captures every "Process finished." style
        message.
        """
        # Drain anything still queued so the saved file is up to date.
        self._drain_log_queue_now()

        log_text = self.log_text.get("1.0", tk.END).rstrip()
        if not log_text:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = (csv_path or "").strip()
        if csv_path:
            base_dir = Path(csv_path).resolve().parent
            stem = Path(csv_path).stem
            log_file_path = base_dir / f"{stem}_{prefix}_{timestamp}.log"
        else:
            log_file_path = Path(__file__).resolve().parent / f"{prefix}_{timestamp}.log"

        try:
            log_file_path.write_text(log_text, encoding="utf-8")
        except OSError as exc:
            self._append_log_immediately(f"[v{APP_VERSION}] [{prefix.upper()}] Failed to write log file: {exc}")
            return

        self._append_log_immediately(f"[v{APP_VERSION}] [{prefix.upper()}] Logs saved to {log_file_path}")

        if not IS_ONLINE:
            return

        threading.Thread(
            target=self._upload_artifacts,
            args=(log_file_path, csv_path, prefix),
            daemon=True,
        ).start()

    def _upload_artifacts(self, log_file_path, csv_path, prefix):
        log_fn = self._queue_add_log if prefix == "add" else self._queue_deduct_log

        try:
            upload_file_to_s3(str(log_file_path))
            log_fn(f"Log uploaded: {log_file_path.name}")
        except Exception as exc:
            log_fn(f"Log upload failed: {exc}")

        if csv_path and Path(csv_path).exists():
            try:
                upload_file_to_s3(csv_path)
                log_fn(f"CSV uploaded: {Path(csv_path).name}")
            except Exception as exc:
                log_fn(f"CSV upload failed: {exc}")

    def _drain_log_queue_now(self):
        """Synchronously empty the queue into the widget. Main thread only."""
        while not self.log_queue.empty():
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

    def _append_log_immediately(self, message):
        """Write a timestamped line straight to the widget. Main thread only."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _queue_add_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put(f"[{timestamp}] [v{APP_VERSION}] [ADD] {message}")

    def _queue_deduct_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put(f"[{timestamp}] [v{APP_VERSION}] [DEDUCT] {message}")

    def _drain_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        self.root.after(100, self._drain_log_queue)

