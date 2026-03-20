# Hurricane Intelligence — Enhancement Plan

## Phase 1-3: COMPLETE (see git history)

---

## Phase 4: Records, Monthly Restyle, Mobile

### 4A: September Label Fix
- [x] 1. Fix September bar label — when bar >75% width, position label inside bar with dark text instead of outside (where it overflows hidden)

### 4B: Records Expansion (4 → 16)
- [ ] 2. Add 12 hardcoded record cards below the 4 live-computed ones
  - Longest Track: Faith (1966), 6,850 mi, Cat 3
  - Fastest Forward Speed: New England (1938), ~70 mph, Cat 5
  - Fastest to Cat 5: Milton (2024), 54 hrs, Cat 5
  - Largest Diameter: Sandy (2012), 1,150 mi, Cat 3
  - Smallest Diameter: Marco (2008), 12 mi, TS
  - Fastest Pressure Drop: Wilma (2005), 97 mb/24hr, Cat 5
  - Costliest: Katrina (2005), $200B (adj), Cat 5
  - Latest Cat 5: Cuba (1932), Nov 5, Cat 5
  - Earliest Cat 5: Beryl (2024), Jul 2, Cat 5
  - Most Erratic Track: Nadine (2012), 3 loops, Cat 1
  - Longest at Cat 5: Irma (2017), 78 hrs, Cat 5
  - Most Countries: Ivan (2004), 10+, Cat 5
- [ ] 3. Each card uses same card() function — icon, color, label, name, year, detail, stat, unit
- [ ] 4. Hardcoded cards include storm_id for click-to-play (look up IDs from AGOL data)

### 4C: Monthly Bars → Card-Style Rows
- [ ] 5. Restyle monthly distribution — each month becomes a card (dark bg, rounded, border) matching record card style
- [ ] 6. Bar fill sits behind text inside card
- [ ] 7. Bold count + percentage as right-side stat (fixed position, always readable)
- [ ] 8. Only show months with data (skip Jan-May, Dec if zero)

### 4D: Mobile Responsive
- [ ] 9. Add @media (max-width: 768px) CSS block
- [ ] 10. Map goes full-screen, tools panel becomes bottom drawer
- [ ] 11. Search bar overlays top of map
- [ ] 12. Playback controls as compact bottom bar
- [ ] 13. Intel panel (records, monthly, compare) opens as full-screen overlay
- [ ] 14. Simplify/hide Compare tool on mobile (doesn't fit)
- [ ] 15. Touch-friendly tap targets (min 44px)

### 4E: Deploy + Verify
- [ ] 16. Git commit + push to GitHub Pages
- [ ] 17. Playwright verify desktop
- [ ] 18. Playwright verify mobile viewport (375px)
