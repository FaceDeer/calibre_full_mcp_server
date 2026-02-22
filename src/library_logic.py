# Backward-compatibility shim.
# All logic has moved to the logic/ package.
# This file is kept so that any direct imports of library_logic still work.
try:
    from .logic import *
    from .logic import (
        _normalize_series_field, _validate_and_normalize_changes,
        _get_library_schema_impl, _update_book_impl, _bulk_update_metadata_impl,
        _get_field_values_impl, _add_book_impl, _delete_book_impl,
        _convert_book_impl, _export_book_impl, _list_importable_files_impl,
        _list_export_files_impl, _search_books_impl, _get_book_details_impl,
        _get_book_content_impl, _fts_search_impl, _search_book_content_impl,
        _list_libraries_impl, _list_help_topics_impl, _get_help_topic_impl,
        SEARCH_CACHE, MAX_CACHE_SIZE,
    )
except ImportError:
    from logic import *
    from logic import (
        _normalize_series_field, _validate_and_normalize_changes,
        _get_library_schema_impl, _update_book_impl, _bulk_update_metadata_impl,
        _get_field_values_impl, _add_book_impl, _delete_book_impl,
        _convert_book_impl, _export_book_impl, _list_importable_files_impl,
        _list_export_files_impl, _search_books_impl, _get_book_details_impl,
        _get_book_content_impl, _fts_search_impl, _search_book_content_impl,
        _list_libraries_impl, _list_help_topics_impl, _get_help_topic_impl,
        SEARCH_CACHE, MAX_CACHE_SIZE,
    )
