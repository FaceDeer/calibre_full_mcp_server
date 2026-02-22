import pytest
import json
import os

@pytest.mark.asyncio
async def test_list_exportable_files(mcp_session):
    result = await mcp_session.call_tool("list_exportable_files", {})
    files = json.loads(result.content[0].text)
    assert isinstance(files, list)
    # The test_files directory should contain at least one file (e.g., Servant of the Shard.txt)
    assert len(files) > 0

@pytest.mark.asyncio
async def test_export_book_basic(mcp_session):
    # Book 10 is Sin City
    target_path = os.path.abspath("tests/test_files/export_test.epub")
    if os.path.exists(target_path):
        os.remove(target_path)
        
    result = await mcp_session.call_tool("export_book", {
        "book_id": 10,
        "file_path": target_path,
        "format": "EPUB"
    })
    res_data = json.loads(result.content[0].text)
    assert res_data["status"] == "success"
    assert os.path.exists(target_path)
    os.remove(target_path)

@pytest.mark.asyncio
async def test_export_book_extension_correction(mcp_session):
    # Sin City (Book 10)
    target_path = os.path.abspath("tests/test_files/export_wrong_ext.txt")
    expected_path = os.path.abspath("tests/test_files/export_wrong_ext.epub")
    if os.path.exists(expected_path):
        os.remove(expected_path)
        
    result = await mcp_session.call_tool("export_book", {
        "book_id": 10,
        "file_path": target_path,
        "format": "EPUB"
    })
    res_data = json.loads(result.content[0].text)
    assert res_data["status"] == "success"
    assert "corrected extension" in res_data.get("info", "").lower()
    assert os.path.exists(expected_path)
    os.remove(expected_path)

@pytest.mark.asyncio
async def test_export_book_conversion(mcp_session):
    # Export Sin City to MOBI (assuming it only has EPUB/TXT)
    target_path = os.path.abspath("tests/test_files/export_converted.mobi")
    if os.path.exists(target_path):
        os.remove(target_path)
        
    result = await mcp_session.call_tool("export_book", {
        "book_id": 10,
        "file_path": target_path,
        "format": "MOBI"
    })
    res_data = json.loads(result.content[0].text)
    assert res_data["status"] == "success"
    assert res_data["was_converted"] is True
    assert os.path.exists(target_path)
    os.remove(target_path)

@pytest.mark.asyncio
async def test_export_book_overwrite_protection(mcp_session):
    target_path = os.path.abspath("tests/test_files/export_overwrite.epub")
    # Create the file first
    with open(target_path, "w") as f:
        f.write("existing content")
        
    result = await mcp_session.call_tool("export_book", {
        "book_id": 10,
        "file_path": target_path,
        "format": "EPUB"
    })
    # Since allow_overwrite_destination is false in config.json, this should fail
    # Note: Tool execution might return an error message rather than raising an exception in the test session if handled by json_tool decorator
    assert "already exists" in result.content[0].text
    os.remove(target_path)

@pytest.mark.asyncio
async def test_export_book_path_protection(mcp_session):
    # Try to write outside allowed_paths
    target_path = os.path.abspath("src/malicious_export.txt")
    
    result = await mcp_session.call_tool("export_book", {
        "book_id": 10,
        "file_path": target_path,
        "format": "TXT"
    })
    assert "not in allowed_paths" in result.content[0].text
    assert not os.path.exists(target_path)
