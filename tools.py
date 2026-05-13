
import importlib
import os
import shutil
import sys
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import pyautogui
from PIL import Image, ImageOps
import cv2
import numpy as np
from pynput.keyboard import Key, Controller
from auto_common import BIDCARD_NUMBER_COORDS, CHECK_OUT_TITLE_COORDS, EASY_NAVIGATOR_TITLE_COORDS, EDIT_BUTTON_COORDS, INVOICE_PAID_FULL_MODAL_COORDS, INVOIE_SUMMARY_BLOCK_COORDS, RETURN_REMAININGS_MODAL_COORDS, PRINTER_POPUP_COORDS, CREDIT_DETAILS_COORDS, SELECT_NEW_BUTTON_COORDS
from auto_common import select_item_by_tabbing, hotkey_combination

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
    kernel_size=(2,2),
    return_coordinates=False,
    screenshot=None,
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

        Set return_coordinates=True to also return word bounding boxes. The
        returned coordinates are in absolute screen pixels.

        Pass a pre-captured PIL screenshot via `screenshot` to reuse it across
        multiple OCR regions in the same UI state and avoid redundant captures.
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

    if screenshot is None:
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
    word_coordinates = []
    ocr_scale = int(preprocess_scale) if preprocess_scale and preprocess_scale > 1 else 1
    texts = ocr_data.get("text", [])
    confidences = ocr_data.get("conf", [])
    lefts = ocr_data.get("left", [])
    tops = ocr_data.get("top", [])
    widths = ocr_data.get("width", [])
    heights = ocr_data.get("height", [])

    for i, raw_text in enumerate(texts):
        raw_conf = confidences[i] if i < len(confidences) else -1
        text = str(raw_text).strip()

        if not text:
            continue

        try:
            confidence = float(raw_conf)
        except (TypeError, ValueError):
            confidence = -1

        if confidence >= confidence_threshold:
            raw_left = int(lefts[i]) if i < len(lefts) else 0
            raw_top = int(tops[i]) if i < len(tops) else 0
            raw_width = int(widths[i]) if i < len(widths) else 0
            raw_height = int(heights[i]) if i < len(heights) else 0

            left = int(round(raw_left / ocr_scale))
            top = int(round(raw_top / ocr_scale))
            width = int(round(raw_width / ocr_scale))
            height = int(round(raw_height / ocr_scale))

            words.append(text)
            word_coordinates.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "x": crop_left + left,
                    "y": crop_top + top,
                    "width": width,
                    "height": height,
                }
            )

    if return_coordinates:
        return words, word_coordinates

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


def is_in_right_invoice_page(bidcard_num, log_fn=print):
    bidcard_num = str(bidcard_num).strip()
    words = extract_center_words_from_screen(**BIDCARD_NUMBER_COORDS, kernel_size=(3,3))
    log_fn(f"OCR-detected words for bidcard  number check: {' '.join(words).lower()}")
    for word in words:
        if bidcard_num in word:
            return True
    return False


_TEMPLATE_COARSE_SCALES = np.arange(0.9, 3.11, 0.1)
_TEMPLATE_FINE_STEP = 0.02
_TEMPLATE_FINE_WINDOW = 0.12


