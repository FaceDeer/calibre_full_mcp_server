# Calibre MCP Server

This MCP server bridges the gap between AI agents and your [**Calibre** ebook libraries](https://calibre-ebook.com/). It enables agents to interact with your collection as a dynamic knowledge base, allowing them to search, manage, and read your digital libraries. Unlike other MCP servers it can also allow an AI agent to update library metadata and contents if a library's permissions are set to allow it.

## Key Features

- **Advanced Search:** Query libraries using book metadata or perform full-text content searches.

- **Metadata Management:** View and update metadata (titles, authors, tags, ratings, etc.) for any book.

- **Library Maintenance:** Add new titles to your collection or remove existing ones.

- **Format Conversion:** Leverage Calibre’s powerful conversion engine to switch between ebook formats (e.g., PDF to EPUB) on the fly.

- **Direct Reading:** Search and read the text content of a book directly into the agent's context window for analysis, summarization, or Q&A.

- **Granular Permissions:** Define strict access controls per library, including read-only modes and field-level write restrictions.

---

## Prerequisites

- **Calibre:** Must be installed on the host system. This server utilizes `calibre-debug` to execute worker processes.

- **Concurrency Note:** Calibre does not support concurrent access to a single library. **Do not** point an agent to a library currently being used by the Calibre desktop application or other calibre processes to avoid database corruption. Setting a `worker_timeout` can reduce the risk of this happening accidentally, but don't rely on that to protect your libraries. Be aware of what you're doing.

---

## Configuration

The server is configured via a JSON file. Since JSON does not support comments, use the structure below as a template.

### Example Configuration (`config.json`)

JSON

```
{
    "libraries": {
        "default": {
            "path": "d:/ebooks/main_library",
            "description": "The primary research library containing technical manuals.",
            "default": true,
            "permissions": {
                "read": ["title", "authors", "tags", "rating", "comments"],
                "write": ["tags", "rating", "comments"],
                "delete": false,
                "convert": true
            },
            "import": {
                "allowed_paths": ["d:/downloads/ebook_imports"],
                "allow_delete_source": false
            },
            "export": {
                "allowed_paths": ["d:/ebook_exports"s],
                "allow_overwrite_destination": false
            },
            "worker_timeout": 300
        }
    },
    "port": 8000,
    "enable_worker_logging": false,
    "expose_resources_via_tools": true,
    "log_level": "warning"
}
```

### Configuration Schema Reference

Each library is identified by a unique text key and can have its own separate configuration values:

| **Key**                              | **Description**                                                                                                                                                                                                                    |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `path`                               | Absolute path to the Calibre library (where `metadata.db` resides).                                                                                                                                                                |
| `description`                        | Free-form context provided to the agent explaining what this library contains or what its purpose is.                                                                                                                              |
| `default`                            | If `true`, the agent uses this library if no specific library is targeted. If you only configure one library then this is unnecessary.                                                                                             |
| `permissions.read`                   | Set to `true` (all fields exposed), `false` (for a write-only library, if you need one), or a list of specific fields (e.g., `["title", "authors"]`).                                                                              |
| `permissions.write`                  | List of metadata fields the agent is allowed to modify, `true` for all fields and `false` for a read-only library.                                                                                                                 |
| `permissions.delete`                 | Boolean. If `false`, the agent cannot delete books from the library.                                                                                                                                                               |
| `permissions.convert`                | Boolean. Allows the agent to add new formats to a book record by converting existing ones. If `false` the server can still convert books for internal use or export, but it won't add the converted files to library book records. |
| `import.allowed_paths`               | A whitelist of directories from which the agent can import new files.                                                                                                                                                              |
| `import.allow_delete_source`         | If `true`, the server can delete the original file after a successful import.                                                                                                                                                      |
| `export.allowed_paths`               | A whitelist of directories the agent can export book files to.                                                                                                                                                                     |
| `export.allow_overwrite_destination` | If `true`, the server can overwrite files in the allowed export paths when it exports files there.                                                                                                                                 |
| `worker_timeout`                     | An integer in seconds. This specific library's `calibre-debug` worker process will be ended if this much time passes without activity. If omitted, defaults to the root configuration for `worker_timeout`.                        |

There are also several top-level configuration settings that apply to the MCP server as a whole:

| Key                          | Description                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `port`                       | The port the server is exposed on.                                                                                                                                                                                                                                                                                                                                                                                                            |
| `enable_worker_logging`      | Each Calibre library has its own `calibre-debug` process that  runs code to intereact with the internal Calibre API. When `true` these processes will write logs to the `logs` folder for debugging purposes.                                                                                                                                                                                                                                 |
| `worker_timeout`             | For efficiency, the `calibre-debug` worker process for each library is kept alive between requests. Calibre doesn't handle multiple processes accessing the same library at once, so to reduce the risk of this happening you can set a timeout (in seconds) for inactive worker processes to expire. If this is not set then processes are kept alive as long as the server is up (unless overridden by a specific library's configuration). |
| `log_level`                  | Sets what minimum level of logging message will be recorded in `logs/app.log`. Set to "error", "warning", "info", "debug" or "none".                                                                                                                                                                                                                                                                                                          |
| `expose_resources_via_tools` | Some older MCP clients don't understand the "resources" type that this server exposes, for example to allow the agent to read the contents of the `/skills` folder. When this setting is `true` those resources will be exposed via `list_help_topics` and `get_help_topic` instead. The `libraries` resource listing the available libraries and their permissions will also be converted into a `list_libraries` tool.                      |

### Example MCP Configuration

Point to the above configuration file with the `CALIBREMCP_CONFIGPATH` environment variable in your MCP configuration. For example:

JSON

```
{
    "mcpServers": {
        "calibre": {
            "command": "python",
            "args": [
                "<full path>/calibre_full_mcp/src/server.py"
            ],
        "env": {
            "PYTHONPATH": "<full path>/calibre_full_mcp/src",
            "CALIBREMCP_CONFIGPATH": "<full path>/calibre_full_mcp/config.json"
            }
        }
    }
}
```

This should allow you to easily switch library configurations as needed for different agents by selecting which configuration to point `CALIBREMCP_CONFIGPATH` at.

---

## Pro-Tips for Better Performance

### 1. Optimize Field Access

Calibre libraries often contain internal metadata that can clutter an agent's context window. It is **highly recommended** to use a specific list for `read` permissions. Only expose fields the agent actually needs (e.g., title, author, tags, comments).

### 2. Custom Fields & Series

- **Custom Fields:** If you use custom columns in Calibre, you must include the `#` prefix (e.g., `#my_custom_field`).

- **Series:** Every `series` field has a corresponding `series_index`. Ensure both are included in your permissions list if you want the agent to see or manage book order within a series.

- **Descriptions:** The server passes custom field "descriptions" to the agent. Use these in Calibre to give the agent hints on how to use specific custom columns. For example if you create a custom field for a book's "age rating"" you could use the description to explain what the values of that field represent.

### 3. Resource Exposure

If your agent does not yet support the `@mcp.resources` standard, set `expose_resources_via_tools` to `true`. This will expose dedicated tools that allow the agent to fetch files via standard tool calls.

---

## Architecture

For a deep dive into how this server manages worker processes and interacts with the Calibre database, please refer to the [Architecture Documentation](doc/Architecture.md).
