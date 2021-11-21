import shutil
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from tinytag import TinyTag

from music_library_tools import utils


@dataclass
class MusicCleanupDaemon:
    todo_path: Path
    export_path: Path

    def cleanup_music(self) -> None:
        album_dirs = [f for d in self.todo_path.iterdir() if d.is_dir() for f in d.iterdir() if f.is_dir()]
        if len(album_dirs) > 0:
            logger.info("Starting Music Cleanup")
            logger.info(f"Processing {len(album_dirs)} albums")

            for alb_dir in album_dirs:
                try:
                    logger.info(f"Checking {alb_dir}")
                    try:
                        alb_dir.rmdir()
                    except OSError:
                        pass
                    files = [f for f in alb_dir.iterdir() if f.suffix in [".flac", ".mp3"]]
                    if len(files) == 0:
                        logger.info(f"{alb_dir} is empty")
                    next_album = False
                    for f in files:
                        if next_album:
                            continue

                        tag = TinyTag.get(alb_dir / f)

                        album_artist = tag.albumartist
                        if album_artist is None:
                            logger.info(f"{alb_dir} does not have an album artist")
                            next_album = True
                            continue

                        album = tag.album

                        try:
                            isrc, *album = album.split(" - ")
                            album = " - ".join(album)
                        except Exception:
                            logger.info(f"Can't split album for {album}")
                            isrc = "TODO"

                        if isrc == "TODO":
                            logger.info(f"ISCR must be set first for {alb_dir}")
                            next_album = True
                            continue

                        title = tag.title
                        track = tag.track

                        album = f"{isrc} - {album}"

                        file_output_dir = self.export_path / album_artist.replace("/", "_") / album.replace("/", "_")
                        file_export_path = file_output_dir / f"{int(track):02d} {title.replace('/', '_')}{f.suffix}"

                        output_file = utils.sanitize_file_path(file_export_path)

                        file_output_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(f, output_file)

                    logger.info(f"Corrected album {alb_dir}")
                    utils.delete_dir(alb_dir)
                except Exception:
                    logger.error(f"Exception in program while processing {alb_dir}: e")

            artist_dirs = [d for d in self.todo_path.iterdir() if d.is_dir()]
            for art_dir in artist_dirs:
                utils.delete_dir(art_dir)
            logger.info("Completed Music Cleanup successfully")
