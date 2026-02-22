from mcp.server.fastmcp import FastMCP
import os
import atexit
import json
from functools import wraps
import nltk
import logging

try:
    from .config_manager import ConfigManager
    from .worker_pool import WorkerPool
    from . import library_logic as logic
    from .logging_setup import setup_logging
except ImportError:
    from config_manager import ConfigManager
    from worker_pool import WorkerPool
    import library_logic as logic
    from logging_setup import setup_logging

# Initialize Configuration
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.getenv("CALIBREMCP_CONFIGPATH", os.path.join(base_dir, "..", "config.json"))
if not os.path.exists(config_path):
    raise ValueError(f"Config file not found: {config_path}")

config_manager = ConfigManager(config_path)

setup_logging(config_manager, base_dir)

def ensure_nltk_dependencies():
    """
    Attempts to load/download NLTK resources required for sentence segmentation.
    Future-proofed for both 'punkt' (old) and 'punkt_tab' (new).
    """
    dependencies = ['punkt', 'punkt_tab']
    for dep in dependencies:
        try:
            nltk.download(dep, quiet=True, raise_on_error=False)
        except Exception as e:
            logging.error(f"Unable to verify/download NLTK dependency '{dep}': {e}")
    try:
        nltk.sent_tokenize("Test sentence.")
    except LookupError:
        logging.error("NLTK segmentation data is missing. Please run this app while connected to the internet once to initialize.")
        return False
    return True

# Initialize NLTK
if not ensure_nltk_dependencies():
    exit(1)

# Initialize FastMCP Server
mcp = FastMCP("Calibre Library Multi-Lib")

# Initialize Worker Pool
worker_pool = WorkerPool(config_manager, base_dir)
atexit.register(worker_pool.shutdown)

def json_tool_impl():
    """Decorator that ensures tool results are JSON-serialized strings."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return json.dumps(result)
        return wrapper
    return decorator

# --- Config Registration Logic ---

libraries = config_manager.list_libraries()
single_library_mode = len(libraries) == 1
default_library_name = libraries[0]["name"] if single_library_mode else None

# Check capabilities
has_delete = any(l["permissions"].get("delete") for l in libraries)
has_convert = any(l["permissions"].get("convert") for l in libraries)
has_write = any(l["permissions"].get("write") for l in libraries)

has_import = False
for lib in libraries:
    conf = config_manager.get_library_config(lib["name"])
    if conf and conf.get("import"):
        has_import = True
        break

has_export = False
for lib in libraries:
    conf = config_manager.get_library_config(lib["name"])
    if conf and conf.get("export"):
        has_export = True
        break

# --- Tool Factory ---

import inspect

def create_tool_wrapper(impl_func, tool_name, description, needs_worker=True, needs_config=False):
    """
    Factory that creates single-library or multi-library tool wrappers.
    
    Args:
        impl_func: The implementation function from library_logic
        tool_name: Name of the tool
        description: Docstring for the tool (shown to agents)
        needs_worker: Whether to pass worker_pool to impl_func
        needs_config: Whether to pass config_manager to impl_func
    """
    # Get the signature of the implementation function
    sig = inspect.signature(impl_func)
    params = list(sig.parameters.values())
    
    # Filter out worker_pool, config_manager, and library_name from the signature
    # to get the actual tool parameters
    tool_params = [p for p in params if p.name not in ('worker_pool', 'config_manager', 'library_name')]
    
    # Build the wrapper function dynamically
    if single_library_mode:
        # Single library mode: no library_name parameter
        # Create new signature without library_name
        new_params = tool_params
        new_sig = sig.replace(parameters=new_params)
        
        def wrapper(*args, **kwargs):
            # Bind the arguments to the tool signature
            bound = new_sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # Build kwargs for implementation function
            impl_kwargs = dict(bound.arguments)
            if needs_worker:
                impl_kwargs['worker_pool'] = worker_pool
            if needs_config:
                impl_kwargs['config_manager'] = config_manager
            impl_kwargs['library_name'] = default_library_name
            return impl_func(**impl_kwargs)
    else:
        # Multi-library mode: include library_name parameter
        # Keep library_name in the signature
        new_params = tool_params + [
            inspect.Parameter('library_name', inspect.Parameter.KEYWORD_ONLY, 
                            default=None, annotation=str | None)
        ]
        new_sig = sig.replace(parameters=new_params)
        
        def wrapper(*args, **kwargs):
            # Bind the arguments to the tool signature
            bound = new_sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # Build kwargs for implementation function
            impl_kwargs = dict(bound.arguments)
            if needs_worker:
                impl_kwargs['worker_pool'] = worker_pool
            if needs_config:
                impl_kwargs['config_manager'] = config_manager
            return impl_func(**impl_kwargs)
    
    # Set the signature on the wrapper
    wrapper.__signature__ = new_sig
    wrapper.__name__ = tool_name
    wrapper.__doc__ = description
    
    # Apply JSON serialization decorator and register
    wrapped = json_tool_impl()(wrapper)
    mcp.tool(name=tool_name)(wrapped)
    
    # Store the wrapper in the module's globals for testing/introspection
    globals()[tool_name] = wrapper


# --- Tool Definitions ---

# Define all tools declaratively
TOOL_DEFINITIONS = [
    # Always-available tools
    {
        "name": "search_books",
        "impl": logic._search_books_impl,
        "description": """Search for books matching a metadata query.
