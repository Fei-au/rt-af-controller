import os
import pygetwindow as gw
import pyautogui
import time
import pandas as pd
from pathlib import Path
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from pynput.keyboard import Key, Controller


keyboard = Controller()

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

LOT_TAB_COUNT = 10
CSV_FILE_PATH = ""


AUCTION_FLEX_WINDOW_TITLE = "auction flex v"
AUCTION_FLEX_CLOUD_TITLE = "auction flex in the cloud"
LOG_BACK = os.getenv("LOG_BACK")
if not LOG_BACK:
    raise RuntimeError("Missing required env var LOG_BACK. Set it in .env before running the app.")
GRAPHQL_URL = LOG_BACK + "/graphql"

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


class StopRequested(Exception):
    """Raised when user requests stopping the automation immediately."""


_STOP_CHECKER = None


def set_stop_checker(stop_checker=None):
    global _STOP_CHECKER
    _STOP_CHECKER = stop_checker


def check_stop_requested():
    if _STOP_CHECKER and _STOP_CHECKER():
        raise StopRequested("Process stopped by user.")
    
    

def get_target_window(window_title_partial):
    windows = gw.getWindowsWithTitle(window_title_partial)
    if not windows:
        raise RuntimeError(
            f"Window with title containing '{window_title_partial}' not found"
        )
    return windows[0]


def activate_window(window):
    if window.isMinimized:
        window.restore()
        time.sleep(0.4)
    window.activate()
    time.sleep(0.4)


def locate_image_in_window(
    window_title_partial,
    image_path,
    timeout=8,
    interval=0.3,
    confidence=None,
):
    """
    Locate image only inside target window region.
    """
    window = get_target_window(window_title_partial)
    activate_window(window)
    region = (window.left, window.top, window.width, window.height)
    end_time = time.time() + timeout

    while time.time() < end_time:
        if confidence is None:
            match = pyautogui.locateOnScreen(image_path, region=region, grayscale=True)
        else:
            try:
                match = pyautogui.locateOnScreen(
                    image_path,
                    region=region,
                    grayscale=True,
                    confidence=confidence,
                )
            except Exception:
                # Fallback when OpenCV confidence matching is unavailable.
                match = pyautogui.locateOnScreen(image_path, region=region, grayscale=True)
        if match:
            return match
        time.sleep(interval)

    return None


def click_image_in_window(window_title_partial, image_path, timeout=8, confidence=None):
    match = locate_image_in_window(
        window_title_partial,
        image_path,
        timeout=timeout,
        confidence=confidence,
    )
    if not match:
        return False

    center = pyautogui.center(match)
    pyautogui.click(center.x, center.y)
    return True


def double_click_image_in_window(
    window_title_partial,
    image_path,
    timeout=8,
    confidence=None,
):
    """
    Locate an image inside the target window and double-click its center.
    """
    match = locate_image_in_window(
        window_title_partial,
        image_path,
        timeout=timeout,
        confidence=confidence,
    )
    if not match:
        return False

    center = pyautogui.center(match)
    pyautogui.doubleClick(center.x, center.y)
    return True


def select_item_by_name(
    item_name,
    confirm_with_enter=True,
    pre_type_delay=0.2,
):
    """
    Select an item by typing into the active modal.

    Assumes the modal is already focused after clicking the relevant button.
    """
    time.sleep(pre_type_delay)
    pyautogui.write(str(item_name), interval=0.1)
    time.sleep(0.2)

    if confirm_with_enter:
        check_stop_requested()
        pyautogui.press("enter")

    return True

