import os
import pygetwindow as gw
import pyautogui
import time
from pynput.keyboard import Key, Controller
import pyperclip



keyboard = Controller()


AUCTION_FLEX_WINDOW_TITLE = "auction flex v"
AUCTION_FLEX_CLOUD_TITLE = "auction flex in the cloud"
IS_ONLINE = True if os.getenv("IS_ONLINE", "FALSE").upper() == "TRUE" else False


INVOICE_PAID_FULL_MODAL_COORDS = {
    "x1": 0.3633,
    "x2": 0.6426,
    "y1": 0.3958,
    "y2": 0.6076,
}

INVOIE_SUMMARY_BLOCK_COORDS = {
    "x1": 0.6313,
    "x2": 0.7676,
    "y1": 0.3646,
    "y2": 0.6424,
}

RETURN_REMAININGS_MODAL_COORDS = {
    "x1": 0.3633,
    "x2": 0.6426,
    "y1": 0.3958,
    "y2": 0.6076,
}

PRINTER_POPUP_COORDS = {
    "x1": 0.1484,
    "x2": 0.2734,
    "y1": 0.1250,
    "y2": 0.3854,
}

CREDIT_DETAILS_COORDS = {
    "x1": 0.3433,
    "x2": 0.5326,
    "y1": 0.5658,
    "y2": 0.6776,
}

QUICK_INFO_COORDS = {
    "x1": 0.3,
    "x2": 0.6,
    "y1": 0.3,
    "y2": 0.7,
}

CHECK_OUT_TITLE_COORDS = {
    "x1": 0.2,
    "x2": 0.5,
    "y1": 0.2,
    "y2": 0.5,
}



_STOP_CHECKER = None

def _normalize_percentage_coordinate(value, name):
    """
    Convert a coordinate to a normalized ratio in range [0, 1].
    Accepts either 0-1 or 0-100 input.
    """
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc

    if 0 <= numeric_value <= 1:
        return numeric_value

    if 0 <= numeric_value <= 100:
        return numeric_value / 100.0

    raise ValueError(f"{name} must be between 0 and 1, or between 0 and 100.")

def set_stop_checker(stop_checker=None):
    global _STOP_CHECKER
    _STOP_CHECKER = stop_checker


def check_stop_requested():
    if _STOP_CHECKER and _STOP_CHECKER():
        raise StopRequested("Process stopped by user.")
    
class StopRequested(Exception):
    """Raised when user requests stopping the automation immediately."""
    
    
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
        hotkey_combination([Key.enter])

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
        hotkey_combination([Key.enter])
    
    return True


def locate_image_in_window(
    window_title_partial,
    image_path,
    timeout=8,
    interval=0.3,
    confidence=None,
    x1=None,
    x2=None,
    y1=None,
    y2=None,
):
    """
    Locate image only inside target window region.
    """
    # Resolve image path relative to script directory
    if image_path.startswith("/"):
        # Remove leading slash and resolve relative to script directory
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path.lstrip("/"))
    elif not os.path.isabs(image_path):
        # If relative path, resolve relative to script directory
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path)
    
    window = get_target_window(window_title_partial)
    activate_window(window)

    has_crop_coords = any(value is not None for value in (x1, x2, y1, y2))
    if has_crop_coords:
        if any(value is None for value in (x1, x2, y1, y2)):
            raise ValueError("Crop coordinates must include x1, x2, y1, and y2 together.")

        x1_ratio = _normalize_percentage_coordinate(x1, "x1")
        x2_ratio = _normalize_percentage_coordinate(x2, "x2")
        y1_ratio = _normalize_percentage_coordinate(y1, "y1")
        y2_ratio = _normalize_percentage_coordinate(y2, "y2")

        if x2_ratio <= x1_ratio or y2_ratio <= y1_ratio:
            raise ValueError("Invalid crop area: x2 must be greater than x1 and y2 greater than y1.")

        crop_left = int(window.width * x1_ratio)
        crop_right = int(window.width * x2_ratio)
        crop_top = int(window.height * y1_ratio)
        crop_bottom = int(window.height * y2_ratio)

        crop_left = max(0, min(crop_left, window.width - 1))
        crop_top = max(0, min(crop_top, window.height - 1))
        crop_right = max(crop_left + 1, min(crop_right, window.width))
        crop_bottom = max(crop_top + 1, min(crop_bottom, window.height))

        region = (
            window.left + crop_left,
            window.top + crop_top,
            crop_right - crop_left,
            crop_bottom - crop_top,
        )
    else:
        region = (window.left, window.top, window.width, window.height)
    end_time = time.time() + timeout
    # Save the region image for debugging
    screenshot = pyautogui.screenshot(region=region)
    screenshot.save("debug_region.png")
    while time.time() < end_time:
        if confidence is None:
            match = pyautogui.locateOnScreen(image_path, region=region, confidence=0.5)
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

def copy():
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.hotkey('ctrl', 'c')
    
def paste():
    time.sleep(0.5)
    field_value = pyperclip.paste()
    return field_value

if __name__ == "__main__":
    time.sleep(5)  # Time to switch to the target window after running the script
    result = locate_image_in_window(
        AUCTION_FLEX_WINDOW_TITLE, 
        "/images/add-store-credit/quick-info-2560-125.png",
        timeout=5, 
        x1=0.20,
        x2=0.48,
        y1=0.38,
        y2=0.48
        )
    # click the center of the found image
    if result:
        center = pyautogui.center(result)
        pyautogui.click(center.x, center.y)
        print("Image found and clicked.")
    else:
        print("Image not found.")