# Stock Monitor Dashboard - Design Document

## Executive Summary

A real-time stock monitoring dashboard that transforms the existing email-based reporting system into an interactive web interface. The dashboard will provide at-a-glance market insights with sector performance visualization, top movers, news feeds, and sparkline price trends.

---

## Design Philosophy

**Data-Ink Ratio**: Maximum information density without visual clutter. Every pixel serves a purpose.

**5-Second Rule**: A user should grasp the market's overall health within 5 seconds of viewing the dashboard.

**Consistency**: Matches the dark theme aesthetic of FlowOS and Signal Desk while introducing data visualization elements that feel native to stock monitoring.

---

## Layout Architecture

### Desktop Layout (1200px+)

```
+------------------------------------------------------------------+
|  HEADER: Stock Monitor    [Last Updated: 2:34 PM]    [Refresh]   |
+------------------------------------------------------------------+
|                                                                   |
|  +-- MARKET INDICES (4-col) --------------------------------+    |
|  |  S&P 500    |  NASDAQ    |  DOW JONES   |  VIX          |    |
|  |  +0.42%     |  +0.67%    |  +0.18%      |  15.23        |    |
|  |  [sparkline]|  [spark]   |  [spark]     |  [spark]      |    |
|  +--------------------------------------------------------------+    |
|                                                                   |
|  +-- LEFT COLUMN (60%) ------------+ +-- RIGHT COLUMN (40%) ----+|
|  |                                 | |                          ||
|  |  SECTOR PERFORMANCE             | |  TOP MOVERS              ||
|  |  +---------------------------+  | |  +-- GAINERS ----------+ ||
|  |  | [Horizontal bar chart]   |  | |  | LUNR  +12.9%  $22.81| ||
|  |  | Tech         [====] +2.1%|  | |  | EOSE  +9.4%   $16.68| ||
|  |  | Space        [===]  +1.8%|  | |  | LEU   +9.0%  $337.76| ||
|  |  | Semis        [==]   +1.2%|  | |  | [sparklines]        | ||
|  |  | Defense      [=]    +0.4%|  | |  +---------------------+ ||
|  |  | Energy       [-]    -0.3%|  | |                          ||
|  |  | Crypto       [--]   -1.2%|  | |  +-- LOSERS -----------+ ||
|  |  +---------------------------+  | |  | APH   -12.9% $145.96| ||
|  |                                 | |  | PRME  -6.1%    $4.03| ||
|  +-- WATCHLIST ---------------------+ |  | KTOS  -5.8%  $112.67| ||
|  |  [Search/Filter: ________]      | |  +---------------------+ ||
|  |  +---------------------------+  | |                          ||
|  |  | Symbol | Price  | Chg  |Sec| | |  NEWS FEED              ||
|  |  |--------|--------|------|---| | |  +---------------------+ ||
|  |  | NVDA   | $892.45| +3.2%|Tch| | |  | [LUNR] Intuitive..  | ||
|  |  | TSLA   | $248.20| -1.5%|Tch| | |  | [INTC] Intel rally..| ||
|  |  | ASTS   | $121.23| +8.7%|Spc| | |  | [Market] Fed holds..| ||
|  |  | ...    | ...    | ...  |...| | |  +---------------------+ ||
|  |  +---------------------------+  | +---------------------------+|
|  +----------------------------------+                             |
+------------------------------------------------------------------+
```

### Tablet Layout (768px - 1199px)

- Market indices: 2x2 grid
- Sector performance: Full width
- Top movers and news: Stack vertically on right
- Watchlist: Full width, collapsible

### Mobile Layout (<768px)

- Single column layout
- Market indices: Horizontal scroll
- Sector performance: Compact horizontal bars
- Top movers: Tab interface (Gainers | Losers)
- Watchlist: Card-based, expandable rows
- News: Bottom panel, pull-up sheet

---

## Color System

Derived from the existing FlowOS/Signal Desk dark themes with stock-specific semantic colors.