If query is not provided, lists all books.
Supports pagination by the limit and offset parameters: limit determines how many results to show (default 50), offset sets the starting point for the results (default 0).
fields: Optional list of metadata fields to return (e.g. ["title", "rating", "#genre"]). Returns all if not provided.
text_field_limit: Optional max length for text fields in the returned metadata.""",
        "needs_worker": True,
        "needs_config": False,
    },
    {
        "name": "get_book_details",
        "impl": logic._get_book_details_impl,
        "description": """Get detailed metadata for a book.
fields: an optional list of metadata fields to return (e.g. ["title", "rating", "#genre"]). If not provided, returns all fields.""",
        "needs_worker": True,
        "needs_config": True,
    },
    {
        "name": "get_book_content",
        "impl": logic._get_book_content_impl,
        "description": """Retrieve text content of a book.
limit: Maximum number of characters to return (default 30,000).
offset: Character offset to start reading from.
sentence_aware: If True, adjusts the limit to the nearest sentence boundary.""",
        "needs_worker": True,
        "needs_config": True,
    },
    {
        "name": "search_book_content",
        "impl": logic._search_book_content_impl,
        "description": """Search for text within a book.
Returns a list of hits with text snippets.
hit_limit: Max number of hits to return (default 10).
offset: Offset for pagination of hits.""",
        "needs_worker": True,
        "needs_config": True,
    },
    {
        "name": "fts_search",
        "impl": logic._fts_search_impl,
        "description": """Full-Text Search for a string. Returns a list of hits that include a book_id and a short snippet of text containing an example of the search string's use in that book.""",
        "needs_worker": True,
        "needs_config": False,
    },
    {
        "name": "get_library_schema",
        "impl": logic._get_library_schema_impl,
        "description": """Get the schema of the library, including standard and custom columns.
Useful for understanding available metadata fields for search and update.""",
        "needs_worker": True,
        "needs_config": True,
    },
    {
        "name": "get_field_values",
        "impl": logic._get_field_values_impl,
        "description": """Get unique values and their counts for a specific metadata field.
Useful for building facets (e.g. list of all tags or authors).
field_name: The name of the field.
book_ids: Optional list of book IDs to restrict the search to.
value_filter: Optional regex to filter values.
limit: Max number of values to return (default 50).
offset: Offset for pagination.""",
        "needs_worker": True,
        "needs_config": True,
    },
    
    # Conditional tools (registered based on permissions)
    {
        "name": "update_book",
        "impl": logic._update_book_impl,
        "description": """Update book metadata.
changes: dict of {field: value}. Values will replace existing values.""",
        "needs_worker": True,
        "needs_config": True,
        "condition": has_write,
    },
    {
        "name": "bulk_update_metadata",
        "impl": logic._bulk_update_metadata_impl,
        "description": """Bulk update metadata for multiple books.
field_name: The field to update.
old_value: The value to replace or remove. if None, new_value is added unconditionally.
new_value: The value to add or replace old_value with. If None, old_value is removed.
book_ids: Optional list of book IDs. If omitted, applies to ALL books.""",
        "needs_worker": True,
        "needs_config": True,
        "condition": has_write,
    },
    {
        "name": "convert_book",
        "impl": logic._convert_book_impl,
        "description": """Convert a book to a new format (e.g., EPUB to TXT).
If target format already exists, requires 'delete' permission to overwrite.""",
        "needs_worker": True,
        "needs_config": True,
        "condition": has_convert,
    },
    {
        "name": "delete_book",
        "impl": logic._delete_book_impl,
        "description": """Delete a book or specific formats.
formats: Optional list of formats to delete (e.g. ['TXT', 'EPUB']). If None, deletes the entire book.""",
        "needs_worker": True,
        "needs_config": True,
        "condition": has_delete,
    },
    {
        "name": "list_importable_files",
        "impl": logic._list_importable_files_impl,
        "description": """List files available for import in the configured allowed_paths.
Returns absolute paths to files.""",
        "needs_worker": False,
        "needs_config": True,
        "condition": has_import,
    },
    {
        "name": "add_book",
        "impl": logic._add_book_impl,
        "description": """Add a book to the library from a file path.
The file_path must be within the configured allowed_paths for the library.
delete_source: If True, delete the original file after successful import.
changes: Optional dict of metadata fields to set on the book after import (e.g. {"title": "New Title", "tags": ["tag1"]}).""",
        "needs_worker": True,
        "needs_config": True,
        "condition": has_import,
    },
    {
        "name": "list_exportable_files",
        "impl": logic._list_export_files_impl,
        "description": """List files in the configured export allowed_paths.
Useful for knowing what's already in the export destination.""",
        "needs_worker": False,
        "needs_config": True,
        "condition": has_export,
    },
    {
        "name": "export_book",
        "impl": logic._export_book_impl,
        "description": """Export a book to a file path.
The file_path must be within the configured export allowed_paths.
If format is omitted, the best available format will be used.
If the format doesn't exist, it will be automatically converted for export.""",
        "needs_worker": True,
        "needs_config": True,
        "condition": has_export,
    },
]

