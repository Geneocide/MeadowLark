"""Unit tests for path_utils helpers."""

from src.path_utils import rename_playlist_folders_from_comments


def test_rename_playlist_folders_with_list_param(tmp_path) -> None:
    na = tmp_path / "NA"
    na.mkdir()

    rename_playlist_folders_from_comments(
        str(tmp_path),
        ["https://youtube.com/playlist?list=PLabc"],
        {"PLabc": "My Show"},
    )

    assert not na.exists()
    assert (tmp_path / "My Show").is_dir()


def test_rename_playlist_folders_with_direct_playlist_id(tmp_path) -> None:
    """Bare video URL (no list= param) should use direct_playlist_id as fallback."""
    na = tmp_path / "NA"
    na.mkdir()

    rename_playlist_folders_from_comments(
        str(tmp_path),
        ["https://youtube.com/watch?v=videoonly"],
        {"PLxyz": "Taskmaster S21"},
        direct_playlist_id="PLxyz",
    )

    assert not na.exists()
    assert (tmp_path / "Taskmaster S21").is_dir()


def test_rename_playlist_folders_no_na_folder(tmp_path) -> None:
    rename_playlist_folders_from_comments(
        str(tmp_path),
        ["https://youtube.com/watch?v=videoonly"],
        {"PLxyz": "Taskmaster S21"},
        direct_playlist_id="PLxyz",
    )
    # No error, nothing renamed
    assert not (tmp_path / "Taskmaster S21").exists()


def test_rename_playlist_folders_no_comments(tmp_path) -> None:
    na = tmp_path / "NA"
    na.mkdir()

    rename_playlist_folders_from_comments(str(tmp_path), ["https://youtube.com/watch?v=x"])

    assert na.exists()


def test_rename_playlist_folders_target_exists_skips(tmp_path) -> None:
    na = tmp_path / "NA"
    na.mkdir()
    (tmp_path / "My Show").mkdir()

    rename_playlist_folders_from_comments(
        str(tmp_path),
        ["https://youtube.com/playlist?list=PLabc"],
        {"PLabc": "My Show"},
    )

    assert na.exists()
    assert (tmp_path / "My Show").is_dir()


def test_rename_playlist_folders_direct_id_not_in_comments(tmp_path) -> None:
    na = tmp_path / "NA"
    na.mkdir()

    rename_playlist_folders_from_comments(
        str(tmp_path),
        ["https://youtube.com/watch?v=videoonly"],
        {"PLother": "Other Show"},
        direct_playlist_id="PLxyz",
    )

    assert na.exists()
