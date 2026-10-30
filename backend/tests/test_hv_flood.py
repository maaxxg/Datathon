import io

import httpx
import pytest
from PIL import Image

from app.hv_flood import TILE_DEG, TILE_PX, HVFloodClient, decode_rgba, pixel_in_tile, tile_origin


def test_decode_exact_legend_colours():
    assert decode_rgba((0xBE, 0xE8, 0xFF, 255)) == "d_lt_0_5"
    assert decode_rgba((0x73, 0xB2, 0xFF, 255)) == "d_1_5_2_5"
    assert decode_rgba((0x00, 0x4D, 0xA8, 255)) == "permanent_water"


def test_decode_transparent_and_unknown():
    assert decode_rgba((0, 0, 0, 0)) == "outside"
    assert decode_rgba((255, 0, 0, 255)) == "outside"


def test_tile_and_pixel_geometry():
    south, west = tile_origin(45.4375, 16.2739)
    assert south <= 45.4375 < south + TILE_DEG
    assert west <= 16.2739 < west + TILE_DEG
    # north-west corner -> pixel (0, 0); south-east corner -> last pixel
    assert pixel_in_tile(south + TILE_DEG, west, south, west) == (0, 0)
    assert pixel_in_tile(south, west + TILE_DEG, south, west) == (TILE_PX - 1, TILE_PX - 1)


def _png(colour):
    buf = io.BytesIO()
    Image.new("RGBA", (TILE_PX, TILE_PX), colour).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_classify_reads_pixel_and_caches_tiles():
    calls = []
    colours = {"velika": (0, 0, 0, 0), "srednja": (0x73, 0xDF, 0xFF, 255), "mala": (0x7A, 0x8E, 0xF5, 255)}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        layer = request.url.params["LAYERS"]
        scenario = next(s for s in colours if f"-{s}-" in layer)
        return httpx.Response(200, content=_png(colours[scenario]), headers={"content-type": "image/png"})

    client = HVFloodClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    result = await client.classify(45.4375, 16.2739)
    assert result == {"velika": "outside", "srednja": "d_0_5_1_5", "mala": "d_gt_2_5"}
    # a nearby point in the same tile must hit the cache
    await client.classify(45.4376, 16.2740)
    assert len(calls) == 3
    # cache keys never contain the user's exact coordinates
    assert all(abs(k[1] / TILE_DEG - round(k[1] / TILE_DEG)) < 1e-6 for k in client._cache)
    await client.aclose()


@pytest.mark.asyncio
async def test_classify_service_error_gives_none():
    def handler(request):
        return httpx.Response(200, text="<ServiceExceptionReport/>", headers={"content-type": "text/xml"})

    client = HVFloodClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    result = await client.classify(45.0, 16.0)
    assert result == {"velika": None, "srednja": None, "mala": None}
    await client.aclose()
