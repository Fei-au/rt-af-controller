
import importlib
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
import pyautogui
from PIL import Image, ImageOps
import cv2
import numpy as np
from pynput.keyboard import Key, Controller
from auto_common import INVOICE_PAID_FULL_MODAL_COORDS, INVOIE_SUMMARY_BLOCK_COORDS, RETURN_REMAININGS_MODAL_COORDS, PRINTER_POPUP_COORDS, CREDIT_DETAILS_COORDS


keyboard = Controller()

def extract_center_words_from_screen(
    x1=40,
    x2=60,
    y1=40,
    y2=60,
    ocr_lang="eng",
    confidence_threshold=0,
    save_debug_images=False,
    debug_output_dir="images/debug-crops",
    preprocess_scale=3,
    preprocess_threshold=180,
    kernel_size=(2,2)
):
    """
    Take a full-screen screenshot, crop by percentage coordinates,
    and return OCR-detected words from that cropped area.

    Coordinates can be passed as either 0-100 percentages or 0-1 normalized
    values, for example:
      - x1=40, x2=60, y1=40, y2=60
      - x1=0.4, x2=0.6, y1=0.4, y2=0.6

        Set save_debug_images=True to save the full screenshot and the cropped
        image, and print their file paths.

        The crop is preprocessed before OCR by converting to grayscale, scaling it
        up, and applying a contrast-friendly binary threshold.
    """
    try:
        pytesseract = importlib.import_module("pytesseract")
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is required for OCR. Install dependencies from requirements.txt."
        ) from exc

    configured_tesseract_cmd = _resolve_tesseract_executable_path()
    if configured_tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = configured_tesseract_cmd

    screenshot = pyautogui.screenshot()
    screen_width, screen_height = screenshot.size

    x1_ratio = _normalize_percentage_coordinate(x1, "x1")
    x2_ratio = _normalize_percentage_coordinate(x2, "x2")
    y1_ratio = _normalize_percentage_coordinate(y1, "y1")
    y2_ratio = _normalize_percentage_coordinate(y2, "y2")

    if x2_ratio <= x1_ratio or y2_ratio <= y1_ratio:
        raise ValueError("Invalid crop area: x2 must be greater than x1 and y2 greater than y1.")

    crop_left = int(screen_width * x1_ratio)
    crop_right = int(screen_width * x2_ratio)
    crop_top = int(screen_height * y1_ratio)
    crop_bottom = int(screen_height * y2_ratio)

    crop_left = max(0, min(crop_left, screen_width - 1))
    crop_top = max(0, min(crop_top, screen_height - 1))
    crop_right = max(crop_left + 1, min(crop_right, screen_width))
    crop_bottom = max(crop_top + 1, min(crop_bottom, screen_height))

    center_crop = screenshot.crop(
        (
            crop_left,
            crop_top,
            crop_right,
            crop_bottom,
        )
    )

    preprocess_result = _preprocess_ocr_crop(
        center_crop,
        scale=preprocess_scale,
        threshold=preprocess_threshold,
        save_intermediate_images=save_debug_images,
        kernel_size=kernel_size
    )

    if save_debug_images:
        preprocessed_crop, preprocess_images = preprocess_result
    else:
        preprocessed_crop = preprocess_result
        preprocess_images = None

    if save_debug_images:
        screenshot_path, crop_path, preprocessed_path = _save_debug_images(
            screenshot,
            center_crop,
            preprocessed_crop,
            debug_output_dir,
            preprocess_images=preprocess_images,
        )

    try:
        ocr_data = pytesseract.image_to_data(
            preprocessed_crop,
            output_type=pytesseract.Output.DICT,
            lang=ocr_lang,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR executable not found. Install Tesseract and add it to PATH."
        ) from exc

    words = []
    for raw_text, raw_conf in zip(ocr_data.get("text", []), ocr_data.get("conf", [])):
        text = str(raw_text).strip()
        if not text:
            continue

        try:
            confidence = float(raw_conf)
        except (TypeError, ValueError):
            confidence = -1

        if confidence >= confidence_threshold:
            words.append(text)

    return words


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


