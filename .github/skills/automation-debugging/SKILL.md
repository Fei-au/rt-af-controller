---
name: "automation-debugging"
description: "Debug, step through, and safely enhance Tkinter automation flows. Use when: fixing broken interaction sequences, adding safety checks, diagnosing OCR/click failures, profiling performance bottlenecks, or improving error handling in auto_add_credit.py or auto_deduct_credit.py without rewriting core logic."
---

# Automation Flow Debugging and Enhancement

This skill provides structured workflows for troubleshooting and improving the store-credit automation flows (`auto_add_credit.py` and `auto_deduct_credit.py`) while preserving their delicate state-machine logic and stop-handling semantics.

## Session Strategy

### 1. Understand the Automation Context

Before modifying any automation flow, confirm:
- **Entry point**: Which automation flow? (`auto_add_credit()` or `auto_deduct_credit()`)
- **Inputs**: What CSV record or data is being processed?
- **Expected state sequence**: What UI elements appear in what order?
- **Current failure**: Where does it break? (UI element not found, OCR fails, timeout, etc.)

**Check these first:**
- Is `auto_common.py` shared behavior or flow-specific logic?
- Does the flow use `set_stop_checker()` to allow user interruption?
- Are there image crops being stored in `images/debug-crops/` for OCR testing?

### 2. Debugging Decision Tree

```
├─ Interaction fails (element not found, click doesn't work, typing fails)
│  ├─ Enable debug screenshots → capture_screen() in tools.py.wait_for_element()
│  ├─ Check element locator (xPath, image template)
│  ├─ Verify page state (is menu open? did previous action complete?)
│  └─ [MINIMAL EDIT] Adjust wait timeout or add explicit state check
│
├─ OCR returns wrong text or empty
│  ├─ Check if image crop is visible and contains readable text
│  ├─ Verify Tesseract is installed and TESSERACT_CMD or PATH is correct
│  ├─ Test with debug crop: read_text_from_image(crop_path)
│  └─ [MINIMAL EDIT] Adjust ROI, rescale image, or preprocess (binarize, denoise)
│
├─ CSV record not updating or status not written
│  ├─ Confirm service.py read_records_from_csv() parsed the row correctly
│  ├─ Check row_offset is being passed to automation flow
│  ├─ Verify CSV file path and write permissions
│  └─ [MINIMAL EDIT] Add missing status/details column or fix field mapping
│
├─ Automation doesn't respect interruption (stop_requested not checked)
│  ├─ Grep for check_stop_requested() calls in flow
│  ├─ Find long-running loops (waits, retries) with no stop check
│  └─ [MINIMAL EDIT] Add stop check at loop boundaries and before critical actions
│
└─ Performance is slow or timeout occurs
   ├─ Profile: Add timestamps or logging before/after sections
   ├─ Identify bottleneck: OCR, wait loops, API calls?
   └─ [MINIMAL EDIT] Tune wait times, add early-exit conditions, parallelize where safe
```

### 3. Code Review Checklist for Changes

**Before committing any automation flow edit:**

- [ ] **State sequence preserved?** New code does not skip or reorder critical steps (login → search → add/deduct → confirm).
- [ ] **Stop handling respected?** Long-running loops call `check_stop_requested()`; no endless waits.
- [ ] **CSV schema stable?** If updating CSV columns, changes are additive (new `details`, `errors`, `status`); no renaming or removal.
- [ ] **Shared behavior isolated?** Flow-specific logic stays in `auto_add_credit.py` / `auto_deduct_credit.py`; shared helpers stay in `auto_common.py`.
- [ ] **Error handling defensive?** File access, OCR, element clicks wrapped in try-except; status/details logged to CSV.
- [ ] **Minimal edit principle?** Only the problematic lines changed; surrounding logic untouched unless fixing a direct root cause.

### 4. Common Patterns

#### Adding a Safety Check Without Rewriting

```python
# BEFORE (fails silently or hangs)
browser.find_element(By.XPATH, "//*[@id='submit']").click()

# AFTER (defensive, with logging)
try:
    submit_btn = browser.find_element(By.XPATH, "//*[@id='submit']")
    submit_btn.click()
except NoSuchElementException:
    update_csv_record(record, status='error', details='Submit button not found')
    return False
```

#### Enabling Graceful Interruption

