import os
import pyautogui
import time
import pandas as pd
from pynput.keyboard import Key, Controller
from auto_common import CHECK_OUT_TITLE_COORDS, EASY_NAVIGATOR_TITLE_COORDS, INVOICE_PAID_FULL_MODAL_COORDS, QUICK_INFO_COORDS, get_target_window, activate_window, hotkey_combination, select_item_by_name, select_item_by_tabbing, StopRequested
from auto_deduct_credit import get_text_coordinates
from tools import extract_center_words_from_screen
from service import query_refund_invoice_enhanced, add_store_credit_refund_invoice, read_records_from_csv
from auto_common import AUCTION_FLEX_CLOUD_TITLE, AUCTION_FLEX_WINDOW_TITLE, IS_ONLINE, check_stop_requested, set_stop_checker

keyboard = Controller()

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

CSV_FILE_PATH = ""

PAYMENT_TYPE_DICT = {
    "-Not": 1,
    "ACH": 2,
    "America Express": 3,
    "Cash": 4,
    "Check": 5,
    "Debit": 6,
    "Discover": 7,
    "E-Transfer": 8,
    "Credit Card": 9,
    "MasterCard": 10,
    "Visa": 11,
}


def run_add_store_credit_flow(
    target_auction_id,
    bidcard_num,
    lot,
    payment_type,
    amount,
    invoice_number,
):
    # Click select auction button
    window = get_target_window(AUCTION_FLEX_WINDOW_TITLE)
    activate_window(window)
    check_stop_requested()
    pyautogui.press("enter")
    time.sleep(1.5)  # Wait for the app to load

    # select auction id in modal
    select_item_by_name(
        target_auction_id,
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
    
    # input bid card number and click enter
    select_item_by_name(
        bidcard_num,
        confirm_with_enter=True,
    )
    time.sleep(3)
    
    # skip n tabs if there is a apply 
    
    # select lot and click enter
    quick_info_x, quick_info_y = get_text_coordinates(text_area=QUICK_INFO_COORDS)
    if quick_info_x == 0 or quick_info_y == 0:
        return -1, f"Failed to locate quick info text area for invoice {invoice_number}: {invoice_number}-{bidcard_num}-{target_auction_id}-{lot}, {payment_type}: {amount}"
    
    pyautogui.click(quick_info_x, quick_info_y)
    time.sleep(0.5)
    
    select_item_by_tabbing(6, confirm_with_enter=False)  # select invoice number field
    
    time.sleep(1)
    
    # input lot number and click enter
    select_item_by_name(
        lot,
        confirm_with_enter=True,
    )
    time.sleep(1)
    
    # reverse tab to select edit item button and click enter
    select_item_by_tabbing(5, confirm_with_enter=True, reverse=True)
    time.sleep(3)
    # esc the edit modal
    hotkey_combination([Key.esc])
    time.sleep(2)
    
    # reverse tab to select edit invoice button and click enter
    select_item_by_tabbing(5, confirm_with_enter=True, reverse=True)
    time.sleep(3)
    editing_title_ocr_result = extract_center_words_from_screen(**CHECK_OUT_TITLE_COORDS)
    has_editing_title = "editing customer for invoice" in " ".join(editing_title_ocr_result).lower()
    if not has_editing_title:
        return -1, f"Failed to open invoice editing page for invoice {invoice_number}: {invoice_number}-{bidcard_num}-{target_auction_id}-{lot}, {payment_type}: {amount}"
    
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
    
    # select add and click
    select_item_by_tabbing(1)
    time.sleep(1)
    
    # click yes for popup modal
    check_stop_requested()
    hotkey_combination([Key.left])
    time.sleep(0.3)
    hotkey_combination([Key.enter])
    time.sleep(2)
    
    edit_deposit_ocr_result = extract_center_words_from_screen(**CHECK_OUT_TITLE_COORDS)
    has_deposit_title = "edit this buyer deposit" in " ".join(edit_deposit_ocr_result).lower()
    if not has_deposit_title:
        return -1, f"Failed to open add store credit page for invoice {invoice_number}: {invoice_number}-{bidcard_num}-{target_auction_id}-{lot}, {payment_type}: {amount}"
            
    # select payment type
    payment_type_index = PAYMENT_TYPE_DICT.get(payment_type, 6)
    for _ in range(payment_type_index):
        hotkey_combination([Key.down])
        time.sleep(0.2)
    
    # select amount field and input amount
    select_item_by_tabbing(1, confirm_with_enter=False)
    time.sleep(0.5)
    pyautogui.write(str(amount), interval=0.1)
    time.sleep(0.5)
    
    # select note field and input note
    select_item_by_tabbing(2, confirm_with_enter=False)
    time.sleep(0.5)
    check_stop_requested()
    pyautogui.write("Store credit-" + str(invoice_number), interval=0.1)
    time.sleep(0.5)
    select_item_by_tabbing(2, confirm_with_enter=False)
    time.sleep(0.5)


    # save the form and close print preview
    for _ in range(2):
        hotkey_combination([Key.esc])
    time.sleep(2)
        
    # back to invoice edit page and esc to exit
    hotkey_combination([Key.esc])
    time.sleep(0.5)
    hotkey_combination([Key.esc])
    time.sleep(1)
    
    # if the invoice is unfully paid invoice, there will be a confirmation popup, click enter to confirm. Other wise, open the invoice detail again
    words = extract_center_words_from_screen(**INVOICE_PAID_FULL_MODAL_COORDS)
    has_unpaid_invoice_text = "This invoice has not been paid in full".lower() in " ".join(words).lower()
    if has_unpaid_invoice_text:
        hotkey_combination([Key.enter])
        time.sleep(3)
        
    # exit to easy natigator page to select another auction
    hotkey_combination([Key.esc])
    time.sleep(3)
    
    select_item_by_tabbing(7, reverse=True, confirm_with_enter=False)  # tab back to auction selection
    time.sleep(1)
        
    return 1, f"Success: {invoice_number}-{bidcard_num}-{target_auction_id}-{lot}, {payment_type}: {amount}"

    
def pre_processing(csv_file_path, log_fn=print, should_stop_fn=None):
    set_stop_checker(should_stop_fn)
    try:

        records = read_records_from_csv(csv_file_path)
        
        # Activate cloud window
        window = get_target_window(AUCTION_FLEX_CLOUD_TITLE)
        activate_window(window)
        time.sleep(1)
        
        # Open auction flex software
        pyautogui.write(str("auc"), interval=0.1)
        pyautogui.press("enter")
        time.sleep(5)

        # Read records from CSV in the project root.
        
        df = pd.read_csv(csv_file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        
        for record in records:
            check_stop_requested()
            if record["status"] == '1' or record["status"] == '-1':
                # log_fn(f"{record['invoice_number']}: Skipped as already processed in CSV.")
                # df.to_csv(csv_file_path, index=False)
                continue
            
            flow_args = {
                "target_auction_id": record["target_auction_id"],
                "bidcard_num": record["bidcard_num"],
                "lot": record["lot"],
                "payment_type": record["payment_type"],
                "amount": record["amount"],
                "invoice_number": record["invoice_number"],
            }

            if IS_ONLINE:
                # Fetch if the store credit record already added in the system by store_credit_added this field in db, if it's added, skip the record
                graphql_result = query_refund_invoice_enhanced(
                    refund_id=record["refund_id"],
                )
                if graphql_result is None:
                    df.at[record["row_offset"], "status"] = '0'
                    df.at[record["row_offset"], "details"] = 'GraphQL query failed' + df.at[record["row_offset"], "details"]
                    df.to_csv(csv_file_path, index=False)
                    log_fn(f"{record['invoice_number']}: GraphQL query failed")
                    continue
                store_credit_added  = graphql_result.get("store_credit_added", False)
                is_store_credit = graphql_result.get("isStoreCredit", False)
                is_completed = graphql_result.get("hasCompleted", False)
                is_voided = graphql_result.get("hasVoided", False)
                
                invalid_store_credit = store_credit_added  or not is_store_credit or is_voided or is_completed
                
                if invalid_store_credit:
                    df.at[record["row_offset"], "status"] = '0'
                    df.at[record["row_offset"], "details"] = f'Invalid store credit record with isStoreCredit: {is_store_credit}, hasCompleted: {is_completed}, hasVoided: {is_voided}, storeCreditAdded: {store_credit_added}' + df.at[record["row_offset"], "details"]
                    df.to_csv(csv_file_path, index=False)
                    log_fn(f"{record['invoice_number']}: Invalid store credit record with isStoreCredit: {is_store_credit}, hasCompleted: {is_completed}, hasVoided: {is_voided}, storeCreditAdded: {store_credit_added}")
                    continue
            check_stop_requested()
            result, msg = run_add_store_credit_flow(**flow_args)
            log_fn(msg)
            if result != 1:
                df.at[record["row_offset"], "status"] = '-1'
                df.at[record["row_offset"], "details"] = msg + df.at[record["row_offset"], "details"]
                raise Exception()
            
            df.at[record["row_offset"], "status"] = '1'
            if IS_ONLINE:
                mutation_result = add_store_credit_refund_invoice(record["refund_id"])
                modified_count = int(mutation_result.get("modified_count", 0) or 0)

                if modified_count == 0:
                    df.at[record["row_offset"], "status"] = '-1'
                    df.at[record["row_offset"], "details"] = 'Store credit added, but mutation modified_count=0' + df.at[record["row_offset"], "details"]
                    log_fn(f"{record['invoice_number']}: Store credit added, but update to database failed")
            
            df.to_csv(csv_file_path, index=False)
            check_resume_status()
        return 'All records processed successfully.'
    except StopRequested as e:
        return str(e)
    except Exception as e:
        return str(e)
    finally:
        set_stop_checker(None)
'''
status
1: Success
0: Failed
-1: Partially successful
'''

def check_resume_status():
    words = extract_center_words_from_screen(**EASY_NAVIGATOR_TITLE_COORDS, save_debug_images=True)
    has_easy_navigator_text = "easy navigator".lower() in " ".join(words).lower()
    if not has_easy_navigator_text:
        raise Exception("Not in easy navigator page, current page might be frozen, please check the application.")
    

