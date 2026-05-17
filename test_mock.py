import asyncio
from unittest.mock import AsyncMock, patch

async def main():
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text.return_value = "OK"

    # For an async context manager, __aenter__ must return a coroutine that resolves to the object,
    # or return the object directly depending on python version?
    # In python 3.8+, AsyncMock.__aenter__.return_value = mock_resp works.
    
    # Wait, in aiohttp, session.post returns an async context manager, so `async with session.post(...) as resp:`
    # For `session.post.return_value` to be an async context manager, its `__aenter__` should return a coroutine?
    # Actually, AsyncMock itself has __aenter__ returning an AsyncMock. 
    
    mock_session = AsyncMock()
    # The return_value of post() is the context manager.
    mock_session.post.return_value.__aenter__.return_value = mock_resp
    
    with patch("aiohttp.ClientSession", return_value=mock_session) as mock_client:
        mock_client.return_value.__aenter__.return_value = mock_session
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post("http://test") as resp:
                print(resp.status)
                print(await resp.text())

asyncio.run(main())
