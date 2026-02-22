import os
import logging

from .permissions import get_lib_conf, validate_path_in_allowed
from .metadata_ops import _update_book_impl

def _list_export_files_impl(config_manager, library_name: str | None = None) -> list:
    logging.info(f"_list_export_files_impl called for library_name '{library_name}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    export_conf = lib_conf.get("export", {})
    allowed_paths = export_conf.get("allowed_paths", [])

    files = []
    for path in allowed_paths:
        if os.path.exists(path) and os.path.isdir(path):
            try:
                for entry in os.scandir(path):
                    if entry.is_file():
                        files.append(os.path.abspath(entry.path))
            except PermissionError:
                continue
    return files


def _export_book_impl(worker_pool, config_manager, book_id: int, format: str | None = None, file_path: str | None = None, library_name: str | None = None) -> dict:
    logging.info(f"_export_book_impl called for book_id '{book_id}' in library_name '{library_name}' with format '{format}' and file_path '{file_path}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    lib_name = lib_conf.get("name", "default")

    export_conf = lib_conf.get("export", {})
    if not export_conf:
        logging.debug(f"Export not configured for library '{lib_name}'.")
        raise PermissionError(f"Export not configured for library '{lib_name}'.")

    allowed_paths = export_conf.get("allowed_paths", [])
    if not allowed_paths:
        logging.debug(f"No allowed_paths configured for export in library '{lib_name}'.")
        raise PermissionError(f"No allowed_paths configured for export in library '{lib_name}'.")

    # Determine format if not provided
    target_format = format
    if not target_format:
        details = worker_pool.send_rpc(library_name, "get_book_details", {"book_id": book_id, "fields": ["formats"]})
        avail_formats = details.get("formats", [])
        try:
            from ..worker import SOURCE_FORMAT_PRIORITY
        except ImportError:
            from worker import SOURCE_FORMAT_PRIORITY
        target_format = None
        for f in SOURCE_FORMAT_PRIORITY:
            if f in [af.upper() for af in avail_formats]:
                target_format = f
                break
        if not target_format and avail_formats:
            target_format = avail_formats[0].upper()

    if not target_format:
        raise ValueError(f"Could not determine target format for book_id {book_id}")

    target_format = target_format.upper()

    # Path validation (raises PermissionError if not in allowed_paths)
    abs_file_path = validate_path_in_allowed(file_path, allowed_paths, operation_name="Export")

    # Extension correction
    expected_ext = f".{target_format.lower()}"
    actual_root, actual_ext = os.path.splitext(abs_file_path)
    corrected_path = abs_file_path if actual_ext.lower() == expected_ext else actual_root + expected_ext

    # Overwrite protection
    if not export_conf.get("allow_overwrite_destination", False):
        if os.path.exists(corrected_path):
            logging.debug(f"Destination file '{corrected_path}' already exists and allow_overwrite_destination is False.")
            raise FileExistsError(f"Destination file '{corrected_path}' already exists and allow_overwrite_destination is False.")

    res = worker_pool.send_rpc(library_name, "export_book", {
        "book_id": book_id,
        "format": target_format,
        "file_path": corrected_path
    })

    if res.get("status") == "success" and corrected_path != abs_file_path:
        res["info"] = f"File written with corrected extension: {corrected_path}"

    logging.debug(f"_export_book_impl returned: {res}")
    return res


def _list_importable_files_impl(config_manager, library_name: str | None = None) -> list:
    logging.info(f"_list_importable_files_impl called for library_name '{library_name}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    import_conf = lib_conf.get("import", {})
    allowed_paths = import_conf.get("allowed_paths", [])

    files = []
    for path in allowed_paths:
        if os.path.exists(path) and os.path.isdir(path):
            try:
                for entry in os.scandir(path):
                    if entry.is_file():
                        files.append(os.path.abspath(entry.path))
            except PermissionError:
                continue

    logging.debug(f"_list_importable_files_impl returned: {files}")
    return files


def _add_book_impl(worker_pool, config_manager, file_path: str, delete_source: bool = False, library_name: str | None = None, changes: dict | None = None) -> dict:
    logging.info(f"_add_book_impl called for library_name '{library_name}' with file_path '{file_path}', delete_source '{delete_source}', changes '{changes}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    import_conf = lib_conf.get("import", {})
    allowed_paths = import_conf.get("allowed_paths", [])

    # Path validation (raises PermissionError if not in allowed_paths)
    abs_file_path = validate_path_in_allowed(file_path, allowed_paths, operation_name="Import")

    if delete_source and not import_conf.get("allow_delete_source"):
        logging.debug("Deleting source after import is disabled in configuration.")
        raise PermissionError("Deleting source after import is disabled in configuration.")

    res = worker_pool.send_rpc(library_name, "add_book", {"file_paths": [abs_file_path]})

    if res.get("status") == "success":
        if changes:
            book_ids = res.get("book_ids", [])
            if book_ids:
                book_id = book_ids[0]
                try:
                    _update_book_impl(worker_pool, config_manager, book_id, changes, library_name=library_name)
                    res["metadata_update"] = "success"
                except Exception as e:
                    res["metadata_update"] = f"failed: {str(e)}"

        if delete_source:
            try:
                os.remove(abs_file_path)
                res["source_deleted"] = True
            except Exception as e:
                res["source_deleted"] = False
                res["source_deletion_error"] = str(e)

    logging.debug(f"_add_book_impl returned: {res}")
    return res


def _delete_book_impl(worker_pool, config_manager, book_id: int, formats: list[str] | None = None, library_name: str | None = None) -> str:
    logging.info(f"_delete_book_impl called for library_name '{library_name}' with book_id '{book_id}' and formats '{formats}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    perms = lib_conf.get("permissions", {})
    lib_name = lib_conf.get("name", "default")

    if not perms.get("delete"):
        logging.debug(f"Delete access denied for library '{lib_name}'.")
        raise PermissionError(f"Delete access denied for library '{lib_name}'.")

    res = worker_pool.send_rpc(library_name, "delete_book", {"book_id": book_id, "formats": formats})
    logging.debug(f"_delete_book_impl returned: {res}")
    return res


def _convert_book_impl(worker_pool, config_manager, book_id: int, target_format: str, library_name: str | None = None) -> dict:
    logging.info(f"_convert_book_impl called for library_name '{library_name}' with book_id '{book_id}' and target_format '{target_format}'")
    lib_conf = get_lib_conf(config_manager, library_name)
    perms = lib_conf.get("permissions", {})
    lib_name = lib_conf.get("name", "default")

    if not perms.get("convert"):
        logging.debug(f"Convert access denied for library '{lib_name}'.")
        raise PermissionError(f"Convert access denied for library '{lib_name}'.")

    # Overwrite protection: target format already exists requires delete permission
    try:
        details_raw = worker_pool.send_rpc(library_name, "get_book_details", {"book_id": book_id})
        existing_formats = [f.upper() for f in details_raw.get("formats", [])]

        if target_format.upper() in existing_formats:
            if not perms.get("delete"):
                logging.debug(f"Target format {target_format} already exists. 'delete' permission required to overwrite.")
                raise PermissionError(f"Target format {target_format} already exists. 'delete' permission required to overwrite.")
    except Exception as e:
        if "PermissionError" in str(type(e)):
            logging.debug(f"PermissionError: {str(e)}")
            raise e
        logging.debug(f"Exception: {str(e)}")
        pass

    res = worker_pool.send_rpc(library_name, "convert_book", {"book_id": book_id, "target_format": target_format})
    logging.debug(f"_convert_book_impl returned: {res}")
    return res