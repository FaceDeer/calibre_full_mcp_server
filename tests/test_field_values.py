import json
import pytest

@pytest.mark.asyncio
async def test_get_field_values_tags(mcp_session):
    """Test getting field value counts for tags."""
    # List tags
    result = await mcp_session.call_tool("get_field_values", {
        "field_name": "tags",
        "limit": 10
    })
    # FastMCP tools already return a string (serialized JSON in our case) via register_tool
    # But call_tool returns a CallToolResult object which has a 'content' attribute.
    # Wait, FastMCP tool implementation in server.py uses json_tool_impl which calls json.dumps.
    # The return value of call_tool is a list of content items.
    
    assert len(result.content) > 0
    data = json.loads(result.content[0].text)
    
    assert "results" in data
    assert data["field_name"] == "tags"
    assert isinstance(data["results"], list)
    
    # Check sorting (count desc, value asc)
    if len(data["results"]) > 1:
        for i in range(len(data["results"]) - 1):
            assert data["results"][i]["count"] >= data["results"][i+1]["count"]
            if data["results"][i]["count"] == data["results"][i+1]["count"]:
                assert data["results"][i]["value"].lower() <= data["results"][i+1]["value"].lower()

@pytest.mark.asyncio
async def test_get_field_values_authors(mcp_session):
    """Test getting field value counts for authors."""
    result = await mcp_session.call_tool("get_field_values", {
        "field_name": "authors",
        "limit": 5
    })
    data = json.loads(result.content[0].text)
    
    assert data["field_name"] == "authors"
    assert len(data["results"]) <= 5

@pytest.mark.asyncio
async def test_get_field_values_pagination(mcp_session):
    """Test pagination of field values."""
    # First page
    res1 = await mcp_session.call_tool("get_field_values", {
        "field_name": "tags",
        "limit": 1,
        "offset": 0
    })
    data1 = json.loads(res1.content[0].text)
    
    # Second page
    res2 = await mcp_session.call_tool("get_field_values", {
        "field_name": "tags",
        "limit": 1,
        "offset": 1
    })
    data2 = json.loads(res2.content[0].text)
    
    if data1["results"] and data2["results"]:
        assert data1["results"][0]["value"] != data2["results"][0]["value"]

@pytest.mark.asyncio
async def test_get_field_values_filter(mcp_session):
    """Test regex filtering of field values."""
    # This assumes there might be a tag with 'a' in it
    result = await mcp_session.call_tool("get_field_values", {
        "field_name": "tags",
        "value_filter": ".*a.*"
    })
    data = json.loads(result.content[0].text)
    
    for item in data["results"]:
        assert 'a' in item["value"].lower()

@pytest.mark.asyncio
async def test_get_field_values_invalid_field(mcp_session):
    """Test requesting a non-existent field."""
    # call_tool might return isError=True instead of raising an exception directly
    result = await mcp_session.call_tool("get_field_values", {
        "field_name": "non_existent_field"
    })
    assert result.isError
    error_text = result.content[0].text.lower()
    assert "non_existent_field" in error_text or "does not exist" in error_text or "denied" in error_text


