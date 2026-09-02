"""Compat shim: re-exporta símbolos dos módulos novos para manter `from wallpha import config` funcionando.
Código novo deve importar diretamente dos módulos (entries, parse, media, yt, etc.)."""
from .entries import LISTAS, TEMPLATE, _apply_sub, _dir_tempo, _list_total, _sub_dur, _sub_index, check_global_default, find_list, format_entry, init_template, list_media_queue, load, load_checked, load_entries
from .log import _append_log, err, info
from .media import IMAGE_EXTS, VIDEO_EXTS, WALLPHA_EXTS, day_shuffled, get_salt, list_dir_files, list_tree_files, match_tipo, video_duration
from .parse import DEFAULT_TEMPO, DIA_RANK, WEEKDAYS, _dia_rank, fmt_dia, is_loop_n, matches_day, parse_dia, parse_hora, parse_loop, parse_tempo, parse_time
from .paths import DEFAULT_CONFIG, LOG_FILE, SALT_FILE
from .randomcfg import build_random_queue, cfg_seconds, default_scan_roots, random_boundary
from .schedule import _cycle_order, _default, _default_result, _finite_total, _free_before, _hora_entries, _hora_slots, _resolve_rot, _rot_duration, _rotation, _sub_by_within, _with_file, _with_file_or_list, _with_list, _slot_end, resolve_active
from .transitions import _next_list_offsets, _wall_for_free, advance_in_dir, advance_in_list, find_by_name, next_after, next_entry, next_sub_by_nome, next_transition
from .yt import YT_CACHE_MB, _extract_playlist_id, _get_shuffled_playlist_ids, clean_yt_buffer, download_yt, get_playlist_ids, yt_dir

# compat: _prune_yt_cache antigo
try:
    from .yt import _prune_yt_cache
except ImportError:
    _prune_yt_cache = clean_yt_buffer

__all__ = [
    "DEFAULT_CONFIG", "SALT_FILE", "LOG_FILE",
    "WALLPHA_EXTS", "VIDEO_EXTS", "IMAGE_EXTS", "DEFAULT_TEMPO", "WEEKDAYS", "DIA_RANK",
    "_dia_rank", "LISTAS", "TEMPLATE",
    "video_duration", "match_tipo", "list_dir_files", "list_tree_files", "get_salt", "day_shuffled",
    "random_boundary", "default_scan_roots", "cfg_seconds", "build_random_queue",
    "yt_dir", "clean_yt_buffer", "_prune_yt_cache", "_extract_playlist_id", "get_playlist_ids", "download_yt",
    "parse_tempo", "parse_time", "parse_hora", "parse_loop", "is_loop_n", "parse_dia", "matches_day", "fmt_dia",
    "init_template", "load", "load_checked", "load_entries", "find_list", "format_entry", "list_media_queue", "check_global_default",
    "_dir_tempo", "_sub_dur", "_list_total", "_sub_index", "_apply_sub",
    "_hora_entries", "_slot_end", "_hora_slots", "_rotation", "_default", "_cycle_order", "_rot_duration", "_free_before", "_resolve_rot", "_with_file", "_sub_by_within", "_with_list", "_default_result", "_with_file_or_list", "resolve_active", "_finite_total",
    "_wall_for_free", "_next_list_offsets", "next_transition", "next_entry", "advance_in_list", "find_by_name", "next_after", "advance_in_dir", "next_sub_by_nome",
    "_append_log", "err", "info", "YT_CACHE_MB",
]

# re-export helpers que em schedule/entries são privados mas tests acessam diretamente via config
try:
    from .entries import _apply_sub, _build_list, _expand_list, _normalize
except ImportError:
    pass
try:
    from .schedule import _slot_end
except ImportError:
    pass
