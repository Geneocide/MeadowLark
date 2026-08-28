"""Tests for src.resolutions registry and resolution-preset derivation functions."""

import pytest

from src.resolutions import (
    DEFAULT_ENABLED_HEIGHTS,
    RESOLUTION_PRESETS,
    all_heights,
    button_label_key,
    drop_label_key,
    format_enabled_heights,
    get_preset,
    height_from_source,
    lower_heights,
    parse_enabled_heights,
    playlist_file_key,
    playlist_source_key,
    source_key,
)

# ---------------------------------------------------------------------------
# Preset registry shape tests
# ---------------------------------------------------------------------------


def test_presets_ordered_descending() -> None:
    """RESOLUTION_PRESETS heights must be strictly descending."""
    heights = tuple(p.height for p in RESOLUTION_PRESETS)
    assert heights == (2160, 1440, 1080, 720, 480, 360)


def test_legacy_playlist_filenames_preserved() -> None:
    """1080 and 720 must keep their legacy playlist filenames."""
    assert get_preset(1080).playlist_filename == "playlists.txt"
    assert get_preset(720).playlist_filename == "720playlists.txt"


# ---------------------------------------------------------------------------
# Legacy settings key mapping
# ---------------------------------------------------------------------------


def test_legacy_playlist_file_keys_preserved() -> None:
    """Legacy playlist file keys for 1080/720 must be preserved."""
    assert playlist_file_key(1080) == "VID_DL_PLAYLISTS_FILE"
    assert playlist_file_key(720) == "VID_DL_PLAYLISTS_720_FILE"
    assert playlist_file_key(1440) == "VID_DL_PLAYLISTS_1440_FILE"


def test_legacy_button_label_keys_preserved() -> None:
    """Legacy button label keys for 1080/720 must be preserved."""
    assert button_label_key(1080) == "VID_DL_LABEL_BTN_PLAYLISTS"
    assert button_label_key(720) == "VID_DL_LABEL_BTN_720"
    assert button_label_key(480) == "VID_DL_LABEL_BTN_480"


def test_drop_label_keys_match_shipped_names() -> None:
    """Drop-label keys must match the names already shipped."""
    assert drop_label_key(1080) == "VID_DL_LABEL_DROP_1080"
    assert drop_label_key(720) == "VID_DL_LABEL_DROP_720"


# ---------------------------------------------------------------------------
# Shipped colors must not change
# ---------------------------------------------------------------------------


def test_shipped_colors_unchanged() -> None:
    """Colors for 1080 and 720 must match the shipped hex values."""
    assert get_preset(1080).color == "#424769"
    assert get_preset(720).color == "#7077A1"


# ---------------------------------------------------------------------------
# height_from_source parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("1080", 1080),
        ("1080playlists", 1080),
        ("360", 360),
        ("2160playlists", 2160),
    ],
)
def test_height_from_source_parses_both_forms(source: str, expected: int) -> None:
    """height_from_source must parse both bare and playlist-suffixed keys."""
    assert height_from_source(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "audio",
        "audio_playlists",
        "Update",
        "",
        "999",
        "999playlists",
        "playlists",
        "abc",
    ],
)
def test_height_from_source_rejects_non_resolution(source: str) -> None:
    """height_from_source must return None for unregistered sources."""
    assert height_from_source(source) is None


# ---------------------------------------------------------------------------
# parse_enabled_heights parsing and fallback
# ---------------------------------------------------------------------------


def test_parse_enabled_heights_roundtrip() -> None:
    """parse_enabled_heights must deserialize format_enabled_heights output."""
    formatted = format_enabled_heights([720, 2160, 480])
    result = parse_enabled_heights(formatted)
    assert result == (2160, 720, 480)


def test_parse_enabled_heights_drops_garbage() -> None:
    """parse_enabled_heights must drop malformed and unregistered entries."""
    result = parse_enabled_heights("1080, ,abc,720,999")
    assert result == (1080, 720)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        ",",
        "999,abc",
    ],
)
def test_parse_enabled_heights_empty_falls_back(raw: str | None) -> None:
    """parse_enabled_heights must fall back to DEFAULT_ENABLED_HEIGHTS."""
    result = parse_enabled_heights(raw)
    assert result == DEFAULT_ENABLED_HEIGHTS
    assert result == (1080, 720)


def test_parse_enabled_heights_dedupes() -> None:
    """parse_enabled_heights must deduplicate and sort descending."""
    result = parse_enabled_heights("720,720,1080")
    assert result == (1080, 720)


