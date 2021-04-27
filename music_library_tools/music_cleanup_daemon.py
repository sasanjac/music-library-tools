import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from pathvalidate import sanitize_filepath
from tinytag import TinyTag

from music_library_tools import utils

logger.add(sys.stdout, colorize=True)


@dataclass
class MusicCleanupDaemon:
    todo_path: Path
    export_path: Path

    def cleanup_music(self) -> None:
        album_dirs = [f for d in self.todo_path.iterdir() if d.is_dir() for f in d.iterdir() if f.is_dir()]
        logger.info("Starting Music Cleanup")
        logger.info("Processing %s albums", len(album_dirs))

        for alb_dir in album_dirs:
            try:
                logger.info("Cleaning up %s", alb_dir)
                try:
                    alb_dir.rmdir()
                except OSError:
                    pass
                files = [f for f in alb_dir.iterdir() if f.suffix in [".flac", ".mp3"]]
                if len(files) == 0:
                    logger.info("%s is empty", alb_dir)
                for f in files:
                    tag = TinyTag.get(str(alb_dir / f))

                    album_artist = tag.albumartist
                    if album_artist is None:
                        logger.info("%s does not have an album artist", alb_dir)
                        continue

                    album = tag.album

                    try:
                        isrc, *album = album.split(" - ")
                        album = " - ".join(album)
                    except Exception:
                        logger.info("Can't split album for %s", album)
                        isrc = "TODO"

                    if isrc == "TODO":
                        continue

                    title = tag.title
                    track = tag.track

                    album = f"{isrc} - {album}"

                    file_output_dir = self.export_path / album_artist.replace("/", "_") / album.replace("/", "_")
                    file_export_path = file_output_dir / f"{int(track):02d} {title.replace('/', '_')}{f.suffix}"

                    output_file = sanitize_filepath(
                        file_export_path,
                        platform="linux",
                    )

                    logger.info("Correcting file %s to %s", f, output_file)
                    file_output_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), output_file)

                utils.delete_dir(alb_dir)
            except Exception:
                logger.exception("Exception in program while processing %s:", alb_dir)

        artist_dirs = [d for d in self.todo_path.iterdir() if d.is_dir()]
        for art_dir in artist_dirs:
            utils.delete_dir(art_dir)
        logger.info("Completed Music Cleanup successfully")
