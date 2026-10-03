# Rural Clinic Explorer

**Why do rural clinics stall?** A two-minute data story and a focused country explorer. It covers health workforce, connectivity, staff absence, paperwork and facility data for about 195 countries, with India, Indonesia and Mongolia in focus.

Built for the Hack-Nation × World Bank *Small AI for Development* hackathon (Health track), October 2026.

- **The story:** five numbers that lead to the problem statement. Press ↓ / ↑ to present.
- **Explore countries:** a world map on an Esri Light Gray basemap. Colour it by health workers, rural share, internet use, service coverage or TB incidence, then pick any country to see its numbers, rank and trend.
- **Data & method:** sources, licenses, evidence labels, and what the data does not show.

## Run locally

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000. The page fetches `world.json`, so opening the file directly from disk will not load the map.

## Files

| File | What |
|---|---|
| `index.html` | Page, styles (Archivo, editorial NYT/Reuters-style layout) |
| `app.js` | Story charts (Observable Plot), explorer (Leaflet + D3), tabs and presenter keys |
| `data.js` | Pre-computed data bundle (`window.DATA`) built from the sources below |
| `world.json` | Natural Earth 110m country shapes (via world-atlas), with ISO3 codes added |

## Data and licenses

| Source | Used for | License |
|---|---|---|
| WHO Global Health Observatory: HWF_0001, HWF_0006, UHC_INDEX_REPORTED | Workforce density, service coverage | WHO terms of use |
| World Bank WDI: SP.RUR.TOTL.ZS, IT.NET.USER.ZS, SH.TBS.INCD | Rural share, internet use, TB incidence | CC BY 4.0 |
| healthsites.io / OpenStreetMap via HDX | Indonesia facility map, record completeness | ODbL |
| Chaudhury et al. (2004 draft; *J. Econ. Perspectives* 2006) | Provider absence | cited |
| Siyam et al. (2021), *BMC Health Serv Res* 21(Suppl 1):691 | Recording share of consultations | cited |
| Natural Earth via world-atlas; Esri Light Gray Canvas | Country shapes; basemap | public domain; Esri terms |

**Evidence labels on every chart:**
- **Data:** computed from a dataset.
- **Literature:** taken from a cited paper.
- **Illustrative:** a model with stated assumptions. The queue chart and the "42 of 100 hours" chart are illustrative.

**Not shown by this data:**
- Sub-national gaps.
- Measured waiting times.
- Recent absence data.
- Causation.
- Mongolia's distance problem, which national averages hide.
