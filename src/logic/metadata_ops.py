import re
import logging
from dateutil import parser as dateutil_parser
from datetime import datetime

from .permissions import get_lib_conf, check_write_permission, check_write_permission_single_field, check_read_permission

# Schema cache: avoids repeated RPC calls for the same library since library schema doesn't change
_library_schemata = {}


def _get_library_schema_impl(worker_pool, config_manager, library_name: str | None = None) -> dict:
    logging.info(f"_get_library_schema_impl called for library_name '{library_name}'")
    if library_name in _library_schemata:
        logging.debug(f"_get_library_schema_impl returning cached schema for library_name '{library_name}'")
        return _library_schemata[library_name]

    schema = worker_pool.send_rpc(library_name, "get_library_schema")
    lib_conf = config_manager.get_library_config(library_name)
    if lib_conf:
        perms = lib_conf.get("permissions", {})
        read_perm = perms.get("read")
        write_perm = perms.get("write")

        # Skip filtering if either permission is True — agent should see all columns
        if read_perm is not True and write_perm is not True:
            allowed_cols = set()
            for perm in [read_perm, write_perm]:
                if isinstance(perm, list) and perm:
                    allowed_cols.update(perm)

            filtered_schema = {k: v for k, v in schema.items() if k in allowed_cols}
            _library_schemata[library_name] = filtered_schema
            return filtered_schema

    _library_schemata[library_name] = schema
    logging.debug(f"_get_library_schema_impl returning schema: {schema}")
    return schema


def _normalize_series_field(series_input: str) -> tuple[str, float | None]:
    """
    Normalize series field input by extracting series name and optional index.
    Supports the Calibre bracket notation e.g. "My Series [2]".
    """
    logging.debug(f"_normalize_series_field called for series_input '{series_input}'")
    series_input = series_input.strip()

    if '[' not in series_input and ']' not in series_input:
        logging.debug(f"_normalize_series_field returning series_input '{series_input}' as is")
        return series_input, None

    if series_input.count('[') != 1 or series_input.count(']') != 1:
        logging.debug(f"Invalid series format: multiple bracket pairs found in '{series_input}'")
        raise ValueError(f"Invalid series format: multiple bracket pairs found in '{series_input}'")

    bracket_pattern = r'^(.*?)\s*\[([^\]]+)\]$'
    match = re.match(bracket_pattern, series_input)

    if not match:
        logging.debug(f"Invalid series format: brackets must be at the end in '{series_input}'")
        raise ValueError(f"Invalid series format: brackets must be at the end in '{series_input}'")

    series_name = match.group(1).rstrip()
    index_str = match.group(2)

    if series_input.count(']') > 0 and series_input.rfind(']') != len(series_input) - 1:
        logging.debug(f"Invalid series format: content found after closing bracket in '{series_input}'")
        raise ValueError(f"Invalid series format: content found after closing bracket in '{series_input}'")

    try:
        series_index = float(index_str)
    except ValueError:
        logging.debug(f"Invalid series index: '{index_str}' is not a valid number in '{series_input}'")
        raise ValueError(f"Invalid series index: '{index_str}' is not a valid number in '{series_input}'")

    logging.debug(f"_normalize_series_field returning series_name '{series_name}' and series_index '{series_index}'")
    return series_name, series_index


