import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

st.set_page_config(
    page_title="Investment Analysis System",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "investment_tracker.db"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');
html, body, [class*="css"] { font-family: 'Libre Baskerville', serif; background-color: #0d0f14; color: #e8e4d9; }
.stApp { background-color: #0d0f14; }
h1, h2, h3 { font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em; }
.metric-card { background: #161b24; border: 1px solid #2a3344; border-radius: 4px; padding: 1.2rem 1.5rem; margin-bottom: 0.75rem; }
.buy-badge         { background: #0d2b1a; color: #3ddc84; border: 1px solid #1a5c35; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.buy-badge-muted   { background: #0a1a10; color: #1f6b40; border: 1px solid #0f3320; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.hold-badge        { background: #2b2200; color: #ffc947; border: 1px solid #5c4a00; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.hold-badge-muted  { background: #1a1500; color: #7a6020; border: 1px solid #332900; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.pass-badge        { background: #2b0d0d; color: #ff6b6b; border: 1px solid #5c1a1a; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.pass-badge-muted  { background: #1a0808; color: #7a3333; border: 1px solid #330f0f; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.hardpass-badge        { background: #1a0a0a; color: #cc3333; border: 1px solid #4d1111; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.hardpass-badge-muted  { background: #100606; color: #5c1a1a; border: 1px solid #2a0808; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.trigger-clear { color: #3ddc84; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.trigger-flag  { color: #ffc947; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.header-block { border-left: 3px solid #2a7fff; padding-left: 1rem; margin-bottom: 1.5rem; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
div[data-testid="stSidebarContent"] { background-color: #0a0c10; border-right: 1px solid #1e2736; }
.stSelectbox label, .stTextInput label, .stNumberInput label, .stTextArea label { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8899aa; }
.stButton button { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; background-color: #1a2436; color: #e8e4d9; border: 1px solid #2a3344; border-radius: 3px; }
.stButton button:hover { background-color: #2a3a56; border-color: #2a7fff; }
</style>
""", unsafe_allow_html=True)


# ── DATABASE ──────────────────────────────────────────────────────────────────

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS buy_list (
        ticker TEXT PRIMARY KEY,
        current_price REAL,
        upside_low REAL,
        upside_high REAL,
        capital_efficiency_score REAL,
        institutional_money TEXT DEFAULT 'Pending',
        date_added TEXT,
        is_new INTEGER DEFAULT 0,
        notes TEXT DEFAULT '')""")

    c.execute("""CREATE TABLE IF NOT EXISTS hold_list (
        ticker TEXT PRIMARY KEY,
        current_price REAL,
        upside_low REAL,
        upside_high REAL,
        fair_entry_low REAL,
        fair_entry_high REAL,
        capital_efficiency_score REAL,
        date_added TEXT,
        is_new INTEGER DEFAULT 0,
        notes TEXT DEFAULT '')""")

    c.execute("""CREATE TABLE IF NOT EXISTS master_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        date_analyzed TEXT,
        verdict TEXT,
        notes TEXT DEFAULT '',
        next_review TEXT DEFAULT 'Trigger-phrase governed',
        is_unified INTEGER DEFAULT 0)""")

    # Migration: add is_unified column if it doesn't exist yet (safe on existing DBs)
    try:
        c.execute("ALTER TABLE master_log ADD COLUMN is_unified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists — no action needed

    c.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        price REAL,
        fetched_at TEXT)""")

    conn.commit()
    conn.close()


def is_seeded():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM buy_list")
    n = c.fetchone()[0]
    conn.close()
    return n > 0


def seed_v2_clean():
    """
    Seed from V2 Master Reference Document — clean anchor.
    is_unified = 0  →  pre-Unified (plain emoji marks in V2)
    is_unified = 1  →  post-Unified (square mark tickers in V2)
    All new entries going forward default to is_unified = 1.
    """
    conn = get_conn()
    c = conn.cursor()

    # ── BUY LIST ──────────────────────────────────────────────────────────────
    buy_data = [
        ("GTLB", 25.98,  40, 60, "Pending", "May 11, 2026", 0),
        ("NKE",  44.14,  50, 70, "Pending", "May 11, 2026", 1),
        ("CRM",  181.82, 45, 60, "Pending", "May 11, 2026", 0),
        ("ADBE", 247.36, 50, 70, "Pending", "May 11, 2026", 0),
    ]
    for ticker, price, ul, uh, inst, dt, is_new in buy_data:
        score = round((ul + uh) / 2 / price, 2)
        c.execute("""INSERT OR IGNORE INTO buy_list
            (ticker, current_price, upside_low, upside_high, capital_efficiency_score,
             institutional_money, date_added, is_new)
            VALUES (?,?,?,?,?,?,?,?)""",
            (ticker, price, ul, uh, score, inst, dt, is_new))

    # ── HOLD LIST ─────────────────────────────────────────────────────────────
    hold_data = [
        ("GFI",   44.86,   35, 45, 28,  33,  "May 11, 2026", 0),
        ("HALO",  66.41,   45, 55, 52,  58,  "May 11, 2026", 0),
        ("TW",    108.81,  45, 55, 83,  92,  "May 11, 2026", 0),
        ("NOW",   92.50,   35, 50, 72,  80,  "May 11, 2026", 0),
        ("NEM",   120.67,  50, 55, 93,  100, "May 11, 2026", 0),
        ("NDAQ",  88.48,   50, 55, 78,  83,  "May 12, 2026", 0),
        ("SNOW",  154.06,  30, 45, 105, 115, "May 11, 2026", 0),
        ("AMZN",  271.82,  25, 40, 195, 210, "May 11, 2026", 0),
        ("INTU",  397.54,  30, 45, 320, 340, "May 11, 2026", 0),
        ("EQIX",  1073.23, 30, 45, 700, 780, "May 12, 2026", 0),
        ("AME",   231.61,  35, 50, 155, 175, "May 12, 2026", 0),
        ("CRWD",  548.02,  35, 50, 310, 360, "May 12, 2026", 1),
    ]
    for ticker, price, ul, uh, fel, feh, dt, is_new in hold_data:
        fep_mid = (fel + feh) / 2
        score = round((ul + uh) / 2 / fep_mid, 2)
        c.execute("""INSERT OR IGNORE INTO hold_list
            (ticker, current_price, upside_low, upside_high, fair_entry_low, fair_entry_high,
             capital_efficiency_score, date_added, is_new)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (ticker, price, ul, uh, fel, feh, score, dt, is_new))

    # ── MASTER LOG — BUY ──────────────────────────────────────────────────────
    # All plain ✅ = pre-Unified = is_unified=0
    buy_log = [
        ("GTLB", "May 4, 2026", 0),
        ("ADBE", "May 4, 2026", 0),
        ("NKE",  "May 4, 2026", 0),
        ("CRM",  "May 4, 2026", 0),
    ]
    for ticker, dt, unified in buy_log:
        c.execute("""INSERT OR IGNORE INTO master_log
            (ticker, date_analyzed, verdict, is_unified) VALUES (?,?,'BUY',?)""",
            (ticker, dt, unified))

    # ── MASTER LOG — HOLD ─────────────────────────────────────────────────────
    # Plain ⚠️ (May 4) = is_unified=0 | ⚠️🟨 (May 5+) = is_unified=1
    hold_log = [
        ("AMZN", "May 4, 2026",  0),
        ("INTU", "May 4, 2026",  0),
        ("NOW",  "May 4, 2026",  0),
        ("SNOW", "May 4, 2026",  0),
        ("HALO", "May 5, 2026",  1),
        ("GFI",  "May 5, 2026",  1),
        ("TW",   "May 5, 2026",  1),
        ("NEM",  "May 11, 2026", 1),
        ("NDAQ", "May 12, 2026", 1),
        ("EQIX", "May 12, 2026", 1),
        ("AME",  "May 12, 2026", 1),
        ("CRWD", "May 12, 2026", 1),
    ]
    for ticker, dt, unified in hold_log:
        c.execute("""INSERT OR IGNORE INTO master_log
            (ticker, date_analyzed, verdict, is_unified) VALUES (?,?,'HOLD',?)""",
            (ticker, dt, unified))

    # ── MASTER LOG — HARD PASS ────────────────────────────────────────────────
    # Plain 🚫 (May 4) = is_unified=0 | 🚫🟥 (May 11-12) = is_unified=1
    hard_pass_log = [
        ("CNXC",  "May 4, 2026",  0),
        ("G",     "May 4, 2026",  0),
        ("EPAM",  "May 4, 2026",  0),
        ("SAIC",  "May 4, 2026",  0),
        ("CTSH",  "May 4, 2026",  0),
        ("GIB",   "May 4, 2026",  0),
        ("DOX",   "May 4, 2026",  0),
        ("XOM",   "May 12, 2026", 1),
        ("INTC",  "May 12, 2026", 1),
        ("CRUS",  "May 11, 2026", 1),
        ("CTRA",  "May 11, 2026", 1),
        ("BRKB",  "May 11, 2026", 1),
        ("PK",    "May 11, 2026", 1),
        ("VNO",   "May 11, 2026", 1),
        ("ROCK",  "May 11, 2026", 1),
        ("PDD",   "May 11, 2026", 1),
        ("GNL",   "May 11, 2026", 1),
        ("PEB",   "May 11, 2026", 1),
        ("EQNR",  "May 11, 2026", 1),
        ("CBT",   "May 11, 2026", 1),
        ("WHD",   "May 11, 2026", 1),
        ("SRI",   "May 12, 2026", 1),
        ("VNOM",  "May 12, 2026", 1),
        ("MBLY",  "May 12, 2026", 1),
        ("LYFT",  "May 12, 2026", 1),
        ("FANUY", "May 12, 2026", 1),
        ("HNNA",  "May 11, 2026", 1),
        ("ODFL",  "May 12, 2026", 1),
        ("MLM",   "May 12, 2026", 1),
        ("POOL",  "May 12, 2026", 1),
        ("TTC",   "May 12, 2026", 1),
        ("CSU",   "May 12, 2026", 1),
        ("NVR",   "May 12, 2026", 1),
        ("EXPD",  "May 12, 2026", 1),
    ]
    for ticker, dt, unified in hard_pass_log:
        c.execute("""INSERT OR IGNORE INTO master_log
            (ticker, date_analyzed, verdict, is_unified) VALUES (?,?,'HARD_PASS',?)""",
            (ticker, dt, unified))

    # ── MASTER LOG — PASS ─────────────────────────────────────────────────────
    # Plain ❌ (May 4) = is_unified=0
    pass_pre = [
        ("CSWI","May 4, 2026"),("TRU","May 4, 2026"),("FIS","May 4, 2026"),
        ("MSFT","May 4, 2026"),("CRWV","May 4, 2026"),("PANW","May 4, 2026"),
        ("SOFI","May 4, 2026"),("PLTR","May 4, 2026"),("DDOG","May 4, 2026"),
        ("COST","May 4, 2026"),("MCD","May 4, 2026"),("HSY","May 4, 2026"),
        ("CL","May 4, 2026"),("AXP","May 4, 2026"),("PG","May 4, 2026"),
        ("JNJ","May 4, 2026"),("PEP","May 4, 2026"),("WM","May 4, 2026"),
        ("MNST","May 4, 2026"),("AZO","May 4, 2026"),("HD","May 4, 2026"),
        ("ROST","May 4, 2026"),("LULU","May 4, 2026"),("BKNG","May 4, 2026"),
        ("SBUX","May 4, 2026"),("CMG","May 4, 2026"),("CPRT","May 4, 2026"),
        ("FAST","May 4, 2026"),("CTAS","May 4, 2026"),("ITW","May 4, 2026"),
        ("ROK","May 4, 2026"),("GEV","May 4, 2026"),("KEYS","May 4, 2026"),
        ("VRT","May 4, 2026"),("LMT","May 4, 2026"),("HON","May 4, 2026"),
        ("TXN","May 4, 2026"),("AMAT","May 4, 2026"),("DIS","May 4, 2026"),
        ("VST","May 4, 2026"),("DVN","May 4, 2026"),("APA","May 4, 2026"),
        ("ET","May 4, 2026"),("CEG","May 4, 2026"),("NEE","May 4, 2026"),
        ("NVT","May 4, 2026"),("ORA","May 4, 2026"),("FSLR","May 4, 2026"),
        ("LNG","May 4, 2026"),("CVX","May 4, 2026"),("FLNG","May 4, 2026"),
        ("CRSP","May 4, 2026"),("LZAGY","May 4, 2026"),("NTLA","May 4, 2026"),
        ("TWST","May 4, 2026"),("SEV","May 4, 2026"),("GRAIL","May 4, 2026"),
        ("GH","May 4, 2026"),("ASML","May 4, 2026"),("KGC","May 4, 2026"),
        ("UBER","May 4, 2026"),("CERT","May 4, 2026"),("RKLB","May 4, 2026"),
        ("RGTI","May 4, 2026"),("LLY","May 4, 2026"),("TMO","May 4, 2026"),
        ("DHR","May 4, 2026"),("ISRG","May 4, 2026"),("SPGI","May 4, 2026"),
        ("MCO","May 4, 2026"),("CSGP","May 4, 2026"),
    ]
    for ticker, dt in pass_pre:
        c.execute("""INSERT OR IGNORE INTO master_log
            (ticker, date_analyzed, verdict, is_unified) VALUES (?,?,'PASS',0)""",
            (ticker, dt))

    # ❌🟥 (May 5+) = is_unified=1
    pass_post = [
        ("TRUE","May 5, 2026"),("EFX","May 5, 2026"),("IT","May 5, 2026"),
        ("ROP","May 5, 2026"),("MSCI","May 5, 2026"),("BR","May 5, 2026"),
        ("FDS","May 5, 2026"),("RSG","May 5, 2026"),("TYL","May 5, 2026"),
        ("SSNC","May 5, 2026"),("LDOS","May 5, 2026"),("J","May 5, 2026"),
        ("BAH","May 5, 2026"),("CACI","May 5, 2026"),("EXPO","May 5, 2026"),
        ("FCN","May 5, 2026"),("MORN","May 5, 2026"),("JKHY","May 5, 2026"),
        ("CDW","May 5, 2026"),("PAYX","May 5, 2026"),("LUNR","May 5, 2026"),
        ("BBAI","May 5, 2026"),("OMAB","May 5, 2026"),("LOPE","May 5, 2026"),
        ("IDCC","May 11, 2026"),("FCFS","May 11, 2026"),("BRO","May 11, 2026"),
        ("PRPO","May 11, 2026"),("CCEL","May 11, 2026"),("FRPT","May 11, 2026"),
        ("OPFI","May 11, 2026"),("VEON","May 11, 2026"),("ENS","May 11, 2026"),
        ("NUTX","May 11, 2026"),("WRB","May 12, 2026"),("ABBNY","May 12, 2026"),
        ("MRVL","May 12, 2026"),("OR","May 12, 2026"),("ROKU","May 12, 2026"),
        ("CART","May 12, 2026"),("ALVO","May 12, 2026"),("TTWO","May 12, 2026"),
        ("MSI","May 12, 2026"),("ZBRA","May 12, 2026"),("AJG","May 12, 2026"),
        ("HEI","May 12, 2026"),("IDXX","May 12, 2026"),("WCN","May 12, 2026"),
        ("BFAM","May 12, 2026"),("CLH","May 12, 2026"),("WSO","May 12, 2026"),
        ("LII","May 12, 2026"),("CSL","May 12, 2026"),
        ("CHWY","May 14, 2026"),("AM","May 14, 2026"),
    ]
    for ticker, dt in pass_post:
        c.execute("""INSERT OR IGNORE INTO master_log
            (ticker, date_analyzed, verdict, is_unified) VALUES (?,?,'PASS',1)""",
            (ticker, dt))

    conn.commit()
    conn.close()


# ── HELPERS ───────────────────────────────────────────────────────────────────

def verdict_badge_html(verdict, is_unified):
    """
    Returns an HTML badge string.
    is_unified=1 → full brightness + square mark prefix
    is_unified=0 → muted styling, no square mark
    Display layer reads the integer field directly — zero emoji parsing.
    """
    square = {
        "BUY":       "🟩",
        "HOLD":      "🟨",
        "PASS":      "🟥",
        "HARD_PASS": "🟥",
    }
    labels = {
        "BUY":       "BUY",
        "HOLD":      "HOLD",
        "PASS":      "PASS",
        "HARD_PASS": "HARD PASS",
    }
    css_class = {
        ("BUY",       1): "buy-badge",
        ("BUY",       0): "buy-badge-muted",
        ("HOLD",      1): "hold-badge",
        ("HOLD",      0): "hold-badge-muted",
        ("PASS",      1): "pass-badge",
        ("PASS",      0): "pass-badge-muted",
        ("HARD_PASS", 1): "hardpass-badge",
        ("HARD_PASS", 0): "hardpass-badge-muted",
    }
    label   = labels.get(verdict, verdict)
    cls     = css_class.get((verdict, is_unified), "pass-badge-muted")
    prefix  = square.get(verdict, "") + " " if is_unified else ""
    return f'<span class="{cls}">{prefix}{label}</span>'


def get_buy_list():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM buy_list ORDER BY capital_efficiency_score DESC", conn)
    conn.close()
    return df


def get_hold_list():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM hold_list ORDER BY capital_efficiency_score DESC", conn)
    conn.close()
    return df


def get_master_log(verdict_filter=None):
    conn = get_conn()
    if verdict_filter and verdict_filter != "ALL":
        df = pd.read_sql(
            "SELECT * FROM master_log WHERE verdict=? ORDER BY date_analyzed DESC, id DESC",
            conn, params=(verdict_filter,))
    else:
        df = pd.read_sql(
            "SELECT * FROM master_log ORDER BY date_analyzed DESC, id DESC", conn)
    conn.close()
    return df


def lookup_ticker(ticker):
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT verdict, date_analyzed, notes, is_unified
                 FROM master_log WHERE ticker=? ORDER BY id DESC LIMIT 1""", (ticker,))
    row = c.fetchone()
    conn.close()
    return row


def add_master_log(ticker, date_str, verdict, notes="", is_unified=1):
    """All new entries default to is_unified=1 — all new analysis is post-Unified."""
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM master_log WHERE ticker=? AND verdict=?", (ticker, verdict))
    existing = c.fetchone()
    if not existing:
        c.execute("""INSERT INTO master_log
            (ticker, date_analyzed, verdict, notes, is_unified)
            VALUES (?,?,?,?,?)""",
            (ticker, date_str, verdict, notes, is_unified))
    conn.commit()
    conn.close()


def add_or_update_buy(ticker, price, ul, uh, inst, date_str, notes, is_unified=1):
    ticker = ticker.upper().strip()
    score  = round((ul + uh) / 2 / price, 2) if price > 0 else 0
    conn   = get_conn()
    c      = conn.cursor()
    c.execute("UPDATE buy_list SET is_new=0")
    c.execute("""INSERT INTO buy_list
        (ticker, current_price, upside_low, upside_high, capital_efficiency_score,
         institutional_money, date_added, is_new, notes)
        VALUES (?,?,?,?,?,?,?,1,?)
        ON CONFLICT(ticker) DO UPDATE SET
            current_price=excluded.current_price,
            upside_low=excluded.upside_low,
            upside_high=excluded.upside_high,
            capital_efficiency_score=excluded.capital_efficiency_score,
            institutional_money=excluded.institutional_money,
            date_added=excluded.date_added,
            is_new=1,
            notes=excluded.notes""",
        (ticker, price, ul, uh, score, inst, date_str, notes))
    conn.commit()
    conn.close()
    add_master_log(ticker, date_str, "BUY", notes, is_unified)


def add_or_update_hold(ticker, price, ul, uh, fel, feh, date_str, notes, is_unified=1):
    ticker  = ticker.upper().strip()
    fep_mid = (fel + feh) / 2 if (fel + feh) > 0 else 1
    score   = round((ul + uh) / 2 / fep_mid, 2)
    conn    = get_conn()
    c       = conn.cursor()
    c.execute("UPDATE hold_list SET is_new=0")
    c.execute("""INSERT INTO hold_list
        (ticker, current_price, upside_low, upside_high, fair_entry_low, fair_entry_high,
         capital_efficiency_score, date_added, is_new, notes)
        VALUES (?,?,?,?,?,?,?,?,1,?)
        ON CONFLICT(ticker) DO UPDATE SET
            current_price=excluded.current_price,
            upside_low=excluded.upside_low,
            upside_high=excluded.upside_high,
            fair_entry_low=excluded.fair_entry_low,
            fair_entry_high=excluded.fair_entry_high,
            capital_efficiency_score=excluded.capital_efficiency_score,
            date_added=excluded.date_added,
            is_new=1,
            notes=excluded.notes""",
        (ticker, price, ul, uh, fel, feh, score, date_str, notes))
    conn.commit()
    conn.close()
    add_master_log(ticker, date_str, "HOLD", notes, is_unified)


def remove_from_buy(ticker):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM buy_list WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def remove_from_hold(ticker):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM hold_list WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def update_price_in_db(table, ticker, new_price, new_score):
    conn  = get_conn()
    c     = conn.cursor()
    today = date.today().strftime("%b %d, %Y")
    c.execute(f"UPDATE {table} SET current_price=?, capital_efficiency_score=?, date_added=? WHERE ticker=?",
              (new_price, new_score, today, ticker))
    conn.commit()
    conn.close()


def fetch_prices_yfinance(tickers):
    results = {}
    if not YFINANCE_AVAILABLE:
        return results
    for t in tickers:
        try:
            info  = yf.Ticker(t).fast_info
            price = round(float(info.last_price), 2)
            results[t] = price
        except Exception:
            results[t] = None
    return results


def run_market_data_update():
    buy_df  = get_buy_list()
    hold_df = get_hold_list()
    all_tickers = list(buy_df["ticker"]) + list(hold_df["ticker"])
    if not YFINANCE_AVAILABLE:
        return None, "yfinance not installed."
    prices = fetch_prices_yfinance(all_tickers)
    today  = date.today().strftime("%b %d, %Y")
    updated_buy = []
    for _, row in buy_df.iterrows():
        t         = row["ticker"]
        new_price = prices.get(t)
        if new_price:
            mid_upside = (row["upside_low"] + row["upside_high"]) / 2
            new_score  = round(mid_upside / new_price, 2)
            update_price_in_db("buy_list", t, new_price, new_score)
        updated_buy.append((t, row["current_price"], new_price))
    updated_hold = []
    for _, row in hold_df.iterrows():
        t         = row["ticker"]
        new_price = prices.get(t)
        if new_price:
            fep_mid   = (row["fair_entry_low"] + row["fair_entry_high"]) / 2
            mid_upside = (row["upside_low"] + row["upside_high"]) / 2
            new_score  = round(mid_upside / fep_mid, 2) if fep_mid > 0 else row["capital_efficiency_score"]
            update_price_in_db("hold_list", t, new_price, new_score)
        updated_hold.append((t, row["current_price"], new_price))
    return {"buy": updated_buy, "hold": updated_hold, "timestamp": today}, None


def check_hard_triggers(df_buy, df_hold):
    flags = []
    conn  = get_conn()
    c     = conn.cursor()
    for _, row in df_buy.iterrows():
        t = row["ticker"]
        c.execute("SELECT price FROM price_history WHERE ticker=? ORDER BY fetched_at ASC LIMIT 1", (t,))
        first = c.fetchone()
        if first:
            pct_move = abs(row["current_price"] - first[0]) / first[0] * 100
            if pct_move >= 20:
                flags.append(f"{t}: price moved {pct_move:.1f}% from baseline")
    conn.close()
    return flags


# ── BOOT ──────────────────────────────────────────────────────────────────────

init_db()
if not is_seeded():
    seed_v2_clean()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 💙🦋 DREAM TEAM")
    st.markdown('<p class="mono" style="color:#8899aa;">Investment Analysis System</p>', unsafe_allow_html=True)
    st.markdown('<p class="mono" style="color:#555e6e; font-size:0.75rem;">V2 — Unified 7 Points</p>', unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("Navigate",
        ["Dashboard", "Buy List", "Hold List", "Master Log",
         "Ticker Lookup", "Add / Update", "Market Data Updates"],
        label_visibility="collapsed")
    st.markdown("---")
    buy_count  = len(get_buy_list())
    hold_count = len(get_hold_list())
    log_count  = len(get_master_log())
    st.markdown(f'<p class="mono" style="color:#3ddc84;">Buy: {buy_count}</p>',   unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#ffc947;">Hold: {hold_count}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#8899aa;">Log: {log_count}</p>',   unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<p class="mono" style="color:#e8e4d9; font-size:0.82rem; font-weight:600;">Fundamentals first. Always.</p>', unsafe_allow_html=True)
    st.markdown('<p class="mono" style="color:#e8e4d9; font-size:0.82rem; font-weight:600;">We are not desperate. We wait. 🐟</p>', unsafe_allow_html=True)


# ── PAGES ─────────────────────────────────────────────────────────────────────

if page == "Dashboard":
    st.markdown(
        '<div class="header-block"><h1>Investment Analysis System</h1>'
        '<p class="mono" style="color:#8899aa;">Unified 7 Points Standards | V2 | Dream Team</p></div>',
        unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    log_df = get_master_log()
    with col1:
        st.markdown(f'<div class="metric-card"><p class="mono" style="color:#8899aa; margin:0; font-size:0.75rem;">BUY LIST</p><h2 style="color:#3ddc84; margin:0; font-family:JetBrains Mono,monospace;">{buy_count}</h2><p class="mono" style="color:#555e6e; margin:0; font-size:0.75rem;">active positions</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><p class="mono" style="color:#8899aa; margin:0; font-size:0.75rem;">HOLD LIST</p><h2 style="color:#ffc947; margin:0; font-family:JetBrains Mono,monospace;">{hold_count}</h2><p class="mono" style="color:#555e6e; margin:0; font-size:0.75rem;">awaiting trigger</p></div>', unsafe_allow_html=True)
    with col3:
        pass_n = len(log_df[log_df["verdict"] == "PASS"])
        st.markdown(f'<div class="metric-card"><p class="mono" style="color:#8899aa; margin:0; font-size:0.75rem;">PASSED</p><h2 style="color:#ff6b6b; margin:0; font-family:JetBrains Mono,monospace;">{pass_n}</h2><p class="mono" style="color:#555e6e; margin:0; font-size:0.75rem;">did not qualify</p></div>', unsafe_allow_html=True)
    with col4:
        hp_n = len(log_df[log_df["verdict"] == "HARD_PASS"])
        st.markdown(f'<div class="metric-card"><p class="mono" style="color:#8899aa; margin:0; font-size:0.75rem;">HARD PASS</p><h2 style="color:#cc3333; margin:0; font-family:JetBrains Mono,monospace;">{hp_n}</h2><p class="mono" style="color:#555e6e; margin:0; font-size:0.75rem;">permanent exclusion</p></div>', unsafe_allow_html=True)
    st.markdown("<hr style='border-top:1px solid #2a3344; margin:1.5rem 0;'>", unsafe_allow_html=True)
    col_b, col_h = st.columns(2)
    with col_b:
        st.markdown("#### Buy List — Ranked by Efficiency")
        buy_df = get_buy_list()
        for _, row in buy_df.iterrows():
            nm = " ← NEW" if row["is_new"] else ""
            st.markdown(
                f'<div class="metric-card" style="border-left:3px solid #3ddc84; padding:0.8rem 1rem;">'
                f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span>'
                f'<span style="color:#3ddc84;">{nm}</span> &nbsp;'
                f'<span class="mono" style="color:#8899aa;">${row["current_price"]:.2f}</span>'
                f'<span style="float:right;" class="mono">'
                f'<span style="color:#3ddc84;">{row["upside_low"]:.0f}–{row["upside_high"]:.0f}% upside</span>'
                f' &nbsp;Score: <em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em>'
                f'</span></div>',
                unsafe_allow_html=True)
    with col_h:
        st.markdown("#### Hold List — Ranked by Efficiency")
        hold_df = get_hold_list()
        for _, row in hold_df.iterrows():
            nm = " ← NEW" if row["is_new"] else ""
            st.markdown(
                f'<div class="metric-card" style="border-left:3px solid #ffc947; padding:0.8rem 1rem;">'
                f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span>'
                f'<span style="color:#ffc947;">{nm}</span> &nbsp;'
                f'<span class="mono" style="color:#8899aa;">${row["current_price"]:.2f}</span>'
                f'<span style="float:right;" class="mono">'
                f'<span style="color:#ffc947;">Entry: ${row["fair_entry_low"]:.0f}–${row["fair_entry_high"]:.0f}</span>'
                f' &nbsp;Score: <em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em>'
                f'</span></div>',
                unsafe_allow_html=True)


elif page == "Buy List":
    st.markdown(
        '<div class="header-block"><h1>Buy List</h1>'
        '<p class="mono" style="color:#8899aa;">Ranked by Capital Efficiency Score (Upside% mid / Current Price)</p></div>',
        unsafe_allow_html=True)
    buy_df = get_buy_list()
    if buy_df.empty:
        st.info("No tickers in Buy List.")
    else:
        for _, row in buy_df.iterrows():
            nm = " ← NEW" if row["is_new"] else ""
            st.markdown(
                f'<div class="metric-card" style="border-left:3px solid #3ddc84;">'
                f'<div style="display:flex; justify-content:space-between;">'
                f'<div><span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1.15rem; color:#e8e4d9;">{row["ticker"]}</span>'
                f'<span style="color:#3ddc84;">{nm}</span> &nbsp;'
                f'<span class="mono" style="color:#3ddc84;">BUY</span></div>'
                f'<div class="mono" style="color:#555e6e; font-size:0.78rem;">{row["date_added"]}</div></div>'
                f'<div style="margin-top:0.6rem; display:flex; gap:2rem; flex-wrap:wrap;">'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CURRENT PRICE</p><p class="mono" style="color:#e8e4d9; margin:0;">${row["current_price"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">UPSIDE</p><p class="mono" style="color:#3ddc84; margin:0;">{row["upside_low"]:.0f}–{row["upside_high"]:.0f}%</p></div>'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CE SCORE</p><p class="mono" style="color:#ffc947; margin:0; font-style:italic;">{row["capital_efficiency_score"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">INSTITUTIONAL $</p><p class="mono" style="color:#e8e4d9; margin:0;">{row["institutional_money"]}</p></div>'
                f'</div></div>',
                unsafe_allow_html=True)
        st.markdown(f'<p class="mono" style="color:#3ddc84;">Total: {len(buy_df)} tickers | Hard Trigger Flags: All Clear</p>', unsafe_allow_html=True)
        st.markdown("---")
        export_df = buy_df[["ticker","current_price","upside_low","upside_high","capital_efficiency_score","institutional_money","date_added"]].copy()
        export_df.columns = ["Ticker","Price","Up Low%","Up High%","CE Score","Institutional $","Date"]
        st.dataframe(export_df, use_container_width=True, hide_index=True)


elif page == "Hold List":
    st.markdown(
        '<div class="header-block"><h1>Hold List</h1>'
        '<p class="mono" style="color:#8899aa;">Ranked by Capital Efficiency Score (Upside% mid / Fair Entry Price mid)</p></div>',
        unsafe_allow_html=True)
    hold_df = get_hold_list()
    if hold_df.empty:
        st.info("No tickers in Hold List.")
    else:
        for _, row in hold_df.iterrows():
            nm = " ← NEW" if row["is_new"] else ""
            st.markdown(
                f'<div class="metric-card" style="border-left:3px solid #ffc947;">'
                f'<div style="display:flex; justify-content:space-between;">'
                f'<div><span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1.15rem; color:#e8e4d9;">{row["ticker"]}</span>'
                f'<span style="color:#ffc947;">{nm}</span> &nbsp;'
                f'<span class="mono" style="color:#ffc947;">HOLD</span></div>'
                f'<div class="mono" style="color:#555e6e; font-size:0.78rem;">{row["date_added"]}</div></div>'
                f'<div style="margin-top:0.6rem; display:flex; gap:2rem; flex-wrap:wrap;">'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CURRENT PRICE</p><p class="mono" style="color:#e8e4d9; margin:0;">${row["current_price"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">UPSIDE</p><p class="mono" style="color:#ffc947; margin:0;">{row["upside_low"]:.0f}–{row["upside_high"]:.0f}%</p></div>'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">FAIR ENTRY</p><p class="mono" style="color:#ffc947; margin:0;">${row["fair_entry_low"]:.0f}–${row["fair_entry_high"]:.0f}</p></div>'
                f'<div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CE SCORE</p><p class="mono" style="color:#ffc947; margin:0; font-style:italic;">{row["capital_efficiency_score"]:.2f}</p></div>'
                f'</div></div>',
                unsafe_allow_html=True)
        st.markdown(f'<p class="mono" style="color:#ffc947;">Total: {len(hold_df)} tickers | Hard Trigger Flags: All Clear</p>', unsafe_allow_html=True)
        st.markdown("---")
        export_df = hold_df[["ticker","current_price","upside_low","upside_high","fair_entry_low","fair_entry_high","capital_efficiency_score","date_added"]].copy()
        export_df.columns = ["Ticker","Price","Up Low%","Up High%","Entry Low","Entry High","CE Score","Date"]
        st.dataframe(export_df, use_container_width=True, hide_index=True)


elif page == "Master Log":
    st.markdown(
        '<div class="header-block"><h1>Master Consolidated Log</h1>'
        '<p class="mono" style="color:#8899aa;">Cross-reference every ticker here first. All sessions. All verdicts.</p>'
        '<p class="mono" style="color:#555e6e; font-size:0.75rem;">'
        'Full brightness = post-Unified (Unified 7 Points) &nbsp;|&nbsp; Muted = pre-Unified (legacy standard)'
        '</p></div>',
        unsafe_allow_html=True)

    col_filter, col_search = st.columns([2, 3])
    with col_filter:
        verdict_filter = st.selectbox("Filter by Verdict", ["ALL", "BUY", "HOLD", "PASS", "HARD_PASS"])
    with col_search:
        search_term = st.text_input("Search Ticker", placeholder="e.g. GTLB")

    log_df  = get_master_log(verdict_filter if verdict_filter != "ALL" else None)
    all_log = get_master_log()

    if search_term:
        log_df = log_df[log_df["ticker"].str.upper() == search_term.upper()]

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#3ddc84; margin:0;">BUY: {len(all_log[all_log.verdict=="BUY"])}</p></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#ffc947; margin:0;">HOLD: {len(all_log[all_log.verdict=="HOLD"])}</p></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#ff6b6b; margin:0;">PASS: {len(all_log[all_log.verdict=="PASS"])}</p></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#cc3333; margin:0;">HARD PASS: {len(all_log[all_log.verdict=="HARD_PASS"])}</p></div>', unsafe_allow_html=True)

    st.markdown(f'<p class="mono" style="color:#8899aa; font-size:0.8rem;">Showing {len(log_df)} records</p>', unsafe_allow_html=True)

    if log_df.empty:
        st.info("No records found.")
    else:
        # Border colors per verdict — full brightness (post-Unified) and muted (pre-Unified)
        border_full = {"BUY": "#3ddc84", "HOLD": "#ffc947", "PASS": "#ff6b6b", "HARD_PASS": "#cc3333"}
        border_muted = {"BUY": "#1a4a2a", "HOLD": "#3a2e00", "PASS": "#3a1010", "HARD_PASS": "#2a0a0a"}

        # Render rows with badge HTML — display layer reads is_unified integer directly
        for _, row in log_df.iterrows():
            is_unified   = int(row.get("is_unified", 0))
            badge_html   = verdict_badge_html(row["verdict"], is_unified)
            ticker_color = "#e8e4d9" if is_unified else "#4a5568"
            date_color   = "#8899aa" if is_unified else "#3a4252"
            border_color = border_full.get(row["verdict"], "#2a3344") if is_unified else border_muted.get(row["verdict"], "#1e2736")
            st.markdown(
                f'<div class="metric-card" style="border-left:3px solid {border_color}; padding:0.6rem 1rem; margin-bottom:0.4rem;">'
                f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; color:{ticker_color}; min-width:80px; display:inline-block;">{row["ticker"]}</span>'
                f'&nbsp;&nbsp;{badge_html}&nbsp;&nbsp;'
                f'<span class="mono" style="color:{date_color}; font-size:0.78rem;">{row["date_analyzed"]}</span>'
                f'<span class="mono" style="color:#3a4252; font-size:0.72rem; float:right;">{row["next_review"]}</span>'
                f'</div>',
                unsafe_allow_html=True)


elif page == "Ticker Lookup":
    st.markdown(
        '<div class="header-block"><h1>Ticker Cross-Reference</h1>'
        '<p class="mono" style="color:#8899aa;">Check Master Consolidated Log instantly before any analysis.</p></div>',
        unsafe_allow_html=True)
    ticker_input = st.text_input("Enter Ticker Symbol", placeholder="e.g. CRWD, NKE, MSFT").upper().strip()
    if ticker_input:
        result = lookup_ticker(ticker_input)
        if result:
            verdict, dt, notes, is_unified = result
            colors  = {"BUY": "#3ddc84", "HOLD": "#ffc947", "PASS": "#ff6b6b", "HARD_PASS": "#cc3333"}
            labels  = {"BUY": "ALREADY ON BUY LIST", "HOLD": "ALREADY ON HOLD LIST",
                       "PASS": "PREVIOUSLY PASSED", "HARD_PASS": "HARD PASS — PERMANENT"}
            actions = {"BUY":       "Already approved and active. Report position + skip.",
                       "HOLD":      "Already analyzed, waiting for price trigger. Report + skip.",
                       "PASS":      "Did not meet standards. Re-evaluation Triggers quarterly.",
                       "HARD_PASS": "Permanent exclusion. BPO/AI-vulnerable or full cyclical fail."}
            col     = colors.get(verdict, "#8899aa")
            lbl     = labels.get(verdict, verdict)
            act     = actions.get(verdict, "")
            std_tag = "POST-UNIFIED" if is_unified else "PRE-UNIFIED"
            std_col = "#8899aa" if is_unified else "#4a5568"
            badge   = verdict_badge_html(verdict, int(is_unified))
            st.markdown(
                f'<div class="metric-card" style="border-left:4px solid {col};">'
                f'<h3 style="color:{col}; font-family:JetBrains Mono,monospace;">{ticker_input} — {lbl}</h3>'
                f'<p class="mono">Date analyzed: {dt} &nbsp;&nbsp; {badge} &nbsp;&nbsp;'
                f'<span style="color:{std_col}; font-size:0.75rem;">{std_tag}</span></p>'
                f'<p class="mono" style="color:{col};">{act}</p>'
                f'{("<p class=mono style=color:#8899aa;>" + notes + "</p>") if notes else ""}'
                f'</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="metric-card" style="border-left:4px solid #2a7fff;">'
                f'<h3 style="color:#2a7fff; font-family:JetBrains Mono,monospace;">{ticker_input} — NOT FOUND IN LOG</h3>'
                f'<p class="mono">Proceed with full Unified 7 Points deep-dive analysis.</p>'
                f'<p class="mono" style="color:#8899aa;">After analysis: add verdict via Add / Update page.</p>'
                f'</div>',
                unsafe_allow_html=True)


elif page == "Add / Update":
    st.markdown(
        '<div class="header-block"><h1>Add / Update Ticker</h1>'
        '<p class="mono" style="color:#8899aa;">HANDOFF line — auto-logs to correct table with Capital Efficiency Score.</p></div>',
        unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["Add to Buy List", "Add to Hold List", "Log PASS / HARD PASS", "Remove Ticker"])

    with tab1:
        st.markdown("#### Add / Update — Buy List")
        with st.form("add_buy_form"):
            col1, col2 = st.columns(2)
            with col1:
                b_ticker = st.text_input("Ticker Symbol *").upper().strip()
                b_price  = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
            with col2:
                b_ul = st.number_input("Upside Low (%)",  min_value=0.0, value=50.0, step=1.0)
                b_uh = st.number_input("Upside High (%)", min_value=0.0, value=70.0, step=1.0)
            b_inst = st.selectbox("Institutional Money / Tape Reading",
                ["Pending", "Strong absorption / aggressive buying",
                 "Neutral / choppy flow", "Distribution / selling pressure"])
            b_notes    = st.text_area("Notes (optional)")
            b_date     = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            b_unified  = st.toggle("Post-Unified (Unified 7 Points)", value=True)
            if st.form_submit_button("Add to Buy List"):
                if not b_ticker:
                    st.error("Ticker is required.")
                elif b_price <= 0:
                    st.error("Price must be greater than 0.")
                else:
                    add_or_update_buy(b_ticker, b_price, b_ul, b_uh, b_inst, b_date, b_notes, int(b_unified))
                    score = round((b_ul + b_uh) / 2 / b_price, 2)
                    st.success(f"{b_ticker} added to Buy List — CE Score: {score:.2f}")

    with tab2:
        st.markdown("#### Add / Update — Hold List")
        with st.form("add_hold_form"):
            col1, col2 = st.columns(2)
            with col1:
                h_ticker = st.text_input("Ticker Symbol *").upper().strip()
                h_price  = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
                h_ul     = st.number_input("Upside Low (%)",  min_value=0.0, value=35.0, step=1.0)
                h_uh     = st.number_input("Upside High (%)", min_value=0.0, value=50.0, step=1.0)
            with col2:
                h_fel = st.number_input("Fair Entry Price Low ($) *",  min_value=0.01, value=80.00, step=0.01)
                h_feh = st.number_input("Fair Entry Price High ($) *", min_value=0.01, value=90.00, step=0.01)
            h_notes   = st.text_area("Notes (optional)")
            h_date    = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            h_unified = st.toggle("Post-Unified (Unified 7 Points)", value=True)
            if st.form_submit_button("Add to Hold List"):
                if not h_ticker:
                    st.error("Ticker is required.")
                else:
                    add_or_update_hold(h_ticker, h_price, h_ul, h_uh, h_fel, h_feh, h_date, h_notes, int(h_unified))
                    fep_mid = (h_fel + h_feh) / 2
                    score   = round((h_ul + h_uh) / 2 / fep_mid, 2)
                    st.success(f"{h_ticker} added to Hold List — CE Score: {score:.2f} — Entry: ${h_fel:.0f}–${h_feh:.0f}")

    with tab3:
        st.markdown("#### Log PASS or HARD PASS")
        with st.form("add_pass_form"):
            p_ticker  = st.text_input("Ticker Symbol *").upper().strip()
            p_verdict = st.radio("Verdict", ["PASS", "HARD_PASS"])
            p_notes   = st.text_area("Notes / reason")
            p_date    = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            p_unified = st.toggle("Post-Unified (Unified 7 Points)", value=True)
            if st.form_submit_button("Log to Master Consolidated Log"):
                if not p_ticker:
                    st.error("Ticker is required.")
                else:
                    add_master_log(p_ticker, p_date, p_verdict, p_notes, int(p_unified))
                    label = "HARD PASS" if p_verdict == "HARD_PASS" else "PASS"
                    st.success(f"{p_ticker} logged — {p_date} — {label}")

    with tab4:
        st.markdown("#### Remove Ticker from Active List")
        st.markdown('<p class="mono" style="color:#cc3333; font-size:0.85rem;">One-Ticker-One-Home Rule: remove before moving to new list.</p>', unsafe_allow_html=True)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            r_ticker_buy = st.text_input("Remove from Buy List").upper().strip()
            if st.button("Remove from Buy List"):
                if r_ticker_buy:
                    remove_from_buy(r_ticker_buy)
                    st.success(f"{r_ticker_buy} removed from Buy List.")
        with col_r2:
            r_ticker_hold = st.text_input("Remove from Hold List").upper().strip()
            if st.button("Remove from Hold List"):
                if r_ticker_hold:
                    remove_from_hold(r_ticker_hold)
                    st.success(f"{r_ticker_hold} removed from Hold List.")


elif page == "Market Data Updates":
    st.markdown(
        '<div class="header-block"><h1>Market Data Updates</h1>'
        '<p class="mono" style="color:#8899aa;">Refreshes prices, recalculates CE Scores, checks Hard Trigger Flags.</p></div>',
        unsafe_allow_html=True)
    if not YFINANCE_AVAILABLE:
        st.error("yfinance not installed. Run: pip install yfinance")
    else:
        st.markdown('<p class="mono" style="color:#3ddc84;">yfinance available</p>', unsafe_allow_html=True)
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("#### Current — Buy List")
        buy_df = get_buy_list()
        if not buy_df.empty:
            disp = buy_df[["ticker","current_price","upside_low","upside_high","capital_efficiency_score","date_added"]].copy()
            disp.columns = ["Ticker","Price","Up Low%","Up High%","CE Score","Date"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
    with col_b:
        st.markdown("#### Current — Hold List")
        hold_df = get_hold_list()
        if not hold_df.empty:
            disp = hold_df[["ticker","current_price","capital_efficiency_score"]].copy()
            disp.columns = ["Ticker","Price","CE Score"]
            st.dataframe(disp, use_container_width=True, hide_index=True)
    st.markdown("---")
    if st.button("RUN MARKET DATA UPDATE", type="primary"):
        with st.spinner("Fetching live prices from Yahoo Finance..."):
            result, error = run_market_data_update()
        if error:
            st.error(f"Error: {error}")
        elif result:
            st.success(f"Market Data Update complete — {result['timestamp']}")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Buy List Updates")
                for t, old, new in result["buy"]:
                    if new:
                        delta     = new - old
                        color     = "#3ddc84" if delta >= 0 else "#ff6b6b"
                        delta_str = f"+${delta:.2f}" if delta >= 0 else f"-${abs(delta):.2f}"
                        st.markdown(f'<p class="mono"><strong>{t}</strong>: ${old:.2f} → <span style="color:{color};">${new:.2f} ({delta_str})</span></p>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<p class="mono" style="color:#8899aa;"><strong>{t}</strong>: unavailable</p>', unsafe_allow_html=True)
            with col2:
                st.markdown("#### Hold List Updates")
                for t, old, new in result["hold"]:
                    if new:
                        delta     = new - old
                        color     = "#3ddc84" if delta >= 0 else "#ff6b6b"
                        delta_str = f"+${delta:.2f}" if delta >= 0 else f"-${abs(delta):.2f}"
                        st.markdown(f'<p class="mono"><strong>{t}</strong>: ${old:.2f} → <span style="color:{color};">${new:.2f} ({delta_str})</span></p>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<p class="mono" style="color:#8899aa;"><strong>{t}</strong>: unavailable</p>', unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("#### Hard Trigger Flags")
            flags = check_hard_triggers(get_buy_list(), get_hold_list())
            if flags:
                for f in flags:
                    st.markdown(f'<p class="trigger-flag">{f}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="trigger-clear">All Clear — {result["timestamp"]}</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("#### Manual Price Override")
    with st.form("manual_price_form"):
        mp_col1, mp_col2, mp_col3 = st.columns(3)
        with mp_col1:
            mp_ticker = st.text_input("Ticker").upper().strip()
        with mp_col2:
            mp_list = st.selectbox("List", ["Buy List", "Hold List"])
        with mp_col3:
            mp_price = st.number_input("New Price ($)", min_value=0.01, value=100.00, step=0.01)
        if st.form_submit_button("Update Price"):
            if mp_ticker and mp_price > 0:
                if mp_list == "Buy List":
                    conn = get_conn()
                    c    = conn.cursor()
                    c.execute("SELECT upside_low, upside_high FROM buy_list WHERE ticker=?", (mp_ticker,))
                    row  = c.fetchone()
                    conn.close()
                    if row:
                        new_score = round((row[0] + row[1]) / 2 / mp_price, 2)
                        update_price_in_db("buy_list", mp_ticker, mp_price, new_score)
                        st.success(f"{mp_ticker} updated to ${mp_price:.2f} — CE Score: {new_score:.2f}")
                    else:
                        st.error(f"{mp_ticker} not found in Buy List.")
                else:
                    conn = get_conn()
                    c    = conn.cursor()
                    c.execute("SELECT upside_low, upside_high, fair_entry_low, fair_entry_high FROM hold_list WHERE ticker=?", (mp_ticker,))
                    row  = c.fetchone()
                    conn.close()
                    if row:
                        fep_mid   = (row[2] + row[3]) / 2
                        new_score = round((row[0] + row[1]) / 2 / fep_mid, 2) if fep_mid > 0 else 0
                        update_price_in_db("hold_list", mp_ticker, mp_price, new_score)
                        st.success(f"{mp_ticker} updated to ${mp_price:.2f} — CE Score: {new_score:.2f}")
                    else:
                        st.error(f"{mp_ticker} not found in Hold List.")
