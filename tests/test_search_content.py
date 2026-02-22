import pytest
import json

@pytest.mark.asyncio
async def test_search_book_content(mcp_session):
    # Book 10 is used in other tests. Verify it exists and has content first via get_book_content
    # (This also triggers auto-convert if implemented and valid)
    await mcp_session.call_tool("get_book_content", {"book_id": 10})
    
    query = "the" 
    
    result = await mcp_session.call_tool("search_book_content", {
        "book_id": 10,
        "query": query,
        "hit_limit": 5
    })
    
    assert result.content is not None
    data = json.loads(result.content[0].text)
    
    assert "results" in data
    assert len(data["results"]) > 0
    assert len(data["results"]) <= 5
    
    hit = data["results"][0]
    assert "start" in hit
    assert "length" in hit
    assert "text" in hit
    # Check if query text is in snippet (simple check)
    # Note: text_search.py stems, so exact match might not be there if we searched for "running" and got "run", 
    # but "the" should be "the".
    assert query.lower() in hit["text"].lower()

@pytest.mark.asyncio
async def test_search_book_content_pagination(mcp_session):
    query = "the"
    limit = 2
    
    res1 = await mcp_session.call_tool("search_book_content", {
        "book_id": 10,
        "query": query,
        "hit_limit": limit,
        "offset": 0
    })
    
    res2 = await mcp_session.call_tool("search_book_content", {
        "book_id": 10,
        "query": query,
        "hit_limit": limit,
        "offset": limit
    })
    
    data1 = json.loads(res1.content[0].text)
    data2 = json.loads(res2.content[0].text)
    
    assert len(data1["results"]) == limit
    # The book might not have enough "the"s if it's short, but usually it does.
    # If data2 is empty, it means we ran out of results, which is also valid pagination behavior 
    # but we want to verify we get different results if we get any.
    
    if len(data2["results"]) > 0:
        assert data1["results"][0]["start"] != data2["results"][0]["start"]
