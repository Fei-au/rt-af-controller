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

## Rules
1. When enter the invoice page, click the bottom right print button to focus it in the following automation

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
   
   4. check top left corner if "printer" exist
   5. check center "Would you like to return the " exist
   6. check if "apply credit" exist


At the end of the request, upload the csv file
- in log_back, add an api to do so

deduct credit
1. at log_back, add a method export a csv file includes everyting
2. import csv
3. do the loop
4. ? if there are more than one credit, which one will be use? the older one?
   1. double check the logic which one has been used, like the last deduct amount is smaller than the credit
   2. add a field to record current credit left
5. update the refunds status on db

Alert

1. Have an overall result output to somewhere, log the task result. And if it failed at certain record, send emails

1. In add credit, after filling the "Store credit-12345", information, copy paste to check if it's really at the step, if not, discard this one 