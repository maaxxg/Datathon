from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from app.efas_flood import EFASFloodReader
from app.risk_rules import Level, combine_flood, flood_efas_level, flood_hv_level


def _write_raster(path: Path, value: float, nodata: float = -9999.0) -> None:
    arr = np.full((10, 10), nodata, dtype=np.float32)
    arr[5, 5] = value
    transform = from_bounds(16.0, 45.0, 17.0, 46.0, 10, 10)
    with rasterio.open(
        path, "w", driver="GTiff", height=10, width=10, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def test_efas_reader_and_fallback(tmp_path):
    _write_raster(tmp_path / "rp10.tif", 0.0)
    _write_raster(tmp_path / "rp100.tif", 0.65)
    _write_raster(tmp_path / "rp500.tif", 1.40)

    reader = EFASFloodReader(tmp_path)
    assert reader.available()

    # Centre of cell (5, 5): lon=16.55, lat=45.45
    depths = reader.depths(45.45, 16.55)
    assert depths == {10: 0.0, 100: 0.65, 500: 1.4}

    # Cell with nodata -> 0.0 m (dry)
    assert reader.depths(45.95, 16.05) == {10: 0.0, 100: 0.0, 500: 0.0}

    # Outside raster bounds -> None per return period
    assert reader.depths(43.0, 16.5) == {10: None, 100: None, 500: None}
    assert flood_efas_level(reader.depths(43.0, 16.5)).level is Level.NO_DATA

    # Fallback when HV returns NO_DATA
    hv_missing = flood_hv_level({"velika": None, "srednja": None, "mala": None})
    combined = combine_flood(hv_missing, flood_efas_level(depths))
    assert combined.source == "flood_efas"
    assert combined.level is Level.MEDIUM
    reader.close()


def test_efas_missing_directory(tmp_path):
    reader = EFASFloodReader(tmp_path / "empty")
    assert not reader.available()
    assert reader.depths(45.45, 16.55) is None


def test_efas_partial_directory_not_available(tmp_path):
    _write_raster(tmp_path / "rp10.tif", 0.5)
    reader = EFASFloodReader(tmp_path)
    assert not reader.available()
    reader.close()
