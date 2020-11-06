#!/usr/bin/python3

import time
from pathlib import Path

import schedule

from .music_import_daemon import MusicImportDaemon


def run():
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

    while True:
        schedule.run_pending()
        time.sleep(1)
