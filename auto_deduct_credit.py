from webbrowser import get

import pygetwindow as gw
import pyautogui
import time
import pandas as pd
from pynput.keyboard import Key, Controller
from pathlib import Path
from auto_common import AUCTION_FLEX_CLOUD_TITLE, INVOICE_PAID_FULL_MODAL_COORDS, IS_ONLINE, PRINTER_POPUP_COORDS, RETURN_REMAININGS_MODAL_COORDS, CREDIT_DETAILS_COORDS, activate_window, check_stop_requested, copy, get_target_window, paste, select_item_by_name, select_item_by_tabbing, INVOIE_SUMMARY_BLOCK_COORDS, set_stop_checker
from service import read_deduct_records_from_csv
from tools import extract_center_words_from_screen

keyboard = Controller()

CSV_FILE_PATH = ""
def processing(csv_file_path, log_fn=print, should_stop_fn=None):
	file_path = Path(csv_file_path)
	if not file_path.exists():
		raise FileNotFoundError(f"CSV file not found: {file_path}")
	set_stop_checker(should_stop_fn)

	try:
		auction_id, records = read_deduct_records_from_csv(csv_file_path)
		log_fn(f"Loaded {len(records)} deduct records from {csv_file_path}")

		df = pd.read_csv(csv_file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)

		# Activate cloud window
		window = get_target_window(AUCTION_FLEX_CLOUD_TITLE)
		activate_window(window)
		time.sleep(1)

		# Open auction flex software
		pyautogui.write(str("auc"), interval=0.1)
		pyautogui.press("enter")
		time.sleep(5)
  
		# Open autction list
		pyautogui.press("enter")
		time.sleep(1.5)
		# select auction id in modal
		select_item_by_name(
			auction_id,
			confirm_with_enter=True,
		)
		time.sleep(2)

		# select checkout bidders and click enter
		select_item_by_tabbing(7)
		time.sleep(2)

		# selct invoices and click enter
		select_item_by_tabbing(10)
		time.sleep(2)

		# select list of invoices
		select_item_by_tabbing(5, confirm_with_enter=False)
		time.sleep(1)

		for bidcard_num, deduct_records in records.items():
			check_stop_requested()
   
			if any(deduct_record['status'] != "" for deduct_record in deduct_records):
				log_fn(f"Skipping bidcard {bidcard_num} as it has already been processed.")
				continue

			results = auto_processing(bidcard_num, deduct_records, log_fn)
	
			for result in results:
				print(result)
				df.at[result["row_offset"], "status"] = result.get("status")
				df.at[result["row_offset"], "details"] = result.get("details")
				df.at[result["row_offset"], "errors"] = result.get("errors")
				if result["status"] == '1' and IS_ONLINE:
					# TODO: update the record in db as completed with completed time
					log_fn(f"Success: {result['details']}")
			df.to_csv(csv_file_path, index=False)
			time.sleep(2)
			back_to_invoice_list()
   
		return f"Deduct process completed for {len(records)} records."
	finally:
		set_stop_checker(None)
  
def back_to_invoice_list():
    # back to invoice edit page and esc to exit
    keyboard.press(Key.esc)
    time.sleep(0.5)
    keyboard.press(Key.esc)
    time.sleep(1)
    
    # if the invoice is unfully paid invoice, there will be a confirmation popup, click enter to confirm. Other wise, open the invoice detail again
    words = extract_center_words_from_screen(**INVOICE_PAID_FULL_MODAL_COORDS)
    has_unpaid_invoice_text = "This invoice has not been paid in full".lower() in " ".join(words).lower()
    if has_unpaid_invoice_text:
        keyboard.press(Key.enter)
        time.sleep(3)

'''
Status codes:
-1: Failed with error (check details for error message)
1: Success
2: only a partial credit was deducted
'''

def has_apply_deposit_button():
	words = extract_center_words_from_screen(**INVOIE_SUMMARY_BLOCK_COORDS)
	print("OCR-detected words in invoice summary block:", words)
	summary_sentence = " ".join(words)
	return "apply deposit" in summary_sentence.lower() or "appty deposit" in summary_sentence.lower()

def is_credit_larger_than_due_amount():
	words = extract_center_words_from_screen(**PRINTER_POPUP_COORDS)
	print("OCR-detected words in printer popup:", words)
	summary_sentence = " ".join(words)
	return "printer" in summary_sentence.lower()

def is_multi_credit_modal():
	words = extract_center_words_from_screen(**RETURN_REMAININGS_MODAL_COORDS)
	print("OCR-detected words in return remainings modal:", words)
	summary_sentence = " ".join(words)
	return "would you like to return the buyer" in summary_sentence.lower()

