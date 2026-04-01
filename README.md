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
pyinstaller --onefile --windowed --icon "images/app.ico" --noconsole --name="SC Controller" --add-data=".env;." main.py
```


Add new store credit
1. when leave the invoice page
Use ocr to check the modal, and do the action

1. When enter the invoice page
Check if there is the apply payment button, 
if it is, tab different times

Deduct store credit
1. Tab twice to skip focus on buttons
2. Check if there is "apply credit" button first, if not write to error
3. shift tab once back to "apply credit"
4. click
   1. (remaining credit < amount due)If the "apply credit" disappear, then all credit has been applied, this invoice has done and return
   2. (multiple remaining credit) If the model pop up "Would you like to return the bidder's remainting deposit(s)", 
      1. click right
      2. click NO
      3. focus remain on the button, back step 4,click the "apply credit" button again
   3. (credit > amount due) Top left corner pop up a printer model
      1. click esc (remove the pop up)
      2. click right (now at the "Would you like to return the " model, move to No)
      3. click No
   
   1. check top left corner if "printer" exist
   2. check center "Would you like to return the " exist
   3. check if "apply credit" exist
