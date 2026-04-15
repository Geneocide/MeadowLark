"""
Backward-compatibility re-export layer for extracted utility modules.

All functions have been moved to src/ submodules for better organization.
This module re-exports them under their original names to maintain compatibility
with existing code without requiring import changes.
"""

# Re-export logging utilities
# Re-export dictionary utilities
from src.dict_utils import (
    _default_postprocessors,
    merge_dicts_recursive,
    remove_sponsorblock_postprocessor,
)
from src.logging_utils import log_exception

# Re-export path utilities
from src.path_utils import (
    resolve_playlist_label,
    sanitize_for_path,
    slugify_if_too_long,
)

# Re-export playlist utilities
from src.playlist_utils import (
    detect_site_from_urls,
    get_playlist_file_for_source,
    is_primitive_technology,
)

# Re-export version utilities
from src.version_utils import (
    get_current_yt_dlp_version,
    get_latest_yt_dlp_version,
    is_yt_dlp_update_available,
    normalize_version,
)

# Re-export yt-dlp option builders
from src.ydl_options import (
    build_base_ydl_opts,
    get_output_template,
    get_postprocessors,
    get_source_options,
)

__all__ = [
    "_default_postprocessors",
    "build_base_ydl_opts",
    "detect_site_from_urls",
    "get_current_yt_dlp_version",
    "get_latest_yt_dlp_version",
    "get_output_template",
    "get_playlist_file_for_source",
    "get_postprocessors",
    "get_source_options",
    "is_primitive_technology",
    "is_yt_dlp_update_available",
    "log_exception",
    "merge_dicts_recursive",
    "normalize_version",
    "remove_sponsorblock_postprocessor",
    "resolve_playlist_label",
    "sanitize_for_path",
    "slugify_if_too_long",
]
