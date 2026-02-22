"""
logic/ package — business logic for the Calibre MCP server.

Book-reading functions live here directly (they are small and self-contained).
Metadata and library-operation functions are re-exported from their sub-modules
so callers see a flat namespace identical to the old library_logic.py.
"""

import os
import nltk
import logging
import glob
from datetime import datetime

from .text_search import _find_fts_matches

# Re-export everything from sub-modules for a flat namespace
from .metadata_ops import (
    _normalize_series_field,
    _validate_and_normalize_changes,
    _get_library_schema_impl,
    _update_book_impl,
    _bulk_update_metadata_impl,
    _get_field_values_impl,
)
from .library_ops import (
    _add_book_impl,
    _delete_book_impl,
    _convert_book_impl,
    _export_book_impl,
    _list_importable_files_impl,
    _list_export_files_impl,
)

# --- Book Reading Functions ---

def _search_books_impl(worker_pool, query: str | None = None, library_name: str | None = None, limit: int = 50, offset: int = 0, fields: list[str] | None = None, text_field_limit: int | None = None) -> dict:
    logging.info(f"_search_books_impl called for query '{query}' and library_name '{library_name}' and limit '{limit}' and offset '{offset}' and fields '{fields}' and text_field_limit '{text_field_limit}'")
    res = worker_pool.send_rpc(library_name, "search_books", {
        "query": query or "", "limit": limit, "offset": offset, "fields": fields, "text_field_limit": text_field_limit
    })
    logging.debug(f"_search_books_impl returning result '{res}'")
    return res


def _get_book_details_impl(worker_pool, config_manager, book_id: int, library_name: str | None = None, fields: list[str] | None = None) -> dict:
    logging.info(f"_get_book_details_impl called for book_id '{book_id}' and library_name '{library_name}' and fields '{fields}'")
    details = worker_pool.send_rpc(library_name, "get_book_details", {"book_id": book_id, "fields": fields})

    lib_conf = config_manager.get_library_config(library_name)
    if lib_conf:
        perms = lib_conf.get("permissions", {})
        read_perm = perms.get("read")
        if isinstance(read_perm, list):
            allowed_keys = set(read_perm) | {'book_id'}
            res = {k: v for k, v in details.items() if k in allowed_keys}
            logging.debug(f"_get_book_details_impl returning result '{res}'")
            return res

    logging.debug(f"_get_book_details_impl returning result '{details}'")
    return details


def _get_book_content_impl(worker_pool, config_manager, book_id: int, library_name: str | None = None, limit: int = 30000, offset: int = 0, sentence_aware: bool = True) -> dict:
    logging.info(f"_get_book_content_impl called for book_id '{book_id}' and library_name '{library_name}' and limit '{limit}' and offset '{offset}' and sentence_aware '{sentence_aware}'")

    auto_convert = False
    lib_conf = config_manager.get_library_config(library_name)
    if lib_conf:
        auto_convert = lib_conf.get("permissions", {}).get("convert", False)

    res = worker_pool.send_rpc(library_name, "get_book_content", {
        "book_id": book_id,
        "limit": limit,
        "offset": offset,
        "auto_convert": auto_convert
    })

    if not res or "content" not in res:
        logging.debug(f"_get_book_content_impl returning result '{res}'")
        return res

    content = res["content"]
    if sentence_aware and len(content) > limit:
        sentences = nltk.sent_tokenize(content, language='english')
        current_len = 0
        split_point = len(content)

        for s in sentences:
            next_len = current_len + len(s)
            if next_len > limit:
                if (next_len - limit) < (limit - current_len):
                    split_point = next_len
                else:
                    split_point = current_len if current_len > 0 else next_len
                break
            current_len = next_len

        content = content[:split_point]
        res["content"] = content
        res["actual_length"] = len(content)

    res["next_offset"] = offset + len(content)
    logging.debug(f"_get_book_content_impl returning result of length '{len(res['content'])}'")
    return res


def _fts_search_impl(worker_pool, query: str, library_name: str | None = None) -> list:
    logging.info(f"_fts_search_impl called for query '{query}' and library_name '{library_name}'")
    res = worker_pool.send_rpc(library_name, "fts_search", {"query": query})
    logging.debug(f"_fts_search_impl returning result '{res}'")
    return res

# Global cache for book content search results
# Key: (library_name, book_id, query), Value: {'timestamp': float, 'results': list}
SEARCH_CACHE = {}
MAX_CACHE_SIZE = 50
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