```css
:root {
  /* Base colors - matches FlowOS dark theme */
  --bg-primary: #0f1115;       /* Deeper than FlowOS for contrast */
  --bg-secondary: #1a1d23;     /* Card backgrounds */
  --bg-tertiary: #232730;      /* Hover states, nested cards */
  --bg-elevated: #2a2e38;      /* Modal overlays */

  /* Text hierarchy */
  --text-primary: #f5f2eb;     /* Primary text - warm white */
  --text-secondary: #a0a0a0;   /* Muted labels */
  --text-subtle: #666;         /* Timestamps, hints */

  /* Semantic colors - Stock specific */
  --gain: #00C853;             /* Positive change - vibrant green */
  --gain-muted: rgba(0, 200, 83, 0.15);  /* Green backgrounds */
  --loss: #FF1744;             /* Negative change - vibrant red */
  --loss-muted: rgba(255, 23, 68, 0.15); /* Red backgrounds */
  --neutral: #9E9E9E;          /* Unchanged */

  /* Accent colors - from email generator */
  --accent-primary: #4fc3f7;   /* Section titles, links */
  --accent-gradient-start: #667eea;  /* Header gradient */
  --accent-gradient-end: #764ba2;

  /* Sector colors - categorical palette */
  --sector-tech: #60a5fa;
  --sector-space: #a78bfa;
  --sector-semis: #34d399;
  --sector-defense: #f97316;
  --sector-energy: #facc15;
  --sector-crypto: #f472b6;
  --sector-nuclear: #22d3ee;
  --sector-robotics: #818cf8;
  --sector-financials: #2dd4bf;
  --sector-industrial: #a3a3a3;
  --sector-etf: #64748b;

  /* Borders and shadows */
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-card: #2d3748;
  --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
  --shadow-elevated: 0 8px 32px rgba(0, 0, 0, 0.6);

  /* Transitions */
  --ease-out: cubic-bezier(0.25, 0.46, 0.45, 0.94);
  --duration-fast: 150ms;
  --duration-normal: 250ms;
}
```

### Colorblind-Safe Considerations

- Green/Red distinction enhanced with:
  - Directional arrows (up/down triangles)
  - Background opacity differences
  - Position encoding (gainers always left/top)
- Optional high-contrast mode with patterns

---

## Typography

```css
:root {
  --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* Type scale */
  --text-xs: 0.6875rem;    /* 11px - timestamps */
  --text-sm: 0.8125rem;    /* 13px - secondary info */
  --text-base: 0.9375rem;  /* 15px - body text */
  --text-lg: 1.125rem;     /* 18px - section titles */
  --text-xl: 1.5rem;       /* 24px - page title */
  --text-2xl: 2rem;        /* 32px - hero numbers */

  /* Font weights */
  --weight-normal: 400;
  --weight-medium: 500;
  --weight-semibold: 600;

  /* Monospace for numbers */
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Monaco', monospace;
}
```

**Number Formatting**:
- Prices use monospace font for alignment
- Percentages show 2 decimal places
- Large numbers use comma separators
- Prices < $1 show 4 decimal places

---

## Component Specifications

### 1. Header Bar

```
+------------------------------------------------------------------+
|  Stock Monitor                       Jan 29, 2026 2:34 PM EST    |
|  [icon]                                          [Refresh] [Settings]|
+------------------------------------------------------------------+
```

**Elements**:
- Logo/title: Left-aligned
- Last updated timestamp: Real-time clock
- Refresh button: Manual data refresh
- Settings: Theme toggle, alert thresholds

### 2. Market Indices Cards

```
+----------------+
|  S&P 500       |
|  6,071.17      |  <- Large, prominent
|  +25.31 (+0.42%)|  <- Color-coded
|  [sparkline~~~~] |  <- 7-day trend
+----------------+
```

**Data Requirements**:
- Current price
- Change (absolute + percentage)
- 7-day historical closes for sparkline

**Sparkline Spec**:
- 64px wide x 24px tall
- Stroke: 2px
- Color: matches change direction
- No axes or labels (pure data)

### 3. Sector Performance

**Visualization**: Horizontal diverging bar chart

```
                    -3%    0%    +3%
Tech         [=======|===========>] +2.1%
Space             [=|=======>]      +1.8%
Semiconductors    [=|=====>]        +1.2%
Defense           [=|==>]           +0.4%
Energy            [<=|]             -0.3%
Crypto       [<====|]               -1.2%
```

**Interaction**:
- Hover: Show stocks in sector
- Click: Filter watchlist to sector

**Data Requirements**:
- Sector name
- Average change % (calculated from watchlist stocks)
- Stock count per sector

### 4. Top Movers Panel

**Layout**: Two columns (Gainers | Losers)

```
+-- GAINERS --------+  +-- LOSERS ---------+
| LUNR              |  | APH               |
| +12.92%   $22.81  |  | -12.85%  $145.96  |
| [~~~~sparkline~~] |  | [~~~sparkline~~~] |
|                   |  |                   |
| EOSE              |  | PRME              |
| +9.38%    $16.68  |  | -6.06%     $4.03  |
| [~~~~sparkline~~] |  | [~~~sparkline~~~] |
+-------------------+  +-------------------+
```

**Features**:
- Top 5 each direction
- Inline sparklines (7-day)
- Volume indicator (>2x avg = badge)
- Click to expand detail card

### 5. Watchlist Table

