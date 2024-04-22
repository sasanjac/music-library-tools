from __future__ import annotations

import pathlib
import shutil
import typing as t
import unicodedata as ud
from dataclasses import dataclass

from loguru import logger
from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC

if t.TYPE_CHECKING:
    from collections.abc import Sequence

REPS = [
    ("(", ""),
    (")", ""),
    ("Ü", "U"),
    ("Ü", "O"),
    ("Ä", "A"),
    ("Å", "A"),
    ("Ø", "O"),
    ("É", "E"),
    ("Ï", "I"),
    (" - ", " "),
    ("EP", "E.P."),
    ("Ș", "S"),
    ("&", "AND"),
    ("'", ""),
]

UNNEEDED_FILES = [".DS_Store", "cover.jpg"]


def safe_delete_path(path: pathlib.Path) -> None:
    try:
        clear_unneeded_files(path)
        path.rmdir()
    except OSError:
        pass


@dataclass
class Exporter:
    export_path: pathlib.Path

    def __post_init__(self) -> None:
        logger.debug(f"Creating output dir: {self.export_path}")
        self.export_path = sanitize_file_path(self.export_path, file_only=False)
        self.export_path.mkdir(parents=True, exist_ok=True)

    def export(self, file: pathlib.Path, *, file_only: bool = True) -> None:
        output_file = self.export_path / file.name
        output_file = sanitize_file_path(output_file, file_only=file_only)
        shutil.move(str(file), str(output_file))
        output_file.chmod(0o0777)


def clear_unneeded_files(path: pathlib.Path) -> None:
    for f in path.iterdir():
        if f.name in UNNEEDED_FILES:
            f.unlink()


def audio(file: pathlib.Path) -> FLAC | EasyID3:
    return FLAC(file) if file.suffix == ".flac" else EasyID3(file)


def replace_all(string: str) -> str:
    for token, replacement in REPS:
        string = string.replace(token, replacement)
    return string


def split_from_to(text: str, froms: Sequence[str], to: str) -> str:
    for frm in froms:
        text = text.split(frm)[1]
    return text.split(to)[0]


def sanitize_file_path(p: pathlib.Path, *, file_only: bool = True) -> pathlib.Path:
    base = str(p.parent / p.stem) if file_only else str(p)
    base = ud.normalize("NFKD", base).encode("ascii", "ignore").decode("utf-8")
    base = base.replace(":", "_").replace(".", "")
    if file_only:
        base = base + p.suffix
    return pathlib.Path(base)


AudioError = MutagenError
