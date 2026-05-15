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
.buy-badge { background: #0d2b1a; color: #3ddc84; border: 1px solid #1a5c35; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.hold-badge { background: #2b2200; color: #ffc947; border: 1px solid #5c4a00; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.pass-badge { background: #2b0d0d; color: #ff6b6b; border: 1px solid #5c1a1a; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.hardpass-badge { background: #1a0a0a; color: #cc3333; border: 1px solid #4d1111; padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; }
.trigger-clear { color: #3ddc84; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.trigger-flag { color: #ffc947; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.header-block { border-left: 3px solid #2a7fff; padding-left: 1rem; margin-bottom: 1.5rem; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
div[data-testid="stSidebarContent"] { background-color: #0a0c10; border-right: 1px solid #1e2736; }
.stSelectbox label, .stTextInput label, .stNumberInput label, .stTextArea label { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8899aa; }
.stButton button { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; background-color: #1a2436; color: #e8e4d9; border: 1px solid #2a3344; border-radius: 3px; }
.stButton button:hover { background-color: #2a3a56; border-color: #2a7fff; }
</style>
""", unsafe_allow_html=True)

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS buy_list (
        ticker TEXT PRIMARY KEY, current_price REAL, upside_low REAL, upside_high REAL,
        capital_efficiency_score REAL, institutional_money TEXT DEFAULT 'Pending',
        date_added TEXT, is_new INTEGER DEFAULT 0, notes TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS hold_list (
        ticker TEXT PRIMARY KEY, current_price REAL, upside_low REAL, upside_high REAL,
        fair_entry_low REAL, fair_entry_high REAL, capital_efficiency_score REAL,
        date_added TEXT, is_new INTEGER DEFAULT 0, notes TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS master_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
        date_analyzed TEXT, verdict TEXT, notes TEXT DEFAULT '',
        next_review TEXT DEFAULT 'Trigger-phrase governed')""")
    c.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, price REAL, fetched_at TEXT)""")
    conn.commit()
    conn.close()

def is_seeded():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM buy_list")
    n = c.fetchone()[0]
    conn.close()
    return n > 0

def seed_v54_clean():
    conn = get_conn()
    c = conn.cursor()
    buy_data = [
        ("GTLB", 25.98, 40, 60, "Pending", "May 11, 2026", 0),
        ("NKE",  44.14, 50, 70, "Pending", "May 11, 2026", 1),
        ("CRM",  181.82, 45, 60, "Pending", "May 11, 2026", 0),
        ("ADBE", 247.36, 50, 70, "Pending", "May 11, 2026", 0),
    ]
    for ticker, price, ul, uh, inst, dt, is_new in buy_data:
        score = round((ul + uh) / 2 / price, 2)
        c.execute("""INSERT OR IGNORE INTO buy_list
            (ticker, current_price, upside_low, upside_high, capital_efficiency_score,
             institutional_money, date_added, is_new) VALUES (?,?,?,?,?,?,?,?)""",
            (ticker, price, ul, uh, score, inst, dt, is_new))
    hold_data = [
        ("GFI",   44.86, 35, 45, 28,  33,  "May 11, 2026", 0),
        ("HALO",  66.41, 45, 55, 52,  58,  "May 11, 2026", 0),
        ("TW",   108.81, 45, 55, 83,  92,  "May 11, 2026", 0),
        ("NOW",   92.50, 35, 50, 72,  80,  "May 11, 2026", 0),
        ("NEM",  120.67, 50, 55, 93,  100, "May 11, 2026", 0),
        ("NDAQ",  88.48, 50, 55, 78,  83,  "May 12, 2026", 0),
        ("SNOW", 154.06, 30, 45, 105, 115, "May 11, 2026", 0),
        ("AMZN", 271.82, 25, 40, 195, 210, "May 11, 2026", 0),
        ("INTU", 397.54, 30, 45, 320, 340, "May 11, 2026", 0),
        ("EQIX",1073.23, 30, 45, 700, 780, "May 12, 2026", 0),
        ("AME",  231.61, 35, 50, 155, 175, "May 12, 2026", 0),
        ("CRWD", 548.02, 35, 50, 310, 360, "May 12, 2026", 1),
    ]
    for ticker, price, ul, uh, fel, feh, dt, is_new in hold_data:
        fep_mid = (fel + feh) / 2
        score = round((ul + uh) / 2 / fep_mid, 2)
        c.execute("""INSERT OR IGNORE INTO hold_list
            (ticker, current_price, upside_low, upside_high, fair_entry_low, fair_entry_high,
             capital_efficiency_score, date_added, is_new) VALUES (?,?,?,?,?,?,?,?,?)""",
            (ticker, price, ul, uh, fel, feh, score, dt, is_new))

    # ── MASTER LOG — BUY (pre-Unified, no square mark) ──
    buy_log = [
        ("GTLB", "May 4, 2026", "✅ BUY"),
        ("ADBE", "May 4, 2026", "✅ BUY"),
        ("NKE",  "May 4, 2026", "✅ BUY"),
        ("CRM",  "May 4, 2026", "✅ BUY"),
    ]
    for ticker, dt, verdict in buy_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict) VALUES (?,?,?)", (ticker, dt, verdict))

    # ── MASTER LOG — HOLD ──
    hold_log = [
        ("AMZN", "May 4, 2026",  "⚠️ HOLD"),
        ("INTU", "May 4, 2026",  "⚠️ HOLD"),
        ("NOW",  "May 4, 2026",  "⚠️ HOLD"),
        ("SNOW", "May 4, 2026",  "⚠️ HOLD"),
        ("HALO", "May 5, 2026",  "⚠️🟨 HOLD"),
        ("GFI",  "May 5, 2026",  "⚠️🟨 HOLD"),
        ("TW",   "May 5, 2026",  "⚠️🟨 HOLD"),
        ("NEM",  "May 11, 2026", "⚠️🟨 HOLD"),
        ("NDAQ", "May 12, 2026", "⚠️🟨 HOLD"),
        ("EQIX", "May 12, 2026", "⚠️🟨 HOLD"),
        ("AME",  "May 12, 2026", "⚠️🟨 HOLD"),
        ("CRWD", "May 12, 2026", "⚠️🟨 HOLD"),
    ]
    for ticker, dt, verdict in hold_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict) VALUES (?,?,?)", (ticker, dt, verdict))

    # ── MASTER LOG — HARD PASS ──
    hard_pass_log = [
        ("CNXC",  "May 4, 2026",  "🚫 HARD PASS"),
        ("G",     "May 4, 2026",  "🚫 HARD PASS"),
        ("EPAM",  "May 4, 2026",  "🚫 HARD PASS"),
        ("SAIC",  "May 4, 2026",  "🚫 HARD PASS"),
        ("CTSH",  "May 4, 2026",  "🚫 HARD PASS"),
        ("GIB",   "May 4, 2026",  "🚫 HARD PASS"),
        ("DOX",   "May 4, 2026",  "🚫 HARD PASS"),
        ("CRUS",  "May 11, 2026", "🚫🟥 HARD PASS"),
        ("CTRA",  "May 11, 2026", "🚫🟥 HARD PASS"),
        ("BRKB",  "May 11, 2026", "🚫🟥 HARD PASS"),
        ("PK",    "May 11, 2026", "🚫🟥 HARD PASS"),
        ("VNO",   "May 11, 2026", "🚫🟥 HARD PASS"),
        ("ROCK",  "May 11, 2026", "🚫🟥 HARD PASS"),
        ("PDD",   "May 11, 2026", "🚫🟥 HARD PASS"),
        ("GNL",   "May 11, 2026", "🚫🟥 HARD PASS"),
        ("PEB",   "May 11, 2026", "🚫🟥 HARD PASS"),
        ("EQNR",  "May 11, 2026", "🚫🟥 HARD PASS"),
        ("CBT",   "May 11, 2026", "🚫🟥 HARD PASS"),
        ("WHD",   "May 11, 2026", "🚫🟥 HARD PASS"),
        ("HNNA",  "May 11, 2026", "🚫🟥 HARD PASS"),
        ("XOM",   "May 12, 2026", "🚫🟥 HARD PASS"),
        ("INTC",  "May 12, 2026", "🚫🟥 HARD PASS"),
        ("SRI",   "May 12, 2026", "🚫🟥 HARD PASS"),
        ("VNOM",  "May 12, 2026", "🚫🟥 HARD PASS"),
        ("MBLY",  "May 12, 2026", "🚫🟥 HARD PASS"),
        ("LYFT",  "May 12, 2026", "🚫🟥 HARD PASS"),
        ("FANUY", "May 12, 2026", "🚫🟥 HARD PASS"),
        ("ODFL",  "May 12, 2026", "🚫🟥 HARD PASS"),
        ("MLM",   "May 12, 2026", "🚫🟥 HARD PASS"),
        ("POOL",  "May 12, 2026", "🚫🟥 HARD PASS"),
        ("TTC",   "May 12, 2026", "🚫🟥 HARD PASS"),
        ("CSU",   "May 12, 2026", "🚫🟥 HARD PASS"),
        ("NVR",   "May 12, 2026", "🚫🟥 HARD PASS"),
        ("EXPD",  "May 12, 2026", "🚫🟥 HARD PASS"),
    ]
    for ticker, dt, verdict in hard_pass_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict) VALUES (?,?,?)", (ticker, dt, verdict))

    # ── MASTER LOG — PASS ──
    pass_log = [
        ("CSWI",  "May 4, 2026",  "❌ PASS"),
        ("TRU",   "May 4, 2026",  "❌ PASS"),
        ("FIS",   "May 4, 2026",  "❌ PASS"),
        ("MSFT",  "May 4, 2026",  "❌ PASS"),
        ("CRWV",  "May 4, 2026",  "❌ PASS"),
        ("PANW",  "May 4, 2026",  "❌ PASS"),
        ("SOFI",  "May 4, 2026",  "❌ PASS"),
        ("PLTR",  "May 4, 2026",  "❌ PASS"),
        ("DDOG",  "May 4, 2026",  "❌ PASS"),
        ("COST",  "May 4, 2026",  "❌ PASS"),
        ("MCD",   "May 4, 2026",  "❌ PASS"),
        ("HSY",   "May 4, 2026",  "❌ PASS"),
        ("CL",    "May 4, 2026",  "❌ PASS"),
        ("AXP",   "May 4, 2026",  "❌ PASS"),
        ("PG",    "May 4, 2026",  "❌ PASS"),
        ("JNJ",   "May 4, 2026",  "❌ PASS"),
        ("PEP",   "May 4, 2026",  "❌ PASS"),
        ("WM",    "May 4, 2026",  "❌ PASS"),
        ("MNST",  "May 4, 2026",  "❌ PASS"),
        ("AZO",   "May 4, 2026",  "❌ PASS"),
        ("HD",    "May 4, 2026",  "❌ PASS"),
        ("ROST",  "May 4, 2026",  "❌ PASS"),
        ("LULU",  "May 4, 2026",  "❌ PASS"),
        ("BKNG",  "May 4, 2026",  "❌ PASS"),
        ("SBUX",  "May 4, 2026",  "❌ PASS"),
        ("CMG",   "May 4, 2026",  "❌ PASS"),
        ("CPRT",  "May 4, 2026",  "❌ PASS"),
        ("FAST",  "May 4, 2026",  "❌ PASS"),
        ("CTAS",  "May 4, 2026",  "❌ PASS"),
        ("ITW",   "May 4, 2026",  "❌ PASS"),
        ("ROK",   "May 4, 2026",  "❌ PASS"),
        ("GEV",   "May 4, 2026",  "❌ PASS"),
        ("KEYS",  "May 4, 2026",  "❌ PASS"),
        ("VRT",   "May 4, 2026",  "❌ PASS"),
        ("LMT",   "May 4, 2026",  "❌ PASS"),
        ("HON",   "May 4, 2026",  "❌ PASS"),
        ("TXN",   "May 4, 2026",  "❌ PASS"),
        ("AMAT",  "May 4, 2026",  "❌ PASS"),
        ("DIS",   "May 4, 2026",  "❌ PASS"),
        ("VST",   "May 4, 2026",  "❌ PASS"),
        ("DVN",   "May 4, 2026",  "❌ PASS"),
        ("APA",   "May 4, 2026",  "❌ PASS"),
        ("ET",    "May 4, 2026",  "❌ PASS"),
        ("CEG",   "May 4, 2026",  "❌ PASS"),
        ("NEE",   "May 4, 2026",  "❌ PASS"),
        ("NVT",   "May 4, 2026",  "❌ PASS"),
        ("ORA",   "May 4, 2026",  "❌ PASS"),
        ("FSLR",  "May 4, 2026",  "❌ PASS"),
        ("LNG",   "May 4, 2026",  "❌ PASS"),
        ("CVX",   "May 4, 2026",  "❌ PASS"),
        ("AM",    "May 14, 2026", "❌🟥 PASS"),
        ("CHWY",  "May 14, 2026", "❌🟥 PASS"),
        ("FLNG",  "May 4, 2026",  "❌ PASS"),
        ("CRSP",  "May 4, 2026",  "❌ PASS"),
        ("LZAGY", "May 4, 2026",  "❌ PASS"),
        ("NTLA",  "May 4, 2026",  "❌ PASS"),
        ("TWST",  "May 4, 2026",  "❌ PASS"),
        ("SEV",   "May 4, 2026",  "❌ PASS"),
        ("GRAIL", "May 4, 2026",  "❌ PASS"),
        ("GH",    "May 4, 2026",  "❌ PASS"),
        ("ASML",  "May 4, 2026",  "❌ PASS"),
        ("KGC",   "May 4, 2026",  "❌ PASS"),
        ("UBER",  "May 4, 2026",  "❌ PASS"),
        ("CERT",  "May 4, 2026",  "❌ PASS"),
        ("RKLB",  "May 4, 2026",  "❌ PASS"),
        ("RGTI",  "May 4, 2026",  "❌ PASS"),
        ("LLY",   "May 4, 2026",  "❌ PASS"),
        ("TMO",   "May 4, 2026",  "❌ PASS"),
        ("DHR",   "May 4, 2026",  "❌ PASS"),
        ("ISRG",  "May 4, 2026",  "❌ PASS"),
        ("SPGI",  "May 4, 2026",  "❌ PASS"),
        ("MCO",   "May 4, 2026",  "❌ PASS"),
        ("CSGP",  "May 4, 2026",  "❌ PASS"),
        ("TRUE",  "May 5, 2026",  "❌🟥 PASS"),
        ("EFX",   "May 5, 2026",  "❌🟥 PASS"),
        ("IT",    "May 5, 2026",  "❌🟥 PASS"),
        ("ROP",   "May 5, 2026",  "❌🟥 PASS"),
        ("MSCI",  "May 5, 2026",  "❌🟥 PASS"),
        ("BR",    "May 5, 2026",  "❌🟥 PASS"),
        ("FDS",   "May 5, 2026",  "❌🟥 PASS"),
        ("RSG",   "May 5, 2026",  "❌🟥 PASS"),
        ("TYL",   "May 5, 2026",  "❌🟥 PASS"),
        ("SSNC",  "May 5, 2026",  "❌🟥 PASS"),
        ("LDOS",  "May 5, 2026",  "❌🟥 PASS"),
        ("J",     "May 5, 2026",  "❌🟥 PASS"),
        ("BAH",   "May 5, 2026",  "❌🟥 PASS"),
        ("CACI",  "May 5, 2026",  "❌🟥 PASS"),
        ("EXPO",  "May 5, 2026",  "❌🟥 PASS"),
        ("FCN",   "May 5, 2026",  "❌🟥 PASS"),
        ("MORN",  "May 5, 2026",  "❌🟥 PASS"),
        ("JKHY",  "May 5, 2026",  "❌🟥 PASS"),
        ("CDW",   "May 5, 2026",  "❌🟥 PASS"),
        ("PAYX",  "May 5, 2026",  "❌🟥 PASS"),
        ("LUNR",  "May 5, 2026",  "❌🟥 PASS"),
        ("BBAI",  "May 5, 2026",  "❌🟥 PASS"),
        ("OMAB",  "May 5, 2026",  "❌🟥 PASS"),
        ("LOPE",  "May 5, 2026",  "❌🟥 PASS"),
        ("IDCC",  "May 11, 2026", "❌🟥 PASS"),
        ("FCFS",  "May 11, 2026", "❌🟥 PASS"),
        ("BRO",   "May 11, 2026", "❌🟥 PASS"),
        ("PRPO",  "May 11, 2026", "❌🟥 PASS"),
        ("CCEL",  "May 11, 2026", "❌🟥 PASS"),
        ("FRPT",  "May 11, 2026", "❌🟥 PASS"),
        ("OPFI",  "May 11, 2026", "❌🟥 PASS"),
        ("VEON",  "May 11, 2026", "❌🟥 PASS"),
        ("ENS",   "May 11, 2026", "❌🟥 PASS"),
        ("NUTX",  "May 11, 2026", "❌🟥 PASS"),
        ("WRB",   "May 12, 2026", "❌🟥 PASS"),
        ("ABBNY", "May 12, 2026", "❌🟥 PASS"),
        ("MRVL",  "May 12, 2026", "❌🟥 PASS"),
        ("OR",    "May 12, 2026", "❌🟥 PASS"),
        ("ROKU",  "May 12, 2026", "❌🟥 PASS"),
        ("CART",  "May 12, 2026", "❌🟥 PASS"),
        ("ALVO",  "May 12, 2026", "❌🟥 PASS"),
        ("TTWO",  "May 12, 2026", "❌🟥 PASS"),
        ("MSI",   "May 12, 2026", "❌🟥 PASS"),
        ("ZBRA",  "May 12, 2026", "❌🟥 PASS"),
        ("AJG",   "May 12, 2026", "❌🟥 PASS"),
        ("HEI",   "May 12, 2026", "❌🟥 PASS"),
        ("IDXX",  "May 12, 2026", "❌🟥 PASS"),
        ("WCN",   "May 12, 2026", "❌🟥 PASS"),
        ("BFAM",  "May 12, 2026", "❌🟥 PASS"),
        ("CLH",   "May 12, 2026", "❌🟥 PASS"),
        ("WSO",   "May 12, 2026", "❌🟥 PASS"),
        ("LII",   "May 12, 2026", "❌🟥 PASS"),
        ("CSL",   "May 12, 2026", "❌🟥 PASS"),
    ]
    for ticker, dt, verdict in pass_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict) VALUES (?,?,?)", (ticker, dt, verdict))

    conn.commit()
    conn.close()

# ── END OF CHUNK 1 — DO NOT PASTE ANYTHING BELOW THIS LINE YET ──
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
        df = pd.read_sql("SELECT * FROM master_log ORDER BY date_analyzed DESC, id DESC", conn)
    conn.close()
    return df

def lookup_ticker(ticker):
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT verdict, date_analyzed, notes FROM master_log WHERE ticker=? ORDER BY id DESC LIMIT 1", (ticker,))
    row = c.fetchone()
    conn.close()
    return row

def add_master_log(ticker, date_str, verdict, notes=""):
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM master_log WHERE ticker=? AND verdict=?", (ticker, verdict))
    existing = c.fetchone()
    if not existing:
        c.execute("INSERT INTO master_log (ticker, date_analyzed, verdict, notes) VALUES (?,?,?,?)",
                  (ticker, date_str, verdict, notes))
    conn.commit()
    conn.close()

def add_or_update_buy(ticker, price, ul, uh, inst, date_str, notes):
    ticker = ticker.upper().strip()
    score = round((ul + uh) / 2 / price, 2) if price > 0 else 0
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE buy_list SET is_new=0")
    c.execute("""INSERT INTO buy_list
        (ticker, current_price, upside_low, upside_high, capital_efficiency_score,
         institutional_money, date_added, is_new, notes)
        VALUES (?,?,?,?,?,?,?,1,?)
        ON CONFLICT(ticker) DO UPDATE SET
            current_price=excluded.current_price, upside_low=excluded.upside_low,
            upside_high=excluded.upside_high, capital_efficiency_score=excluded.capital_efficiency_score,
            institutional_money=excluded.institutional_money, date_added=excluded.date_added,
            is_new=1, notes=excluded.notes""",
        (ticker, price, ul, uh, score, inst, date_str, notes))
    conn.commit()
    conn.close()
    add_master_log(ticker, date_str, "BUY", notes)

def add_or_update_hold(ticker, price, ul, uh, fel, feh, date_str, notes):
    ticker = ticker.upper().strip()
    fep_mid = (fel + feh) / 2 if (fel + feh) > 0 else 1
    score = round((ul + uh) / 2 / fep_mid, 2)
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE hold_list SET is_new=0")
    c.execute("""INSERT INTO hold_list
        (ticker, current_price, upside_low, upside_high, fair_entry_low, fair_entry_high,
         capital_efficiency_score, date_added, is_new, notes)
        VALUES (?,?,?,?,?,?,?,?,1,?)
        ON CONFLICT(ticker) DO UPDATE SET
            current_price=excluded.current_price, upside_low=excluded.upside_low,
            upside_high=excluded.upside_high, fair_entry_low=excluded.fair_entry_low,
            fair_entry_high=excluded.fair_entry_high, capital_efficiency_score=excluded.capital_efficiency_score,
            date_added=excluded.date_added, is_new=1, notes=excluded.notes""",
        (ticker, price, ul, uh, fel, feh, score, date_str, notes))
    conn.commit()
    conn.close()
    add_master_log(ticker, date_str, "HOLD", notes)

def remove_from_buy(ticker):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM buy_list WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()

def remove_from_hold(ticker):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM hold_list WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()

def update_price_in_db(table, ticker, new_price, new_score):
    conn = get_conn()
    c = conn.cursor()
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
            info = yf.Ticker(t).fast_info
            price = round(float(info.last_price), 2)
            results[t] = price
        except Exception:
            results[t] = None
    return results

def run_market_data_update():
    buy_df = get_buy_list()
    hold_df = get_hold_list()
    all_tickers = list(buy_df["ticker"]) + list(hold_df["ticker"])
    if not YFINANCE_AVAILABLE:
        return None, "yfinance not installed."
    prices = fetch_prices_yfinance(all_tickers)
    today = date.today().strftime("%b %d, %Y")
    updated_buy = []
    for _, row in buy_df.iterrows():
        t = row["ticker"]
        new_price = prices.get(t)
        if new_price:
            mid_upside = (row["upside_low"] + row["upside_high"]) / 2
            new_score = round(mid_upside / new_price, 2)
            update_price_in_db("buy_list", t, new_price, new_score)
        updated_buy.append((t, row["current_price"], new_price))
    updated_hold = []
    for _, row in hold_df.iterrows():
        t = row["ticker"]
        new_price = prices.get(t)
        if new_price:
            fep_mid = (row["fair_entry_low"] + row["fair_entry_high"]) / 2
            mid_upside = (row["upside_low"] + row["upside_high"]) / 2
            new_score = round(mid_upside / fep_mid, 2) if fep_mid > 0 else row["capital_efficiency_score"]
            update_price_in_db("hold_list", t, new_price, new_score)
        updated_hold.append((t, row["current_price"], new_price))
    return {"buy": updated_buy, "hold": updated_hold, "timestamp": today}, None

def check_hard_triggers(df_buy, df_hold):
    flags = []
    conn = get_conn()
    c = conn.cursor()
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

init_db()
if not is_seeded():
    seed_v54_clean()

with st.sidebar:
    st.markdown("### 💙🦋 DREAM TEAM")
    st.markdown('<p class="mono" style="color:#8899aa;">Investment Analysis System</p>', unsafe_allow_html=True)
    st.markdown('<p class="mono" style="color:#555e6e; font-size:0.75rem;">V54 — Unified 7 Points</p>', unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("Navigate",
        ["Dashboard", "Buy List", "Hold List", "Master Log",
         "Ticker Lookup", "Add / Update", "Market Data Updates"],
        label_visibility="collapsed")
    st.markdown("---")
    buy_count = len(get_buy_list())
    hold_count = len(get_hold_list())
    log_count = len(get_master_log())
    st.markdown(f'<p class="mono" style="color:#3ddc84;">Buy: {buy_count}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#ffc947;">Hold: {hold_count}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#8899aa;">Log: {log_count}</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<p style="font-family:JetBrains Mono,monospace; color:#e8e4d9; font-size:0.82rem; font-weight:600; margin:0;">Fundamentals first. Always.</p>', unsafe_allow_html=True)
st.markdown('<p style="font-family:JetBrains Mono,monospace; color:#e8e4d9; font-size:0.82rem; font-weight:600; margin:0;">We are not desperate. We wait. 🐟</p>', unsafe_allow_html=True)

if page == "Dashboard":
    st.markdown('<div class="header-block"><h1>Investment Analysis System</h1><p class="mono" style="color:#8899aa;">Unified 7 Points Standards | V55 | Dream Team</p></div>', unsafe_allow_html=True)
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
            nm = " <- NEW" if row["is_new"] else ""
            st.markdown(f'<div class="metric-card" style="border-left:3px solid #3ddc84; padding:0.8rem 1rem;"><span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span><span style="color:#3ddc84;">{nm}</span> &nbsp;<span class="mono" style="color:#8899aa;">${row["current_price"]:.2f}</span><span style="float:right;" class="mono"><span style="color:#3ddc84;">{row["upside_low"]:.0f}-{row["upside_high"]:.0f}% upside</span> &nbsp;Score: <em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em></span></div>', unsafe_allow_html=True)
    with col_h:
        st.markdown("#### Hold List — Ranked by Efficiency")
        hold_df = get_hold_list()
        for _, row in hold_df.iterrows():
            nm = " <- NEW" if row["is_new"] else ""
            st.markdown(f'<div class="metric-card" style="border-left:3px solid #ffc947; padding:0.8rem 1rem;"><span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span><span style="color:#ffc947;">{nm}</span> &nbsp;<span class="mono" style="color:#8899aa;">${row["current_price"]:.2f}</span><span style="float:right;" class="mono"><span style="color:#ffc947;">Entry: ${row["fair_entry_low"]:.0f}-${row["fair_entry_high"]:.0f}</span> &nbsp;Score: <em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em></span></div>', unsafe_allow_html=True)

# ── END OF CHUNK 2 — DO NOT PASTE ANYTHING BELOW THIS LINE YET ──
elif page == "Buy List":
    st.markdown('<div class="header-block"><h1>Buy List</h1><p class="mono" style="color:#8899aa;">Ranked by Capital Efficiency Score (Upside% mid / Current Price)</p></div>', unsafe_allow_html=True)
    buy_df = get_buy_list()
    if buy_df.empty:
        st.info("No tickers in Buy List.")
    else:
        for _, row in buy_df.iterrows():
            nm = " <- NEW" if row["is_new"] else ""
            st.markdown(f'<div class="metric-card" style="border-left:3px solid #3ddc84;"><div style="display:flex; justify-content:space-between;"><div><span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1.15rem; color:#e8e4d9;">{row["ticker"]}</span><span style="color:#3ddc84;">{nm}</span> &nbsp;<span class="mono" style="color:#3ddc84;">BUY</span></div><div class="mono" style="color:#555e6e; font-size:0.78rem;">{row["date_added"]}</div></div><div style="margin-top:0.6rem; display:flex; gap:2rem; flex-wrap:wrap;"><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CURRENT PRICE</p><p class="mono" style="color:#e8e4d9; margin:0;">${row["current_price"]:.2f}</p></div><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">UPSIDE</p><p class="mono" style="color:#3ddc84; margin:0;">{row["upside_low"]:.0f}-{row["upside_high"]:.0f}%</p></div><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CE SCORE</p><p class="mono" style="color:#ffc947; margin:0; font-style:italic;">{row["capital_efficiency_score"]:.2f}</p></div><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">INSTITUTIONAL $</p><p class="mono" style="color:#e8e4d9; margin:0;">{row["institutional_money"]}</p></div></div></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="mono" style="color:#3ddc84;">Total: {len(buy_df)} tickers | Hard Trigger Flags: All Clear</p>', unsafe_allow_html=True)
        st.markdown("---")
        export_df = buy_df[["ticker","current_price","upside_low","upside_high","capital_efficiency_score","institutional_money","date_added"]].copy()
        export_df.columns = ["Ticker","Price","Up Low%","Up High%","CE Score","Institutional $","Date"]
        st.dataframe(export_df, use_container_width=True, hide_index=True)

elif page == "Hold List":
    st.markdown('<div class="header-block"><h1>Hold List</h1><p class="mono" style="color:#8899aa;">Ranked by Capital Efficiency Score (Upside% mid / Fair Entry Price mid)</p></div>', unsafe_allow_html=True)
    hold_df = get_hold_list()
    if hold_df.empty:
        st.info("No tickers in Hold List.")
    else:
        for _, row in hold_df.iterrows():
            nm = " <- NEW" if row["is_new"] else ""
            st.markdown(f'<div class="metric-card" style="border-left:3px solid #ffc947;"><div style="display:flex; justify-content:space-between;"><div><span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1.15rem; color:#e8e4d9;">{row["ticker"]}</span><span style="color:#ffc947;">{nm}</span> &nbsp;<span class="mono" style="color:#ffc947;">HOLD</span></div><div class="mono" style="color:#555e6e; font-size:0.78rem;">{row["date_added"]}</div></div><div style="margin-top:0.6rem; display:flex; gap:2rem; flex-wrap:wrap;"><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CURRENT PRICE</p><p class="mono" style="color:#e8e4d9; margin:0;">${row["current_price"]:.2f}</p></div><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">UPSIDE</p><p class="mono" style="color:#ffc947; margin:0;">{row["upside_low"]:.0f}-{row["upside_high"]:.0f}%</p></div><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">FAIR ENTRY</p><p class="mono" style="color:#ffc947; margin:0;">${row["fair_entry_low"]:.0f}-${row["fair_entry_high"]:.0f}</p></div><div><p class="mono" style="color:#8899aa; margin:0; font-size:0.72rem;">CE SCORE</p><p class="mono" style="color:#ffc947; margin:0; font-style:italic;">{row["capital_efficiency_score"]:.2f}</p></div></div></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="mono" style="color:#ffc947;">Total: {len(hold_df)} tickers | Hard Trigger Flags: All Clear</p>', unsafe_allow_html=True)
        st.markdown("---")
        export_df = hold_df[["ticker","current_price","upside_low","upside_high","fair_entry_low","fair_entry_high","capital_efficiency_score","date_added"]].copy()
        export_df.columns = ["Ticker","Price","Up Low%","Up High%","Entry Low","Entry High","CE Score","Date"]
        st.dataframe(export_df, use_container_width=True, hide_index=True)

elif page == "Master Log":
    st.markdown('<div class="header-block"><h1>Master Consolidated Log</h1><p class="mono" style="color:#8899aa;">Cross-reference every ticker here first. All sessions. All verdicts.</p></div>', unsafe_allow_html=True)

    # ── styling helper ──
    def verdict_style(verdict):
        has_square = "🟥" in verdict or "🟨" in verdict
        if "BUY" in verdict:
            if has_square:
                return "#3ddc84", "1px solid #3ddc84", "0d2b1a"
            return "#1a6640", "1px solid #1a6640", "#061a0e"
        elif "HARD PASS" in verdict:
            if has_square:
                return "#cc3333", "1px solid #cc3333", "#1a0a0a"
            return "#5c1a1a", "1px solid #3d1111", "#0f0606"
        elif "HOLD" in verdict:
            if has_square:
                return "#ffc947", "1px solid #ffc947", "#2b2200"
            return "#7a6020", "1px solid #4d3c00", "#161000"
        elif "PASS" in verdict:
            if has_square:
                return "#ff6b6b", "1px solid #ff6b6b", "#2b0d0d"
            return "#7a3333", "1px solid #4d1f1f", "#150808"
        return "#8899aa", "1px solid #2a3344", "#161b24"

    col_filter, col_search = st.columns([2, 3])
    with col_filter:
        verdict_filter = st.selectbox("Filter by Verdict", [
            "ALL",
            "✅ BUY",
            "⚠️ HOLD", "⚠️🟨 HOLD",
            "🚫 HARD PASS", "🚫🟥 HARD PASS",
            "❌ PASS", "❌🟥 PASS"
        ])
    with col_search:
        search_term = st.text_input("Search Ticker", placeholder="e.g. GTLB")

    all_log = get_master_log()
    log_df = all_log if verdict_filter == "ALL" else all_log[all_log["verdict"] == verdict_filter]
    if search_term:
        log_df = log_df[log_df["ticker"].str.upper().str.contains(search_term.upper())]

    buy_n  = len(all_log[all_log["verdict"].str.contains("BUY",  na=False)])
    hold_n = len(all_log[all_log["verdict"].str.contains("HOLD", na=False)])
    hp_n   = len(all_log[all_log["verdict"].str.contains("HARD", na=False)])
    pass_n = len(all_log[all_log["verdict"].str.contains("PASS", na=False) & ~all_log["verdict"].str.contains("HARD", na=False)])

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#3ddc84; margin:0;">BUY: {buy_n}</p></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#ffc947; margin:0;">HOLD: {hold_n}</p></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#ff6b6b; margin:0;">PASS: {pass_n}</p></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card"><p class="mono" style="color:#cc3333; margin:0;">HARD PASS: {hp_n}</p></div>', unsafe_allow_html=True)

    st.markdown(f'<p class="mono" style="color:#8899aa; font-size:0.8rem;">Showing {len(log_df)} records</p>', unsafe_allow_html=True)

    if log_df.empty:
        st.info("No records found.")
    else:
        for _, row in log_df.iterrows():
            color, border, bg = verdict_style(row["verdict"])
            st.markdown(
                f'<div style="background:#{bg}; border-left:3px solid {color}; border-top:{border}; '
                f'border-right:{border}; border-bottom:{border}; border-radius:4px; '
                f'padding:0.6rem 1rem; margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">'
                f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; color:{color}; font-size:0.95rem;">{row["ticker"]}</span>'
                f'<span style="font-family:JetBrains Mono,monospace; color:{color}; font-size:0.85rem;">{row["verdict"]}</span>'
                f'<span style="font-family:JetBrains Mono,monospace; color:#8899aa; font-size:0.78rem;">{row["date_analyzed"]}</span>'
                f'<span style="font-family:JetBrains Mono,monospace; color:#555e6e; font-size:0.72rem;">{row["next_review"]}</span>'
                f'</div>',
                unsafe_allow_html=True)

elif page == "Ticker Lookup":
    st.markdown('<div class="header-block"><h1>Ticker Cross-Reference</h1><p class="mono" style="color:#8899aa;">Check Master Consolidated Log instantly before any analysis.</p></div>', unsafe_allow_html=True)
    ticker_input = st.text_input("Enter Ticker Symbol", placeholder="e.g. CRWD, NKE, MSFT").upper().strip()
    if ticker_input:
        result = lookup_ticker(ticker_input)
        if result:
            verdict, dt, notes = result
            colors = {"BUY": "#3ddc84", "HOLD": "#ffc947", "PASS": "#ff6b6b", "HARD_PASS": "#cc3333"}
            labels = {"BUY": "ALREADY ON BUY LIST", "HOLD": "ALREADY ON HOLD LIST", "PASS": "PREVIOUSLY PASSED", "HARD_PASS": "HARD PASS — PERMANENT"}
            actions = {"BUY": "Already approved and active. Report position + skip.", "HOLD": "Already analyzed, waiting for price trigger. Report + skip.", "PASS": "Did not meet standards. Re-evaluation Triggers quarterly.", "HARD_PASS": "Permanent exclusion. BPO/AI-vulnerable or full cyclical fail."}
            col = colors.get(verdict, "#8899aa")
            lbl = labels.get(verdict, verdict)
            act = actions.get(verdict, "")
            st.markdown(f'<div class="metric-card" style="border-left:4px solid {col};"><h3 style="color:{col}; font-family:JetBrains Mono,monospace;">{ticker_input} — {lbl}</h3><p class="mono">Date analyzed: {dt}</p><p class="mono" style="color:{col};">{act}</p>{("<p class=mono style=color:#8899aa;>" + notes + "</p>") if notes else ""}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-card" style="border-left:4px solid #2a7fff;"><h3 style="color:#2a7fff; font-family:JetBrains Mono,monospace;">{ticker_input} — NOT FOUND IN LOG</h3><p class="mono">Proceed with full Unified 7 Points deep-dive analysis.</p><p class="mono" style="color:#8899aa;">After analysis: add verdict via Add / Update page.</p></div>', unsafe_allow_html=True)

elif page == "Add / Update":
    st.markdown('<div class="header-block"><h1>Add / Update Ticker</h1><p class="mono" style="color:#8899aa;">HANDOFF line — auto-logs to correct table with Capital Efficiency Score.</p></div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["Add to Buy List", "Add to Hold List", "Log PASS / HARD PASS", "Remove Ticker"])
    with tab1:
        st.markdown("#### Add / Update — Buy List")
        with st.form("add_buy_form"):
            col1, col2 = st.columns(2)
            with col1:
                b_ticker = st.text_input("Ticker Symbol *").upper().strip()
                b_price = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
            with col2:
                b_ul = st.number_input("Upside Low (%)", min_value=0.0, value=50.0, step=1.0)
                b_uh = st.number_input("Upside High (%)", min_value=0.0, value=70.0, step=1.0)
            b_inst = st.selectbox("Institutional Money / Tape Reading",
                ["Pending", "Strong absorption / aggressive buying",
                 "Neutral / choppy flow", "Distribution / selling pressure"])
            b_notes = st.text_area("Notes (optional)")
            b_date = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            if st.form_submit_button("Add to Buy List"):
                if not b_ticker:
                    st.error("Ticker is required.")
                elif b_price <= 0:
                    st.error("Price must be greater than 0.")
                else:
                    add_or_update_buy(b_ticker, b_price, b_ul, b_uh, b_inst, b_date, b_notes)
                    score = round((b_ul + b_uh) / 2 / b_price, 2)
                    st.success(f"{b_ticker} added to Buy List — CE Score: {score:.2f}")
    with tab2:
        st.markdown("#### Add / Update — Hold List")
        with st.form("add_hold_form"):
            col1, col2 = st.columns(2)
            with col1:
                h_ticker = st.text_input("Ticker Symbol *").upper().strip()
                h_price = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
                h_ul = st.number_input("Upside Low (%)", min_value=0.0, value=35.0, step=1.0)
                h_uh = st.number_input("Upside High (%)", min_value=0.0, value=50.0, step=1.0)
            with col2:
                h_fel = st.number_input("Fair Entry Price Low ($) *", min_value=0.01, value=80.00, step=0.01)
                h_feh = st.number_input("Fair Entry Price High ($) *", min_value=0.01, value=90.00, step=0.01)
            h_notes = st.text_area("Notes (optional)")
            h_date = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            if st.form_submit_button("Add to Hold List"):
                if not h_ticker:
                    st.error("Ticker is required.")
                else:
                    add_or_update_hold(h_ticker, h_price, h_ul, h_uh, h_fel, h_feh, h_date, h_notes)
                    fep_mid = (h_fel + h_feh) / 2
                    score = round((h_ul + h_uh) / 2 / fep_mid, 2)
                    st.success(f"{h_ticker} added to Hold List — CE Score: {score:.2f} — Entry: ${h_fel:.0f}-${h_feh:.0f}")
    with tab3:
        st.markdown("#### Log PASS or HARD PASS")
        with st.form("add_pass_form"):
            p_ticker = st.text_input("Ticker Symbol *").upper().strip()
            p_verdict = st.radio("Verdict", ["PASS", "HARD_PASS"])
            p_notes = st.text_area("Notes / reason")
            p_date = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            if st.form_submit_button("Log to Master Consolidated Log"):
                if not p_ticker:
                    st.error("Ticker is required.")
                else:
                    add_master_log(p_ticker, p_date, p_verdict, p_notes)
                    st.success(f"{p_ticker} added — {p_date} — {'HARD PASS' if p_verdict == 'HARD_PASS' else 'PASS'}")
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
    st.markdown('<div class="header-block"><h1>Market Data Updates</h1><p class="mono" style="color:#8899aa;">Refreshes prices, recalculates CE Scores, checks Hard Trigger Flags.</p></div>', unsafe_allow_html=True)
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
                        delta = new - old
                        color = "#3ddc84" if delta >= 0 else "#ff6b6b"
                        delta_str = f"+${delta:.2f}" if delta >= 0 else f"-${abs(delta):.2f}"
                        st.markdown(f'<p class="mono"><strong>{t}</strong>: ${old:.2f} to <span style="color:{color};">${new:.2f} ({delta_str})</span></p>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<p class="mono" style="color:#8899aa;"><strong>{t}</strong>: unavailable</p>', unsafe_allow_html=True)
            with col2:
                st.markdown("#### Hold List Updates")
                for t, old, new in result["hold"]:
                    if new:
                        delta = new - old
                        color = "#3ddc84" if delta >= 0 else "#ff6b6b"
                        delta_str = f"+${delta:.2f}" if delta >= 0 else f"-${abs(delta):.2f}"
                        st.markdown(f'<p class="mono"><strong>{t}</strong>: ${old:.2f} to <span style="color:{color};">${new:.2f} ({delta_str})</span></p>', unsafe_allow_html=True)
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
                    c = conn.cursor()
                    c.execute("SELECT upside_low, upside_high FROM buy_list WHERE ticker=?", (mp_ticker,))
                    row = c.fetchone()
                    conn.close()
                    if row:
                        new_score = round((row[0] + row[1]) / 2 / mp_price, 2)
                        update_price_in_db("buy_list", mp_ticker, mp_price, new_score)
                        st.success(f"{mp_ticker} updated to ${mp_price:.2f} — CE Score: {new_score:.2f}")
                    else:
                        st.error(f"{mp_ticker} not found in Buy List.")
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT upside_low, upside_high, fair_entry_low, fair_entry_high FROM hold_list WHERE ticker=?", (mp_ticker,))
                    row = c.fetchone()
                    conn.close()
                    if row:
                        fep_mid = (row[2] + row[3]) / 2
                        new_score = round((row[0] + row[1]) / 2 / fep_mid, 2) if fep_mid > 0 else 0
                        update_price_in_db("hold_list", mp_ticker, mp_price, new_score)
                        st.success(f"{mp_ticker} updated to ${mp_price:.2f} — CE Score: {new_score:.2f}")
                    else:
                        st.error(f"{mp_ticker} not found in Hold List.")

# ── END OF CHUNK 3 — FILE COMPLETE ──

