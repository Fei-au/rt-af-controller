from webbrowser import get
import re

import pygetwindow as gw
import pyautogui
import time
import pandas as pd
from pynput.keyboard import Key, Controller
from pathlib import Path
from auto_common import AUCTION_FLEX_CLOUD_TITLE, INVOICE_PAID_FULL_MODAL_COORDS, IS_ONLINE, PRINTER_POPUP_COORDS, QUICK_INFO_COORDS, RETURN_REMAININGS_MODAL_COORDS, CREDIT_DETAILS_COORDS, activate_window, check_stop_requested, copy, get_target_window, paste, select_item_by_name, select_item_by_tabbing, INVOIE_SUMMARY_BLOCK_COORDS, CHECK_OUT_TITLE_COORDS, set_stop_checker, hotkey_combination
from service import complete_refund_invoice, read_deduct_records_from_csv, upload_file_to_s3
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
		hotkey_combination([Key.enter])
		time.sleep(5)
  
		# Open autction list
		hotkey_combination([Key.enter])
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
				log_fn(result)
				df.at[result["row_offset"], "status"] = result.get("status")
				df.at[result["row_offset"], "details"] = result.get("details")
				df.at[result["row_offset"], "errors"] = result.get("errors")
				if result["status"] == '1' and IS_ONLINE:
					sc_id = str(df.at[result["row_offset"], "sc_id"]).strip()
					if sc_id:
						try:
							complete_refund_invoice(sc_id)
						except Exception as exc:
							error_message = f"Failed to mark refund {sc_id} complete: {exc}"
							existing_errors = df.at[result["row_offset"], "errors"]
							if existing_errors:
								df.at[result["row_offset"], "errors"] = f"{existing_errors}; {error_message}"
							else:
								df.at[result["row_offset"], "errors"] = error_message
							log_fn(error_message)
					else:
						log_fn(f"Missing sc_id for row {result['row_offset']}, skip completion update.")

					log_fn(f"Success: {result['details']}")
			df.to_csv(csv_file_path, index=False)
			if IS_ONLINE:
				try:
					upload_file_to_s3(csv_file_path)
				except Exception as exc:
					log_fn(f"Failed to upload deduct CSV to S3: {exc}")
			time.sleep(2)
			back_to_invoice_list()
		# After processing all records, save the final results to CSV
		df.to_csv(csv_file_path, index=False)
		if IS_ONLINE:
			try:
				upload_file_to_s3(csv_file_path)
			except Exception as exc:
				log_fn(f"Failed to upload final deduct CSV to S3: {exc}")
		
		return f"Deduct process completed for {len(records)} records."
	finally:
		set_stop_checker(None)
  
def back_to_invoice_list():
	# back to invoice edit page and esc to exit
	hotkey_combination([Key.esc])
	time.sleep(0.5)
        
    # if the invoice is unfully paid invoice, there will be a confirmation popup, click enter to confirm. Other wise, open the invoice detail again
	words = extract_center_words_from_screen(**INVOICE_PAID_FULL_MODAL_COORDS)
	has_unpaid_invoice_text = "This invoice has not been paid in full".lower() in " ".join(words).lower()
	if has_unpaid_invoice_text:
		hotkey_combination([Key.enter])
		time.sleep(5)
		return
        
	words = extract_center_words_from_screen(**CHECK_OUT_TITLE_COORDS)
	has_checkout_title = "check-out customers for auction" in " ".join(words).lower()
	if has_checkout_title:
		time.sleep(5)
		return

	hotkey_combination([Key.esc])
	time.sleep(1)
    
	# if the invoice is unfully paid invoice, there will be a confirmation popup, click enter to confirm. Other wise, open the invoice detail again
	words = extract_center_words_from_screen(**INVOICE_PAID_FULL_MODAL_COORDS)
	has_unpaid_invoice_text = "This invoice has not been paid in full".lower() in " ".join(words).lower()
	if has_unpaid_invoice_text:
		hotkey_combination([Key.enter])
		time.sleep(5)
		return
    
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

def get_text_coordinates(text_area):
	_, coordinates = extract_center_words_from_screen(
		**text_area,
		return_coordinates=True
	)
	quick_x = 0
	quick_y = 0
	info_x = 0
	info_y = 0
	for coor in coordinates:
		if coor.get("text") == "QUICK":
			quick_x = coor['x'] + coor['width']//2
			quick_y = coor['y'] + coor['height']//2
		if coor.get("text") == "INFO" and coor['y'] + coor['height']//2 >= quick_y - 10 and coor['y'] + coor['height']//2 <= quick_y + 10:
			info_x = coor['x'] + coor['width']//2
			info_y = coor['y'] + coor['height']//2
   
	if quick_x == 0 or quick_y == 0 or info_x == 0 or info_y == 0:
		return 0,0

	middle_x = (quick_x + info_x) // 2
	middle_y = (quick_y + info_y) // 2

	return middle_x, middle_y

