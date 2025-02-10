# Copyright (c) 2024-2025 Sasan Jacob Rasti

from __future__ import annotations

import contextlib
import shutil
import typing as t
from dataclasses import dataclass

from loguru import logger
from tinytag import TinyTag

from music_library_tools import utils

if t.TYPE_CHECKING:
    import pathlib


@dataclass
class MusicCleanupDaemon:
    todo_path: pathlib.Path
    export_path: pathlib.Path

    def cleanup_music(self) -> None:
        album_paths = [f for d in self.todo_path.iterdir() if d.is_dir() for f in d.iterdir() if f.is_dir()]
        if len(album_paths) > 0:
            logger.info("Starting Music Cleanup")
            logger.info(f"Processing {len(album_paths)} albums")

            for album_path in album_paths:
                self.cleanup_album(album_path=album_path)

            artist_dirs = [d for d in self.todo_path.iterdir() if d.is_dir()]
            for art_dir in artist_dirs:
                utils.safe_delete_path(art_dir)

            logger.info("Completed Music Cleanup successfully")

    def cleanup_album(self, album_path: pathlib.Path) -> None:
        try:
            self._cleanup_album(album_path)
        except ValueError:
            logger.exception(f"Exception in program while processing album {album_path}")

    def _cleanup_album(self, album_path: pathlib.Path) -> None:
        with contextlib.suppress(OSError):
            album_path.rmdir()

        files = [f for f in album_path.iterdir() if f.suffix in {".flac", ".mp3"}]
        if len(files) == 0:
            logger.error(f"{album_path} is empty")

        for f in files:
            tag = TinyTag.get(album_path / f)

            album_artist = tag.albumartist
            if album_artist is None:
                logger.error(f"{album_path} does not have an album artist")
                return

            album = tag.album
            if album is None:
                logger.error(f"Album tag is None for {album_path}")
                return

            isrc, *rest = album.split(" - ")
            album = " - ".join(rest)

            if isrc == "TODO":
                logger.error(f"ISCR must be set first for {album_path}")
                return

            title = tag.title
            if title is None:
                logger.error(f"Title tag is None for {album_path}")
                return

            track = tag.track
            if track is None:
                logger.error(f"Track tag is None for {album_path}")
                return

            album = f"{isrc} - {album}"

            file_output_dir = self.export_path / album_artist.replace("/", "_") / album.replace("/", "_")
            file_export_path = file_output_dir / f"{int(track):02d} {title.replace('/', '_')}{f.suffix}"

            output_dir = utils.sanitize_file_path(file_output_dir, file_only=False)
            output_file = utils.sanitize_file_path(file_export_path)

            logger.debug(f"Creating {output_file}")
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(f, output_file)

        logger.info(f"Corrected album {album_path} to {output_dir}")
        utils.safe_delete_path(album_path)
