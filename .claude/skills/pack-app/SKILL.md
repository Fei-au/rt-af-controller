---
name: pack-app
description: Build the SC Controller Windows executable with PyInstaller. Use when the user asks to "pack the app", "build the app", "build the exe", "create installer", or otherwise produce the distributable. Activates the project virtualenv first, then runs the documented PyInstaller command. Output lands in dist/SC Controller.exe.
---

# Pack the SC Controller app

This project ships as a single-file Windows executable built with PyInstaller. Always work from the project root (the directory containing `main.py`).

## Steps

### 1. Activate the Python virtual environment

Look for a venv in this order, and use the **first one that exists**:

1. `.\venv\Scripts\Activate.ps1` (project-local venv)
2. `.\.venv\Scripts\Activate.ps1` (project-local hidden venv)
3. `..\venv\Scripts\Activate.ps1` (sibling to the worktree, when running inside `.claude/worktrees/<name>/`)
4. `..\..\..\venv\Scripts\Activate.ps1` (project root venv when working from a worktree three levels deep)

PowerShell example:

```powershell
.\venv\Scripts\Activate.ps1
```

If none of those paths exist, **stop and ask the user where their venv is** rather than installing PyInstaller into a system Python — the system interpreter at `D:\pyhton\python.exe` does not have the project dependencies.

After activation, verify with:

```powershell
python -c "import sys; print(sys.executable)"
python -c "import PyInstaller, pyautogui, pytesseract" 
```

If `PyInstaller` is missing inside the venv, ask the user before installing it.

### 2. Confirm `.env` exists

The PyInstaller command bundles `.env` via `--add-data`. If `.env` is missing the build will fail. Run:

```powershell
Test-Path .env
```

If it returns `False`, stop and tell the user — do not invent a `.env`.

### 3. Run the build

Use the exact command from `CLAUDE.md`:

```powershell
pyinstaller --onefile --windowed --icon "images/app.ico" --noconsole --name="SC Controller" --add-data=".env;." --hidden-import="pytesseract" main.py
```

Notes:
- `--add-data=".env;."` uses a semicolon on Windows (colon on Linux/macOS — but this app is Windows-only).
- Run with `run_in_background: true` if you expect a long build; otherwise allow up to ~5 minutes.
- PyInstaller writes intermediate artifacts to `build/` and the final binary to `dist/SC Controller.exe`. The spec file `SC Controller.spec` is regenerated each run.

### 4. Verify and report

After the build finishes:

```powershell
Test-Path "dist\SC Controller.exe"
Get-Item "dist\SC Controller.exe" | Select-Object FullName, Length, LastWriteTime
```

Report the full path, file size (MB), and modification time to the user. If the build failed, surface the **last 30 lines** of PyInstaller output so the user can see the actual error — don't summarize or guess.

## Things to avoid

- Do not install PyInstaller or any other dependency into the system Python without asking.
- Do not modify `requirements.txt`, `main.py`, or any source file as part of "packing" — packing is a build step, not a code change.
- Do not delete `build/` or `dist/` from prior runs unless the user asks; PyInstaller overwrites them safely.
- Do not commit `build/`, `dist/`, or `*.spec` — they are build outputs.