def _validate_and_normalize_changes(changes: dict, schema: dict) -> tuple[dict, list[str]]:
    """
    Validates and normalizes the changes dictionary according to the library schema.

    Returns:
        Tuple of (normalized_changes, error_messages).
        If error_messages is non-empty, the changes should not be applied.
    """
    logging.debug(f"_validate_and_normalize_changes called for changes '{changes}' and schema '{schema}'")
    normalized = {}
    errors = []

    for field_name, value in changes.items():
        if field_name not in schema:
            errors.append(f"Field '{field_name}' does not exist in the library schema.")
            continue

        field_schema = schema[field_name]
        datatype = field_schema.get("datatype")

        try:
            if datatype == "text":
                # Special case: identifiers is marked as text but should be a dictionary
                if field_name == "identifiers":
                    if isinstance(value, dict):
                        normalized[field_name] = value
                    else:
                        errors.append(f"Field '{field_name}': expected dictionary, got {type(value).__name__}.")
                else:
                    separator = field_schema.get("separator")
                    if separator:
                        if isinstance(value, str):
                            normalized[field_name] = [item.strip() for item in value.split(separator) if item.strip()]
                        elif isinstance(value, list):
                            normalized[field_name] = [str(item).strip() for item in value if str(item).strip()]
                        else:
                            errors.append(f"Field '{field_name}' (text with separator): expected string or list, got {type(value).__name__}.")
                    else:
                        normalized[field_name] = value if isinstance(value, str) else str(value)

            elif datatype == "series":
                if not isinstance(value, str):
                    value = str(value)
                try:
                    s_name, s_index = _normalize_series_field(value)
                    normalized[field_name] = s_name
                    if s_index is not None:
                        index_field = field_name + "_index"
                        if index_field in changes:
                            try:
                                provided_index = float(changes[index_field])
                                if provided_index != s_index:
                                    errors.append(
                                        f"Field '{field_name}': series string '{value}' implies index {s_index}, "
                                        f"but '{index_field}' is also provided with a different value of {provided_index}."
                                    )
                            except (ValueError, TypeError):
                                pass
                        else:
                            normalized[index_field] = s_index
                except ValueError as e:
                    errors.append(f"Field '{field_name}' (series): {str(e)}")

            elif datatype == "rating":
                try:
                    rating_val = int(value)
                    if rating_val < 0 or rating_val > 10:
                        errors.append(f"Field '{field_name}' (rating): value must be between 0 and 10, got {rating_val}.")
                    else:
                        normalized[field_name] = rating_val
                except (ValueError, TypeError):
                    errors.append(f"Field '{field_name}' (rating): expected integer 0-10, got {type(value).__name__} '{value}'.")

            elif datatype == "datetime":
                if isinstance(value, str):
                    try:
                        parsed_dt = dateutil_parser.parse(value)
                        normalized[field_name] = parsed_dt.isoformat()
                    except (ValueError, TypeError) as e:
                        errors.append(f"Field '{field_name}' (datetime): unable to parse '{value}' as a date/time: {str(e)}.")
                elif isinstance(value, datetime):
                    normalized[field_name] = value.isoformat()
                else:
                    errors.append(f"Field '{field_name}' (datetime): expected string or datetime object, got {type(value).__name__}.")

            elif datatype == "int":
                try:
                    normalized[field_name] = int(value)
                except (ValueError, TypeError):
                    errors.append(f"Field '{field_name}' (int): expected integer, got {type(value).__name__} '{value}'.")

            elif datatype == "float":
                try:
                    normalized[field_name] = float(value)
                except (ValueError, TypeError):
                    errors.append(f"Field '{field_name}' (float): expected number, got {type(value).__name__} '{value}'.")

            elif datatype == "composite":
                errors.append(f"Field '{field_name}' is a composite field and cannot be written to.")

            elif datatype == "enumeration":
                allowed_values = field_schema.get("allowed_values", [])
                if value == "" or value in allowed_values:
                    normalized[field_name] = value
                else:
                    errors.append(f"Field '{field_name}' (enumeration): value '{value}' not in allowed values {allowed_values}. Empty string is also allowed.")

            elif datatype == "comments":
                normalized[field_name] = value if isinstance(value, str) else str(value)

            elif datatype == "bool":
                if isinstance(value, bool):
                    normalized[field_name] = value
                elif value is None:
                    normalized[field_name] = None
                elif isinstance(value, str):
                    lower_val = value.lower().strip()
                    if lower_val in ("true", "yes", "1"):
                        normalized[field_name] = True
                    elif lower_val in ("false", "no", "0"):
                        normalized[field_name] = False
                    elif lower_val in ("none", "null", ""):
                        normalized[field_name] = None
                    else:
                        errors.append(f"Field '{field_name}' (bool): unable to convert string '{value}' to boolean. Use 'true', 'false', or 'none'.")
                else:
                    errors.append(f"Field '{field_name}' (bool): expected boolean, None, or string, got {type(value).__name__}.")

            else:
                errors.append(f"Field '{field_name}': unknown datatype '{datatype}', passing value through without validation.")
                normalized[field_name] = value

        except Exception as e:
            errors.append(f"Field '{field_name}': unexpected error during validation: {str(e)}.")

    logging.debug(f"_validate_and_normalize_changes returning normalized '{normalized}' and errors '{errors}'")
    return normalized, errors


