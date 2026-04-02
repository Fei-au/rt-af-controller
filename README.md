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



In the invoice
for invoice in invoices:
   while: true
      words = get_words()
      due_amount = get_due_amount_from_words()
      apply_deposit: 
      if apply_deposit:
         click
      else:
         break
      multi_credit_modal = get()
      cur_credit_larger_than_due_amount_modal = get()

      if multi_credit_modal:
         dissmiss_multi_credit_modal
         mark_the_first_credit_as_complete # invoices got from api should order by created_at asc
      elif cur_credit_larger_than_due_amount_modal:


      

   