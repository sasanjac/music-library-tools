#!/usr/bin/python3
import os
import sys
import time
from pathlib import Path

import schedule
from loguru import logger

from music_library_tools.music_cleanup_daemon import MusicCleanupDaemon
from music_library_tools.music_import_daemon import MusicImportDaemon
from music_library_tools.plex_daemon import PlexDaemon

logger.remove()
logger.add(sys.stderr, colorize=True, format="<level>{message}</level>")  # noqa

import_path = Path("/data/import")
todo_path = Path("/data/todo")
export_electro_path = Path("/data/export_electro")
export_general_path = Path("/data/export_general")
plex_url = os.environ["PLEX_URL"]
token = os.environ["PLEX_TOKEN"]
base_path = "/data/export_electro"

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

pd = PlexDaemon(
    plex_url=plex_url,
    token=token,
    base_path=base_path,
)

pd.check_and_fix_duplicates()
schedule.every(24).hours.do(pd.check_and_fix_duplicates)
pd.update_labels()
schedule.every(24).hours.do(pd.update_labels)

while True:
    schedule.run_pending()
    time.sleep(10)
