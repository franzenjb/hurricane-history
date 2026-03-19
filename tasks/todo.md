# Hurricane Intelligence — Enhancement Plan

## Current State
- 2,004 storms, 55,605 track points, HURDAT2 raw data present
- GitHub Pages app working with search, playback, info panel
- Bug spotted: popup shows raw epoch timestamp (1728518400000) instead of date

## Work Items

### Phase 1: Data Enrichment (Python scripts)
- [ ] 1. **Narrative Generator** — Add `generate_narratives.py` that reads HURDAT2 + summary CSV, generates 150-200 word narratives per storm from the data itself (formation location, track description, peak intensity, landfall details, duration). Cat 3+ get richer narratives. Adds `narrative` and `is_retired` columns to summary CSV.
- [ ] 2. **Retired Storm Names** — Hardcode the ~90 retired Atlantic names list. Flag in summary CSV.
- [ ] 3. **Landfall State Enrichment** — Download US state + territory boundaries (Natural Earth or Census shapefiles). Point-in-polygon join landfall points to get state/country names. Add `landfall_state` field to tracks CSV.

### Phase 2: Frontend Enhancement (docs/index.html)
- [ ] 4. **Narrative display** — When a storm is selected/clicked, show narrative text in the info panel below the current stats.
- [ ] 5. **Landfall cards** — Query track points for `is_landfall=1` for the selected storm. Show each landfall as a card with date, location (state), wind, category, pressure.
- [ ] 6. **Storm stats summary** — Total distance traveled, days active, peak wind with date in info panel.
- [ ] 7. **Monthly distribution mini-chart** — Small bar chart in controls panel showing storm count by month for current filter.
- [ ] 8. **Fix epoch timestamp bug** — The popup/info panel shows raw millisecond timestamps for `datetime` field. Format properly.

### Phase 3: Deploy
- [ ] 9. Re-run Python scripts to regenerate CSVs
- [ ] 10. Re-upload to AGOL (summary table + track points)
- [ ] 11. Git commit + push to GitHub Pages
- [ ] 12. Playwright verification

## Execution Strategy
- Items 1-3 run as parallel Python agents
- Items 4-8 are the HTML update (single file, sequential)
- Items 9-12 are deploy steps
