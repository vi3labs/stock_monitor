# Stock Monitor - Development Notes

## Session: January 22, 2026

### What We Set Up

1. **Email Configuration**
   - Configured Gmail SMTP with App Password
   - Sender/Recipient: vi3labs@gmail.com
   - Credentials stored in `config.yaml`

2. **Dependencies Installed**
   - All packages from `requirements.txt` installed via pip3
   - yfinance, pandas, matplotlib, schedule, etc.

3. **Fixed Email Formatting**
   - Rewrote `email_generator.py` with **inline CSS** (was using `<style>` block which email clients strip)
   - Now uses table-based layout for email client compatibility
   - Dark theme with purple gradient header, green/red color coding

4. **Test Watchlist Created**
   - Reduced from 117 stocks to 20 for faster testing
   - Top 10 large cap: NVDA, GOOGL, AMZN, META, TSLA, TSM, XOM, WMT, LMT, BA
   - Bottom 10 small cap: RIME, SBET, UAMY, VOYG, MNTS, BKSY, LPTH, OSS, ONDS, LUNR
   - Full watchlist preserved in config.yaml (commented out)

5. **Tested All Reports**
   - Pre-market: ~2 min with 20 stocks (was ~10 min with 117)
   - Post-market: ~1 min 10 sec
   - Weekly: ~1 min 9 sec (also generates charts)

### Performance Notes

| Stocks | Pre-market | Post-market | Weekly |
|--------|------------|-------------|--------|
| 117    | ~10 min    | -           | -      |
| 20     | ~2 min     | ~1 min      | ~1 min |

Bottleneck is sequential Yahoo Finance API calls. Each stock requires multiple requests.

### Known Issues

- Some ETFs show "No earnings dates found" warnings (expected - ETFs don't have earnings)
- News fetching returns 0 items (may need investigation)
- MNTS flagged as potentially delisted
- yfinance shows deprecation warnings (Pandas 4 compatibility)

---

## TODOs for Tomorrow

### High Priority
- [ ] Set up scheduled runs (choose one):
  - Option A: macOS LaunchAgent (recommended for Mac)
  - Option B: Cron jobs
  - Option C: Run scheduler daemon in background
- [ ] Switch to full watchlist for production (edit config.yaml)
- [ ] Test with full watchlist to confirm timing

### Medium Priority
- [ ] Add parallelization to `data_fetcher.py` to speed up API calls
  - Use ThreadPoolExecutor for concurrent requests
  - Could reduce 117-stock runtime from 10 min to ~2-3 min
- [ ] Investigate why news fetching returns 0 items
- [ ] Review and clean up watchlist (remove delisted tickers)

### Lower Priority
- [ ] Notion integration (`notion_sync.py` is prepared but not connected)
- [ ] Add SMS alerts for big movers (Twilio integration mentioned in README)
- [ ] Consider paid API (Polygon.io) for more reliable data
- [ ] Suppress yfinance deprecation warnings

### Nice to Have
- [ ] Add sector performance summary to reports
- [ ] Weekly report chart as inline image vs attachment
- [ ] Mobile-optimized email tweaks if needed

---

## Quick Reference

```bash
# Run reports manually
python3 scheduler.py --premarket
python3 scheduler.py --postmarket
python3 scheduler.py --weekly

# Test all reports
python3 scheduler.py --test

# Run scheduler daemon
python3 scheduler.py

# Check saved reports
ls reports/
```

## Files Modified Today
- `config.yaml` - Added email credentials, created test watchlist
- `email_generator.py` - Complete rewrite with inline CSS
- `claude.md` - Created for AI context
- `notes.md` - This file
