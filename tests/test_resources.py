import pytest
import sys
import os
from unittest.mock import patch

# Add src to path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

@pytest.fixture
def clean_server_import():
    if 'server' in sys.modules:
        del sys.modules['server']
    yield
    if 'server' in sys.modules:
        del sys.modules['server']

def test_list_resources(clean_server_import):
    # Mock ConfigManager to allow safe import
    # FIXME: Mocking ConfigManager is resulting in logging_setup switching to DEBUG level logging,
    # ConfigManager's .get("debug") check always returns true in that case. Need to fix this.
    with patch('config_manager.ConfigManager'):
        import server
        
        # Call list_help_topics
        # Note: FastMCP decorator might wrap the function. 
        # If it's a simple wrapper, it might be callable.
        # If not, we might need to unwrap it or test logic differently.
        # Assuming callable for now or we check if it has __call__.
        
        # We need to ensure we call the underlying function if the decorator returns a Resource object that isn't directly callable.
        # However, many frameworks preserve callability.
        
        result = server.list_help_topics()
        assert "Available help topics:" in result
        assert "search_basics" in result
        assert "search_structure" in result

def test_get_resource(clean_server_import):
    with patch('config_manager.ConfigManager'):
        import server
        
        # Test valid topic
        content = server.get_help_topic("search_basics")
        assert "Basic Search Queries" in content
        
        # Test non-existent topic
        with pytest.raises(ValueError):
            server.get_help_topic("non_existent_topic")
            
        # Test distinct content in another file
        content_dates = server.get_help_topic("search_dates_numbers")
        assert "Searching Dates and Numbers" in content_dates
        
        # Test path traversal attempt
        with pytest.raises(ValueError):
            server.get_help_topic("../config.json")

def test_get_libraries_resource(clean_server_import):
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.list_libraries.return_value = [{"name": "lib1", "permissions": {"read": True}}]
        
        import server
        
        content = server.get_libraries()
        # content is a list of dicts
        assert any(lib["name"] == "lib1" for lib in content)

def test_tool_fallbacks(clean_server_import):
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.get_global_setting.side_effect = lambda k, d=None: True if k == "expose_resources_via_tools" else d
        instance.list_libraries.return_value = [{"name": "lib1", "permissions": {"read": True}}]
        
        import server
        
        # Tools should be present
        assert hasattr(server, "list_libraries")
        assert hasattr(server, "list_help_topics")
        assert hasattr(server, "get_help_topic")
        
        # Test content (they are wrapped in json_tool_impl, so they return strings)
        lib_content = server.list_libraries()
        assert "lib1" in lib_content
        
        help_list = server.list_help_topics()
        assert "search_basics" in help_list
        
        help_topic = server.get_help_topic("search_basics")
        assert "Basic Search Queries" in help_topic

def test_tool_fallbacks_disabled(clean_server_import):
    with patch('config_manager.ConfigManager') as MockCM:
        instance = MockCM.return_value
        instance.get_global_setting.side_effect = lambda k, d=None: False if k == "expose_resources_via_tools" else d
        
        import server
        
        # Tools should NOT be present
        assert not hasattr(server, "list_libraries")
        assert not hasattr(server, "list_help_topics")
        assert not hasattr(server, "get_help_topic")


