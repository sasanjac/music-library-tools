#!/usr/bin/python3

import logging
import time
from pathlib import Path

import schedule

from music_library_tools.music_cleanup_daemon import MusicCleanupDaemon
from music_library_tools.music_import_daemon import MusicImportDaemon

logging.basicConfig(format="%(asctime)-15s %(message)s", level=logging.INFO)

import_path = Path("/data/import")
todo_path = Path("/data/todo")
export_electro_path = Path("/data/export_electro")
export_general_path = Path("/data/export_general")


mid = MusicImportDaemon(
    import_path=import_path,
    todo_path=todo_path,
    export_electro_path=export_electro_path,
    export_general_path=export_general_path,
)

mid.import_music()
schedule.every(15).minutes.do(mid.import_music)

mcd = MusicCleanupDaemon(
    todo_path=todo_path,
    export_path=export_electro_path,
)

mcd.cleanup_music()
schedule.every(15).minutes.do(mcd.cleanup_music)

while True:
    schedule.run_pending()
    time.sleep(1)
