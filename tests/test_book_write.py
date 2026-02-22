import pytest
import json

@pytest.mark.asyncio
async def test_update_book(mcp_session):
    new_languages = "eng"
    new_tags = "comics, graphic novel"
    new_series = "Sin City"
    new_series_index = 1
    new_comments = "A classic noir graphic novel."
    new_rating = 5
    new_pubdate = "1991-01-01"
    new_publisher = "Dark Horse Comics"
    new_identifiers = {"goodreads": "123456789", "library_of_congress": "987654321"}

    result = await mcp_session.call_tool("update_book", {
        "book_id": 10, 
        "changes": {
            "languages": new_languages,
            "tags": new_tags,
            "series": new_series,
            "series_index": new_series_index,
            "comments": new_comments,
            "rating": new_rating,
            "pubdate": new_pubdate,
            "publisher": new_publisher,
            "identifiers": new_identifiers
        }
    })
    res_data = json.loads(result.content[0].text)

    assert isinstance(res_data, dict), f"Expected dict for update result, got {type(res_data)}: {res_data}"
    assert res_data.get("status") == "success"
    
    # Verify
    verify_result = await mcp_session.call_tool("get_book_details", {"book_id": 10})
    data = json.loads(verify_result.content[0].text)
    assert "eng" in data["languages"]
    assert "comics" in data["tags"]
    assert "Sin City" in data["series"]
    assert data["series_index"] == 1
    assert "A classic noir graphic novel." in data["comments"]
    assert data["rating"] == 5
    assert "1991" in data["pubdate"]
    assert "Dark Horse Comics" in data["publisher"]
    assert "123456789" == data["identifiers"]["goodreads"]
    assert "987654321" == data["identifiers"]["library_of_congress"]

@pytest.mark.asyncio
async def test_list_importable_files(mcp_session):
    result = await mcp_session.call_tool("list_importable_files", {})
    files = json.loads(result.content[0].text)
    
    assert isinstance(files, list), f"Expected list, got {type(files)}: {files}"
    assert len(files) > 0

@pytest.mark.asyncio
async def test_add_and_delete_book(mcp_session):
    # First find a file to add
    res = await mcp_session.call_tool("list_importable_files", {})
    importable = json.loads(res.content[0].text)
        
    if not importable:
        pytest.skip("No importable files found in test_files")
        
    file_to_add = importable[0]
    for p in importable:
        if "Servant" in p:
            file_to_add = p
            break
            
    # Add book
    add_result = await mcp_session.call_tool("add_book", {"file_path": file_to_add})
    add_res_data = json.loads(add_result.content[0].text)
        
    assert isinstance(add_res_data, dict), f"Expected dict for add result, got {type(add_res_data)}: {add_res_data}"
    assert add_res_data.get("status") == "success"
    new_book_id = add_res_data["book_ids"][0]
    
    # Verify add
    details = await mcp_session.call_tool("get_book_details", {"book_id": new_book_id})
    assert "Servant" in details.content[0].text
    
    # Delete book
    del_result = await mcp_session.call_tool("delete_book", {"book_id": new_book_id})
    del_msg = json.loads(del_result.content[0].text)
        
    assert "success" in del_msg.lower() or "deleted" in del_msg.lower()
    
    # Verify delete (should fail or return error message)
    try:
        details_post = await mcp_session.call_tool("get_book_details", {"book_id": new_book_id})
        # If it doesn't throw, it should at least not contain the book
        assert "not found" in details_post.content[0].text.lower() or "error" in details_post.content[0].text.lower()
    except Exception:
        pass
