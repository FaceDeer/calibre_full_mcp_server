
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
import inspect

# Helper to unload server module
def unload_server():
    if 'server' in sys.modules:
        del sys.modules['server']

# Add src to path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Test import
try:
    import config_manager
except ImportError:
    raise RuntimeError(f"Could not import config_manager from {SRC_DIR}")

@pytest.fixture
def clean_server_import():
    if 'server' in sys.modules:
        del sys.modules['server']
    yield
    if 'server' in sys.modules:
        del sys.modules['server']

def test_single_library_signature(clean_server_import):
    # Mock ConfigManager to return one library
    # FIXME: Mocking ConfigManager is resulting in logging_setup switching to DEBUG level logging,
    # ConfigManager's .get("debug") check always returns true in that case. Need to fix this.
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.list_libraries.return_value = [
            {"name": "lib1", "permissions": {"read": True, "write": True, "delete": True, "convert": True}, "path": "/tmp/lib1"}
        ]
        instance.get_library_config.return_value = {
            "name": "lib1", 
            "path": "/tmp/lib1", 
            "permissions": {"read": True},
            "import": {"allowed_paths": ["/tmp"]}
        }
        
        # Import server
        import server
        
        # Check search_books signature
        sig = inspect.signature(server.search_books)
        assert "library_name" not in sig.parameters
        
        # Check that all tools are present
        assert hasattr(server, "delete_book")
        assert hasattr(server, "convert_book")
        
def test_multi_library_signature(clean_server_import):
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.list_libraries.return_value = [
            {"name": "lib1", "permissions": {"read": True, "write": True}},
            {"name": "lib2", "permissions": {"read": True}}
        ]
        
        # Import server
        import server
        
        # Check search_books signature
        sig = inspect.signature(server.search_books)
        assert "library_name" in sig.parameters

def test_permission_hiding(clean_server_import):
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.list_libraries.return_value = [
            {"name": "lib1", "permissions": {"read": True, "write": False, "delete": False, "convert": False}}
        ]
        instance.get_library_config.return_value = {"name": "lib1", "permissions": {"read": True}}

        import server
        
        # Write, delete, convert tools should be missing
        assert not hasattr(server, "update_book")
        assert not hasattr(server, "delete_book")
        assert not hasattr(server, "convert_book")
        # Read tools should be present
        assert hasattr(server, "search_books")

def test_filtering_logic(clean_server_import):
    # This tests the implementation functions directly, so we don't need to reload server
    # But we need to make sure server is imported with a config that allows us to access _impl functions
    
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.list_libraries.return_value = [{"name": "default", "permissions": {"read": True}}]
        instance.get_library_config.return_value = {
            "name": "default", 
            "permissions": {"read": ["title", "author"], "write": False}
        }
        
        import server
        
        # Mock worker_pool.send_rpc
        server.worker_pool.send_rpc = MagicMock()
        
        # Test get_book_details filtering
        server.worker_pool.send_rpc.return_value = {
            "id": 1, "title": "Book 1", "author": "John", "rating": 5, "comments": "Good"
        }
        
        # Test get_book_details filtering
        # The implementation functions now take worker_pool and config_manager as parameters
        result = server.logic._get_book_details_impl(server.worker_pool, server.config_manager, 1, "default")
        
        # Should only have id, title, author (and title/id are always kept)
        assert "rating" not in result
        assert "comments" not in result
        assert "title" in result
        # Test get_library_schema filtering
        # Assume server._get_library_schema_impl calls worker_pool.send_rpc
        server.worker_pool.send_rpc.return_value = {
            "title": {"name": "Title"},
            "author": {"name": "Author"},
            "rating": {"name": "Rating"},
            "#genre": {"name": "Genre"}
        }
        
        # We are using the "default" library config from previous test setup which has read=["title", "author"]
        schema_result = server.logic._get_library_schema_impl(server.worker_pool, server.config_manager, "default")
        
        assert "rating" not in schema_result
        assert "#genre" not in schema_result
        assert "title" in schema_result
        assert "author" in schema_result


