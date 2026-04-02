import pygetwindow as gw
import pyautogui
import time
import pandas as pd
from pynput.keyboard import Key, Controller


keyboard = Controller()

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

if __name__ == "__main__":
    m = locate_image_in_window(
        "Auction Flex v",
        "images/add-store-credit/edit-invoice-1440-125.png",
    )
    
    print("Match found at:", m)
    center = pyautogui.center(m)
    pyautogui.click(center.x, center.y)