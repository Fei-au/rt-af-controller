# rt-af-controller

## Get coordinates on screen
```cmd
python -m pyautogui
```

## Pack the app
```cmd
pyinstaller --onefile --windowed --icon "images/app.ico" --noconsole --name="SC Controller" --add-data=".env;." main.py
```