@lru_cache(maxsize=32)
def _load_template_gray(template_path):
    img = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot load template: {template_path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _match_template_at_scale(haystack_gray, template_gray, scale):
    new_w = int(template_gray.shape[1] * scale)
    new_h = int(template_gray.shape[0] * scale)
    if new_w >= haystack_gray.shape[1] or new_h >= haystack_gray.shape[0]:
        return None
    if new_w < 8 or new_h < 8:
        return None
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized = cv2.resize(template_gray, (new_w, new_h), interpolation=interp)
    result = cv2.matchTemplate(haystack_gray, resized, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return {
        "score": float(max_val),
        "loc": max_loc,
        "size": (new_w, new_h),
        "scale": float(scale),
    }


def _multi_scale_template_search(haystack_gray, template_gray):
    best = None
    for scale in _TEMPLATE_COARSE_SCALES:
        r = _match_template_at_scale(haystack_gray, template_gray, scale)
        if r and (best is None or r["score"] > best["score"]):
            best = r
    if best is None:
        return None

    center = best["scale"]
    fine_scales = np.arange(
        max(0.9, center - _TEMPLATE_FINE_WINDOW),
        min(3.1, center + _TEMPLATE_FINE_WINDOW) + _TEMPLATE_FINE_STEP,
        _TEMPLATE_FINE_STEP,
    )
    for scale in fine_scales:
        r = _match_template_at_scale(haystack_gray, template_gray, scale)
        if r and r["score"] > best["score"]:
            best = r
    return best


def detect_template_on_screen(
    template_paths,
    x1,
    x2,
    y1,
    y2,
    confidence_threshold=0.80,
    save_debug_images=False,
    debug_output_dir="images/debug-crops",
    return_coordinates=False,
    screenshot=None,
):
    """
    Take a screenshot, crop by percentage coordinates, and search for a
    template image inside that crop using multi-scale template matching.

    Good for detecting buttons, icons, or any constant pixel pattern that
    signals a popup or page state. Restricting the search to a small crop
    keeps it fast and robust across resolutions/DPI (1080p..4K @ 100/125/150%).

    template_paths: a single path (str/Path) or a list of paths. Multiple
        templates are tried as redundant variants and the best score wins.
    x1, x2, y1, y2: crop area, as 0-100 percentages or 0-1 normalized values.
    confidence_threshold: minimum normalized match score (0..1) to count as
        detected.
    save_debug_images: save the full screenshot, the cropped region, and an
        annotated match visualization under debug_output_dir.
    return_coordinates: if True, also return a dict with the match details.
    screenshot: pass a pre-captured PIL screenshot to reuse it across multiple
        checks in the same UI state and avoid redundant captures.

    Returns:
        detected (bool) by default.
        (detected, info) when return_coordinates=True. `info` keys: template,
            score, scale, x, y, width, height. x, y are absolute screen
            pixels of the match's center (suitable for click targets);
            width, height describe the bounding box. All are None when no
            template matched at all.
    """
    if isinstance(template_paths, (str, Path)):
        template_paths = [template_paths]
    if not template_paths:
        raise ValueError("template_paths must contain at least one path.")

    if screenshot is None:
        screenshot = pyautogui.screenshot()
    screen_width, screen_height = screenshot.size

    x1_ratio = _normalize_percentage_coordinate(x1, "x1")
    x2_ratio = _normalize_percentage_coordinate(x2, "x2")
    y1_ratio = _normalize_percentage_coordinate(y1, "y1")
    y2_ratio = _normalize_percentage_coordinate(y2, "y2")

    if x2_ratio <= x1_ratio or y2_ratio <= y1_ratio:
        raise ValueError(
            "Invalid crop area: x2 must be greater than x1 and y2 greater than y1."
        )

    crop_left = max(0, min(int(screen_width * x1_ratio), screen_width - 1))
    crop_top = max(0, min(int(screen_height * y1_ratio), screen_height - 1))
    crop_right = max(crop_left + 1, min(int(screen_width * x2_ratio), screen_width))
    crop_bottom = max(crop_top + 1, min(int(screen_height * y2_ratio), screen_height))

    crop_pil = screenshot.crop((crop_left, crop_top, crop_right, crop_bottom))
    crop_bgr = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)
    crop_gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)

    best = None
    for path in template_paths:
        template_gray = _load_template_gray(str(path))
        result = _multi_scale_template_search(crop_gray, template_gray)
        if result is None:
            continue
        result["template"] = Path(path).stem
        if best is None or result["score"] > best["score"]:
            best = result

    if best is None:
        info = {
            "template": None,
            "score": 0.0,
            "scale": None,
            "x": None,
            "y": None,
            "width": None,
            "height": None,
        }
        detected = False
    else:
        loc_x, loc_y = best["loc"]
        w, h = best["size"]
        info = {
            "template": best["template"],
            "score": best["score"],
            "scale": best["scale"],
            "x": crop_left + loc_x + w // 2,
            "y": crop_top + loc_y + h // 2,
            "width": w,
            "height": h,
        }
        detected = info["score"] >= confidence_threshold

    if save_debug_images:
        _save_template_debug_images(
            screenshot,
            crop_pil,
            crop_bgr,
            info,
            (crop_left, crop_top),
            debug_output_dir,
        )

    if return_coordinates:
        return detected, info
    return detected


def _save_template_debug_images(
    screenshot, crop_pil, crop_bgr, info, crop_origin, debug_output_dir
):
    output_dir = Path(debug_output_dir)
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    screenshot.save(output_dir / f"screen_{timestamp}.png")
    crop_pil.save(output_dir / f"template_crop_{timestamp}.png")

    if info.get("template") is None:
        return

    annotated = crop_bgr.copy()
    crop_left, crop_top = crop_origin
    w, h = int(info["width"]), int(info["height"])
    # info x,y are the match center; recover top-left for the bounding box
    rel_x = int(info["x"] - crop_left - w // 2)
    rel_y = int(info["y"] - crop_top - h // 2)
    cv2.rectangle(annotated, (rel_x, rel_y), (rel_x + w, rel_y + h), (0, 255, 0), 2)
    label = f"{info['template']} {info['score']:.3f} @ {info['scale']:.2f}x"
    cv2.putText(
        annotated,
        label,
        (rel_x, max(rel_y - 8, 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
    )
    cv2.imwrite(str(output_dir / f"template_match_{timestamp}.png"), annotated)


if __name__ == "__main__":
    time.sleep(5)  # Time to switch to the target screen before OCR
    # words, coordinates = extract_center_words_from_screen(
    #     **CHECK_OUT_TITLE_COORDS, kernel_size=(3,3),
    #     save_debug_images=True,
    #     return_coordinates=True
    # )
    # print("OCR-detected words:", words)

    # test_screenshot = Image.open("images/detail4k150.png")
    
    detected, info = detect_template_on_screen(
        template_paths=["images/select-new/image.png"],
        **EASY_NAVIGATOR_TITLE_COORDS,
        save_debug_images=True,
        return_coordinates=True
    )
    print(f"Detected: {detected}")
    print(f"Detection info: {info}")
