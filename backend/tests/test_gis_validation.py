import pytest
from pydantic import ValidationError

from app.schemas.gis import GisFeatureCreate


def test_gis_accepts_matching_geojson():
    payload = GisFeatureCreate(project_id="p", feature_type="Point", latitude="4.71", longitude="-74.07", geometry_json='{"type":"Point","coordinates":[-74.07,4.71]}')
    assert payload.feature_type == "Point"


def test_gis_normalizes_external_type_aliases():
    payload = GisFeatureCreate(project_id="p", feature_type="geotrace", geometry_json='{"type":"LineString","coordinates":[[0,0],[1,1]]}')
    assert payload.feature_type == "LineString"


def test_gis_rejects_out_of_range_coordinates():
    with pytest.raises(ValidationError, match="Latitud fuera de rango"):
        GisFeatureCreate(project_id="p", feature_type="Point", latitude="91", longitude="0")


def test_gis_rejects_geometry_type_mismatch():
    with pytest.raises(ValidationError, match="GeoJSON incompatible"):
        GisFeatureCreate(project_id="p", feature_type="Polygon", geometry_json='{"type":"Point","coordinates":[0,0]}')


def test_gis_rejects_open_polygon():
    with pytest.raises(ValidationError, match="anillo cerrado"):
        GisFeatureCreate(project_id="p", feature_type="Polygon", geometry_json='{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1]]]}')