def _preprocess_ocr_crop(image, scale=3, threshold=180, save_intermediate_images=False, kernel_size=(2,2)):
    """
    Prepare a cropped image for OCR by increasing its size and simplifying it.
    """
    intermediate_images = {} if save_intermediate_images else None

    grayscale_image = ImageOps.grayscale(image)
    # if intermediate_images is not None:
    #     intermediate_images["grayscale"] = grayscale_image.copy()

    if scale and scale > 1:
        resized_size = (
            max(1, grayscale_image.width * int(scale)),
            max(1, grayscale_image.height * int(scale)),
        )
        resample_filter = getattr(Image, "Resampling", Image).LANCZOS
        grayscale_image = grayscale_image.resize(resized_size, resample=resample_filter)

    # if intermediate_images is not None:
    #     intermediate_images["resized"] = grayscale_image.copy()

    grayscale_image = ImageOps.autocontrast(grayscale_image)


    if threshold is not None:
        grayscale_image = grayscale_image.point(
            lambda pixel: 255 if pixel > int(threshold) else 0,
            mode="1",
        ).convert("L")

    if intermediate_images is not None:
        intermediate_images["autocontrast"] = grayscale_image.copy()
    
    # Convert PIL image to OpenCV format
    cv_image = np.array(grayscale_image)
    
    # Apply Adaptive Threshold
    # 255: Value to give if pixel exceeds threshold
    # ADAPTIVE_THRESH_GAUSSIAN_C: Uses a weighted sum of neighborhood
    # THRESH_BINARY: Standard black/white
    # 11: Block size (must be odd). Larger = more global; Smaller = more local.
    # 2: Constant subtracted from the mean
    # cv_image = cv2.adaptiveThreshold(cv_image, 255, 
    #                                 cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
    #                                 cv2.THRESH_BINARY, 11, 2)
    # adaptive_thresh_image = Image.fromarray(cv_image)
    # if intermediate_images is not None:
    #     intermediate_images["adaptive_threshold"] = adaptive_thresh_image.copy()
    
    # Dilate to make text bolder
    kernel = np.ones(kernel_size, np.uint8) # A small 2x2 kernel

    # This will make the black lines (text and borders) thinner
    processed = cv2.dilate(cv_image, kernel, iterations=1)
    
    processed_image = Image.fromarray(processed)
    
    if intermediate_images is not None:
        return processed_image, intermediate_images

    return processed_image


def _save_debug_images(screenshot, center_crop, preprocessed_crop, debug_output_dir, preprocess_images=None):
    """
    Save debug images and return absolute file paths.
    """
    output_dir = Path(debug_output_dir)
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    screenshot_path = output_dir / f"screen_{timestamp}.png"
    crop_path = output_dir / f"center_crop_{timestamp}.png"
    preprocessed_path = output_dir / f"preprocessed_crop_{timestamp}.png"
    grayscale_path = output_dir / f"preprocess_grayscale_{timestamp}.png"
    resized_path = output_dir / f"preprocess_resized_{timestamp}.png"
    autocontrast_path = output_dir / f"preprocess_autocontrast_{timestamp}.png"
    adaptive_thresh_path = output_dir / f"preprocess_adaptive_threshold_{timestamp}.png"

    screenshot.save(screenshot_path)
    center_crop.save(crop_path)
    preprocessed_crop.save(preprocessed_path)

    if preprocess_images:
        if preprocess_images.get("grayscale") is not None:
            preprocess_images["grayscale"].save(grayscale_path)
        if preprocess_images.get("resized") is not None:
            preprocess_images["resized"].save(resized_path)
        if preprocess_images.get("autocontrast") is not None:
            preprocess_images["autocontrast"].save(autocontrast_path)
        if preprocess_images.get("adaptive_threshold") is not None:
            preprocess_images["adaptive_threshold"].save(adaptive_thresh_path)
    return (
        str(screenshot_path.resolve()),
        str(crop_path.resolve()),
        str(preprocessed_path.resolve()),
    )


def _resolve_tesseract_executable_path():
    """
    Resolve a usable Tesseract executable path for Windows environments.
    """
    # When bundled with PyInstaller, binaries are extracted under _MEIPASS.
    if getattr(sys, "frozen", False):
        bundled_cmd = os.path.join(sys._MEIPASS, "Tesseract-OCR", "tesseract.exe")
        if os.path.isfile(bundled_cmd):
            return bundled_cmd

    env_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if env_cmd and os.path.isfile(env_cmd):
        return env_cmd

    discovered_cmd = shutil.which("tesseract")
    if discovered_cmd:
        return discovered_cmd

    common_windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
    ]
    for candidate in common_windows_paths:
        if os.path.isfile(candidate):
            return candidate

    return None


if __name__ == "__main__":
    target_phrase = "This invoice has not been paid in full"
    target_button1 = "Add Receipt"
    target_button2 = "Apply Deposit"
    # words = extract_center_words_from_screen(
    #     x1=0.3433,
    #     x2=0.5326,
    #     y1=0.5658,
    #     y2=0.6776,
    #     save_debug_images=True
    # )
    
    # words = extract_center_words_from_screen(x1=0.3633, x2=0.6426, y1=0.3958, y2=0.6076, save_debug_images=True)
    time.sleep(5)  # Time to switch to the target screen before OCR
    words = extract_center_words_from_screen(
        **PRINTER_POPUP_COORDS,
        save_debug_images=True,
    )
    ocr_text = " ".join(words)
    # has_unpaid_invoice_text = target_phrase.lower() in ocr_text.lower()

    # has_add_receipt_button = target_button1.lower() in ocr_text.lower()
    # has_apply_deposit_button = target_button2.lower() in ocr_text.lower()
    print("OCR-detected words in center area:", words)
    # print(f"Unpaid:", has_unpaid_invoice_text)
    # print(f"Has '{target_button1}':", has_add_receipt_button)
    # print(f"Has '{target_button2}':", has_apply_deposit_button)
    
    # import time
    # time.sleep(5)  # Time to switch to the target screen before OCR
    # # Select all and copy
    # pyautogui.hotkey('ctrl', 'a')
    # pyautogui.hotkey('ctrl', 'c')
    # import pyperclip
    # time.sleep(0.5)
    # # Get the data
    # field_value = pyperclip.paste()
    # print(f"The value is: {field_value}")