# Register all tools
for tool_def in TOOL_DEFINITIONS:
    # Check if tool should be registered (based on condition if present)
    if tool_def.get("condition", True):
        create_tool_wrapper(
            impl_func=tool_def["impl"],
            tool_name=tool_def["name"],
            description=tool_def["description"],
            needs_worker=tool_def.get("needs_worker", True),
            needs_config=tool_def.get("needs_config", False),
        )


# --- Resources ---

skills_dir = os.path.join(base_dir, "..", "skills")

@mcp.resource("calibre://libraries")
def get_libraries() -> list:
    """List available configured libraries, including their permissions."""
    return logic._list_libraries_impl(config_manager)

@mcp.resource("calibre://help/list")
def get_help_topics() -> str:
    """List available help topics."""
    return logic._list_help_topics_impl(skills_dir)

@mcp.resource("calibre://help/{topic}")
def return_help_topic(topic: str) -> str:
    """Get help on a specific topic."""
    return logic._get_help_topic_impl(topic, skills_dir)

# --- Tool Fallbacks ---
# These are for compatibility with agents that haven't implemented MCP resources yet.

expose_via_tools = config_manager.get_global_setting("expose_resources_via_tools", False)

if expose_via_tools:
    @mcp.tool()
    @json_tool_impl()
    def list_libraries() -> str:
        """
        List available configured libraries, including their permissions.
        """
        return logic._list_libraries_impl(config_manager)
    
    @mcp.tool()
    @json_tool_impl()
    def list_help_topics() -> str:
        """
        List available help topics for using the Calibre MCP server.
        """
        return logic._list_help_topics_impl(skills_dir)
    
    @mcp.tool()
    @json_tool_impl()
    def get_help_topic(topic: str) -> str:
        """
        Get detailed documentation on a specific topic.
        """
        return logic._get_help_topic_impl(topic, skills_dir)


if __name__ == "__main__":
    mcp.run()
