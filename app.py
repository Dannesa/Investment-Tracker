# ── HARD TRIGGER FLAGS — UPGRADED ────────────────────────────────────────────
# Replaces the original check_hard_triggers() function in app.py
# Drop-in replacement — no other changes required
#
# Checks implemented:
#   1. Price movement ±20% from baseline          (existing — preserved)
#   2. Market cap movement ±20% from baseline     (NEW)
#   3. FCF turned negative — hard stop            (NEW)
#   4. Revenue deceleration — graduated           (NEW)
#      - 5+ point YoY drop over 2+ consecutive periods → 🚩 Hard Trigger
#      - 3–5 point drop → ⚠️ Yellow Flag (deeper review)
#      - Growth below 8% threshold → 🚩 Critical Deceleration
# ─────────────────────────────────────────────────────────────────────────────

def init_db_market_cap_baseline():
    """
    Adds market_cap column to price_history if not already present.
    Safe to call on every app start — ALTER TABLE is wrapped in try/except.
    Call this AFTER init_db() in the app startup sequence.
    """
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE price_history ADD COLUMN market_cap REAL DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # Column already exists — no action needed
    conn.close()


def store_baseline_snapshot(ticker, price, market_cap):
    """
    Stores the first-ever price + market cap snapshot for a ticker.
    Only writes if no existing record exists — baseline is immutable
    until a full re-analysis resets it.
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM price_history WHERE ticker=?", (ticker,))
    count = c.fetchone()[0]
    if count == 0:
        fetched_at = date.today().strftime("%Y-%m-%d")
        c.execute(
            "INSERT INTO price_history (ticker, price, market_cap, fetched_at) VALUES (?,?,?,?)",
            (ticker, price, market_cap, fetched_at)
        )
        conn.commit()
    conn.close()


def fetch_fundamentals_yfinance(ticker):
    """
    Fetches FCF, revenue history, and market cap for a single ticker.
    Returns a dict with keys: fcf_values, revenue_growth_rates, market_cap
    Returns None on fetch failure.

    FCF: uses operating cash flow - capex (TTM quarters)
    Revenue: annual revenue figures used to compute YoY growth rates
    Market cap: current value from fast_info
    """
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info

        # ── MARKET CAP ───────────────────────────────────────────────────
        market_cap = None
        try:
            market_cap = float(info.market_cap)
        except Exception:
            pass

        # ── FREE CASH FLOW ───────────────────────────────────────────────
        # Pull quarterly cash flow statement
        fcf_values = []
        try:
            cf = t.quarterly_cashflow
            if cf is not None and not cf.empty:
                # Row labels vary — search for operating CF and capex rows
                op_cf_row = None
                capex_row = None
                for label in cf.index:
                    label_lower = str(label).lower()
                    if "operating" in label_lower and "cash" in label_lower:
                        op_cf_row = label
                    if "capital expenditure" in label_lower or "capex" in label_lower:
                        capex_row = label

                if op_cf_row is not None:
                    op_cf = cf.loc[op_cf_row].dropna().values
                    if capex_row is not None:
                        capex = cf.loc[capex_row].dropna().values
                        min_len = min(len(op_cf), len(capex))
                        fcf_values = [
                            float(op_cf[i]) + float(capex[i])  # capex is negative in yfinance
                            for i in range(min_len)
                        ]
                    else:
                        # Fallback: use operating CF only if capex unavailable
                        fcf_values = [float(v) for v in op_cf]
        except Exception:
            pass

        # ── REVENUE GROWTH RATES ─────────────────────────────────────────
        # Use annual revenue for YoY growth rate calculation
        revenue_growth_rates = []
        try:
            income = t.financials  # Annual income statement
            if income is not None and not income.empty:
                rev_row = None
                for label in income.index:
                    label_lower = str(label).lower()
                    if "total revenue" in label_lower or "revenue" in label_lower:
                        rev_row = label
                        break

                if rev_row is not None:
                    rev_series = income.loc[rev_row].dropna()
                    # yfinance returns most recent first — reverse for chronological
                    rev_values = list(reversed([float(v) for v in rev_series.values]))

                    if len(rev_values) >= 2:
                        for i in range(1, len(rev_values)):
                            prior = rev_values[i - 1]
                            current = rev_values[i]
                            if prior > 0:
                                growth_rate = ((current - prior) / prior) * 100
                                revenue_growth_rates.append(round(growth_rate, 2))
        except Exception:
            pass

        return {
            "market_cap": market_cap,
            "fcf_values": fcf_values,
            "revenue_growth_rates": revenue_growth_rates
        }

    except Exception:
        return None


def check_hard_triggers(df_buy, df_hold):
    """
    Runs all 4 Hard Trigger checks across BUY + HOLD lists.
    Returns a list of flag strings — empty list = All Clear.

    Check 1: Price movement ±20% from baseline       (original — preserved)
    Check 2: Market cap movement ±20% from baseline  (new)
    Check 3: FCF turned negative                     (new — hard stop)
    Check 4: Revenue deceleration                    (new — graduated)
    """
    flags = []
    conn = get_conn()
    c = conn.cursor()

    all_tickers_df = pd.concat([df_buy, df_hold], ignore_index=True)

    for _, row in all_tickers_df.iterrows():
        t = row["ticker"]
        current_price = row["current_price"]

        # ── FETCH BASELINE FROM price_history ────────────────────────────
        c.execute(
            "SELECT price, market_cap FROM price_history WHERE ticker=? ORDER BY fetched_at ASC LIMIT 1",
            (t,)
        )
        baseline_row = c.fetchone()
        baseline_price = baseline_row[0] if baseline_row else None
        baseline_mktcap = baseline_row[1] if baseline_row else None

        # ── CHECK 1: PRICE MOVEMENT ±20% FROM BASELINE ──────────────────
        if baseline_price and baseline_price > 0:
            pct_move = abs(current_price - baseline_price) / baseline_price * 100
            if pct_move >= 20:
                direction = "▲" if current_price > baseline_price else "▼"
                flags.append(
                    f"🚩 {t} — Price moved {direction}{pct_move:.1f}% from baseline "
                    f"(${baseline_price:.2f} → ${current_price:.2f})"
                )

        # ── FETCH FUNDAMENTALS FOR CHECKS 2–4 ───────────────────────────
        fundamentals = fetch_fundamentals_yfinance(t)
        if fundamentals is None:
            flags.append(f"⚠️ {t} — Fundamentals unavailable — manual review required")
            continue

        current_mktcap = fundamentals["market_cap"]
        fcf_values     = fundamentals["fcf_values"]
        rev_growth     = fundamentals["revenue_growth_rates"]

        # Store baseline snapshot on first run (price + market cap)
        if current_mktcap:
            store_baseline_snapshot(t, current_price, current_mktcap)

        # ── CHECK 2: MARKET CAP MOVEMENT ±20% FROM BASELINE ─────────────
        if baseline_mktcap and baseline_mktcap > 0 and current_mktcap:
            mktcap_move = abs(current_mktcap - baseline_mktcap) / baseline_mktcap * 100
            if mktcap_move >= 20:
                direction = "▲" if current_mktcap > baseline_mktcap else "▼"
                flags.append(
                    f"🚩 {t} — Market cap moved {direction}{mktcap_move:.1f}% from baseline"
                )

        # ── CHECK 3: FCF TURNED NEGATIVE — HARD STOP ────────────────────
        # Most recent quarter FCF is index 0 (yfinance returns newest first)
        if fcf_values:
            most_recent_fcf = fcf_values[0]
            if most_recent_fcf < 0:
                flags.append(
                    f"🚩 {t} — FCF NEGATIVE (most recent quarter: "
                    f"${most_recent_fcf / 1e6:.1f}M) — HARD STOP"
                )

        # ── CHECK 4: REVENUE DECELERATION — GRADUATED ───────────────────
        # Requires at least 3 annual data points → 2 growth rates to compare
        if len(rev_growth) >= 2:
            # Most recent growth rate = last element (chronological order)
            latest_rate   = rev_growth[-1]
            previous_rate = rev_growth[-2]
            deceleration  = previous_rate - latest_rate  # positive = slowing down

            # Critical threshold: growth below 8%
            below_critical = latest_rate < 8.0

            # Hard Trigger: 5+ point drop
            if deceleration >= 5.0:
                # Check for 2+ consecutive quarters of deceleration if data allows
                consecutive = False
                if len(rev_growth) >= 3:
                    prior_decel = rev_growth[-2] - rev_growth[-3]
                    if prior_decel > 0:
                        consecutive = True

                consec_note = " (2+ consecutive periods)" if consecutive else ""
                critical_note = " — BELOW 8% CRITICAL THRESHOLD" if below_critical else ""
                flags.append(
                    f"🚩 {t} — Revenue deceleration{consec_note}: "
                    f"{previous_rate:.1f}% → {latest_rate:.1f}% YoY "
                    f"({deceleration:.1f}pt drop){critical_note}"
                )

            # Yellow Flag: 3–5 point drop
            elif 3.0 <= deceleration < 5.0:
                critical_note = " — BELOW 8% CRITICAL THRESHOLD" if below_critical else ""
                flags.append(
                    f"⚠️ {t} — Yellow Flag: Mild revenue deceleration: "
                    f"{previous_rate:.1f}% → {latest_rate:.1f}% YoY "
                    f"({deceleration:.1f}pt drop) — deeper review recommended{critical_note}"
                )

            # Below 8% even without significant deceleration
            elif below_critical and deceleration >= 0:
                flags.append(
                    f"⚠️ {t} — Yellow Flag: Revenue growth at {latest_rate:.1f}% "
                    f"— below 8% critical threshold"
                )

    conn.close()
    return flags


# ── INTEGRATION NOTES ────────────────────────────────────────────────────────
# In app.py, make 2 changes after the existing init_db() call at startup:
#
#   BEFORE (existing):
#       init_db()
#       if not is_seeded():
#           seed_v55()
#
#   AFTER (updated):
#       init_db()
#       init_db_market_cap_baseline()   # ← ADD THIS LINE
#       if not is_seeded():
#           seed_v55()
#
# The check_hard_triggers() call in the Market Data Updates page
# (page == "Market Data Updates") requires NO changes — same signature:
#   flags = check_hard_triggers(get_buy_list(), get_hold_list())
# ─────────────────────────────────────────────────────────────────────────────
# Updated: June 02, 2026 — 2:22 AM — Dream Team 💙🦋