def _update_book_impl(worker_pool, config_manager, book_id: int, changes: dict, library_name: str | None = None) -> dict:
    logging.info(f"_update_book_impl called for library_name '{library_name}', book_id '{book_id}' and changes '{changes}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    check_write_permission(lib_conf, changes_keys=changes.keys())

    schema = _get_library_schema_impl(worker_pool, config_manager, library_name)
    normalized_changes, validation_errors = _validate_and_normalize_changes(changes, schema)

    if validation_errors:
        error_message = "Validation errors occurred:\n" + "\n".join(f"  - {err}" for err in validation_errors)
        logging.debug(f"_update_book_impl returning error '{error_message}'")
        raise ValueError(error_message)

    res = worker_pool.send_rpc(library_name, "update_book", {"book_id": book_id, "changes": normalized_changes})
    logging.debug(f"_update_book_impl returning result '{res}'")
    return res


def _bulk_update_metadata_impl(worker_pool, config_manager, field_name: str, old_value: str | None = None, new_value: str | None = None, book_ids: list[int] | None = None, library_name: str | None = None) -> dict:
    logging.info(f"_bulk_update_metadata_impl called for library_name '{library_name}', field_name '{field_name}', old_value '{old_value}', new_value '{new_value}', book_ids '{book_ids}'")
    if not field_name:
        logging.debug("_bulk_update_metadata_impl returning error 'field_name is required'")
        raise ValueError("field_name is required")

    if old_value is None and new_value is None:
        logging.debug("_bulk_update_metadata_impl returning error 'Either old_value or new_value (or both) must be provided.'")
        raise ValueError("Either old_value or new_value (or both) must be provided.")

    if old_value is not None and isinstance(old_value, (list, tuple, dict)):
        logging.debug("_bulk_update_metadata_impl returning error 'old_value must be a simple string/number. Complex logical matching is not supported.'")
        raise ValueError("old_value must be a simple string/number. Complex logical matching is not supported.")

    lib_conf = get_lib_conf(config_manager, library_name)
    check_write_permission_single_field(lib_conf, field_name)

    if new_value is not None:
        schema = _get_library_schema_impl(worker_pool, config_manager, library_name)
        dummy_changes = {field_name: new_value}
        normalized_changes, errors = _validate_and_normalize_changes(dummy_changes, schema)

        if errors:
            logging.debug("_bulk_update_metadata_impl returning error 'Invalid new_value for field '{field_name}': {'; '.join(errors)}'")
            raise ValueError(f"Invalid new_value for field '{field_name}': {'; '.join(errors)}")

        new_value = normalized_changes[field_name]

    res = worker_pool.send_rpc(library_name, "bulk_update_metadata", {
        "field_name": field_name,
        "old_value": old_value,
        "new_value": new_value,
        "book_ids": book_ids
    })
    logging.debug(f"_bulk_update_metadata_impl returning result '{res}'")
    return res


def _get_field_values_impl(worker_pool, config_manager, library_name: str | None = None, field_name: str | None = None, book_ids: list[int] | None = None, value_filter: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    logging.info(f"_get_field_values_impl called for library_name '{library_name}', field_name '{field_name}', book_ids '{book_ids}', value_filter '{value_filter}', limit '{limit}', offset '{offset}'")
    if not field_name:
        logging.debug("_get_field_values_impl returning error 'field_name is required'")
        raise ValueError("field_name is required")

    lib_conf = get_lib_conf(config_manager, library_name)
    check_read_permission(lib_conf, field_name=field_name)

    res = worker_pool.send_rpc(library_name, "get_field_value_counts", {
        "field_name": field_name,
        "book_ids": book_ids,
        "regex": value_filter
    })

    if not isinstance(res, dict):
        logging.debug(f"Unexpected response from worker: {res}")
        raise RuntimeError(f"Unexpected response from worker: {res}")

    items = [{"value": k, "count": v} for k, v in res.items()]
    items.sort(key=lambda x: (-x["count"], x["value"].lower()))

    total_count = len(items)
    paged_items = items[offset: offset + limit]

    res = {
        "field_name": field_name,
        "total_results": total_count,
        "offset": offset,
        "limit": limit,
        "results": paged_items
    }
    logging.debug(f"_get_field_values_impl returning result '{res}'")
    return res
