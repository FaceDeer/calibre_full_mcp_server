import json
import os
import logging

#NOTE: logging_setup uses config, so the logging calls here are sent before logging is set up, using the default logging setup.

class ConfigManager:
    def __init__(self, config_path="config.json"):
        self.config_path = os.path.abspath(config_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.config = {}
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            # Fallback default if no config exists
            self.config = {
                "libraries": {
                    "default": {
                        "path": os.path.join(self.config_dir, "test_library"),
                        "description": "This default test library is available if no config file is found. If you are seeing this library the Calibre MCP server may not be set up correctly.",
                        "default": True,
                        "permissions": {"read": True, "write": False}
                    }
                }
            }
            logging.warning(f"Warning: {self.config_path} not found. Using default in-memory config.")
            return

        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            # Maintain empty or default state to avoid crashing hard without explanation
            self.config = {"libraries": {}}

    def _resolve_path(self, path):
        """Resolves a path relative to the config file's directory if it's relative."""
        if not path:
            return path
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self.config_dir, path))

    def get_library_config(self, library_name=None):
        """
        Returns the config dict for the specified library.
        If library_name is None, returns the marked 'default' library.
        If no default is marked, returns the first one found.
        All paths are resolved to absolute paths.
        """
        libs = self.config.get("libraries", {})
        if not libs:
            return None

        conf = None
        if library_name:
            conf = libs.get(library_name)
        else:
            # Find default
            for name, c in libs.items():
                if c.get("default"):
                    conf = c
                    library_name = name
                    break
            # Fallback to first
            if not conf and libs:
                library_name = list(libs.keys())[0]
                conf = libs[library_name]

        if not conf:
            return None

        # Create a copy so we don't modify the original cached config
        res = conf.copy()
        res["name"] = library_name
        
        # Resolve paths
        res["path"] = self._resolve_path(res.get("path"))
        
        if "import" in res:
            imp = res["import"].copy()
            if "allowed_paths" in imp:
                imp["allowed_paths"] = [self._resolve_path(p) for p in imp["allowed_paths"]]
            res["import"] = imp
            
        if "export" in res:
            exp = res["export"].copy()
            if "allowed_paths" in exp:
                exp["allowed_paths"] = [self._resolve_path(p) for p in exp["allowed_paths"]]
            res["export"] = exp
            
        return res

    def get_global_setting(self, key, default=None):
        """Returns a top-level setting from the config."""
        return self.config.get(key, default)

    def list_libraries(self):
        result = []
        libs = self.config.get("libraries", {})
        for name, conf in libs.items():
            ret = {
                "name": name,
                "permissions": conf.get("permissions", {})
            }
            if (v := conf.get("description", None)) is not None:
                ret["description"] = v
            result.append(ret)
        return result
