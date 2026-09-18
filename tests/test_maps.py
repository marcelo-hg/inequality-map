import json
import math
import xml.etree.ElementTree as ET

import pytest

from inequality_map.maps import CALLOUTS, COLORS, _callouts, _color, _global_summary, _project, _reference_income


@pytest.mark.parametrize("percent,index", [(0, 0), (10, 1), (30, 2), (50, 3), (70, 4), (90, 5), (100, 5)])
def test_legend_thresholds_include_lower_bound_and_ignore_float_noise(percent, index):
    assert _color(percent / 100)[0] == COLORS[index]
    if 0 < percent < 100:
        assert _color(percent / 100 - 1e-15)[0] == COLORS[index]
        assert _color((percent - .01) / 100)[0] == COLORS[index - 1]


def test_equal_earth_projection_has_uniform_scale_and_geographic_symmetry():
    # Known spherical Equal Earth pole/equator coordinates, before page fitting.
    assert _project(0, 0) == (900, 580)
    assert (580 - _project(0, 90)[1]) / 1.3173627591574 == pytest.approx(270)
    assert (_project(180, 0)[0] - 900) / (math.pi / (math.sqrt(3) / 2 * 1.340264)) == pytest.approx(270)
    east, north = _project(80, 40)
    west, south = _project(-80, -40)
    assert east + west == pytest.approx(1800)
    assert north + south == pytest.approx(1160)


def test_map_rejects_stale_global_values(tmp_path):
    rows = [{"iso3": "BRA", "population": 100, "winner_share": .8, "unchanged_share": 0, "loser_share": .2}]
    (tmp_path / "global_results.json").write_text(json.dumps({"winner_population": 79}))
    with pytest.raises(ValueError, match="Global summary disagrees"):
        _global_summary(tmp_path, rows)


def test_annotation_dots_share_the_geographic_transform():
    rows = [{"iso3": iso, "country_name": iso, "winner_share": .84} for iso in CALLOUTS]
    groups = ET.fromstring("<svg>" + _callouts(rows, "winner_share") + "</svg>")
    for group, (lon, lat, _, _) in zip(groups, CALLOUTS.values()):
        dot = group.find("circle")
        x, y = _project(lon, lat)
        assert float(dot.get("cx")) == pytest.approx(x)
        assert float(dot.get("cy")) == pytest.approx(y)
        assert group.findall("text")[1].text == "84.0%"


def test_income_caption_respects_basis_multiplier_and_clamp():
    metadata = {"population_basis": "adult_20_plus", "reference": {"value_ppp": 100, "ppp_currency": "USD_PPP", "price_year": 2025},
                "scenario": {"redistribution": {"type": "equal", "target_multiplier": .5}}}
    assert _reference_income(metadata) == "Equal income: 50 2025 PPP USD per adult per year"
    metadata["scenario"]["redistribution"] = {"type": "clamp", "floor_multiplier": .6, "ceiling_multiplier": 3}
    assert _reference_income(metadata) == "Income floor: 60 • Ceiling: 300 2025 PPP USD per adult per year"
