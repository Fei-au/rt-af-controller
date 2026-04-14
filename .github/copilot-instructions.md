# Copilot Instructions

This repository is a Windows-only Python/Tkinter automation app for Auction Flex store-credit add and deduct flows.

## Project Rules
- Keep `main.py` as the entrypoint. It loads `.env` before importing UI code, so preserve that import order when touching environment-dependent modules.
- Treat `tkinter_gui.py` as the UI orchestration layer and keep long-running work on worker threads.
- Treat `auto_add_credit.py` and `auto_deduct_credit.py` as automation flow modules. Keep changes focused and avoid rewriting the interaction sequence unless required.
- Keep shared behavior in `auto_common.py`, OCR/image logic in `tools.py`, and CSV/GraphQL helpers in `service.py`.
- Preserve stop handling with `set_stop_checker()` and `check_stop_requested()` so users can interrupt long-running automations safely.
- Keep CSV schemas stable. `service.py` may add or update `status`, `details`, and `errors` columns; do not rename or remove existing headers without updating all callers.
- Be careful with environment variables. `LOG_BACK` is required for GraphQL calls when online, and OCR may need `TESSERACT_CMD` or a valid PATH fallback on Windows.
- Prefer minimal, targeted edits. Do not refactor unrelated automation steps, OCR heuristics, or GUI layout unless the task requires it.
- Avoid modifying generated artifacts such as `build/` or packaging outputs unless explicitly requested.
- Keep dependencies and packaging aligned with the existing `requirements.txt` and PyInstaller workflow documented in `README.md`.

## Coding Conventions
- Use `pathlib.Path` for file paths.
- Preserve existing Python style and keep changes small.
- Prefer defensive error handling around file access, OCR, and external tool integration.
- Update `README.md` if you add a new required environment variable, file format, or run step.
