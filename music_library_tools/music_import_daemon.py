from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from statistics import mode
from typing import List
from typing import Union

import requests
from loguru import logger
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError
from mutagen.flac import FLAC

from music_library_tools import utils

ELECTRO_GENRES = ["", "TECHNO", "HOUSE", "ELECTRO", "DANCE"]

MIX_STRS = ["MIX", "REMIX", "EDIT", "REWORK", "BOOTLEG", "VERSION", "DUB", "ENACTMENT"]


@dataclass
class ID3Data:
    album: str
    genre: str
    albumartist: str
    label: str
    isrc: str = ""


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
        track_nos = [int(utils.Audio(f)["tracknumber"][0]) for f in files]
        if not max(track_nos) == len(track_nos):
            raise ValueError("Less audio files than tracks in album.")

    def _filter_general_music(self, files: List[Path]) -> None:
        try:
            genres = [" ".join(utils.Audio(f)["genre"]).upper() for f in files]
            if not any([g in genre for g in ELECTRO_GENRES for genre in genres]):
                export_path = self.export_general_path / files[0].parent.parent.name
                exporter = utils.Exporter(export_path)
                exporter.export(files[0].parent)
                raise ValueError("Album is moved to general music.")
        except KeyError:
            pass

    def _compile_id3_data(self, files: List[Path]) -> ID3Data:
        albums = [utils.Audio(f)["album"][0] for f in files]
        if len(set(albums)) == 1:
            album = albums[0]
        else:
            raise ValueError("Audio files have different albums as tags")
        genres = [" ".join(utils.Audio(f).get("genre", [])) for f in files]
        genre = mode(genres)
        albumartist = self._compile_album_artists(files=files)
        label = self._create_label_tag(files=files)
        id3_data = ID3Data(album=album, albumartist=albumartist, genre=genre, label=label)
        id3_data = self._get_id3_from_beatport(files=files, id3_data=id3_data)
        return id3_data

    def _compile_album_artists(self, files: List[Path]) -> str:
        try:
            artists = [e for f in files for e in utils.Audio(f)["artist"][0].split(", ")]
        except KeyError:
            try:
                artists = [e for f in files for e in utils.Audio(f)["albumartist"][0].split(", ")]
            except KeyError:
                raise ValueError("Could not find artists.")

        if len(set(artists)) != 1:
            return "Various Artists"
        else:
            audio_file = utils.Audio(files[0])
            try:
                return audio_file["albumartist"][0]
            except Exception:
                return audio_file["artist"][0]

    def _create_label_tag(self, files: List[Path]) -> str:
        try:
            labels = [utils.Audio(f)["organization"][0] for f in files]
        except Exception:
            try:
                labels = [utils.Audio(f)["publisher"][0] for f in files]
            except Exception:
                logger.exception("Can't determine label.")
                labels = [""]
        if len(set(labels)) == 1:
            return labels[0]
        else:
            raise ValueError("Audio files have different labels as tags")

    def _create_request(self, files: List[Path], id3_data: ID3Data) -> str:
        audio_file = utils.Audio(files[0])
        req_album = urllib.parse.quote_plus(id3_data.album)
        if id3_data.albumartist == "Various Artists":
            req_artist = audio_file["artist"][0].split(",")[0]
        else:
            req_artist = urllib.parse.quote_plus(id3_data.albumartist)

        try:
            req_year = audio_file["year"][0].split("-")[0]
        except Exception:
            req_year = ""
        return f"https://www.beatport.com/search?q={req_album}+{req_artist}+{req_year}"

    def _get_id3_from_beatport(self, files: List[Path], id3_data: ID3Data) -> ID3Data:
        req_str = self._create_request(files=files, id3_data=id3_data)
        try:
            ids = requests.get(req_str).text.split('href="/release/')[1:]
            ids = [i.split('"')[0] for i in ids]
            ids = list(set(ids))
            album = id3_data.album.upper()
            albums = [album, utils.replace_all(album)]
            albumartist = id3_data.albumartist.upper()
            if albumartist == "VARIOUS ARTISTS":
                audio_file = utils.Audio(files[0])
                albumartist = audio_file["artist"][0].split(",")[0].upper()
            albumartists = [albumartist, utils.replace_all(albumartist)]
            label = id3_data.label.split()[0].upper()
            labels = [label, utils.replace_all(label)]
            for id in ids:
                r = requests.get("https://www.beatport.com/release/" + id)
                rdata = utils.split_from_to(r.text, ['<script type="application/ld+json">'], "</script>")
                data = json.loads(rdata)
                data = [d for d in data if d["@type"] == "MusicRelease"]
                data = data[0]
                bp_album = data["name"]
                bp_albumartist = [x["name"] for x in data["@producer"]]
                bp_label = data["recordLabel"]["name"].split()[0]
                bp_albums = [bp_album.upper(), utils.replace_all(bp_album.upper())]
                bp_albumartists = [a.upper() for a in bp_albumartist] + [
                    utils.replace_all(a.upper()) for a in bp_albumartist
                ]
                bp_labels = [bp_label.upper(), utils.replace_all(bp_label.upper())]
                conditions = (
                    any(i in bp_albums for i in albums)
                    and any(i in bp_labels for i in labels)
                    and any(i in bp_albumartists for i in albumartists)
                )
                if conditions:
                    isrc_str = data["catalogNumber"]
                    try:
                        isrc = re.split(r"(\d+)", isrc_str)[:3]
                        if isrc[2] in ["DIG", "CD", "DIGITAL"]:
                            isrc[2] = ""
                        id3_data.isrc = "".join(isrc)
                    except Exception:
                        id3_data.isrc = isrc_str
                    id3_data.genre = utils.split_from_to(r.text, ['data-ec-d3="'], '">').replace("&amp;", "&")
                    return id3_data
            raise IndexError
        except Exception:
            id3_data.isrc = "TODO"
            return id3_data

    def _create_export_path(self, id3_data: ID3Data) -> Path:
        albumartist = id3_data.albumartist.replace("/", "_")
        album = id3_data.album.replace("/", "_")
        if id3_data.isrc != "TODO":
            export_path = self.export_electro_path / albumartist / (id3_data.isrc + " - " + album)
        else:
            export_path = self.todo_path / albumartist / (id3_data.isrc + " - " + album)
        return utils.sanitize_file_path(export_path)

    def _finalize_file(self, file: Path, id3_data: ID3Data) -> None:
        audio_file = utils.Audio(file)
        audio_file = self._apply_id3_data(audio_file, id3_data)
        audio_file = self._fix_title(audio_file)
        audio_file.save()

    def _apply_id3_data(self, audio_file: Union[FLAC, EasyID3], id3_data: ID3Data) -> Union[FLAC, EasyID3]:
        audio_file["isrc"] = id3_data.isrc
        audio_file["albumartist"] = id3_data.albumartist
        audio_file["album"] = id3_data.isrc + " - " + id3_data.album
        audio_file["genre"] = id3_data.genre.replace("/", "-")
        try:
            audio_file["label"] = id3_data.label
        except EasyID3KeyError:
            audio_file["organization"] = id3_data.label
        return audio_file

    def _fix_title(self, audio_file: Union[FLAC, EasyID3]) -> Union[FLAC, EasyID3]:
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
        return audio_file

    def import_music(self):
        artist_dirs = [d for d in self.import_path.iterdir() if d.is_dir()]
        if len(artist_dirs) > 0:
            for art_dir in artist_dirs:
                album_dirs = [d for d in art_dir.iterdir() if d.is_dir()]
                logger.info(f"Importing albums for artist {art_dir.name} ...")
                try:
                    for d in album_dirs:
                        logger.info(f"Checking files for album {d.name} ...")
                        try:
                            files = self._prepare_files(d)
                            self._filter_general_music(files)
                            self._check_track_numbers(files)
                            logger.info(f"Compiling ID3 data for album {d.name} ...")
                            id3_data = self._compile_id3_data(files)
                            logger.info(f"Importing album {d.name} ...")
                            export_path = self._create_export_path(id3_data)
                            exporter = utils.Exporter(export_path)
                            for f in files:
                                self._finalize_file(file=f, id3_data=id3_data)
                                exporter.export(f)
                            utils.delete_dir(d)
                            logger.info(f"Importing album {id3_data.album} completed.")
                        except ValueError as e:
                            logger.error(e)
                except Exception:
                    logger.exception(f"Exception in program while processing artist {art_dir}")
                logger.info(f"Importing albums for artist {art_dir.name} completed.")
                utils.delete_dir(art_dir)
            logger.info("Importing music completed.")
