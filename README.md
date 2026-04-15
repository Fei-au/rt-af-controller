# rt-af-controller

## Dependencies:
1. TesseractOCR
   ```cmd
   winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements
   ```
2. requirements

## Get coordinates on screen
```cmd
python -m pyautogui
```

## Pack the app
```cmd
pyinstaller --onefile --windowed --icon "images/app.ico" --noconsole --name="SC Controller" --add-data=".env;." --hidden-import="pytesseract" main.py
```


At the end of the request, upload the csv file
- in log_back, add an api to do so

