#! /usr/bin/python
from __future__ import annotations

import os
import pathlib
import sys
import time

import schedule
import watchdog.events as we
import watchdog.observers as wo
from loguru import logger

from music_library_tools.music_cleanup_daemon import MusicCleanupDaemon
from music_library_tools.music_import_daemon import MusicImportDaemon

logger.remove()
logger.add(sys.stderr, colorize=True, format="<level>{message}</level>")

import_path = pathlib.Path("/data/import")
todo_path = pathlib.Path("/data/todo")
export_electro_path = pathlib.Path("/data/export_electro")
export_general_path = pathlib.Path("/data/export_general")
plex_url = os.environ["PLEX_URL"]
token = os.environ["PLEX_TOKEN"]
base_path = "/data/export_electro"


class MIDHandler(we.FileSystemEventHandler):
    def __init__(self, mid: MusicImportDaemon) -> None:
        self._mid = mid

    def on_created(self, event: we.DirCreatedEvent | we.FileCreatedEvent) -> None:
        src_path = pathlib.Path(event.src_path)
        if event.is_directory and src_path.exists():
            time.sleep(15)
            files = [f for f in src_path.iterdir() if f.suffix == ".flac"]
            if len(files) > 0:
                for _ in range(6):
                    if int(files[-1].name.split(" - ")[0]) == len(files):
                        self._mid.import_album(album_path=src_path)
                        return

                    time.sleep(5)
                    files = [f for f in src_path.iterdir() if f.suffix == ".flac"]

                logger.error(f"{src_path!s} can not be imported. Missing files.")


class MCDHandler(we.FileSystemEventHandler):
    def __init__(self, mcd: MusicCleanupDaemon) -> None:
        self._mcd = mcd

    def on_modified(self, event: we.FileModifiedEvent | we.DirModifiedEvent) -> None:
        src_path = pathlib.Path(event.src_path)
        if not self.is_directory and src_path.parent.exists():
            time.sleep(5)
            self._mcd.cleanup_album(album_path=src_path.parent)


mid = MusicImportDaemon(
    import_path=import_path,
    todo_path=todo_path,
    export_electro_path=export_electro_path,
    export_general_path=export_general_path,
)

mid.import_music()
mid_observer = wo.Observer()
mid_handler = MIDHandler(mid=mid)
mid_observer.schedule(mid_handler, import_path, recursive=True)
mid_observer.start()

mcd = MusicCleanupDaemon(
    todo_path=todo_path,
    export_path=export_electro_path,
)

mcd.cleanup_music()
mcd_observer = wo.Observer()
mcd_handler = MCDHandler(mcd=mcd)
mcd_observer.schedule(mcd_handler, todo_path, recursive=True)
mcd_observer.start()


try:
    while True:
        schedule.run_pending()
        time.sleep(10)
except KeyboardInterrupt:
    mid_observer.stop()
    mcd_observer.stop()

mid_observer.join()
mcd_observer.join()
