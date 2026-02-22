import sys
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest_asyncio.fixture
async def mcp_session():
    import asyncio
    # Define server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/server.py"],
        env=None
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
                # Finalize
                await asyncio.sleep(0.1)
    except (RuntimeError, Exception) as e:
        # Known issue with anyio/asyncio interaction during teardown
        # "Attempted to exit cancel scope in a different task than it was entered in"
        msg = str(e)
        if "cancel scope" in msg or "TaskGroup" in msg:
            pass # Suppress known teardown error
        else:
            raise
