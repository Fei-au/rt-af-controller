import pygetwindow as gw
import pyautogui
import time
from pynput.keyboard import Key, Controller


keyboard = Controller()

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


AUCTION_FLEX_WINDOW_TITLE = "auction flex v"
AUCTION_FLEX_CLOUD_TITLE = "auction flex in the cloud"

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
        pyautogui.press("enter")

    return True

def hotkey_combination(keys, delay_between_keys=0.1):
    
    for key in keys:
        keyboard.press(key)
        time.sleep(delay_between_keys)
    for key in reversed(keys):
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


def run_add_store_credit_flow(target_auction_id=272, bidcard_num=1812, lot=2608, payment_type="Cash", amount=1.23, invoice_number=12345):
    # Click select auction button
    window = get_target_window(AUCTION_FLEX_WINDOW_TITLE)
    activate_window(window)
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
    select_item_by_tabbing(12, confirm_with_enter=False)
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
    keyboard.press(Key.esc)
    time.sleep(2)
    
    # reverse tab to select edit invoice button and click enter
    select_item_by_tabbing(5, confirm_with_enter=True, reverse=True)
    time.sleep(3)
    
    # select B.History
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
    pyautogui.write(str(amount), interval=0.1)
    time.sleep(0.5)
    
    # select note field and input note
    select_item_by_tabbing(2, confirm_with_enter=False)
    time.sleep(0.5)
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
        
    return f"Success: {bidcard_num}-{target_auction_id}-{invoice_number}-{lot}, {payment_type}: {amount}"
        
    
def pre_processing():
    try:
        # Activate cloud window
        window = get_target_window(AUCTION_FLEX_CLOUD_TITLE)
        activate_window(window)
        time.sleep(1)
        
        # Open auction flex software
        pyautogui.write(str("auc"), interval=0.1)
        pyautogui.press("enter")
        time.sleep(5)

        # get data from csv
        # target_auction_id=250, bidcard_num=1033, lot=2333, payment_type="Cash", amount=1.23, invoice_number=12345
        records = [
            # target_auction_id=272, bidcard_num=1812, lot=2608, payment_type="Cash", amount=1.23, invoice_number=12345,
            {"target_auction_id": 272, "bidcard_num": 1812, "lot": 2608, "payment_type": "Cash", "amount": 1.23, "invoice_number": 65587},
            {"target_auction_id": 250, "bidcard_num": 1033, "lot": 3206, "payment_type": "Cash", "amount": 1.23, "invoice_number": 55610},
            {"target_auction_id": 250, "bidcard_num": 1033, "lot": 3206, "payment_type": "Cash", "amount": 1.23, "invoice_number": 55610},
            {"target_auction_id": 272, "bidcard_num": 1812, "lot": 2608, "payment_type": "Cash", "amount": 1.23, "invoice_number": 65587},
            {"target_auction_id": 272, "bidcard_num": 1812, "lot": 2608, "payment_type": "Cash", "amount": 1.23, "invoice_number": 65587},
            {"target_auction_id": 250, "bidcard_num": 1033, "lot": 3206, "payment_type": "Cash", "amount": 1.23, "invoice_number": 55610},
            {"target_auction_id": 272, "bidcard_num": 1812, "lot": 2608, "payment_type": "Cash", "amount": 1.23, "invoice_number": 65587},
        ]
        for record in records:
            msg = run_add_store_credit_flow(**record)
        # later on, save the log to db with timestamp
        print(msg)
        
        return 'All records processed successfully.'
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    msg = pre_processing()
    print(msg)