**Columns**:
| Column | Width | Sort | Notes |
|--------|-------|------|-------|
| Symbol | 80px | A-Z | Bold, clickable |
| Name | flex | A-Z | Truncate with ellipsis |
| Price | 100px | High-Low | Monospace |
| Change | 90px | High-Low | Color-coded pill |
| Sparkline | 80px | - | 7-day trend |
| Sector | 100px | A-Z | Colored badge |
| Volume | 80px | High-Low | Relative to avg |

**Features**:
- Sticky header row
- Virtual scrolling for 80+ stocks
- Search/filter input
- Sector filter dropdown
- Sort by clicking column headers
- Row click expands detail panel

**Row States**:
- Default: Normal
- Hovered: Slight elevation, show actions
- Selected: Border highlight
- Alert: Pulse animation for big moves

### 6. Stock Detail Panel (Expandable)

```
+----------------------------------------------------------+
| NVDA - NVIDIA Corporation                          [X]   |
+----------------------------------------------------------+
|                                                          |
|  $892.45  +$27.34 (+3.16%)                              |
|                                                          |
|  [========= 7-Day Price Chart ===========]              |
|                                                          |
|  +-- STATS ------+  +-- INFO -----------+               |
|  | Open:  $865.11|  | Sector: Tech      |               |
|  | High:  $894.20|  | Market Cap: $2.2T |               |
|  | Low:   $863.50|  | Avg Volume: 45.2M |               |
|  | Vol:   52.1M  |  | 52W H/L: $974/$450|               |
|  +---------------+  +-------------------+               |
|                                                          |
|  +-- RECENT NEWS ----------------------------------+    |
|  | NVIDIA announces new AI chip architecture...    |    |
|  | Analysts raise price target after earnings...   |    |
|  +------------------------------------------------+    |
+----------------------------------------------------------+
```

### 7. News Feed Panel

**Layout**: Scrollable list with category badges

```
+-- NEWS ----------------------------------------+
| [MARKET] Fed holds rates steady, signals...    |
| Reuters | 2 hours ago                          |
|                                                |
| [LUNR] Intuitive Machines secures $150M...     |
| Bloomberg | 3 hours ago                        |
|                                                |
| [TECH] NVIDIA AI chip demand exceeds...        |
| WSJ | 5 hours ago                              |
+------------------------------------------------+
```

**Features**:
- Category badges: Market, Stock-specific, Sector
- Time-relative formatting (2h ago, Yesterday)
- Click to expand summary
- External link icon

---

## Interaction Patterns

### Data Refresh

1. **Auto-refresh**: Every 5 minutes during market hours
2. **Manual refresh**: Button in header
3. **Visual feedback**:
   - Spinning icon during fetch
   - Subtle pulse on updated data
   - Toast notification on errors

### Filtering & Search

```
+-- Filter Bar ----------------------------------+
| [Search: ____]  [Sector: All v]  [Sort: Chg v]|
+------------------------------------------------+
```

- Debounced search (300ms)
- Filter persists across refresh
- URL params for shareable state

### Hover States

- **Cards**: Slight lift (translateY -2px)
- **Table rows**: Background highlight
- **Sparklines**: Show tooltip with value

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `j/k` | Navigate watchlist rows |
| `Enter` | Expand selected row |
| `Escape` | Collapse/clear |
| `r` | Refresh data |

---

## Sparkline Specification

**Technology**: Canvas-based for performance (80+ symbols)

**Dimensions**: 80px x 24px per sparkline

**Rendering**:
```javascript
// Normalize data to 0-1 range
const normalized = data.map(v => (v - min) / (max - min));

// Draw path
ctx.strokeStyle = change > 0 ? '--gain' : '--loss';
ctx.lineWidth = 1.5;
ctx.beginPath();
normalized.forEach((y, x) => {
  const px = (x / (data.length - 1)) * width;
  const py = height - (y * height);
  x === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
});
ctx.stroke();

// Optional: Fill area under curve
ctx.globalAlpha = 0.1;
ctx.fill();
```

**Data**: 7 daily closes (or 24 hourly for intraday)

---

## Tech Stack Recommendation

### Primary Choice: Vanilla JavaScript

**Rationale**:
- Matches existing FlowOS and Signal Desk architecture
- No build step required
- Full control over rendering
- Minimal bundle size

**Structure**:
```
dashboard/
  index.html
  css/
    variables.css      # Design tokens
    base.css           # Reset, typography
    components.css     # Card, table, pill styles
    dashboard.css      # Layout-specific styles
    responsive.css     # Media queries
  js/
    app.js             # Main controller
    store.js           # State management
    api.js             # Data fetching layer
    charts.js          # Sparkline/bar chart rendering
    components/
      header.js
      indices.js
      sectors.js
      movers.js
      watchlist.js
      news.js
      detail.js
    utils.js           # Formatting, helpers
```

### Data Layer

**API Server**: Python Flask/FastAPI