```python
# BEFORE (no stop check in loop)
for attempt in range(max_retries):
    result = attempt_action()
    if result:
        return True
    time.sleep(wait_interval)

# AFTER (respects stop requests)
for attempt in range(max_retries):
    if check_stop_requested():
        update_csv_record(record, status='stopped', details='User interrupted')
        return False
    result = attempt_action()
    if result:
        return True
    time.sleep(wait_interval)
```

#### Debugging OCR with Image Crops

```python
from tools import read_text_from_image

# Save a crop for inspection
crop_path = "images/debug-crops/invoice_field.png"
ocr_text = read_text_from_image(crop_path)
print(f"OCR result: {ocr_text}")

# If OCR fails, test preprocessing
from PIL import Image, ImageOps, ImageFilter
img = Image.open(crop_path).convert('L')  # Grayscale
img = ImageOps.autocontrast(img)
ocr_text = read_text_from_image(img)  # Retry with preprocessed image
```

### 5. Testing Isolated Flow Changes

**Before running full automation:**

1. **Unit test the changed section** in isolation:
   ```python
   # Extract the problematic function into a test file
   from auto_add_credit import wait_for_invoice_field
   
   # Mock or use a real browser session
   result = wait_for_invoice_field(mock_browser, timeout=5)
   assert result is not None
   ```

2. **Run with a single CSV record** to catch errors early:
   - Edit the CSV to retain only 1 row.
   - Run automation and monitor for the expected behavior.
   - Check CSV output for correct `status`, `details`, and `errors` columns.

3. **Inspect debug artifacts**:
   - Check `images/debug-crops/` for OCR crops.
   - Review logs or print statements for timing and element state.
   - Compare with successful prior runs if available.

### 6. Environment and Setup Validation

Before debugging automation flow logic, ensure:

- [ ] **Python environment active**: Check that `.venv` is activated.
- [ ] **`.env` file present**: `LOG_BACK` set for GraphQL, `TESSERACT_CMD` or Tesseract in PATH.
- [ ] **Dependencies installed**: `pip install -r requirements.txt`.
- [ ] **Browser setup ready**: Selenium or Playwright is properly configured; no stale processes.
- [ ] **CSV file valid**: Required headers present, encodings correct (`utf-8-sig`), paths writable.

### 7. Conversation Workflow

When asked to fix or enhance an automation flow:

1. **Ask clarifying questions** if not provided:
   - Which flow? (add or deduct)
   - What is the failure mode? (element not found, timeout, OCR error, etc.)
   - Does it fail consistently or intermittently?
   - Are there logs or debug screenshots available?

2. **Search the codebase** for similar patterns or prior fixes:
   - Use grep to find how other flows handle the same issue.
   - Check `auto_common.py` for existing helpers.

3. **Make the minimal edit**:
   - Identify the exact line or block causing the issue.
   - Fix only that—do not refactor surrounding logic unless it's the root cause.
   - Preserve all stop-check calls and state-machine ordering.

4. **Validate and document**:
   - Run a test with a single CSV record.
   - Confirm the fix resolves the issue without breaking state sequencing.
   - Update the related flow's docstring if new behavior is introduced.

## Common Issues and Quick Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Element not found after click | Page didn't navigate or element loaded late | Add explicit wait with `wait_for_element(timeout)` or poll page state |
| OCR returns empty string | Image crop has no text or is too small | Expand ROI, increase image resolution, or binarize image |
| CSV record not updating | `row_offset` not passed through flow | Confirm `record['row_offset']` is threaded through all helpers |
| Timeout during automation | Wait interval too short or element stuck | Increase timeout, add early-exit check in loop, or add stop-check call |
| Automation doesn't stop on user interrupt | No stop-check in long loop | Add `if check_stop_requested(): return False` in loop or before critical action |
| GraphQL mutation fails silently | LOG_BACK env var not set or network issue | Validate .env, test GraphQL endpoint with curl, check network logs |

## Key References

- **Main entry**: `main.py` — loads `.env` before UI imports.
- **UI layer**: `tkinter_gui.py` — orchestrates automation on worker threads.
- **Automation flows**: `auto_add_credit.py`, `auto_deduct_credit.py` — state machines; preserve ordering and stop handling.
- **Shared logic**: `auto_common.py` — common UI interactions and waits.
- **OCR/images**: `tools.py` — Tesseract integration, image cropping, element location.
- **CSV/GraphQL**: `service.py` — CSV parsing, refund/deduct mutations; stable schema.
