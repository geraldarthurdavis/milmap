# Data sources (verified 2026-10-07)

## ISW — control-of-terrain map layers

* ArcGIS Online org: `https://services5.arcgis.com/SaBe5HMtmnbqSWlu/ArcGIS/rest/services`
  (~325 FeatureServers, mixed theatres: Ukraine, Israel/Lebanon/Syria, Iran…).
* **Monthly timelapse services carry daily history.** Example
  `Ukraine_Timelapse_April_2026_WFL1` (layers 33/62/64/30/31: control, advances,
  infiltration, claimed RU, claimed UA counteroffensives). Fields include `datetime`
  (epoch ms UTC, ~20:00 UTC = afternoon ET), `Area_KM`. `f=geojson`, `maxRecordCount` 2000.
  Older months follow other names (`January_Control_Timelapse`, `OCTclaim`, `COT_Merge_Jan_2026_view`…).
* Some "live" views (`MDS_*_view`) return **no layers anonymously** — don't depend on them.
  Today's map may lag until the month's timelapse service updates; v2 options: ISW report PNGs
  (display only, never vectorise without permission) or a permission-based feed.
* Classification is regex over layer names (`pipeline/config/isw_layer_map.yaml`), first
  match wins; `milmap isw-discover` prints the table and flags unclassified layers.
* Layer copyright text: "Institute for the Study of War and American Enterprise Institute's
  Critical Threats Project". See LICENSING.md.

## ISW — daily reports (text)

* "Russian Offensive Campaign Assessment, <Month> <D>, <YYYY>", mirrored on
  `https://www.criticalthreats.org/analysis/russian-offensive-campaign-assessment-<month>-<d>-<yyyy>`.
* Structure: key takeaways → strategic sections → **frontline sections by direction**
  ("Kupyansk direction"…) → numbered endnotes with source URLs. Language is epistemically
  precise ("ISW assesses", "geolocated footage indicates", "milbloggers claimed") — the
  extraction prompt maps that vocabulary onto `status`.
* Header lines include "Assessment as of" and sometimes "Data Cutoff" in ET.

## DeepState — occupied territory

* Community mirror `github.com/cyterat/deepstate-map-data` (GPL-3.0 repo, daily ~03:00 UTC):
  `deepstate-map-data.geojson.gz` with every day `{id, date, geometry}` (MultiPolygon).
* Treated as a second `assessed_control` opinion (`source_id = deepstate`, reliability B).

## Telegram

* Telethon (MTProto, user session; v1.45, maintenance mode). Public channels only, text only,
  incremental by message id (`tg_cursor` table). Channel list + Admiralty grade in
  `config/telegram_channels.yaml` (placeholders — curate deliberately).
* Expect propaganda. Every TG item is `claimed` or `reported` unless it carries geolocatable
  media *and* someone geolocated it.

## Reference geography

* Ukraine outline: Natural Earth 1:10m admin-0, **Ukraine point-of-view** file
  (`ne_10m_admin_0_countries_ukr`, includes Crimea; public domain). The default NE file
  excludes Crimea from Ukraine — don't use it for the front mask.
* Gazetteer: GeoNames `UA.txt` + `RU.txt` filtered to border oblasts (CC BY 4.0).
* Admin boundaries (oblast/raion/hromada): OCHA/HDX COD-AB for Ukraine.
* Basemap: Protomaps extract (OSM, ODbL) or OpenFreeMap (dev). Hillshade: AWS Terrain Tiles.
