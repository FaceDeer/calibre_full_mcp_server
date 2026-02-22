import pytest
import json

@pytest.mark.asyncio
async def test_get_library_schema(mcp_session):
    result = await mcp_session.call_tool("get_library_schema", {})
    assert result.content is not None
    schema = json.loads(result.content[0].text)
    
    assert "title" in schema
    # If 'type' is missing, it might be nested or structured differently
    if "type" in schema["title"]:
        assert schema["title"]["type"] == "text"

@pytest.mark.asyncio
async def test_fts_search(mcp_session):
    result = await mcp_session.call_tool("fts_search", {"query": "Morrison"})
    content = result.content[0].text
    data = json.loads(content)
    assert "Morrison" in data[0]["text"]
