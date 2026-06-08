# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows-only Python/Tkinter desktop app that automates Auction Flex store-credit **add** and **deduct** workflows. It drives the Auction Flex GUI via PyAutoGUI, reads form state with Tesseract OCR, processes batch records from CSV files, and optionally calls a GraphQL backend and uploads results to S3.

## Setup

**System dependency — install once:**
```cmd
winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements
```

**Python dependencies:**
```cmd
pip install -r requirements.txt
```

**Environment — create a `.env` file:**
- `LOG_BACK` (required when online): GraphQL/S3 backend URL, default `http://127.0.0.1:8008`
- `TESSERACT_CMD` (optional): full path to `tesseract.exe` if not on PATH
- `IS_ONLINE` (optional): set to `TRUE` to enable GraphQL mutations and S3 upload; default `FALSE`

## Run & Build

```cmd
# Run in development
python main.py

# Get screen coordinates (for debugging automation positions)
python -m pyautogui

# Package as single-file Windows executable
pyinstaller --onefile --windowed --icon "images/app.ico" --noconsole --name="SC Controller" --add-data=".env;." --add-data="sounds;sounds" --hidden-import="pytesseract" main.py
```

There are no automated tests; validation is done by running the app and inspecting live logs and output CSVs.

## Architecture

### Layer responsibilities

| File | Role |
|---|---|
| `main.py` | Entry point. **Must** load `.env` before any other import — preserve this order. |
| `tkinter_gui.py` | UI orchestration. Spawns daemon worker threads; drains a `queue.Queue` every 100 ms to update the log widget. Enforces mutual exclusion (only one add or deduct process at a time). |
| `service.py` | Data layer. Reads/validates CSV records, executes GraphQL queries/mutations via `gql`, uploads files to S3. |
| `auto_add_credit.py` | Add-credit automation flow. Called from a worker thread; drives the Auction Flex GUI step-by-step. |
| `auto_deduct_credit.py` | Deduct-credit automation flow. Similar structure; groups records by bidcard number. |
| `auto_common.py` | Shared automation utilities: screen coordinate constants (as 0–1 percentage ratios), window activation, keyboard/clipboard helpers, stop-event handling (`set_stop_checker` / `check_stop_requested`), and shared exceptions (`StopRequested`, `MulStepError`). |
| `tools.py` | OCR and image processing. `extract_center_words_from_screen()` captures a screenshot, crops by percentage coordinates, preprocesses with OpenCV, and runs Tesseract. |

### Threading model

The Tkinter mainloop runs on the main thread. Each automation process (add / deduct) runs on its own `threading.Thread` (daemon). A `threading.Event` signals graceful stop; automation loops call `check_stop_requested()` at each step. Logging flows back to the UI via `queue.Queue` — never write directly to the Tkinter widget from a worker thread.

### Data flow

1. User picks a CSV → worker thread calls `pre_processing()` (add) or `processing()` (deduct).
2. `service.py` parses and validates the CSV; auto-appends `status`, `details`, `errors` columns if absent.
3. The automation loop iterates rows: GUI interaction → OCR validation → optional GraphQL mutation → write result back to CSV.
4. When `IS_ONLINE=TRUE`, results CSV is uploaded to S3 at the end.

### CSV schemas

**Add-credit CSV required headers:** `refund_id`, `target_auction_id`, `bidcard_num`, `lot`, `payment_type`, `amount`, `invoice_number`

**Deduct-credit CSV required headers:** `auction_id`, `bidcard_num`, `invoice_number`, `sc_id`, `sc_invoice_number`

Both: `status` (`1` = success, `-1` = error), `details`, `errors` are written by the app. Do not rename or remove existing headers without updating all callers.

## Key Rules

- `main.py` loads `.env` before importing UI code — preserve this import order when adding environment-dependent modules.
- Keep long-running work on worker threads; never block the Tkinter mainloop.
- Preserve `set_stop_checker()` / `check_stop_requested()` in automation loops so users can interrupt safely.
- Screen coordinates in `auto_common.py` are normalised 0–1 ratios, not pixels. Use `python -m pyautogui` to discover new coordinates.
- Use `pathlib.Path` for file paths. Prefer defensive error handling around file I/O, OCR, and external tool calls.
- Prefer minimal, targeted edits. Do not rewrite automation sequences or OCR heuristics unless the task explicitly requires it.
- Do not modify `build/` or PyInstaller outputs unless asked.
- Update `README.md` if you add a new required environment variable, file format, or run step.
