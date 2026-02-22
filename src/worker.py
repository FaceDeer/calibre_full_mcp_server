import sys
import json
import os
import re
import tempfile
import traceback
import contextlib
from datetime import datetime

try:
    from calibre.library import db
    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.ebooks.metadata.meta import get_metadata
    from calibre.ebooks.conversion.plumber import Plumber
    from calibre.utils.logging import Log
except ImportError:
    # These will be missing if not run with calibre-debug,
    # we'll report this more gracefully in main()
    db = Metadata = get_metadata = Plumber = Log = None

STANDARD_DESCRIPTIONS = {
    "comments": "The main description or summary of the book.",
    "title": "The title of the book.",
    "sort": "The version of the title that is used for sorting.",
    "authors": "The authors of the book.",
    "author_sort": "The version of the author name that is used for sorting.",
    "tags": "The tags associated with the book.",
    "pages": "The estimated number of pages in the book. Special values: -3 = book has DRM, -2 = error, -1 = None",
    "path": "The folder the ebook's files are stored in relative to the library root",
    "marked": "Used to mark books temporarily. Not persistent, is cleared when the Calibre process ends.",
    "last_modified": "The last modified date of the entry in the database.",
    "timestamp": "The timestamp this entry was added to the database.",
    "formats": "The formats available for the book.",
    "identifiers": "The identifiers associated with the book, such as ISBN, ASIN, etc.",
    "pubdate": "The publication date of the book.",
    "publisher": "The publisher of the book.",
    "rating": "The rating of the book.",
    "series": "The series the book belongs to.",
    "series_index": "The index of the book in its series.",
    "series_sort": "The version of the series name that is used for sorting.",
    "languages": "ISO 639 codes for the languages the book is written in.",
    "uuid": "A uuid for the book used internally by Calibre.",
    "size": "The size of the book in bytes.",
    "au_map": "Used internally by Calibre for mapping author ids to books",
    "cover": "An integer that functions as a boolean flag to indicate if the book has a cover image.",
    "ondevice": "Indicates whether the book is also present on a connected mobile device.",
    "in_tag_browser": "Internal state field used by Calibre's UI."
}

# This script is designed to be run via `calibre-debug src/worker.py`
# It acts as a bridge to the Calibre internal API.

class JsonSafeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles non-standard types returned by Calibre.
    """
    def default(self, obj):
        try:
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if isinstance(obj, (set, frozenset)):
                return list(obj)
            if isinstance(obj, bytes):
                return obj.decode('utf-8', errors='replace')
            # Handle Calibre-specific metadata objects if they leak through
            if hasattr(obj, '__dict__'):
                return str(obj)
            return super().default(obj)
        except Exception:
            return str(obj)

# Format preference for conversion source
SOURCE_FORMAT_PRIORITY = ['LIT', 'MOBI', 'AZW', 'EPUB', 'AZW3', 'FB2', 'DOCX', 'HTML', 'PRC', 'RTF', 'TXT', 'PDF']

def _get_best_source_format(available_formats):
    """
    Select the best source format from available formats.
    """
    if not available_formats:
        return None
    available_upper = [f.upper() for f in available_formats]
    for fmt in SOURCE_FORMAT_PRIORITY:
        if fmt in available_upper:
            return fmt
    # Fallback: pick the first one
    if available_upper:
        return available_upper[0]
    return None

def _ensure_format(database, book_id, target_format, auto_convert):
    """
    Ensures that the book has the target format.
    If not, tries to convert if auto_convert is True.
    Returns (path_to_format, error_message, was_converted, source_format)
    """
    if book_id is None:
        return None, "book_id is required", False, None
    
    target_format = target_format.upper()
    was_converted = False
    source_format = None
    
    if not database.has_format(book_id, target_format):
        if auto_convert:
            # Auto-convert logic
            formats_str = database.formats(book_id)
            avail_formats = formats_str.split(",") if hasattr(formats_str, 'split') else formats_str
            source_format = _get_best_source_format(avail_formats)
            
            if source_format:
                try:
                    if Plumber is None or Log is None:
                        return None, "Calibre conversion libraries (Plumber/Log) not available.", False, None
                        
                    with tempfile.TemporaryDirectory() as temp_dir:
                        source_path = os.path.join(temp_dir, f"source.{source_format.lower()}")
                        database.copy_format_to(book_id, source_format, source_path)
                        output_path = os.path.join(temp_dir, f"output.{target_format.lower()}")
                        
                        log = Log()
                        plumber = Plumber(source_path, output_path, log)
                        with contextlib.redirect_stdout(sys.stderr):
                            #redirecting stdout to stderr to avoid polluting the JSON-RPC channel
                            plumber.run()
                        
                        if os.path.exists(output_path):
                             database.add_format(book_id, target_format, output_path, replace=True)
                             was_converted = True
                        else:
                             return None, f"Auto-conversion to {target_format} failed for book_id {book_id}.", False, source_format
                except Exception as conv_err:
                     return None, f"Auto-conversion failed: {conv_err}", False, source_format
            else:
                return None, f"No suitable source format found for auto-conversion of book_id {book_id}", False, None
        else:
             return None, f"Format {target_format} not found for book_id {book_id}", False, None
    
    path = database.format_abspath(book_id, target_format)
    if not path or not os.path.exists(path):
        return None, f"File missing on disk for {target_format}", was_converted, source_format
        
    return path, None, was_converted, source_format

def _get_field_value_counts(db, field_name, book_ids, regex):
    """
    Return a dictionary {value: count} for the specified field.

    For multi‑value fields (e.g., tags, authors) each item contributes
    separately to the count. For identifiers, each key:value pair is
    converted to a string "key:value". For all other fields the stored
    value is converted to a string. Empty values (None, empty list, empty dict)
    are ignored.

    Args:
        db: A Calibre LibraryDatabase object (or db.new_api).
        field_name: The lookup name of the field. For custom columns this
                    must include the '#' prefix (e.g., '#mytags').
        book_ids: Optional list of book IDs to consider. If None, all books.
        regex: Optional regex pattern (string or compiled re.Pattern) to filter
               values. Only values that match the regex (via re.search) are counted.

    Returns:
        dict: {string_value: integer_count}
    """
    # Pre‑compile regex if given as string
    if regex is not None and not hasattr(regex, 'search'):
        regex = re.compile(regex)

    # Fetch values only for the requested books (or all if book_ids is None)
    # database in main() is already the new_api (Cache object) if available
    api = getattr(db, 'new_api', db)
    
    if hasattr(api, 'get_field_values_for_all_books'):
        values_by_book = api.get_field_values_for_all_books(
            field_name, book_ids=book_ids
        )
    else:
        # Fallback to all_field_for which exists on most versions of Cache objects
        if book_ids is not None:
            target_ids = book_ids
        elif hasattr(api, 'all_book_ids'):
            target_ids = api.all_book_ids()
        else:
            # Last resort
            target_ids = list(api.search(''))
            
        values_by_book = api.all_field_for(field_name, target_ids)


    counts = {}


    for book_id, value in values_by_book.items():
        if value is None:
            continue

        # ---- Helper to add a value if it passes regex filter ----
        def add_if_matches(key_candidate):
            s = str(key_candidate)
            if regex is None or regex.search(s):
                counts[s] = counts.get(s, 0) + 1

        # Handle different value types
        if isinstance(value, list):
            # Multi‑value field (tags, authors, etc.)
            for item in value:
                if item:  # skip empty strings
                    add_if_matches(item)

        elif isinstance(value, dict):
            # Identifiers (or any dict‑based custom column)
            for k, v in value.items():
                if k and v:  # both parts present
                    combined = f"{k}:{v}"
                    add_if_matches(combined)

        else:
            # Single value (ratings, series, text, numbers, etc.)
            if value != "":
                add_if_matches(value)

    return counts

def main():
    # 1. Check Calibre libraries
    if db is None:
        error_msg = {"error": "Failed to import calibre libraries. Run this with calibre-debug."}
        print(json.dumps(error_msg), file=sys.stderr)
        sys.exit(1)

    # 2. Initialize Database
    if len(sys.argv) > 1:
        library_path = sys.argv[1]
    else:
        # Fallback for compatibility/testing
        library_path = os.path.abspath("test_library")
    
    if not os.path.exists(library_path):
        print(json.dumps({"error": f"Library not found at {library_path}"}), file=sys.stderr)
        sys.exit(1)

    try:
        database = db(library_path)
        if hasattr(database, 'new_api'):
            database = database.new_api
    except Exception as e:
        print(json.dumps({"error": f"DB Init failed: {str(e)}", "traceback": traceback.format_exc()}), file=sys.stderr)
        sys.exit(1)

    # Signal readiness
    print(json.dumps({"status": "ready", "library": library_path}), file=sys.stderr)
    sys.stderr.flush()

    # 3. Main Loop
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")

            result = None
            error = None

            try:
                if method == "search_books":
                    query = params.get("query", "")
                    limit = params.get("limit", 50)
                    offset = params.get("offset", 0)
                    fields = params.get("fields")
                    text_field_limit = params.get("text_field_limit")
                    
                    try:
                        all_ids = database.search_getting_ids(query, None, sort_results=True)
                        if not isinstance(all_ids, (list, tuple)):
                            all_ids = list(all_ids)
                    except AttributeError:
                        all_ids = sorted(list(database.search(query)))
                    except Exception as e:
                        print(f"Search error: {e}", file=sys.stderr)
                        all_ids = []

                    ids = all_ids[offset : offset + limit]
                    
                    books = []
                    for book_id in ids:
                        try:
                            mi = database.get_metadata(book_id)
                            
                            if not fields:
                                book_data = {
                                    "book_id": int(book_id),
                                    "title": str(mi.title),
                                    "authors": list(mi.authors),
                                    "formats": list(database.formats(book_id))
                                }
                            else:
                                book_data = {"book_id": int(book_id)}
                                for field in fields:
                                    val = None
                                    if field == "formats":
                                        val = database.formats(book_id)
                                    elif field.startswith("#"):
                                        val = mi.get(field)
                                    elif hasattr(mi, field):
                                        val = getattr(mi, field)
                                    
                                    if text_field_limit and isinstance(val, str) and len(val) > text_field_limit:
                                        val = val[:text_field_limit] + "..."
                                        
                                    book_data[field] = val
                            books.append(book_data)
                        except Exception as item_err:
                            print(f"Error processing book {book_id}: {item_err}", file=sys.stderr)
                            continue

                    result = books
                
                elif method == "get_book_details":
                    book_id = params.get("book_id")
                    fields = params.get("fields")
                    if book_id is None:
                        raise ValueError("book_id is required")
                    
                    result = {
                        'book_id': int(book_id)
                    }
                    # We're avoiding using get_metadata() because it returns stringified values for some fields
                    all_fields = database.field_metadata.all_field_keys()
                    if fields:
                        all_fields = [field for field in fields if field in all_fields]
                    for field in all_fields:
                        val = database.field_for(field, book_id)
                        if val is None:
                            continue
                        # Convert datetime objects to ISO strings for JSON compatibility
                        if isinstance(val, datetime):
                            val = val.isoformat()
                        # Ensure tuples (like authors) become lists for JSON
                        if isinstance(val, tuple):
                            if not val:
                                # Skip empty tuples
                                continue
                            val = list(val)
                        if isinstance(val, dict):
                            if not val:
                                # Skip empty dictionaries. Only "identifiers" should return a dictionary, but might as well future-proof it.
                                continue

                        result[field] = val
               
                elif method == "get_library_schema":
                    schema = {}
                    field_meta = database.field_metadata
                    all_fields = field_meta.all_field_keys()
                    
                    for key in all_fields:
                        meta = field_meta[key]
                        schema[key] = {
                            "name": str(meta.get("name", "")),
                            "datatype": str(meta.get("datatype", ""))
                        }

                        if field_meta.is_custom_field(key):
                            if field_meta.is_series_index(key):
                                schema[key]["description"] = f"index for the {key[:-len('_index')]} series field"
                            elif description := meta.get("display", {}).get("description", ""):
                                schema[key]["description"] = description
                        else:
                            standard_desc = STANDARD_DESCRIPTIONS.get(key, "")
                            if standard_desc:
                                schema[key]["description"] = standard_desc

                        if meta.get("datatype", "") == "text":
                            if separator := meta.get("is_multiple",{}).get("ui_to_list", ""):
                                schema[key]["separator"] = separator

                        if meta.get('datatype') == 'enumeration':
                            allowed_values = meta.get('display', {}).get('enum_values', [])
                            schema[key]["allowed_values"] = allowed_values
                    result = schema

                elif method == "add_book":
                    file_paths = params.get("file_paths")
                    if not file_paths:
                        raise ValueError("file_paths (list) is required")
                    
                    books_to_add = []
                    for p in file_paths:
                        if not os.path.exists(p):
                            print(f"Warning: File not found {p}", file=sys.stderr)
                            continue
                        
                        ext = os.path.splitext(p)[1].lower().replace(".", "")
                        if not ext:
                            ext = "unknown"
                            
                        mi = None
                        try:
                            with open(p, 'rb') as f:
                                mi = get_metadata(f, stream_type=ext)
                        except Exception as e:
                            print(f"Metadata extraction failed for {p}: {e}", file=sys.stderr)
                        
                        if mi is None:
                            mi = Metadata(os.path.basename(p))
                            
                        books_to_add.append((mi, {ext.upper(): p}))
                    
                    if not books_to_add:
                        raise ValueError("No valid books to add")
                        
                    ids, _ = database.add_books(books_to_add)
                    result = {"status": "success", "book_ids": [int(i) for i in ids]}

                elif method == "convert_book":
                    book_id = params.get("book_id")
                    target_format = params.get("target_format")
                    
                    if not book_id or not target_format:
                        raise ValueError("book_id and target_format are required")
                    
                    path, error, was_converted, source_format = _ensure_format(
                        database, book_id, target_format, auto_convert=True
                    )
                    
                    if error:
                        raise RuntimeError(error)
                        
                    result = {
                        "status": "success", 
                        "book_id": book_id, 
                        "source_format": source_format, 
                        "target_format": target_format.upper(),
                        "was_converted": was_converted,
                        "path": str(path)
                    }

                elif method == "export_book":
                    book_id = params.get("book_id")
                    target_format = params.get("format")
                    file_path = params.get("file_path")
                    
                    if not book_id or not file_path:
                        raise ValueError("book_id and file_path are required")
                    
                    # If no format specified, pick the best one available
                    if not target_format:
                        formats_str = database.formats(book_id)
                        avail_formats = formats_str.split(",") if hasattr(formats_str, 'split') else formats_str
                        target_format = _get_best_source_format(avail_formats)
                        
                    if not target_format:
                         raise ValueError(f"No suitable format found for book_id {book_id}")

                    # Ensure format exists (converts to library if needed)
                    path, error, was_converted, source_format = _ensure_format(
                        database, book_id, target_format, auto_convert=True
                    )
                    
                    if error:
                        raise RuntimeError(f"Export failed: {error}")
                    
                    # Copy from library to target path
                    database.copy_format_to(book_id, target_format.upper(), file_path)
                    
                    result = {
                        "status": "success",
                        "book_id": book_id,
                        "format": target_format.upper(),
                        "file_path": file_path,
                        "was_converted": was_converted,
                        "source_format": source_format
                    }

                elif method == "delete_book":
                    book_id = params.get("book_id")
                    formats_to_delete = params.get("formats") # Optional list of strings

                    if book_id is None:
                        raise ValueError("book_id is required")
                    
                    if formats_to_delete:
                        # logical delete of specific formats
                        # remove_formats(formats_map, db_only=False)
                        # map is {book_id: [formats]}
                        database.remove_formats({int(book_id): formats_to_delete})
                        result = f"Formats {formats_to_delete} deleted from book_id {book_id}."
                    else:
                        # Full delete
                        database.remove_books([book_id], permanent=True)
                        result = f"book_id {book_id} deleted."

                elif method == "bulk_update_metadata":
                    field_name = params.get("field_name")
                    old_value = params.get("old_value")
                    new_value = params.get("new_value")
                    book_ids = params.get("book_ids")
                    
                    if not book_ids:
                         try:
                            # Use search('') to get all
                            all_ids = database.search_getting_ids('', None, sort_results=True)
                            if not isinstance(all_ids, (list, tuple)):
                                all_ids = list(all_ids)
                            book_ids = all_ids
                         except Exception:
                            book_ids = list(database.search(''))
                    
                    updated_count = 0
                    errors = []

                    for book_id in book_ids:
                        try:
                            mi = database.get_metadata(book_id)
                            current_val = None
                            is_custom = field_name.startswith("#")
                            
                            # Get current value
                            if is_custom:
                                current_val = mi.get(field_name)
                            elif hasattr(mi, field_name):
                                current_val = getattr(mi, field_name)
                            elif field_name == "identifiers":
                                current_val = mi.identifiers
                            else:
                                pass
                            
                            should_update = False
                            final_val = current_val
                            

                            # Handle tuples (authors)
                            if isinstance(final_val, tuple):
                                final_val = list(final_val)

                            # --- Logic for modification ---
                            
                            if isinstance(final_val, list):
                                # Multi-value (List) - Tags, Authors
                                # Ensure we are working with a list copy of STRINGS
                                temp_list = list(final_val) if final_val else []
                                vals_to_add = new_value if isinstance(new_value, list) else ([new_value] if new_value is not None else [])
                                
                                if old_value is not None:
                                    if old_value in temp_list:
                                        # Match found
                                        if new_value is not None:
                                            # Replace logic
                                            new_list = []
                                            replaced_any = False
                                            for x in temp_list:
                                                if x == old_value:
                                                    new_list.extend(vals_to_add)
                                                    replaced_any = True
                                                else:
                                                    new_list.append(x)
                                            
                                            if replaced_any:
                                                temp_list = new_list
                                                should_update = True
                                        else:
                                            # Remove logic
                                            while old_value in temp_list:
                                                temp_list.remove(old_value)
                                            should_update = True
                                else:
                                    # Add logic
                                    for v in vals_to_add:
                                        if v not in temp_list:
                                            temp_list.append(v)
                                            should_update = True
                                
                                if should_update:
                                    final_val = temp_list

                            elif isinstance(final_val, dict):
                                # ... (existing logic)
                                temp_dict = final_val.copy() if final_val else {}
                                
                                if new_value is not None and isinstance(new_value, dict):
                                    temp_dict.update(new_value)
                                    should_update = True
                                
                                if should_update:
                                    final_val = temp_dict
                            
                            else:
                                # Single Value
                                if old_value is not None:
                                    if current_val == old_value:
                                        if new_value is not None:
                                            final_val = new_value
                                            should_update = True
                                        else:
                                            final_val = None
                                            should_update = True
                                else:
                                    # Overwrite
                                    if new_value is not None:
                                        final_val = new_value
                                        should_update = True
                            
                            # --- Apply Update ---
                            if should_update:
                                if is_custom:
                                    mi.set_user_metadata(field_name, final_val)
                                elif field_name == "identifiers":
                                    mi.set_identifiers(final_val)
                                else:
                                    setattr(mi, field_name, final_val)
                                
                                database.set_metadata(book_id, mi)
                                updated_count += 1
                                
                        except Exception as e:
                            errors.append(f"Book {book_id}: {str(e)}")

                    result = {
                        "status": "success", 
                        "updated_count": updated_count,
                        "processed_count": len(book_ids),
                        "errors": errors
                    }

                elif method == "update_book":
                    book_id = params.get("book_id")
                    changes = params.get("changes")
                    if not book_id or not changes:
                        raise ValueError("book_id and changes are required")
                    
                    mi = database.get_metadata(book_id)
                    for key, value in changes.items():
                        if key.startswith("#"):
                            if key in database.field_metadata.custom_field_keys():
                                mi.set_user_metadata(key, value)
                        elif hasattr(mi, key):
                            setattr(mi, key, value)
                    
                    database.set_metadata(book_id, mi)
                    result = {"status": "success", "book_id": int(book_id), "changes": list(changes.keys())}

                elif method == "get_book_content":
                    book_id = params.get("book_id")
                    limit_raw = params.get("limit")
                    offset = params.get("offset", 0)
                    auto_convert = params.get("auto_convert", False)

                    if book_id is None:
                        raise ValueError("book_id is required")
                    
                    path, error, was_converted, source_format = _ensure_format(database, book_id, "TXT", auto_convert)
                    
                    if not error:
                        try:
                            with open(path, "r", encoding="utf-8", errors="replace") as f:
                                full_content = f.read()
                                if limit_raw is not None:
                                    content = full_content[offset : offset + limit_raw]
                                else:
                                    content = full_content[offset:]
                                    
                                result = {
                                    "content": content,
                                    "path": str(path),
                                    "offset": offset,
                                    "limit_requested": limit_raw,
                                    "actual_length": len(content),
                                    "total_length": len(full_content)
                                }
                        except Exception as read_err:
                            error = f"Failed to read file: {read_err}"

                elif method == "fts_search":
                    query = params.get("query", "")
                    if not hasattr(database, 'fts_search'):
                        error = "Full-Text Search (FTS) is not supported by this Calibre version or API."
                    else:
                        try:
                            #This Calibre API is not documented. I found the parameters by inspecting the source code.
                            raw_res = database.fts_search(query, 
                                use_stemming=True,
                                highlight_start="", 
                                highlight_end="",
                                snippet_size=64,
                                return_text=True
                            )
                            try:
                                results = list(raw_res) 
                            except TypeError:
                                results = str(raw_res)
                            result = results
                        except Exception as fts_err:
                            error = f"FTS Error: {str(fts_err)}."
                elif method == "get_field_value_counts":
                    field_name = params.get("field_name")
                    book_ids = params.get("book_ids")
                    regex = params.get("regex")
                    
                    if not field_name:
                        raise ValueError("field_name is required")
                        
                    result = _get_field_value_counts(database, field_name, book_ids, regex)
                else:
                    error = f"Method '{method}' not found"


            except Exception as e:
                error = str(e)
                print(f"Internal Error processing {method}: {traceback.format_exc()}", file=sys.stderr)

            # Send Response
            response = {
                "jsonrpc": "2.0",
                "id": req_id
            }
            if error:
                response["error"] = {"code": -32603, "message": error}
            else:
                response["result"] = result
            
            try:
                print(json.dumps(response, cls=JsonSafeEncoder))
                sys.stdout.flush()
            except Exception as ser_err:
                # Final fallback for serialization errors
                print(f"Serialization Error: {ser_err}", file=sys.stderr)
                # Create a minimal safe error response
                safe_err = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"Data serialization failed: {ser_err}"}
                }
                print(json.dumps(safe_err))
                sys.stdout.flush()

        except json.JSONDecodeError:
            print("JSON Decode Error", file=sys.stderr)
        except Exception as e:
            print(f"Fatal Loop Error: {e}", file=sys.stderr)
            break

if __name__ == "__main__":
    main()
