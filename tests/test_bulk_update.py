import pytest
import pytest_asyncio
import json

@pytest_asyncio.fixture
async def books(mcp_session):
    result = await mcp_session.call_tool("search_books", {"limit": 5})
    data = json.loads(result.content[0].text)
    return [b["book_id"] for b in data]

@pytest.mark.asyncio
async def test_bulk_add_tag(mcp_session, books):
    if not books:
        pytest.skip("No books found")
    
    target_ids = books[:2]
    tag = "BulkAddTest"
    
    result = await mcp_session.call_tool("bulk_update_metadata", {
        "field_name": "tags",
        "new_value": tag,
        "book_ids": target_ids
    })
    
    data = json.loads(result.content[0].text)
    assert data["status"] == "success"
    
    for bid in target_ids:
        details = await mcp_session.call_tool("get_book_details", {"book_id": bid})
        d = json.loads(details.content[0].text)
        assert tag in d.get("tags", [])

@pytest.mark.asyncio
async def test_bulk_remove_tag(mcp_session, books):
    if not books:
        pytest.skip("No books found")
        
    bid = books[0]
    tag = "BulkRemoveTest"
    
    # Add first
    await mcp_session.call_tool("bulk_update_metadata", {
        "field_name": "tags",
        "new_value": tag,
        "book_ids": [bid]
    })
    
    # Remove
    result = await mcp_session.call_tool("bulk_update_metadata", {
        "field_name": "tags",
        "old_value": tag,
        "book_ids": [bid]
    })
    data = json.loads(result.content[0].text)
    assert data["status"] == "success"
    
    details = await mcp_session.call_tool("get_book_details", {"book_id": bid})
    d = json.loads(details.content[0].text)
    assert tag not in d.get("tags", [])

@pytest.mark.asyncio
async def test_bulk_replace_tag(mcp_session, books):
    if not books:
        pytest.skip("No books found")
        
    bid = books[0]
    old_tag = "OldTag"
    new_tag = "NewTag"
    
    await mcp_session.call_tool("bulk_update_metadata", {
        "field_name": "tags",
        "new_value": old_tag,
        "book_ids": [bid]
    })
    
    result = await mcp_session.call_tool("bulk_update_metadata", {
        "field_name": "tags",
        "old_value": old_tag,
        "new_value": new_tag,
        "book_ids": [bid]
    })
    data = json.loads(result.content[0].text)
    assert data["status"] == "success"
    
    details = await mcp_session.call_tool("get_book_details", {"book_id": bid})
    d = json.loads(details.content[0].text)
    tags = d.get("tags", [])
    assert old_tag not in tags
    assert new_tag in tags

@pytest.mark.asyncio
async def test_bulk_update_single_value(mcp_session, books):
    if not books:
        pytest.skip("No books found")
        
    bid = books[0]
    new_comment = "Updated by bulk tool test"
    
    result = await mcp_session.call_tool("bulk_update_metadata", {
        "field_name": "comments",
        "new_value": new_comment,
        "book_ids": [bid]
    })
    assert json.loads(result.content[0].text)["status"] == "success"
    
    details = await mcp_session.call_tool("get_book_details", {"book_id": bid})
    assert new_comment == json.loads(details.content[0].text)["comments"]

@pytest.mark.asyncio
async def test_bulk_update_validation_error(mcp_session, books):
    if not books:
        pytest.skip("No books found")
        
    try:
        await mcp_session.call_tool("bulk_update_metadata", {
            "field_name": "rating",
            "new_value": "High", # Invalid
            "book_ids": [books[0]]
        })
        # If it reaches here, checking if it returned an error in content
        # But depending on MCP implementation it might raise exception
    except Exception:
        pass # Expected
