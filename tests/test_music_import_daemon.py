import shutil
from pathlib import Path
import pytest

from music_library_tools.music_import_daemon import MusicImportDaemon


@pytest.fixture
def teardown():
    yield
    import_path = Path("./tests/test_data/import/")
    shutil.rmtree(import_path)


@pytest.mark.parametrize(
    "src_path, export_path",
    [
        ("./tests/test_data/src_electro/", "./tests/test_data/export_electro/"),
        ("./tests/test_data/src_general/", "./tests/test_data/export_general/"),
        ("./tests/test_data/src_todo/", "./tests/test_data/todo/"),
    ],
)
def test_music_import_daemon(teardown, src_path, export_path):
    data_path = Path(src_path)
    import_path = Path("./tests/test_data/import/")
    shutil.copytree(data_path, import_path)
    todo_path = Path("./tests/test_data/todo/")
    export_electro_path = Path("./tests/test_data/export_electro/")
    export_general_path = Path("./tests/test_data/export_general/")
    export_path = Path(export_path)
    mid = MusicImportDaemon(
        import_path=import_path,
        todo_path=todo_path,
        export_electro_path=export_electro_path,
        export_general_path=export_general_path,
    )
    mid.import_music()
    children = list(export_path.glob("[!.]*"))
    assert len(children) == 1
    shutil.rmtree(children[0])
