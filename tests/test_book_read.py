import pytest
import json

@pytest.mark.asyncio
async def test_search_books_all(mcp_session):
    result = await mcp_session.call_tool("search_books", {"limit": 1})
    assert result.content is not None
    assert len(result.content) == 1
    books = json.loads(result.content[0].text)
    
    assert isinstance(books, list), f"Expected list, got {type(books)}: {books}"
    assert len(books) > 0
    book = books[0]
    # Check for ID (standard field)
    assert "book_id" in book, f"ID missing in {book}"

@pytest.mark.asyncio
async def test_search_books_pagination(mcp_session):
    limit = 2
    res1 = await mcp_session.call_tool("search_books", {"limit": limit, "offset": 0})
    res2 = await mcp_session.call_tool("search_books", {"limit": limit, "offset": 1})
    
    assert res1.content and res2.content
    assert res1.content[0].text != res2.content[0].text

@pytest.mark.asyncio
async def test_search_books_with_fields(mcp_session):
    # Book ID 10 has a lengthy comment, use for text_field_limit
    result = await mcp_session.call_tool("search_books", {
        "limit": 1,
        "fields": ["title", "comments"],
        "text_field_limit": 50
    })
    assert result.content is not None
    books = json.loads(result.content[0].text)
    
    assert isinstance(books, list)
    assert len(books) > 0
    book = books[0]
    
    # Check for keys (case-insensitive)
    found_keys = [k.lower() for k in book.keys()]
    assert "title" in found_keys
    assert "comments" in found_keys
    
    title_key = next(k for k in book.keys() if k.lower() == "title")
    assert "Robots" in book[title_key]

@pytest.mark.asyncio
async def test_search_books(mcp_session):
    result = await mcp_session.call_tool("search_books", {"query": "title:Robots"})
    assert result.content is not None
    content = result.content[0].text
    assert "Robots" in content

@pytest.mark.asyncio
async def test_get_book_details(mcp_session):
    result = await mcp_session.call_tool("get_book_details", {"book_id": 10})
    assert result.content is not None
    content = result.content[0].text
    data = json.loads(content)
    assert "Robots" in data["title"]

    result = await mcp_session.call_tool("get_book_details", {"book_id": 10, "fields": ["title"]})
    assert result.content is not None
    content = result.content[0].text
    data = json.loads(content)
    assert "Robots" in data["title"]

@pytest.mark.asyncio
async def test_get_book_content_txt(mcp_session):
    result = await mcp_session.call_tool("get_book_content", {"book_id": 10})
    assert result.content is not None
    data = json.loads(result.content[0].text)
    
    if isinstance(data, dict):
        text = data.get("content", "")
    else:
        text = str(data)
    assert len(text.strip()) > 0

@pytest.mark.asyncio
async def test_fts_search(mcp_session):
    result = await mcp_session.call_tool("fts_search", {"query": "Morrison"})
    assert result.content is not None
    assert "Morrison" in result.content[0].text
