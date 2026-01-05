# Copyright (c) 2024-2025 Sasan Jacob Rasti

from __future__ import annotations

import json
import re
import typing as t
import urllib.parse
from dataclasses import dataclass
from statistics import mode

import requests
from loguru import logger
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError

from music_library_tools import utils

if t.TYPE_CHECKING:
    import pathlib
    from collections.abc import Sequence

    from mutagen.flac import FLAC

ELECTRO_GENRES = ["TECHNO", "HOUSE", "ELECTRO", "DANCE"]

MIX_STRS = ["MIX", "REMIX", "EDIT", "REWORK", "BOOTLEG", "VERSION", "DUB", "ENACTMENT"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36",
}

MIN_SCORE = 1000


@dataclass
class ID3Data:
    album: str
    genre: str
    albumartist: str
    label: str
    isrc: str = ""


@dataclass
class MusicImportDaemon:
    import_path: pathlib.Path
    todo_path: pathlib.Path
    export_electro_path: pathlib.Path
    export_general_path: pathlib.Path

    @staticmethod
    def prepare_files(
        path: pathlib.Path,
    ) -> Sequence[pathlib.Path]:
        files = [f for f in path.iterdir() if f.is_file()]
        if any(f.suffix == ".temp" for f in files):
            msg = "Album not finished downloading."
            raise ValueError(msg)

        if any(["errors.txt" in files]):
            with (path / "errors.txt").open() as f:
                file_contents = f.read()
                raise ValueError(file_contents)

        files = [f for f in files if (f.suffix in {".flac", ".mp3"})]
        if len(files) == 0:
            msg = "No files in album."
            raise ValueError(msg)

        return files

    @staticmethod
    def check_track_numbers(
        files: Sequence[pathlib.Path],
    ) -> None:
        try:
            track_nos = [int(utils.audio(f)["tracknumber"][0].split("/")[0]) for f in files]
        except KeyError as e:
            msg = "Something wrong with audio file. Probably still downloading."
            raise ValueError(msg) from e

        if max(track_nos) != len(track_nos):
            msg = "Less audio files than tracks in album."
            raise ValueError(msg)

    def _filter_general_music(self, files: Sequence[pathlib.Path]) -> None:
        nogenre = False
        try:
            genres = [" ".join(utils.audio(f)["genre"]).upper() for f in files]
        except KeyError:
            nogenre = True

        if nogenre or not any(g in genre for g in ELECTRO_GENRES for genre in genres):
            album_path = files[0].parent
            export_path = self.export_general_path / album_path.parent.name / album_path.name
            exporter = utils.Exporter(export_path)
            for f in album_path.iterdir():
                if f.is_file():
                    exporter.export(f, file_only=True)

            utils.safe_delete_path(album_path)
            msg = "Album is moved to general music."
            raise ValueError(msg)

    def _compile_id3_data(
        self,
        files: Sequence[pathlib.Path],
    ) -> ID3Data:
        albums = [utils.audio(f)["album"][0] for f in files]
        if len(set(albums)) == 1:
            album = albums[0]
        else:
            msg = "Audio files have different albums as tags"
            raise ValueError(msg)

        genres = [" ".join(utils.audio(f).get("genre", [])) for f in files]
        genre = mode(genres)
        albumartist = self._compile_album_artists(files=files)
        label = self._create_label_tag(files=files)
        id3_data = ID3Data(album=album, albumartist=albumartist, genre=genre, label=label)
        return self._get_id3_from_beatport(files=files, id3_data=id3_data)

    @staticmethod
    def _compile_album_artists(
        files: Sequence[pathlib.Path],
    ) -> str:
        try:
            artists = [e for f in files for e in utils.audio(f)["artist"][0].split(", ")]
        except KeyError:
            try:
                artists = [e for f in files for e in utils.audio(f)["albumartist"][0].split(", ")]
            except KeyError as err:
                msg = "Could not find artists."
                raise ValueError(msg) from err

        if len(set(artists)) != 1:
            return "Various Artists"

        audio_file = utils.audio(files[0])
        try:
            return t.cast("str", audio_file["albumartist"][0])

        except KeyError:
            return t.cast("str", audio_file["artist"][0])

    @staticmethod
    def _create_label_tag(
        files: Sequence[pathlib.Path],
    ) -> str:
        try:
            labels = [utils.audio(f)["organization"][0] for f in files]
        except KeyError:
            try:
                labels = [utils.audio(f)["publisher"][0] for f in files]
            except KeyError:
                try:
                    labels = [utils.audio(f)["composer"][0] for f in files]
                except KeyError:
                    logger.exception("Can't determine label.")
                    labels = [""]

        if len(set(labels)) == 1:
            return t.cast("str", labels[0])

        msg = "Audio files have different labels as tags"
        raise ValueError(msg)

    @staticmethod
    def _create_request(
        files: Sequence[pathlib.Path],
        id3_data: ID3Data,
    ) -> str:
        audio_file = utils.audio(files[0])
        req_album = urllib.parse.quote_plus(id3_data.album)
        if id3_data.albumartist == "Various Artists":
            req_artist = audio_file["artist"][0].split(",")[0]
        else:
            req_artist = urllib.parse.quote_plus(id3_data.albumartist)

        try:
            req_year = audio_file["year"][0].split("-")[0]
        except KeyError:
            req_year = ""

        return f"https://www.beatport.com/search?q={req_album}+{req_artist}+{req_year}"

    def _get_id3_from_beatport(self, files: Sequence[pathlib.Path], id3_data: ID3Data) -> ID3Data:
        req_str = self._create_request(files=files, id3_data=id3_data)
        try:
            return self._handle_id3_beatport_request(req_str=req_str, id3_data=id3_data)
        except KeyError:
            id3_data.isrc = "TODO"
            return id3_data

    @staticmethod
    def _handle_id3_beatport_request(
        req_str: str,
        id3_data: ID3Data,
    ) -> ID3Data:
        data = (
            requests.get(req_str, headers=HEADERS, timeout=120)
            .text.split('<script id="__NEXT_DATA__" type="application/json">')[1]
            .split("</script>")[0]
        )
        data_json = json.loads(data)
        data_json = data_json["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["tracks"]["data"]
        if len(data_json) > 0:
            max_score = max(e["score"] for e in data_json)
            entry = next(e for e in data_json if e["score"] == max_score)
            if entry["score"] <= MIN_SCORE:
                msg = f"ID3 entry score too low: {entry['score']}"
                raise KeyError(msg)

            isrc_str = entry["catalog_number"]
            try:
                isrc = re.split(r"(\d+)", isrc_str)[:3]
                if isrc[2] in {"DIG", "CD", "DIGITAL"}:
                    isrc[2] = ""

                id3_data.isrc = "".join(isrc)

            except KeyError:
                id3_data.isrc = isrc_str

            genres = [e["genre_name"] for e in entry["genre"]]
            id3_data.genre = max(set(genres), key=genres.count)
            return id3_data

        msg = "Could not get ID3 data."
        raise KeyError(msg)

    def _create_export_path(
        self,
        id3_data: ID3Data,
    ) -> pathlib.Path:
        albumartist = id3_data.albumartist.replace("/", "_")
        album = id3_data.album.replace("/", "_")
        if id3_data.isrc != "TODO":
            export_path = self.export_electro_path / albumartist / (id3_data.isrc + " - " + album)
        else:
            export_path = self.todo_path / albumartist / (id3_data.isrc + " - " + album)
        return utils.sanitize_file_path(export_path)

    def _finalize_file(
        self,
        file: pathlib.Path,
        id3_data: ID3Data,
    ) -> None:
        audio_file = utils.audio(file)
        audio_file = self._apply_id3_data(audio_file, id3_data)
        audio_file = self._fix_title(audio_file)
        audio_file.save()

    @staticmethod
    def _apply_id3_data(
        audio_file: FLAC | EasyID3,
        id3_data: ID3Data,
    ) -> FLAC | EasyID3:
        audio_file["isrc"] = id3_data.isrc
        audio_file["albumartist"] = id3_data.albumartist
        audio_file["album"] = id3_data.isrc + " - " + id3_data.album
        audio_file["genre"] = id3_data.genre.replace("/", "-")
        try:
            audio_file["label"] = id3_data.label
        except EasyID3KeyError:
            audio_file["organization"] = id3_data.label

        return audio_file

    @staticmethod
    def _fix_title(
        audio_file: FLAC | EasyID3,
    ) -> FLAC | EasyID3:
        title = audio_file["title"][0]
        # Add Original Mix if no already there
        if not any(mix_str in title.upper() for mix_str in MIX_STRS):
            title += " (Original Mix)"

        # Capitalize Remix, etc.
        splits = title.split(" ")
        splits[-1] = splits[-1].capitalize()
        audio_file["title"] = " ".join(splits)
        if title.endswith("]"):
            audio_file["title"] = title.replace("]", ")")
        return audio_file

    def import_music(
        self,
    ) -> None:
        artist_paths = [d for d in self.import_path.iterdir() if d.is_dir()]
        if len(artist_paths) > 0:
            for art_dir in artist_paths:
                album_paths = [d for d in art_dir.iterdir() if d.is_dir()]
                logger.info(f"Importing albums for artist {art_dir.name} ...")
                try:
                    for d in album_paths:
                        self.import_album(album_path=d)

                except ValueError:
                    logger.exception(f"Exception in program while processing artist {art_dir}")

                logger.info(f"Importing albums for artist {art_dir.name} completed.")
                utils.safe_delete_path(art_dir)

            logger.info("Importing music completed.")

    def import_album(
        self,
        album_path: pathlib.Path,
    ) -> None:
        logger.info(f"Checking files for album {album_path.name} ...")
        try:
            files = self.prepare_files(album_path)
            self._filter_general_music(files)
            self.check_track_numbers(files)
            logger.info(f"Compiling ID3 data for album {album_path.name} ...")
            id3_data = self._compile_id3_data(files)
            logger.info(f"Importing album {album_path.name} ...")
            export_path = self._create_export_path(id3_data)
            exporter = utils.Exporter(export_path)
            for f in files:
                self._finalize_file(file=f, id3_data=id3_data)
                exporter.export(f, file_only=True)

            utils.safe_delete_path(album_path)
            logger.info(f"Importing album {id3_data.album} completed.")
        except ValueError as e:
            logger.error(e)
