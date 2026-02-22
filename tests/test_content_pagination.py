import pytest
import json
import logging

@pytest.mark.asyncio
async def test_get_book_content_pagination(mcp_session):
    book_id = 10
    
    # Test 1: Small limit, sentence_aware=True
    limit = 500
    res = await mcp_session.call_tool("get_book_content", {
        "book_id": book_id, 
        "limit": limit, 
        "sentence_aware": True
    })
    
    assert res.content is not None
    data = json.loads(res.content[0].text)
    content = data["content"]
    
    logging.info(f"\nPage 1 actual length: {len(content)}")
    logging.info(f"Page 1 ends with: {content[-30:]!r}")
    
    # Check that we didn't just return nothing
    assert len(content) > 0
    
    # Test 2: Next page
    res2 = await mcp_session.call_tool("get_book_content", {
        "book_id": book_id, 
        "limit": limit, 
        "offset": data["next_offset"],
        "sentence_aware": True
    })
    
    data2 = json.loads(res2.content[0].text)
    content2 = data2["content"]
    
    logging.info(f"Page 2 actual length: {len(content2)}")
    logging.info(f"Page 2 starts with: {content2[:30]!r}")
    
    # Test 3: Consistency
    # Fetch a larger chunk without sentence split to check the sequence
    full_res = await mcp_session.call_tool("get_book_content", {
        "book_id": book_id,
        "limit": 2000,
        "sentence_aware": False
    })
    full_data = json.loads(full_res.content[0].text)
    full_content = full_data["content"]
    
    # Page 1 should be a prefix
    assert full_content.startswith(content)
    # The remainder of full_content should start with Page 2
    remainder = full_content[len(content):]
    assert remainder.startswith(content2)