def _purge_search_cache():
    """Remove expired entries from SEARCH_CACHE."""
    now = datetime.now().timestamp()
    expired_keys = [
        k for k, v in SEARCH_CACHE.items()
        if now - v["timestamp"] > CACHE_TTL_SECONDS
    ]
    for k in expired_keys:
        logging.debug(f"Purged expired book content search {k}")
        del SEARCH_CACHE[k]

def _search_book_content_impl(worker_pool, config_manager, book_id: int, query: str, hit_limit: int = 10, offset: int = 0, library_name: str | None = None) -> dict:
    logging.info(f"_search_book_content_impl called for book_id '{book_id}' and query '{query}' and hit_limit '{hit_limit}' and offset '{offset}' and library_name '{library_name}'")
    auto_convert = False
    lib_conf = config_manager.get_library_config(library_name)
    if lib_conf:
        if lib_conf.get("permissions", {}).get("convert"):
            auto_convert = True

    cache_key = (library_name, book_id, query)
    cached_data = SEARCH_CACHE.get(cache_key)

    if cached_data:
        # Update timestamp on hit so it stays alive
        cached_data["timestamp"] = datetime.now().timestamp()
    else:
        res = worker_pool.send_rpc(library_name, "get_book_content", {
            "book_id": book_id,
            "limit": None,
            "offset": 0,
            "auto_convert": auto_convert
        })

        if not res or "content" not in res:
            logging.debug(f"_search_book_content_impl returning error 'Could not retrieve content for book {book_id}. Ensure it exists and is convertible to TXT.'")
            raise RuntimeError(f"Could not retrieve content for book {book_id}. Ensure it exists and is convertible to TXT.")

        full_text = res["content"]

        try:
            spans = _find_fts_matches(full_text, query)
            search_results = []
            snippet_padding = 100

            for start, end in spans:
                snippet_start = max(0, start - snippet_padding)
                snippet_end = min(len(full_text), end + snippet_padding)
                snippet = full_text[snippet_start:snippet_end]
                rel_start = start - snippet_start
                rel_end = end - snippet_start
                search_results.append({
                    "start": start,
                    "length": end - start,
                    "text": snippet,
                    "match_in_text": [rel_start, rel_end]
                })

            cached_data = {
                "timestamp": datetime.now().timestamp(),
                "results": search_results
            }

            if len(SEARCH_CACHE) >= MAX_CACHE_SIZE:
                sorted_keys = sorted(SEARCH_CACHE.keys(), key=lambda k: SEARCH_CACHE[k]["timestamp"])
                logging.debug(f"Cache full. Purged oldest book content search {sorted_keys[0]}")
                del SEARCH_CACHE[sorted_keys[0]]

            SEARCH_CACHE[cache_key] = cached_data

        except Exception as e:
            logging.debug(f"_search_book_content_impl returning error 'Search processing failed: {e}'")
            raise RuntimeError(f"Search processing failed: {e}")

    all_results = cached_data["results"]
    paged_results = all_results[offset: offset + hit_limit]

    res = {
        "book_id": book_id,
        "query": query,
        "total_results": len(all_results),
        "offset": offset,
        "limit": hit_limit,
        "results": paged_results
    }

    _purge_search_cache() # purge expired searches
    logging.debug(f"_search_book_content_impl returning result '{res}'")
    return res


# --- Resource / Help Functions ---

def _list_libraries_impl(config_manager) -> list:
    logging.info("_list_libraries_impl called")
    res = config_manager.list_libraries()
    logging.debug(f"_list_libraries_impl returning result '{res}'")
    return res


def _list_help_topics_impl(skills_dir: str) -> str:
    logging.info("_list_help_topics_impl called")
    files = glob.glob(os.path.join(skills_dir, "*.md"))
    topics = [os.path.splitext(os.path.basename(f))[0] for f in files]
    res = "Available help topics:\n" + "\n".join(f"- {t}" for t in topics)
    logging.debug(f"_list_help_topics_impl returning result '{res}'")
    return res


def _get_help_topic_impl(topic: str, skills_dir: str) -> str:
    logging.info(f"_get_help_topic_impl called for topic '{topic}' and skills_dir '{skills_dir}'")
    if ".." in topic or "/" in topic or "\\" in topic:
        logging.debug(f"_get_help_topic_impl returning error 'Invalid topic name.'")
        raise ValueError("Invalid topic name.")
    safe_topic = os.path.basename(topic)
    file_path = os.path.join(skills_dir, f"{safe_topic}.md")
    if not os.path.exists(file_path):
        logging.debug(f"_get_help_topic_impl returning error 'Help topic '{topic}' not found.'")
        raise ValueError(f"Help topic '{topic}' not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        res = f.read()
        logging.debug(f"_get_help_topic_impl returning result of length '{len(res)}'")
        return res
