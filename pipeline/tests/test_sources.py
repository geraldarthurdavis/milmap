from datetime import UTC, date, datetime

import pytest

from milmap.extract.gazetteer import Gazetteer, Place, norm, offset
from milmap.extract.llm import strict_schema
from milmap.sources.isw_arcgis import IswConfig
from milmap.sources.isw_reports import parse_report, report_url
from milmap.timeutil import day_index, isw_day, telegram_day


@pytest.mark.parametrize(
    "name,cat",
    [
        ("UkraineControlMapAO30A_Merge_APR", "assessed_control"),
        ("AssessedRussianAdvance_Merge_APR", "assessed_advance"),
        ("AssessedRussianInfiltr_Merge_APR", "assessed_infiltration"),
        ("ClaimedRussianTerritor_Merge_APR", "claimed_control"),
        ("ClaimedUkrainianCounte_Merge_APR", "claimed_ua_counter"),
        ("UkraineControlMapAO31JAN2023", "assessed_control"),
        ("Claimed_Russian_Control_over_Ukrainian_Territory31", "claimed_control"),
        ("VIEW_Russian_controlled_Ukrainian_Territory_before_February_24_2022", "pre_2022"),
    ],
)
def test_isw_layer_classification(name, cat):
    assert IswConfig.load().classify(name) == cat


def test_isw_service_filter():
    cfg = IswConfig.load()
    assert cfg.wants_service("Ukraine_Timelapse_April_2026_WFL1")
    assert not cfg.wants_service("Assessed_Israeli_Advances_VIEW")


def test_time_mapping():
    assert day_index(date(2022, 2, 24)) == 0
    # ISW timelapse stamp 2026-04-01 20:00 UTC -> 16:00 ET -> April 1
    ms = int(datetime(2026, 4, 1, 20, 0, tzinfo=UTC).timestamp() * 1000)
    assert isw_day(ms) == day_index(date(2026, 4, 1))
    # 22:30 UTC on Oct 6 is already Oct 7 in Kyiv
    assert telegram_day(datetime(2026, 10, 6, 22, 30, tzinfo=UTC)) == day_index(date(2026, 10, 7))


def test_report_url():
    assert report_url(day_index(date(2026, 10, 1))).endswith(
        "russian-offensive-campaign-assessment-october-1-2026"
    )


def test_parse_report_sections_and_footnotes():
    html = """<html><body><h1>Russian Offensive Campaign Assessment, October 6, 2026</h1>
    <article><p>Intro paragraph.</p>
    <h3>Kupyansk direction</h3>
    <p>Geolocated footage published on October 6 indicates that Russian forces recently
    advanced north of Pishchane.[12]</p>
    <p>[12] https://t.me/example/1 ; https://t.me/example/2</p></article></body></html>"""
    doc = parse_report(html, "https://x", 1685)
    assert [s.heading for s in doc.sections] == ["", "Kupyansk direction"]
    assert doc.footnotes["12"] == ["https://t.me/example/1", "https://t.me/example/2"]


def test_norm_collapses_transliterations():
    assert norm("Kostyantynivka") == norm("Kostiantynivka")
    assert norm("Horlivka") == norm("Gorlivka")
    assert norm("Kupyansk") == norm("Kupiansk") == norm("Kup'yansk")


def test_gazetteer_prefers_place_near_front():
    g = Gazetteer(
        [
            Place("geonames:1", "Novoselivka", 30.0, 50.0, "13", 500),  # far west
            Place("geonames:2", "Novoselivka", 37.5, 48.5, "05", 300),  # near the front
        ]
    )
    m = g.resolve("Novoselivka", front_distance_km=lambda lon, lat: abs(lon - 37.6) * 75)
    assert m is not None and m.place.gid == "geonames:2"


def test_offset_moves_north():
    lon, lat = offset(37.0, 48.0, "north_of", 5)
    assert lat > 48.04 and abs(lon - 37.0) < 1e-9


def test_strict_schema_closes_objects():
    s = strict_schema()
    assert s["additionalProperties"] is False
    ev = s["$defs"]["ExtractedEvent"]
    assert ev["additionalProperties"] is False
    assert set(ev["required"]) == set(ev["properties"]), "no optional fields (grammar limits)"
