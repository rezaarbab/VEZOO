"""
ماژول گرفتن کلید KissKH با Playwright
"""
import asyncio
import logging
import os
import re

logger = logging.getLogger(__name__)

EPISODE_URL = "https://kisskh.nl/Drama/Payback__UNCUT_/Episode-1?id=12822&ep=214618&page=0&pageSize=100"

_cached_sub_key = None
_cached_stream_key = None


async def get_fresh_keys():
    """گرفتن کلید جدید با Playwright"""
    global _cached_sub_key, _cached_stream_key
    
    # اول چک کن env var داره
    sub_key = os.environ.get("KISSKH_SUB_KEY", "")
    stream_key = os.environ.get("KISSKH_STREAM_KEY", "")
    if sub_key and stream_key:
        logger.info("Using keys from environment")
        return stream_key, sub_key
    
    # اگه cache داشت
    if _cached_sub_key and _cached_stream_key:
        logger.info("Using cached keys")
        return _cached_stream_key, _cached_sub_key
    
    logger.info("Getting fresh keys with Playwright...")
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            
            sub_key_found = None
            stream_key_found = None
            
            context = await browser.new_context()
            page = await context.new_page()
            
            # intercept requests
            async def handle_request(request):
                nonlocal sub_key_found, stream_key_found
                url = request.url
                if "kkey=" in url:
                    match = re.search(r'kkey=([A-F0-9]+)', url)
                    if match:
                        key = match.group(1)
                        if "/api/Sub/" in url:
                            sub_key_found = key
                            logger.info(f"Got sub key: {key[:20]}...")
                        elif "/api/DramaList/" in url or "/m3u8" in url:
                            stream_key_found = key
                            logger.info(f"Got stream key: {key[:20]}...")
            
            page.on("request", handle_request)
            
            await page.goto(EPISODE_URL, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            await browser.close()
            
            if sub_key_found:
                _cached_sub_key = sub_key_found
                _cached_stream_key = stream_key_found or sub_key_found
                os.environ["KISSKH_SUB_KEY"] = _cached_sub_key
                os.environ["KISSKH_STREAM_KEY"] = _cached_stream_key
                logger.info("Keys cached successfully!")
                return _cached_stream_key, _cached_sub_key
            else:
                logger.error("Could not capture keys!")
                return None, None
                
    except Exception as e:
        logger.error(f"Playwright error: {e}")
        return None, None


async def ensure_keys():
    """اطمینان از داشتن کلید معتبر"""
    stream_key, sub_key = await get_fresh_keys()
    return bool(sub_key)
