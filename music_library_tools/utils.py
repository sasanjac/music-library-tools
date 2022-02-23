import shutil
import unicodedata as ud
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from loguru import logger
from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC

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


def delete_dir(dir: Path) -> None:
    try:
        clear_unneeded_files(dir)
        dir.rmdir()
    except OSError:
        pass


@dataclass
class Exporter:
    export_path: Path

    def __post_init__(self) -> None:
        logger.debug(f"Creating output dir: {self.export_path}")
        self.export_path = sanitize_file_path(self.export_path)
        self.export_path.mkdir(parents=True, exist_ok=True)

    def export(self, file: Path) -> None:
        output_file = self.export_path / file.name
        output_file = sanitize_file_path(output_file)
        shutil.move(file, output_file)
        output_file.chmod(0o0777)


def clear_unneeded_files(path: Path) -> None:
    for f in path.iterdir():
        if f.name in UNNEEDED_FILES:
            f.unlink()


def Audio(file: Path) -> Union[FLAC, EasyID3]:
    return FLAC(file) if file.suffix == ".flac" else EasyID3(file)


def replace_all(string) -> str:
    for token, replacement in REPS:
        string = string.replace(token, replacement)
    return string


def split_from_to(text, froms, to) -> str:
    for frm in froms:
        text = text.split(frm)[1]
    return text.split(to)[0]


def sanitize_file_path(p: Path) -> Path:
    if p.is_file():
        base = str(p.parent / p.stem)
    else:
        base = str(p)
    base = ud.normalize("NFKD", base).encode("ascii", "ignore").decode("utf-8")
    base = base.replace(":", "_").replace(".", "")
    if p.is_file():
        base = base + p.suffix
    return Path(base)


AudioError = MutagenError
