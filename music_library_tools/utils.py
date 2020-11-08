from pathlib import Path
from typing import Union
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
import shutil


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


def delete_dir(dir: Path) -> None:
    try:
        _clear_DS_STORE(dir)
        dir.rmdir()
    except OSError:
        pass


def export_file(file: Path, export_path: Path) -> None:
    output_file = export_path / file.name
    shutil.move(str(file), str(output_file))
    output_file.chmod(0o0777)


def _clear_DS_STORE(path: Path) -> None:
    for f in path.iterdir():
        if f.name == ".DS_Store":
            f.unlink()


def get_audio_format(file: Path) -> Union[FLAC, EasyID3]:
    return FLAC if file.suffix == ".flac" else EasyID3


def replace_all(string) -> str:
    for token, replacement in REPS:
        string = string.replace(token, replacement)
    return string


def split_from_to(text, froms, to) -> str:
    for frm in froms:
        text = text.split(frm)[1]
    return text.split(to)[0]
