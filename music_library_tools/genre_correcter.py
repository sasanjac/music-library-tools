from pathlib import Path

from music_library_tools import utils

import_path = Path("/data/export_electro")

artist_dirs = [d for d in import_path.iterdir() if d.is_dir()]
for art_dir in artist_dirs:
    album_dirs = [d for d in art_dir.iterdir() if d.is_dir()]
    for d in album_dirs:
        files = [f for f in d.iterdir() if (f.suffix == ".flac" or f.suffix == ".mp3")]
        for f in files:
            audio_format = utils.get_audio_format(f)
            audio_file = audio_format(str(f))
            audio_file["genre"] = audio_file["genre"][0].replace("/", "-")
            audio_file.save()