```python
# Endpoints
GET /api/quotes          # All watchlist quotes
GET /api/quotes/{symbol} # Single symbol detail
GET /api/sectors         # Sector performance
GET /api/movers          # Top gainers/losers
GET /api/news            # Aggregated news
GET /api/indices         # Market indices
GET /api/history/{symbol}?period=7d  # Historical data
```

**Backend reuses existing**:
- `data_fetcher.py` - Quote fetching
- `news_fetcher.py` - News aggregation
- `notion_sync.py` - Sector mapping

### Alternative: React (if scaling needed)

Only consider if:
- Team needs to maintain the code
- Complex state management required
- Significant interactivity growth planned

---

## File Structure

```
/Users/tom/Documents/VScode/stock_monitor/
├── dashboard/
│   ├── index.html
│   ├── css/
│   │   ├── variables.css
│   │   ├── base.css
│   │   ├── layout.css
│   │   ├── components.css
│   │   └── responsive.css
│   ├── js/
│   │   ├── app.js
│   │   ├── store.js
│   │   ├── api.js
│   │   ├── charts.js
│   │   └── components/
│   │       ├── Header.js
│   │       ├── Indices.js
│   │       ├── Sectors.js
│   │       ├── Movers.js
│   │       ├── Watchlist.js
│   │       ├── News.js
│   │       └── StockDetail.js
│   └── assets/
│       └── icons/
├── api/
│   ├── server.py           # Flask/FastAPI server
│   ├── routes/
│   │   ├── quotes.py
│   │   ├── sectors.py
│   │   ├── movers.py
│   │   └── news.py
│   └── requirements.txt
├── start-dashboard.sh      # Launch script
└── DESIGN.md               # This document
```

---

## Performance Considerations

### Data Loading Strategy

1. **Initial Load**: Fetch all data in parallel
2. **Incremental Updates**: Only fetch changed data
3. **Background Refresh**: Web Worker for API calls

### Rendering Optimization

1. **Virtual Scrolling**: For 80+ row watchlist
2. **Canvas Sparklines**: Better than SVG for many charts
3. **Debounced Search**: 300ms delay
4. **CSS Containment**: `contain: layout` on cards

### Caching

```javascript
// In-memory cache with TTL
const cache = new Map();
const TTL = 5 * 60 * 1000; // 5 minutes

async function fetchWithCache(endpoint) {
  const cached = cache.get(endpoint);
  if (cached && Date.now() - cached.timestamp < TTL) {
    return cached.data;
  }
  const data = await fetch(endpoint).then(r => r.json());
  cache.set(endpoint, { data, timestamp: Date.now() });
  return data;
}
```

---

## Accessibility

### WCAG 2.1 AA Compliance

- **Color Contrast**: All text meets 4.5:1 ratio
- **Focus Indicators**: Visible focus rings on all interactive elements
- **Screen Reader**: Proper ARIA labels on charts
- **Keyboard**: Full navigation without mouse

### Specific Implementations

```html
<!-- Sparkline with accessible description -->
<div role="img"
     aria-label="NVDA 7-day trend: Started at $865, ended at $892, up 3.1%">
  <canvas class="sparkline"></canvas>
</div>

<!-- Change indicator with icon -->
<span class="change positive" aria-label="Up 3.16%">
  <span aria-hidden="true">+</span>3.16%
</span>
```

---

## Future Enhancements

### Phase 2
- [ ] Alerts system (price targets, big moves)
- [ ] Portfolio tracking (holdings, P&L)
- [ ] Comparison charts (overlay multiple symbols)
- [ ] Custom watchlists

### Phase 3
- [ ] Historical analysis views
- [ ] Earnings calendar integration
- [ ] Options chain viewer
- [ ] Mobile app (PWA)

---

## Implementation Priority

### MVP (Week 1)
1. Basic layout and styling
2. Market indices with sparklines
3. Static sector performance bars
4. Watchlist table (no virtual scroll)
5. Manual refresh

### Enhancement (Week 2)
1. Top movers panel
2. News feed integration
3. Stock detail panel
4. Search and filter
5. Auto-refresh

### Polish (Week 3)
1. Animations and transitions
2. Keyboard navigation
3. Responsive refinements
4. Performance optimization
5. Error states and loading skeletons

---

## Design Mockup Reference

The dashboard should feel like a natural evolution of the existing email reports, transformed into an interactive experience. The dark theme with accent highlights creates visual hierarchy, while the grid-based layout ensures information density without overwhelming the viewer.

Key visual inspirations:
- TradingView (data density)
- Stripe Dashboard (polish and transitions)
- Bloomberg Terminal (information architecture)
- FlowOS (dark theme warmth)

---

*Document Version: 1.0*
*Last Updated: January 29, 2026*
*Author: Stock Monitor Design System*
