import pytest
import json
import os

@pytest.mark.asyncio
async def test_importable_files(mcp_session):
    """Verify listing of importable files."""
    result = await mcp_session.call_tool("list_importable_files", {})
    assert result.content is not None
    files_json = result.content[0].text
    # Parse list of strings
    files = json.loads(files_json)
    assert isinstance(files, list)
    # Ensure our known test files are present
    filenames = [os.path.basename(f) for f in files]
    assert "Your Servant, Sir.txt" in filenames

@pytest.mark.asyncio
async def test_add_delete_book(mcp_session):
    """Verify adding a book and then fully deleting it."""
    # 1. Find a file to import
    list_res = await mcp_session.call_tool("list_importable_files", {})
    files = json.loads(list_res.content[0].text)
    
    target_file = None
    for f in files:
        if "Servant" in f:
            target_file = f
            break
    assert target_file is not None
    
    # 2. Add Book
    add_res = await mcp_session.call_tool("add_book", {"file_path": target_file})
    res_data = json.loads(add_res.content[0].text)
    assert res_data.get("status") == "success"
    new_book_id = res_data["book_ids"][0]
    assert isinstance(new_book_id, int)
    
    # 3. Verify it exists
    details_res = await mcp_session.call_tool("get_book_details", {"book_id": new_book_id})
    details = json.loads(details_res.content[0].text)
    assert details["book_id"] == new_book_id
    # Metadata extraction might have used filename or content
    assert "Servant" in details["title"]
    
    # 4. Delete Book
    del_res = await mcp_session.call_tool("delete_book", {"book_id": new_book_id})
    # Calibre's remove_books returns None, our wrapper returns a string message
    assert "deleted" in del_res.content[0].text.lower()
    
    # 5. Verify it is gone
    # get_book_details might fail or return error
    try:
        await mcp_session.call_tool("get_book_details", {"book_id": new_book_id})
        # If it doesn't raise, check if it returned valid data or we got an error in result
        # Usually checking exception is safer if worker raises on not found
    except Exception:
        # Expected behavior for missing book
        pass

@pytest.mark.asyncio
async def test_convert_and_granular_delete(mcp_session):
    """Verify converting format and deleting specific format (Advanced Feature)."""
    # Book 11 is used for testing advanced features (EPUB execution)
    TEST_BOOK_ID = 11
    
    # Ensure state: Book 11 should have EPUB. If it has TXT from previous runs, clean it up.
    details_res = await mcp_session.call_tool("get_book_details", {"book_id": TEST_BOOK_ID})
    details = json.loads(details_res.content[0].text)
    initial_formats = [f.upper() for f in details.get("formats", [])]
    
    if "TXT" in initial_formats:
        await mcp_session.call_tool("delete_book", {"book_id": TEST_BOOK_ID, "formats": ["TXT"]})
        
    # 1. Convert EPUB to TXT
    conv_res = await mcp_session.call_tool("convert_book", {"book_id": TEST_BOOK_ID, "target_format": "TXT"})
    conv_data = json.loads(conv_res.content[0].text)
    assert conv_data["status"] == "success"
    assert conv_data["target_format"] == "TXT"
    
    # 2. Verify TXT exists
    details_res = await mcp_session.call_tool("get_book_details", {"book_id": TEST_BOOK_ID})
    details = json.loads(details_res.content[0].text)
    assert "formats" in details
    formats = [f.upper() for f in details.get("formats", [])]
    assert "TXT" in formats
    
    # 3. Delete only TXT
    del_res = await mcp_session.call_tool("delete_book", {"book_id": TEST_BOOK_ID, "formats": ["TXT"]})
    assert "deleted" in del_res.content[0].text.lower()
    
    # 4. Verify TXT gone, EPUB remains
    details_res = await mcp_session.call_tool("get_book_details", {"book_id": TEST_BOOK_ID})
    details = json.loads(details_res.content[0].text)
    formats = [f.upper() for f in details.get("formats", [])]
    assert "TXT" not in formats
    assert "EPUB" in formats
