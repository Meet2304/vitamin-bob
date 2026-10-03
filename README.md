# Rural Clinic Explorer

**Why do rural clinics stall?** A two-minute data story and a focused country explorer. It covers health workforce, connectivity, staff absence, paperwork and facility data for about 195 countries, with Indonesia and India in focus, and a feasibility case for starting in Indonesia.

Built by Egshi, Meet, Rizaldy and Yusril for the Hack-Nation × World Bank *Small AI for Development* hackathon (Health track), October 2026.

- **The story:** seven numbers that lead to the problem statement. They include why Indonesia is ready (power, internet, mobile and mandatory e-records are in place; health workers are not) and a Pareto of why Indonesia and India are worth it: 74% of the people in countries that are ready but short-staffed. Press ↓ / ↑ to present.
- **Explore countries:** a world map on an Esri Light Gray basemap. Colour it by health workers, rural share, internet use, mobile, electricity, service coverage, TB incidence or feasibility, then pick any country to see its numbers, rank and trend.
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
| World Bank WDI: SP.POP.TOTL, SP.RUR.TOTL, SP.RUR.TOTL.ZS, IT.NET.USER.ZS, IT.CEL.SETS.P2, EG.ELC.ACCS.ZS, SH.TBS.INCD | Rural share, internet, mobile, electricity, TB incidence | CC BY 4.0 |
| Permenkes 24/2022; Kemenkes SATUSEHAT and SITB; Sahabat-AI model card | Indonesia's digital-health rails | cited |
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
- Clinic-level connectivity (feasibility uses national averages).