def auto_processing(bidcard_num: int, deduct_records: list[dict], log_fn=print) -> str:
	# input bid card number and click enter
	select_item_by_name(
		bidcard_num,
		confirm_with_enter=True,
	)
	time.sleep(4)

	all_deducted_count = 0
	has_partial_deduct = False
	# check if there is "apply deposit" button
	if not has_apply_deposit_button():
		return [{
			'status': '-1', 
			'details': f"No credit to deduct for bidcard {bidcard_num}, invoice: {deduct_records[0]['invoice_number']}",
			'row_offset': deduct_records[0]['row_offset']
		}]
	print(f"Found 'Apply Deposit' button for bidcard {bidcard_num}, starting deduction...")
 
	# focus and click appy deposit button
	select_item_by_tabbing(3, confirm_with_enter=False, reverse=True)
 
	# deduct all credit
	while True:
		check_stop_requested()
  
		select_item_by_tabbing(1, confirm_with_enter=True, reverse=True)
		time.sleep(2)
  
		multi_credit_modal = False
		if is_credit_larger_than_due_amount():
			# dismiss the model
			select_item_by_tabbing(3, confirm_with_enter=False)
			time.sleep(0.5)
			pyautogui.press("right")
			time.sleep(0.5)
			pyautogui.press("enter")
			time.sleep(2)
			print(f"Credit amount is larger than due amount for bidcard {bidcard_num}. Please manually review and return remaining credits to buyer if needed.")
			has_partial_deduct = True
			multi_credit_modal = True
   
		multi_credit_modal = multi_credit_modal or is_multi_credit_modal()
		if multi_credit_modal:	
			# click "no" to return remaining credits to buyer
			print(f"Multi-credit modal detected for bidcard {bidcard_num}. Returning remaining credits to buyer.")
			pyautogui.press("right")
			time.sleep(0.5)
			pyautogui.press("enter")
			time.sleep(2)

		# Move out of the button for the next OCR to work
		select_item_by_tabbing(1, confirm_with_enter=False)
		time.sleep(1)
		if has_partial_deduct:
			break
		all_deducted_count += 1
		if not has_apply_deposit_button():
			print(f"All credits deducted for bidcard {bidcard_num}.")
			break


	if all_deducted_count == 0 and has_partial_deduct:
		return [{'status': '1', 'details': "only a partial credit was deducted", 'row_offset': deduct_records[0]['row_offset']}]

	if not IS_ONLINE:
		return [{'status': '1', 'details': '', 'row_offset': deduct_record['row_offset']} for deduct_record in deduct_records]
	# check credits and return result
	# go to invoice detail
	select_item_by_tabbing(4, confirm_with_enter=True)

	# select B.History
	check_stop_requested()
	time.sleep(0.5)
	keyboard.press(Key.up)
	time.sleep(0.5)
	keyboard.press(Key.up)
	time.sleep(0.5)
	pyautogui.press("enter")

	# select second title bar
	select_item_by_tabbing(5, confirm_with_enter=False)

	# select deposit and click enter
	select_item_by_tabbing(4, confirm_with_enter=False, navigation=True)
	time.sleep(2)

	credit_invoices = {}
	for deduct_record in deduct_records:
		credit_invoices[deduct_record["sc_invoice_number"]] = deduct_record
	# credit invoices on file
	results = []
	# select the list of credits
	select_item_by_tabbing(5, confirm_with_enter=False)
	time.sleep(0.5)
	for i in range(5):
		keyboard.press(Key.page_down)
		time.sleep(0.1)
		keyboard.release(Key.page_down)
		time.sleep(0.1)
	time.sleep(1.5)
	errors = []
	i = 0
	last_credit = None
	same_credit_count = 0
	while (i < len(deduct_records) + len(errors)) and same_credit_count < 2:
		check_stop_requested()
		# escape the loop
		i += 1
		print("before click enter")
		pyautogui.press("enter")
		time.sleep(1)

		# skip to non input focus
		select_item_by_tabbing(1, confirm_with_enter=False)
		time.sleep(1)
		copy()
		cur_store_credit = paste()
		print(f"pasted store credit: {cur_store_credit}")
		# if the store credit is the same as last one, it means we have reached the end of the list, break the loop to avoid infinite loop
		if cur_store_credit == last_credit:
			same_credit_count += 1
			if same_credit_count >= 2:
				break
		last_credit = cur_store_credit
  
		select_item_by_tabbing(1, confirm_with_enter=False)
		time.sleep(1.5)
		cur_sc_invoice = cur_store_credit.strip().split("-")
		if len(cur_sc_invoice) != 2:
			errors.append(f"No invoice number found for: {cur_store_credit}")
			continue
		cur_sc_invoice_number = cur_sc_invoice[1].strip()
		words = extract_center_words_from_screen(**CREDIT_DETAILS_COORDS, save_debug_images=True, kernel_size=(3,3))
		print("words:", words)
		scetence = " ".join(words).lower()
		if ("amount returned:" not in scetence) or ("amount remaining:" not in scetence):
			errors.append(f"OCR failed {cur_sc_invoice_number} with: {scetence}")
			continue
		
		# check if the invoice is fully deducted
		amount_remaining_idx = scetence.index("amount remaining:") + len("amount remaining:")
		is_completed = "0.00" in scetence[amount_remaining_idx+1:]
	
		if cur_sc_invoice_number in credit_invoices:
			if not is_completed:
				results.append({
					'status': '1',
					'details': f"Invoice {cur_sc_invoice_number} is not fully deducted, OCR result: {scetence}",
					'row_offset': credit_invoices[cur_sc_invoice_number]['row_offset']
				})
			else:
				# update the record in db as completed with completed time
				results.append({
					'status': '1',
					'details': "",
					'row_offset': credit_invoices[cur_sc_invoice_number]['row_offset']
				})
		else:
			errors.append(f"Invoice {cur_sc_invoice_number} not found in records, OCR result: {scetence}")
   
		pyautogui.press("esc")
		time.sleep(1)
		pyautogui.press("up")
		time.sleep(1)

	# Append errors
	if len(results) > 0:
		results[0]['errors'] = "; ".join(errors)
	else:
		return [{'status': '-1', 'details': '', 'row_offset': deduct_records[0]['row_offset'], 'errors': "; ".join(errors)}]
	return results
			