def auto_processing(bidcard_num: int, deduct_records: list[dict], log_fn=print) -> str:
	# input bid card number and click enter
	select_item_by_tabbing(1, confirm_with_enter=False, reverse=True)
	time.sleep(1)
	select_item_by_tabbing(1, confirm_with_enter=False)
	time.sleep(1)
	select_item_by_name(
		bidcard_num,
		confirm_with_enter=True,
	)
	time.sleep(4)

	all_deducted_count = 0
	has_partial_deduct = False
 
	quick_info_x, quick_info_y = get_text_coordinates(text_area=QUICK_INFO_COORDS)
	if quick_info_x == 0 or quick_info_y == 0:
		return [{
			'status': '-1', 
			'details': f"Failed to locate QUICK and INFO words, OCR might have failed for bidcard {bidcard_num}", 
			'row_offset': deduct_records[i]['row_offset']
		} for i in range(len(deduct_records))]
	pyautogui.click(quick_info_x, quick_info_y)
	time.sleep(1)
 
	# check if there is "apply deposit" button
	if not has_apply_deposit_button():
		return [{
			'status': '-1', 
			'details': f"No credit to deduct for bidcard {bidcard_num}, invoice: {deduct_records[0]['invoice_number']}",
			'row_offset': deduct_records[i]['row_offset']
		} for i in range(len(deduct_records))]
	log_fn(f"Found 'Apply Deposit' button for bidcard {bidcard_num}, starting deduction...")
 
	# focus and click appy deposit button
	select_item_by_tabbing(14, confirm_with_enter=False)
 
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
			hotkey_combination([Key.right])
			time.sleep(0.5)
			hotkey_combination([Key.enter])
			time.sleep(3)
			log_fn(f"Credit amount is larger than due amount for bidcard {bidcard_num}. Please manually review and return remaining credits to buyer if needed.")
			has_partial_deduct = True
   
		multi_credit_modal = is_multi_credit_modal()
		if multi_credit_modal:	
			# click "no" to return remaining credits to buyer
			log_fn(f"Multi-credit modal detected for bidcard {bidcard_num}. Returning remaining credits to buyer.")
			hotkey_combination([Key.right])
			time.sleep(0.5)
			hotkey_combination([Key.enter])
			time.sleep(2)

		# Move out of the button for the next OCR to work
		select_item_by_tabbing(1, confirm_with_enter=False)
		time.sleep(1)
		if has_partial_deduct:
			break
		all_deducted_count += 1
		if not has_apply_deposit_button():
			log_fn(f"All credits deducted for bidcard {bidcard_num}.")
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
	hotkey_combination([Key.up])
	time.sleep(0.5)
	hotkey_combination([Key.up])
	time.sleep(0.5)
	hotkey_combination([Key.enter])

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
		hotkey_combination([Key.page_down])
		time.sleep(0.1)
		hotkey_combination([Key.page_down])
		time.sleep(0.1)
	time.sleep(1)
	errors = []
	i = 0
	last_credit = None
	same_credit_count = 0
	while (i < len(deduct_records) + len(errors)) and same_credit_count < 2:
		check_stop_requested()
		# escape the loop
		i += 1
		hotkey_combination([Key.enter])
		time.sleep(2)

		# skip to non input focus
		select_item_by_tabbing(1, confirm_with_enter=False)
		time.sleep(1)
		copy()
		cur_store_credit = paste()
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
		scetence = " ".join(words).lower()
		log_fn(f"{cur_sc_invoice_number}: {scetence}")
		if ("amount returned:" not in scetence) or ("amount remaining:" not in scetence):
			errors.append(f"OCR failed {cur_sc_invoice_number} with: {scetence}")
			continue
		
		# check if the invoice is fully deducted
		amount_remaining_idx = scetence.index("amount remaining:") + len("amount remaining:")
		remaining_text = scetence[amount_remaining_idx:]
		remaining_match = re.search(r"-?\d+(?:\.\d+)?", remaining_text.replace(",", ""))
		if not remaining_match:
			errors.append(f"Unable to parse amount remaining for {cur_sc_invoice_number}, OCR result: {scetence}")
			hotkey_combination([Key.esc])
			time.sleep(1)
			hotkey_combination([Key.up])
			time.sleep(1)
			continue

		amount_remaining = float(remaining_match.group())
		# Treat only exact zero or small negative rounding (e.g. -0.02) as completed.
		is_completed = (-1.0 < amount_remaining <= 0.0)
	
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
   
		hotkey_combination([Key.esc])
		time.sleep(1)
		hotkey_combination([Key.up])
		time.sleep(1)

	# Append errors
	if len(results) > 0:
		results[0]['errors'] = "; ".join(errors)
	else:
		return [{'status': '-1', 'details': '', 'row_offset': deduct_records[0]['row_offset'], 'errors': "; ".join(errors)}]
	return results
			








