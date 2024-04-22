from __future__ import annotations

import pathlib

from music_library_tools import utils

import_path = pathlib.Path("/data/export_electro")

artist_paths = [path for path in import_path.iterdir() if path.is_dir()]
for art_path in artist_paths:
    album_paths = [path for path in art_path.iterdir() if path.is_dir()]
    for path in album_paths:
        file_paths = [f for f in path.iterdir() if f.suffix in {".flac", ".mp3"}]
        for f in file_paths:
            audio_file = utils.audio(f)
            audio_file["genre"] = audio_file["genre"][0].replace("/", "-")
            audio_file.save()
