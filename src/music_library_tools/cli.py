# Copyright (c) 2024-2025 Sasan Jacob Rasti

from __future__ import annotations

import pathlib
import sys
import time

import schedule
from loguru import logger

from music_library_tools.music_cleanup_daemon import MusicCleanupDaemon
from music_library_tools.music_import_daemon import MusicImportDaemon


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, colorize=True, format="<level>{message}</level>")

    import_path = pathlib.Path("/data/import")
    todo_path = pathlib.Path("/data/todo")
    export_electro_path = pathlib.Path("/data/export_electro")
    export_general_path = pathlib.Path("/data/export_general")


    mid = MusicImportDaemon(
        import_path=import_path,
        todo_path=todo_path,
        export_electro_path=export_electro_path,
        export_general_path=export_general_path,
    )

    mid.import_music()
    schedule.every(5).minutes.do(mid.import_music)

    mcd = MusicCleanupDaemon(
        todo_path=todo_path,
        export_path=export_electro_path,
    )

    mcd.cleanup_music()
    schedule.every(5).minutes.do(mcd.cleanup_music)

    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    main()