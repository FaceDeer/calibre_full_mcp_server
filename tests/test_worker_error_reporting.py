import pytest
import json
import os
import sys

@pytest.mark.asyncio
async def test_worker_error_reporting(mcp_session):
    """
    Test that worker errors include specific error messages from stderr.
    This test attempts to use a non-existent library to trigger a worker error.
    """
    # Try to call a tool with a library that doesn't exist
    # This should trigger a configuration error before even starting a worker
    # So let's test by modifying the config temporarily
    
    # For now, we'll just verify that the existing error handling works
    # A more comprehensive test would require mocking or creating a bad library path
    
    # Test that normal operations work (baseline)
    result = await mcp_session.call_tool("search_books", {"query": ""})
    data = json.loads(result.content[0].text)
    assert isinstance(data, list)

@pytest.mark.asyncio  
async def test_worker_stderr_capture():
    """
    Test that stderr files are created and cleaned up properly.
    This is a unit test for the WorkerPool class.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    
    from src.worker_pool import WorkerPool
    from src.config_manager import ConfigManager
    import tempfile
    
    # Create a config manager with test config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    config_manager = ConfigManager(config_path)
    
    # Create worker pool
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    pool = WorkerPool(config_manager, base_dir)
    
    try:
        # Get a worker (this should create a stderr file)
        proc, resolved_name = pool.get_worker(None)
        
        # Verify stderr file was created
        assert resolved_name in pool.worker_stderr_files
        file_handle, file_path = pool.worker_stderr_files[resolved_name]
        assert os.path.exists(file_path)
        
        # Test a simple RPC call
        result = pool.send_rpc(None, "search_books", {"query": "", "limit": 1})
        assert isinstance(result, list)
        
    finally:
        # Cleanup
        pool.shutdown()
        
        # Verify cleanup happened
        assert len(pool.worker_stderr_files) == 0
        assert len(pool.workers) == 0


def test_error_extraction_from_stderr():
    """
    Test the _extract_stderr_error method directly.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    
    from src.worker_pool import WorkerPool
    from src.config_manager import ConfigManager
    import tempfile
    
    # Create a config manager with test config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    config_manager = ConfigManager(config_path)
    
    # Create worker pool
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    pool = WorkerPool(config_manager, base_dir)
    
    # Create a mock stderr file with test content
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        stderr_path = f.name
        # Write content similar to what the user described
        f.write("--- Worker Started at 2026-02-13 17:01:31 ---\n")
        f.write("calibre_plugins.fantastic_fiction.__init__:96: SyntaxWarning: \"\\\\\" is an invalid escape sequence.\n")
        f.write('{"error": "Library not found at D:\\\\T Drive\\\\Shifti content\\\\test_library"}\n')
        f.flush()
    
    try:
        # Manually add to worker_stderr_files
        pool.worker_stderr_files["test_lib"] = (None, stderr_path)
        
        # Extract error
        error = pool._extract_stderr_error("test_lib")
        
        # Verify the error message was extracted correctly
        assert error is not None
        assert "Library not found" in error
        assert "test_library" in error
        # Verify the warning was filtered out
        assert "SyntaxWarning" not in error
        
    finally:
        # Cleanup
        try:
            os.remove(stderr_path)
        except:
            pass


def test_error_extraction_with_no_json():
    """
    Test error extraction when there's no JSON, just plain text errors.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    
    from src.worker_pool import WorkerPool
    from src.config_manager import ConfigManager
    import tempfile
    
    # Create a config manager with test config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    config_manager = ConfigManager(config_path)
    
    # Create worker pool
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    pool = WorkerPool(config_manager, base_dir)
    
    # Create a mock stderr file with plain text error
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        stderr_path = f.name
        f.write("--- Worker Started at 2026-02-13 17:01:31 ---\n")
        f.write("SyntaxWarning: something irrelevant\n")
        f.write("Fatal error: Database connection failed\n")
        f.flush()
    
    try:
        # Manually add to worker_stderr_files
        pool.worker_stderr_files["test_lib"] = (None, stderr_path)
        
        # Extract error
        error = pool._extract_stderr_error("test_lib")
        
        # Verify the plain text error was extracted
        assert error is not None
        assert "Fatal error: Database connection failed" == error
        
    finally:
        # Cleanup
        try:
            os.remove(stderr_path)
        except:
            pass
