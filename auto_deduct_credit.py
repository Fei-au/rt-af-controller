import pygetwindow as gw
import pyautogui
import time
import pandas as pd
from pynput.keyboard import Key, Controller

from pathlib import Path

from service import read_deduct_records_from_csv


CSV_FILE_PATH = ""
def processing(csv_file_path, log_fn=print, should_stop_fn=None):
	file_path = Path(csv_file_path)
	if not file_path.exists():
		raise FileNotFoundError(f"CSV file not found: {file_path}")

	auction_id, records = read_deduct_records_from_csv(csv_file_path)
	log_fn(f"Loaded {len(records)} deduct records from {csv_file_path}")

	for record in records:
		if should_stop_fn and should_stop_fn():
			log_fn("Deduct process stopped by user.")
			return "Deduct process stopped."

		log_fn(f"Deduct flow placeholder for invoice {record['invoice_number']}.")
		time.sleep(0.1)

	return f"Deduct process completed for {len(records)} records."


