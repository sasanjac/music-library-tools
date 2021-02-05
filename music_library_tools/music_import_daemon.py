import json
import logging
import re
import shutil
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests
from pathvalidate import sanitize_filepath

from music_library_tools import utils

logger = logging.getLogger()

ELECTRO_GENRES = ["TECHNO", "HOUSE", "ELECTRO", "DANCE"]

MIX_STRS = ["MIX", "REMIX", "EDIT", "REWORK", "BOOTLEG", "VERSION", "DUB", "ENACTMENT"]


@dataclass
class MusicImportDaemon:
    import_path: Path
    todo_path: Path
    export_electro_path: Path
    export_general_path: Path

    def _prepare_files(self, dir: Path) -> List[Path]:
        files = [f for f in dir.iterdir() if f.is_file()]
        if any([f.suffix == ".temp" for f in files]):
            raise ValueError("Album not finished downloading.")
        if any(["errors.txt" in files]):
            with (dir / "errors.txt").open() as f:
                file_contents = f.read()
                raise ValueError(file_contents)
        files = [f for f in files if (f.suffix == ".flac" or f.suffix == ".mp3")]
        if len(files) == 0:
            raise ValueError("No files in album.")
        return files

    def _check_track_numbers(self, files: List[Path]) -> None:
        audio_format = utils.get_audio_format(files[0])
        track_nos = [int(audio_format(str(f))["tracknumber"][0]) for f in files]
        if not max(track_nos) == len(track_nos):
            raise ValueError("Less audio files than tracks in album.")

    def _filter_general_music(self, file: Path) -> None:
        audio_format = utils.get_audio_format(file)
        try:
            genre = " ".join(audio_format(str(file))["genre"]).upper()
            if not any([g in genre for g in ELECTRO_GENRES]):
                export_path = self.export_general_path / file.parent.parent.name / file.parent.name
                export_path.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file.parent), str(export_path))
                raise ValueError("Album is moved to general music.")
        except KeyError:
            pass

    def _compile_album_artists(self, files: List[Path]) -> str:
        audio_format = utils.get_audio_format(files[0])
        try:
            artists = [e for f in files for e in audio_format(str(f))["artist"][0].split(", ")]
        except KeyError:
            try:
                artists = [e for f in files for e in audio_format(str(f))["albumartist"][0].split(", ")]
            except KeyError:
                raise ValueError("Could not find artists.")

        if len(set(artists)) != 1:
            return "Various Artists"
        else:
            audio_file = audio_format(str(files[0]))
            try:
                return audio_file["albumartist"][0]
            except Exception:
                return audio_file["artist"][0]

    def _create_request(self, files: List[Path], id3_data: Dict[str, str]) -> str:
        audio_format = utils.get_audio_format(files[0])
        audio_file = audio_format(str(files[0]))
        req_album = urllib.parse.quote_plus(id3_data["album"])
        if id3_data["albumartist"] == "Various Artists":
            req_artist = ""
        else:
            req_artist = urllib.parse.quote_plus(id3_data["albumartist"])

        try:
            req_year = audio_file["year"][0].split("-")[0]
        except Exception:
            req_year = ""
        return f"https://www.beatport.com/search?q={req_album}+{req_artist}+{req_year}"

    def _create_label_tag(self, files: List[Path]) -> str:
        audio_format = utils.get_audio_format(file=files[0])
        audio_file = audio_format(str(files[0]))
        try:
            rv = audio_file["organization"]
        except Exception:
            try:
                rv = audio_file["publisher"]
            except Exception:
                logger.exception("Can't determine label.")
                rv = ""
        return rv

    def _get_id3_from_beatport(self, files: List[Path], id3_data: Dict[str, str]):
        req_str = self._create_request(files=files, id3_data=id3_data)
        try:
            ids = requests.get(req_str).text.split('href="/release/')[1:]
            ids = [i.split('"')[0] for i in ids]
            ids = list(set(ids))
            for id in ids:
                r = requests.get("https://www.beatport.com/release/" + id)
                rdata = utils.split_from_to(r.text, ['<script type="application/ld+json">'], "</script>")
                data = json.loads(rdata)
                data = [d for d in data if d["@type"] == "MusicRelease"]
                data = data[0]
                bp_album = data["name"]
                bp_albumartist = data["@producer"][0]["name"]
                bp_label = data["recordLabel"]["name"]
                bp_albums = [bp_album.upper(), utils.replace_all(bp_album.upper())]
                bp_albumartists = [bp_albumartist.upper(), utils.replace_all(bp_albumartist.upper())]
                bp_labels = [bp_label.upper(), utils.replace_all(bp_label.upper())]
                albums = [id3_data["album"].upper(), utils.replace_all(id3_data["album"])]
                albumartists = [id3_data["albumartist"].upper(), utils.replace_all(id3_data["albumartist"].upper())]
                labels = [id3_data["label"].upper(), utils.replace_all(id3_data["label"].upper())]
                print(bp_labels)
                print(labels)
                if (
                    any(i in bp_albums for i in albums)
                    and any(i in bp_albumartists for i in albumartists)
                    and any(i in bp_labels for i in labels)
                ):
                    isrc_str = data["catalogNumber"]
                    try:
                        isrc = re.split(r"(\d+)", isrc_str)[:3]
                        if isrc[2] in ["DIG", "CD", "DIGITAL"]:
                            isrc[2] = ""
                        id3_data["isrc"] = "".join(isrc)
                    except Exception:
                        id3_data["isrc"] = isrc_str
                    id3_data["genre"] = utils.split_from_to(r.text, ['"genres":', '"name": "'], '"')
                    return id3_data
            raise IndexError
        except Exception:
            id3_data["isrc"] = "TODO"
            return id3_data

    def _create_export_path(self, id3_data: Dict[str, str]) -> Path:
        albumartist = id3_data["albumartist"].replace("/", "_")
        album = id3_data["album"].replace("/", "_")
        if id3_data["isrc"] != "TODO":
            export_path = self.export_electro_path / albumartist / (id3_data["isrc"] + " - " + album)
        else:
            export_path = self.todo_path / albumartist / (id3_data["isrc"] + " - " + album)
        export_path = Path(sanitize_filepath(export_path, platform="linux"))
        logger.debug("Creating output dir: %s", export_path)
        export_path.mkdir(parents=True, exist_ok=True)
        return export_path

    def _finalize_file(self, file: Path, id3_data: Dict[str, str]) -> None:
        audio_format = utils.get_audio_format(file=file)
        audio_file = audio_format(str(file))
        audio_file["isrc"] = id3_data["isrc"]
        audio_file["album"] = id3_data["isrc"] + " - " + audio_file["album"][0]
        audio_file["genre"] = id3_data["genre"]
        audio_file["label"] = id3_data["label"]

        title = audio_file["title"][0]
        # Add Original Mix if no already there
        if not any([mix_str in title.upper() for mix_str in MIX_STRS]):
            title += " (Original Mix)"
        # Capitalize Remix, etc.
        splits = title.split(" ")
        splits[-1] = splits[-1].capitalize()
        audio_file["title"] = " ".join(splits)
        if title.endswith("]"):
            audio_file["title"] = title.replace("]", ")")

        audio_file["albumartist"] = id3_data["albumartist"]
        audio_file.save()

    def import_music(self):
        logger.info("Importing music ...")
        artist_dirs = [d for d in self.import_path.iterdir() if d.is_dir()]
        for art_dir in artist_dirs:
            album_dirs = [d for d in art_dir.iterdir() if d.is_dir()]
            logger.info(f"    Importing albums for artist {art_dir.name} ...")
            try:
                for d in album_dirs:
                    logger.info(f"        Checking files for album {d.name} ...")
                    id3_data = {}
                    try:
                        files = self._prepare_files(dir=d)
                        self._check_track_numbers(files=files)
                        self._filter_general_music(files[0])
                        audio_format = utils.get_audio_format(files[0])
                        audio_file = audio_format(str(files[0]))
                        id3_data["album"] = audio_file["album"][0]
                        logger.info(f"        Checking files for album {id3_data['album']} completed.")
                        logger.info(f"        Importing album {id3_data['album']} ...")
                        id3_data["genre"] = " ".join(audio_file.get("genre", []))
                        id3_data["albumartist"] = self._compile_album_artists(files=files)
                        id3_data["label"] = self._create_label_tag(files=files)
                        id3_data = self._get_id3_from_beatport(files=files, id3_data=id3_data)
                        export_path = self._create_export_path(id3_data)
                        for f in files:
                            self._finalize_file(file=f, id3_data=id3_data)
                            utils.export_file(file=f, export_path=export_path)
                        (d / "cover.jpg").unlink()
                        utils.delete_dir(d)
                        logger.info(f"        Importing album {id3_data['album']} completed.")
                    except ValueError as e:
                        logger.error(e)
                        continue
            except Exception as e:
                logger.exception(e)
            logger.info(f"    Importing albums for artist {art_dir.name} completed.")
            utils.delete_dir(art_dir)
        logger.info("Importing music completed.")
