
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
from auto_common import CHECK_OUT_TITLE_COORDS, INVOICE_NUMBER_COORDS, INVOICE_PAID_FULL_MODAL_COORDS, INVOIE_SUMMARY_BLOCK_COORDS, RETURN_REMAININGS_MODAL_COORDS, PRINTER_POPUP_COORDS, CREDIT_DETAILS_COORDS
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
    words = extract_center_words_from_screen(**INVOICE_NUMBER_COORDS, kernel_size=(3,3))
    log_fn(f"OCR-detected words for bidcard  number check: {" ".join(words).lower()}")
    for word in words:
        if bidcard_num in word:
            return True
    return False


import cv2
import numpy as np
from pathlib import Path


class ButtonDetector:
    def __init__(self, template_paths, search_region_ratio=None):
        """
        template_paths: 模板图片路径列表，可以传 1-3 张冗余模板
                        例如：完整按钮 + 单独的绿色✓图标
        search_region_ratio: (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
                             例如 (0.75, 0.15, 1.0, 0.75) 表示只在右侧 Summary 区域搜
                             None 表示全图搜
        """
        self.templates = []
        for path in template_paths:
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(f"Cannot load template: {path}")
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self.templates.append({
                'name': Path(path).stem,
                'gray': gray,
                'h': gray.shape[0],
                'w': gray.shape[1],
            })
        self.search_region_ratio = search_region_ratio

        # Scale 范围：覆盖 1080p/2K/4K × 100/125/150% 全部组合
        # 粗扫步长 0.1，细扫步长 0.02
        self.coarse_scales = np.arange(0.9, 3.11, 0.1)
        self.fine_step = 0.02
        self.fine_window = 0.12  # 在最佳粗扫尺度 ±0.12 范围内细扫

    def _crop_search_region(self, screenshot_gray):
        if self.search_region_ratio is None:
            return screenshot_gray, (0, 0)
        h, w = screenshot_gray.shape
        x1r, y1r, x2r, y2r = self.search_region_ratio
        x1, y1 = int(w * x1r), int(h * y1r)
        x2, y2 = int(w * x2r), int(h * y2r)
        return screenshot_gray[y1:y2, x1:x2], (x1, y1)

    def _match_at_scale(self, screenshot, template, scale):
        new_w = int(template['w'] * scale)
        new_h = int(template['h'] * scale)

        # 模板不能比搜索区域大，也不能太小
        if new_w >= screenshot.shape[1] or new_h >= screenshot.shape[0]:
            return None
        if new_w < 8 or new_h < 8:
            return None

        # 缩小用 INTER_AREA，放大用 INTER_CUBIC
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        resized = cv2.resize(template['gray'], (new_w, new_h), interpolation=interp)

        result = cv2.matchTemplate(screenshot, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return {
            'score': max_val,
            'loc': max_loc,
            'size': (new_w, new_h),
            'scale': scale,
        }

    def _multi_scale_search(self, screenshot, template):
        """两阶段：粗扫 + 细扫"""
        # 阶段 1：粗扫
        best = None
        for scale in self.coarse_scales:
            result = self._match_at_scale(screenshot, template, scale)
            if result and (best is None or result['score'] > best['score']):
                best = result
        
        if best is None:
            return None

        # 阶段 2：在最佳粗扫尺度附近细扫
        center = best['scale']
        fine_scales = np.arange(
            max(0.9, center - self.fine_window),
            min(3.1, center + self.fine_window) + self.fine_step,
            self.fine_step,
        )
        for scale in fine_scales:
            result = self._match_at_scale(screenshot, template, scale)
            if result and result['score'] > best['score']:
                best = result
        
        return best

    def detect(self, screenshot_bgr, threshold=0.75, verbose=False):
        """
        返回 (是否检测到, 详细信息)
        screenshot_bgr: cv2.imread 读出来的 BGR 图像
        """
        screenshot_gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)
        cropped, offset = self._crop_search_region(screenshot_gray)

        results = []
        for template in self.templates:
            best = self._multi_scale_search(cropped, template)
            if best is not None:
                # 把坐标还原到全图
                best['loc'] = (best['loc'][0] + offset[0], best['loc'][1] + offset[1])
                best['template'] = template['name']
                results.append(best)

        if not results:
            return False, {'reason': 'no match', 'all_results': []}

        # 取所有模板里分数最高的
        best_overall = max(results, key=lambda r: r['score'])
        detected = best_overall['score'] >= threshold

        if verbose:
            print(f"[Detect] template={best_overall['template']} "
                  f"score={best_overall['score']:.4f} "
                  f"scale={best_overall['scale']:.2f} "
                  f"loc={best_overall['loc']} "
                  f"detected={detected}")

        return detected, {
            'best': best_overall,
            'all_results': results,
        }

    def visualize(self, screenshot_bgr, detect_info, output_path='debug_match.png'):
        """画出匹配框，调试用"""
        if 'best' not in detect_info:
            return
        best = detect_info['best']
        x, y = best['loc']
        w, h = best['size']
        out = screenshot_bgr.copy()
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(out, f"{best['score']:.3f} @ {best['scale']:.2f}x",
                    (x, max(y - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imwrite(output_path, out)


if __name__ == "__main__":
    # time.sleep(5)  # Time to switch to the target screen before OCR
    # words, coordinates = extract_center_words_from_screen(
    #     **CHECK_OUT_TITLE_COORDS, kernel_size=(3,3),
    #     save_debug_images=True,
    #     return_coordinates=True
    # )
    # print("OCR-detected words:", words)


    detector = ButtonDetector(
        template_paths=[
            # 'images/apply-deposit/image-1080-100.png',    # 只有绿色 ✓ 的小模板（兜底）
            'images/edit-button/image.png',     # 完整按钮模板
        ],
        search_region_ratio=(0.0, 0.0, 1, 1),  # 只在 Summary 区域搜
    )
    
    screenshot = cv2.imread('images/detail4k150.png')
    detected, info = detector.detect(screenshot, threshold=0.85, verbose=True)
    print(f"Detection info: {info}")
    print(f"Apply Deposit button present: {detected}")

    # # 调试：画出匹配框
    detector.visualize(screenshot, info, 'debug.png')
