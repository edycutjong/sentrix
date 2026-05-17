import asyncio
from unittest.mock import AsyncMock, patch

async def main():
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text.return_value = "OK"

    # mock session post response context manager
    mock_resp_cm = AsyncMock()
    mock_resp_cm.__aenter__.return_value = mock_resp
    
    mock_session = AsyncMock()
    mock_session.post.return_value = mock_resp_cm
    
    # mock client session context manager
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    
    with patch("aiohttp.ClientSession", return_value=mock_session_cm) as mock_client:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post("http://test") as resp:
                print(resp.status)
                print(await resp.text())

asyncio.run(main())
