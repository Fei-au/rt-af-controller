from webbrowser import get

import pygetwindow as gw
import pyautogui
import time
import pandas as pd
from pynput.keyboard import Key, Controller
from pathlib import Path
from auto_common import AUCTION_FLEX_CLOUD_TITLE, INVOICE_PAID_FULL_MODAL_COORDS, IS_ONLINE, PRITER_POPUP_COORDS, RETURN_REMAININGS_MODAL_COORDS, CREDIT_DETAILS_COORDS, activate_window, check_stop_requested, copy, get_target_window, paste, select_item_by_name, select_item_by_tabbing, INVOIE_SUMMARY_BLOCK_COORDS, set_stop_checker
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

def has_apply_credit_button():
	words = extract_center_words_from_screen(**INVOIE_SUMMARY_BLOCK_COORDS,save_debug_images=True)
	print("OCR-detected words in invoice summary block:", words)
	summary_sentence = " ".join(words)
	return "apply deposit" in summary_sentence.lower()

def is_credit_larger_than_due_amount():
	words = extract_center_words_from_screen(**PRITER_POPUP_COORDS,save_debug_images=True)
	print("OCR-detected words in printer popup:", words)
	summary_sentence = " ".join(words)
	return "print" in summary_sentence.lower()

def is_multi_credit_modal():
	words = extract_center_words_from_screen(**RETURN_REMAININGS_MODAL_COORDS,save_debug_images=True)
	print("OCR-detected words in return remainings modal:", words)
	summary_sentence = " ".join(words)
	return "would you like to return the buyer" in summary_sentence.lower()

def auto_processing(bidcard_num: int, deduct_records: list[dict], log_fn=print) -> str:
	# input bid card number and click enter
	select_item_by_name(
		bidcard_num,
		confirm_with_enter=True,
	)
	time.sleep(3)

	all_deducted_count = 0
	has_partial_deduct = False

	# check if there is "apply credit" button
	if not has_apply_credit_button():
		return [{
			'status': '-1', 
			'details': f"No credit to deduct for bidcard {bidcard_num}, invoice: {deduct_records[0]['invoice_number']}",
			'row_offset': deduct_records[0]['row_offset']
		}]
	print(f"Found 'Apply Credit' button for bidcard {bidcard_num}, starting deduction...")

	# deduct all credit
	while True:
		check_stop_requested()
		# focus and click appy deposit button
		select_item_by_tabbing(4, confirm_with_enter=True, reverse=True)
		time.sleep(2)
  
		# check
		multi_credit_modal = is_multi_credit_modal()
		if is_credit_larger_than_due_amount():
			# TODO: dismiss the model
			print(f"Credit amount is larger than due amount for bidcard {bidcard_num}. Please manually review and return remaining credits to buyer if needed.")
			has_partial_deduct = True
			multi_credit_modal = True
		if multi_credit_modal:
			# click "no" to return remaining credits to buyer
			print(f"Multi-credit modal detected for bidcard {bidcard_num}. Returning remaining credits to buyer.")
			pyautogui.press("right")
			pyautogui.press("enter")
			time.sleep(2)
		if has_partial_deduct:
			break
		all_deducted_count += 1

		# Move out of the button for the next OCR to work
		select_item_by_tabbing(4, confirm_with_enter=False)
		time.sleep(0.5)
		if not has_apply_credit_button():
			print(f"All credits deducted for bidcard {bidcard_num}.")
			break


	if all_deducted_count == 0 and has_partial_deduct:
		return [{'status': '1', 'details': "only a partial credit was deducted", 'row_offset': deduct_records[0]['row_offset']}]

	if not IS_ONLINE:
		return [{'status': '1', 'details': '', 'row_offset': deduct_record['row_offset']} for deduct_record in deduct_records]
	# check credits and return result
	# go to invoice detail
	select_item_by_tabbing(5, confirm_with_enter=True)

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
	pyautogui.press("pagedown")
	errors = []
	i = 0
	while i < len(results) + len(errors):
		check_stop_requested()
		# escape the loop
		i += 1
		pyautogui.press("enter")
		time.sleep(1)

		# skip to non input focus
		select_item_by_tabbing(1, confirm_with_enter=False)
		copy()
		cur_store_credit = paste()
		select_item_by_tabbing(1, confirm_with_enter=False)
		cur_sc_invoice = cur_store_credit.strip().split("-")
		if len(cur_sc_invoice) != 2:
			errors.append(f"No invoice number found for: {cur_store_credit}")
			continue
		cur_sc_invoice_number = cur_sc_invoice[1].strip()
		words = extract_center_words_from_screen(**CREDIT_DETAILS_COORDS)
		scetence = " ".join(words).lower()
		if "amount returned" not in scetence or "amount remaining" not in scetence or "0.00" not in scetence:
			errors.append(f"OCR failed {cur_sc_invoice_number} with: {scetence}")
			continue
		
		# check if the invoice is fully deducted
		first_zero_idx = words.index("0.00")
		is_completed = any(word == "0.00" for word in words[first_zero_idx+1:])
	
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
			








