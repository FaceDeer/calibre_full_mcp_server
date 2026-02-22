import os
import logging


def get_lib_conf(config_manager, library_name):
    """
    Retrieves the library config, raising ValueError if not found.
    Centralizes the repeated 3-line pattern across all impl functions.
    """
    logging.debug(f"get_lib_conf called for library_name '{library_name}'")
    lib_conf = config_manager.get_library_config(library_name)
    if not lib_conf:
        logging.debug(f"get_lib_conf returning error 'Library '{library_name}' not found.'")
        raise ValueError(f"Library '{library_name}' not found.")
    logging.debug(f"get_lib_conf returning lib_conf '{lib_conf}'")
    return lib_conf


def check_write_permission(lib_conf, changes_keys=None):
    """
    Checks write permission, raising PermissionError if denied.
    
    Args:
        lib_conf: Library config dict from config_manager
        changes_keys: Optional iterable of field names being written.
                      If provided and write_perm is a list, checks each field.
    """
    logging.debug(f"check_write_permission called for lib_conf '{lib_conf}' and changes_keys '{changes_keys}'")
    perms = lib_conf.get("permissions", {})
    write_perm = perms.get("write")
    lib_name = lib_conf.get("name", "default")

    if not write_perm:
        logging.debug(f"check_write_permission returning error 'Write access denied for library '{lib_name}'.')")
        raise PermissionError(f"Write access denied for library '{lib_name}'.")

    if isinstance(write_perm, list) and changes_keys is not None:
        allowed_fields = set(write_perm)
        requested_fields = set(changes_keys)
        denied_fields = requested_fields - allowed_fields
        if denied_fields:
            logging.debug(f"check_write_permission returning error 'Write access denied for fields: {denied_fields} in library '{lib_name}'. "
                f"Allowed: {allowed_fields}")
            raise PermissionError(
                f"Write access denied for fields: {denied_fields} in library '{lib_name}'. "
                f"Allowed: {allowed_fields}"
            )

    logging.debug(f"check_write_permission returning write_perm '{write_perm}'")
    return write_perm


def check_write_permission_single_field(lib_conf, field_name):
    """
    Checks write permission for a single field (used by bulk_update).
    Raises PermissionError if denied.
    """
    logging.debug(f"check_write_permission_single_field called for lib_conf '{lib_conf}' and field_name '{field_name}'")
    perms = lib_conf.get("permissions", {})
    write_perm = perms.get("write")
    lib_name = lib_conf.get("name", "default")

    if not write_perm:
        logging.debug(f"check_write_permission_single_field returning error 'Write access denied for library '{lib_name}'.")
        raise PermissionError(f"Write access denied for library '{lib_name}'.")

    if isinstance(write_perm, list):
        if field_name not in write_perm:
            logging.debug(f"check_write_permission_single_field returning error 'Write access denied for field '{field_name}' in library '{lib_name}'. "
                f"Allowed: {write_perm}"
            )
            raise PermissionError(
                f"Write access denied for field '{field_name}' in library '{lib_name}'. "
                f"Allowed: {write_perm}"
            )

    logging.debug(f"check_write_permission_single_field returning write_perm '{write_perm}'")
    return write_perm


def check_read_permission(lib_conf, field_name=None):
    """
    Checks read permission, raising PermissionError if denied.
    
    Args:
        lib_conf: Library config dict from config_manager
        field_name: Optional specific field to check against a list-based read perm.
    """
    perms = lib_conf.get("permissions", {})
    read_perm = perms.get("read")
    lib_name = lib_conf.get("name", "default")

    if isinstance(read_perm, list):
        if field_name is not None and field_name not in read_perm:
            raise PermissionError(
                f"Read access denied for field '{field_name}' in library '{lib_name}'."
            )
    elif not read_perm:
        raise PermissionError(f"Read access denied for library '{lib_name}'.")

    return read_perm


def validate_path_in_allowed(file_path, allowed_paths, operation_name="Operation"):
    """
    Validates that file_path is within one of the allowed_paths.
    Uses case-insensitive comparison on Windows.
    
    Returns: absolute path string if valid
    Raises: PermissionError if not within any allowed path
    """
    abs_file_path = os.path.abspath(file_path)
    is_windows = os.name == 'nt'
    check_path = abs_file_path.lower() if is_windows else abs_file_path

    for path in allowed_paths:
        abs_allowed = os.path.abspath(path)
        allowed_check = abs_allowed.lower() if is_windows else abs_allowed

        if check_path.startswith(allowed_check):
            # Ensure it's at a real path boundary, not just a prefix match
            if (len(check_path) == len(allowed_check) or
                    check_path[len(allowed_check)] == os.sep or
                    check_path[len(allowed_check)] == '/'):
                return abs_file_path

    raise PermissionError(
        f"{operation_name} denied. Path '{file_path}' is not in allowed_paths."
    )
