#!/usr/bin/python3

from pathlib import Path
import schedule
import time

IMPORT_DIR = Path("/data/import")
TODO_DIR = Path("/data/todo")
OUTPUT_DIR = Path("/data/export_electro")
OUTPUT_DIR_GEN = Path("/data/export_general")


schedule.every(15).minutes.do(music_import_daemon)

while True:
    schedule.run_pending()
    time.sleep(1)