def hotkey_combination(keys, delay_between_keys=0.1):
    
    for key in keys:
        check_stop_requested()
        keyboard.press(key)
        time.sleep(delay_between_keys)
    for key in reversed(keys):
        check_stop_requested()
        keyboard.release(key)
        time.sleep(delay_between_keys // 5)

def select_item_by_tabbing(
    click_times,
    tab_delay=0.3,
    confirm_with_enter=True,
    pre_tab_delay=0.2,
    reverse=False,
    navigation=False,
):

    if confirm_with_enter:
        check_stop_requested()
    time.sleep(pre_tab_delay)
    
    for _ in range(click_times):
        if reverse and navigation:
            hotkey_combination([Key.ctrl, Key.shift, Key.tab])
        elif reverse and not navigation:
            hotkey_combination([Key.shift, Key.tab])
        elif not reverse and navigation:
            hotkey_combination([Key.ctrl, Key.tab])
        else:
            pyautogui.hotkey("tab")
        time.sleep(tab_delay)
    
    if confirm_with_enter:
        pyautogui.press("enter")
    
    return True


def read_records_from_csv(csv_file_path):
    """
    Read store-credit records from a CSV file and convert fields to expected types.

    Required headers:
    - refund_id
    - target_auction_id
    - bidcard_num
    - lot
    - payment_type
    - amount
    - invoice_number
    """
    required_fields = [
        "refund_id",
        "target_auction_id",
        "bidcard_num",
        "lot",
        "payment_type",
        "amount",
        "invoice_number",
    ]

    file_path = Path(csv_file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    df = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )

    missing_fields = [field for field in required_fields if field not in df.columns]
    if missing_fields:
        raise ValueError(f"Missing required CSV headers: {', '.join(missing_fields)}")

    if 'status' not in df.columns:
        df['status'] = pd.NA
        df.to_csv(csv_file_path, index=False)
    if 'details' not in df.columns:
        df['details'] = pd.NA
        df.to_csv(csv_file_path, index=False)
        
    records = []
    for row_offset, row in df.iterrows():
        row_index = row_offset + 2
        
        if not row["bidcard_num"] or row["bidcard_num"].strip() == "":
            df.at[row_offset, 'status'] = '-1'
            df.at[row_offset, 'details'] = 'Missing bidcard' + df.at[row_offset, 'details']
            df.to_csv(csv_file_path, index=False)
            continue

        try:
            record = {
                "row_offset": row_offset,
                "refund_id": str(row["refund_id"]).strip(),
                "target_auction_id": int(row["target_auction_id"]),
                "bidcard_num": int(row["bidcard_num"]),
                "lot": int(row["lot"]),
                "payment_type": str(row["payment_type"]).strip(),
                "amount": float(row["amount"]),
                "invoice_number": int(row["invoice_number"]),
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid data at CSV row {row_index}: {row.to_dict()}") from exc

        records.append(record)

    if not records:
        raise ValueError("CSV file has no valid data rows")

    return records


def query_refund_invoice_enhanced(
    refund_id,
    *,
    timeout=15,
    headers=None,
):
    """
    Query refund invoice records from a GraphQL endpoint.

    Query by refund_id and return only fields needed for skip logic.
    """
    graphql_url = GRAPHQL_URL

    graphql_query = gql(
        """
        query QueryRefundInvoiceById($input: RefundInvoiceByIdInput!) {
            refundInvoice(input: $input) {
                invoiceNumber
                hasCompleted
                hasVoided
                isStoreCredit
                store_credit_added: storeCreditAdded
                store_credit_added_time: storeCreditAddedTime
            }
        }
        """
    )

    transport_headers = {"Accept": "application/json"}
    if headers:
        transport_headers.update(headers)

    transport = RequestsHTTPTransport(
        url=graphql_url,
        headers=transport_headers,
        timeout=timeout,
        verify=True,
    )

    variables = {
        "input": {
            "refundId": str(refund_id),
        }
    }

    try:
        with Client(transport=transport, fetch_schema_from_transport=False) as session:
            result = session.execute(graphql_query, variable_values=variables)
    except Exception as exc:
        raise RuntimeError(f"GraphQL request failed: {exc}") from exc

    if "refundInvoice" not in result:
        raise RuntimeError("GraphQL response missing 'refundInvoice' field")

    return result["refundInvoice"]


def add_store_credit_refund_invoice(refund_id, *, timeout=15, headers=None):
    """
    Mark a refund invoice as store-credit-added via GraphQL mutation.
    """
    graphql_mutation = gql(
        """
        mutation AddStoreCreditRefundInvoice($input: MarkAsStoreCreditRefundInvoiceInput!) {
            addStoreCreditRefundInvoice(input: $input) {
                modified_count: modifiedCount
            }
        }
        """
    )

    transport_headers = {"Accept": "application/json"}
    if headers:
        transport_headers.update(headers)

    transport = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        headers=transport_headers,
        timeout=timeout,
        verify=True,
    )

    variables = {
        "input": {
            "refundId": str(refund_id),
        }
    }

    try:
        with Client(transport=transport, fetch_schema_from_transport=False) as session:
            result = session.execute(graphql_mutation, variable_values=variables)
    except Exception as exc:
        raise RuntimeError(f"GraphQL mutation failed: {exc}") from exc

    if "addStoreCreditRefundInvoice" not in result:
        raise RuntimeError("GraphQL response missing 'addStoreCreditRefundInvoice' field")

    return result["addStoreCreditRefundInvoice"]


def run_add_store_credit_flow(
    target_auction_id=272,
    bidcard_num=1812,
    lot=2608,
    payment_type="Cash",
    amount=1.23,
    invoice_number=12345,
    lot_tab_count=LOT_TAB_COUNT,
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
    
    # select lot and click enter
    select_item_by_tabbing(
        lot_tab_count,
        confirm_with_enter=False,
    )
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
    check_stop_requested()
    keyboard.press(Key.esc)
    time.sleep(2)
    
    # reverse tab to select edit invoice button and click enter
    select_item_by_tabbing(5, confirm_with_enter=True, reverse=True)
    time.sleep(3)
    
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
    
    # select add and click
    select_item_by_tabbing(1)
    time.sleep(1)
    
    # click yes for popup modal
    check_stop_requested()
    keyboard.press(Key.left)
    time.sleep(0.3)
    keyboard.press(Key.enter)
    time.sleep(2)
    
    # select payment type
    payment_type_index = PAYMENT_TYPE_DICT.get(payment_type, 6)
    for _ in range(payment_type_index):
        keyboard.press(Key.down)
        time.sleep(0.5)
    
    # select amount field and input amount
    select_item_by_tabbing(1, confirm_with_enter=False)
    time.sleep(0.5)
    check_stop_requested()
    pyautogui.write(str(amount), interval=0.1)
    time.sleep(0.5)
    
    # select note field and input note
    select_item_by_tabbing(2, confirm_with_enter=False)
    time.sleep(0.5)
    check_stop_requested()
    pyautogui.write("Store credit-" + str(invoice_number), interval=0.1)
    time.sleep(0.5)

    # save the form
    for _ in range(2):
        keyboard.press(Key.esc)
        
    # update refund invoice to complete
    print("Updating refund invoice to complete...")
    time.sleep(2)
    
    # if the invoice is unfullly paid invoice, there will be a confirmation popup, click enter to confirm. Other wise, open the invoice detail again
    for _ in range(2):
        keyboard.press(Key.esc)
        time.sleep(2)
    keyboard.press(Key.enter)
    time.sleep(3)
    # exit to easy natigator page to select another auction
    for _ in range(2):
        keyboard.press(Key.esc)
        time.sleep(2)
    time.sleep(3)
    
    select_item_by_tabbing(7, reverse=True, confirm_with_enter=False)  # tab back to auction selection
    time.sleep(1)
        
    return f"Success: {invoice_number}-{bidcard_num}-{target_auction_id}-{lot}, {payment_type}: {amount}"

    
def pre_processing(csv_file_path, log_fn=print, should_stop_fn=None, lot_tab_count=10):
    set_stop_checker(should_stop_fn)
    try:
        try:
            parsed_lot_tab_count = int(lot_tab_count)
        except (TypeError, ValueError) as exc:
            raise ValueError("Lot tab count must be an integer.") from exc

        if parsed_lot_tab_count <= 0:
            raise ValueError("Lot tab count must be greater than 0.")

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

            flow_args = {
                "target_auction_id": record["target_auction_id"],
                "bidcard_num": record["bidcard_num"],
                "lot": record["lot"],
                "payment_type": record["payment_type"],
                "amount": record["amount"],
                "invoice_number": record["invoice_number"],
                "lot_tab_count": parsed_lot_tab_count,
            }

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
            msg = run_add_store_credit_flow(**flow_args)
            log_fn(msg)
            
            mutation_result = add_store_credit_refund_invoice(record["refund_id"])
            modified_count = int(mutation_result.get("modified_count", 0) or 0)

            if modified_count > 0:
                df.at[record["row_offset"], "status"] = '1'
                log_fn(f"{record['invoice_number']}: Store credit added successfully.")
            else:
                df.at[record["row_offset"], "status"] = '-1'
                df.at[record["row_offset"], "details"] = 'Store credit added, but mutation modified_count=0' + df.at[record["row_offset"], "details"]
                log_fn(f"{record['invoice_number']}: Store credit added, but update to database failed")

            df.to_csv(csv_file_path, index=False)
            

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

