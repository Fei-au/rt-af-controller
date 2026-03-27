# rt-af-controller

## Get coordinates on screen
```cmd
python -m pyautogui
```

1. prepare dedicated csv file
- target_auction_id
- bidcard_num
- lot
- payment_type
- amount
- invoice_number

2. read csv file
3. check whether the record has been put in or not, (add a field in the model)
   1. If the record is inconsistent with the one on file, then add the notice log 
4. after add the record, update it on both file and db
   
