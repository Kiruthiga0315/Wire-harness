import asyncio

import httpx

from app.main import app


def test_health_endpoint() -> None:
    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["database"] == "connected"
    assert payload["ai_mode"] == "mock"


def test_demo_image_endpoint_preserves_jpeg_content() -> None:
    async def request_demo_image() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/test-images/harness_sample_01.jpeg")

    response = asyncio.run(request_demo_image())

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-image-source"] == "data/test_images/harness_sample_01.jpeg"
    assert response.content.startswith(b"\xff\xd8\xff")