# ---------------------------------------------------------------------------
# lower_heights retry-ladder descent
# ---------------------------------------------------------------------------


def test_lower_heights_unrestricted() -> None:
    """lower_heights without restriction must return all rungs below the height."""
    result = lower_heights(1080)
    assert result == (720, 480, 360)


def test_lower_heights_restricted_to_enabled() -> None:
    """lower_heights with enabled must filter to only enabled rungs."""
    result = lower_heights(2160, enabled=(1080, 480))
    assert result == (1080, 480)


def test_lower_heights_empty_restriction_falls_back() -> None:
    """lower_heights must fall back to unrestricted when enabled is empty."""
    result = lower_heights(2160, enabled=(2160,))
    assert result == (1440, 1080, 720, 480, 360)


def test_lower_heights_lowest_rung_is_empty() -> None:
    """lower_heights from the lowest rung must return empty."""
    result = lower_heights(360)
    assert result == ()


def test_lower_heights_explicit_empty_enabled_falls_back() -> None:
    """
    An explicitly empty (but not None) enabled iterable must still fall back.

    A caller that passes enabled=() (e.g. every rung got disabled) must get a
    working retry ladder rather than being stranded with nowhere to descend to
    - the same invariant the empty-restriction-after-filtering case documents.
    """
    result = lower_heights(1080, enabled=())
    assert result == (720, 480, 360)


def test_lower_heights_below_lowest_registered_rung_is_empty() -> None:
    """A height below every registered rung has nothing to descend to."""
    assert lower_heights(100) == ()


def test_lower_heights_above_highest_registered_rung_returns_all() -> None:
    """A height above every registered rung must return the full ladder."""
    assert lower_heights(9999) == all_heights()


# ---------------------------------------------------------------------------
# all_heights / get_preset / source_key / playlist_source_key
# ---------------------------------------------------------------------------


def test_all_heights_matches_registry_order() -> None:
    """all_heights must mirror RESOLUTION_PRESETS order exactly."""
    assert all_heights() == (2160, 1440, 1080, 720, 480, 360)


def test_get_preset_unregistered_height_returns_none() -> None:
    """get_preset must return None, not raise, for an unregistered height."""
    assert get_preset(999) is None
    assert get_preset(0) is None
    assert get_preset(-1080) is None


def test_source_key_and_playlist_source_key_forms() -> None:
    """source_key/playlist_source_key must build the bare and suffixed keys."""
    assert source_key(1080) == "1080"
    assert playlist_source_key(1080) == "1080playlists"
    assert playlist_source_key(2160) == "2160playlists"


# ---------------------------------------------------------------------------
# height_from_source - int() parsing quirks that widen the "digits" gate
# ---------------------------------------------------------------------------


def test_height_from_source_accepts_underscore_separated_digits() -> None:
    """
    Python's int() accepts PEP-515 underscore separators - "1_080" parses to 1080.

    height_from_source has no digit-only pre-check before int(), so this
    non-obvious literal is accepted as a valid source key even though nothing
    in the app ever generates it.
    """
    assert height_from_source("1_080") == 1080


def test_height_from_source_accepts_leading_whitespace() -> None:
    """int() strips whitespace, so a padded height string still resolves."""
    assert height_from_source(" 1080") == 1080
    assert height_from_source("1080 ") == 1080


def test_height_from_source_accepts_leading_plus_sign() -> None:
    """int() accepts a leading '+', so "+1080" resolves like "1080"."""
    assert height_from_source("+1080") == 1080


def test_height_from_source_rejects_float_looking_string() -> None:
    """A float-formatted height string must be rejected (ValueError from int())."""
    assert height_from_source("1080.0") is None


def test_height_from_source_rejects_negative_height() -> None:
    """A negative height parses but is not a registered rung."""
    assert height_from_source("-1080") is None


# ---------------------------------------------------------------------------
# format_enabled_heights
# ---------------------------------------------------------------------------


def test_format_enabled_heights_empty_iterable_returns_empty_string() -> None:
    """An empty heights collection serializes to an empty string, not a crash."""
    assert format_enabled_heights([]) == ""


def test_format_enabled_heights_does_not_validate_registry_membership() -> None:
    """
    format_enabled_heights is a pure serializer - it does not drop unregistered heights.

    Only parse_enabled_heights validates against the registry; round-tripping
    an unregistered height through format then parse is expected to drop it
    (see test_parse_enabled_heights_drops_garbage), but format alone must not.
    """
    assert format_enabled_heights([999, 1080]) == "1080,999"
