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

# ── BORDER STYLE HELPERS ──────────────────────────────────────────────────────

def dash_card(color, label, value, sub):
    """Dashboard counter cards: 7px left border, bright category color."""
    return (
        f'<div class="metric-card" style="border-left: 7px solid {color};">'
        f'<p class="mono" style="color:#8899aa; margin:0; font-size:0.75rem;">{label}</p>'
        f'<h2 style="color:{color}; margin:0; font-family:JetBrains Mono,monospace;">{value}</h2>'
        f'<p class="mono" style="color:#555e6e; margin:0; font-size:0.75rem;">{sub}</p>'
        f'</div>'
    )

def log_counter_card(color, text):
    """Master Log counter cards: full frame 2px + 7px left = dimensional effect."""
    return (
        f'<div class="metric-card" style="border: 2px solid {color}; border-left: 7px solid {color};">'
        f'<p class="mono" style="color:{color}; margin:0;">{text}</p>'
        f'</div>'
    )

def log_record_row(is_unified, border_color, ticker_color, date_color, row_id, ticker, date_str, badge_html, next_review):
    """Master Log show-records rows.
    Post-Unified: full frame 2px + 7px left, full brightness color.
    Pre-Unified:  7px left only, muted color.
    """
    if is_unified:
        border_style = f"border: 2px solid {border_color}; border-left: 7px solid {border_color};"
    else:
        border_style = f"border-left: 7px solid {border_color};"
    return (
        f'<div class="metric-card" style="{border_style} padding: 0.7rem 1.2rem; margin-bottom: 0.4rem;">'
        f'<div style="display:flex; align-items:center; gap:1.2rem; flex-wrap:wrap;">'
        f'<span class="mono" style="color:#555e6e; font-size:0.72rem; min-width:2rem;">#{row_id}</span>'
        f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1rem; color:{ticker_color}; min-width:4rem;">{ticker}</span>'
        f'{badge_html}'
        f'<span class="mono" style="color:{date_color};">{date_str}</span>'
        f'<span class="mono" style="color:#555e6e; font-size:0.78rem; margin-left:auto;">{next_review}</span>'
        f'</div>'
        f'</div>'
    )

def verdict_badge_html(verdict, is_unified):
    """Full brightness + square mark for post-Unified; muted styling for pre-Unified."""
    label = {"BUY": "BUY", "HOLD": "HOLD", "PASS": "PASS", "HARD_PASS": "HARD PASS"}
    if is_unified:
        css = {"BUY": "buy-badge", "HOLD": "hold-badge", "PASS": "pass-badge", "HARD_PASS": "hardpass-badge"}
        cls = css.get(verdict, "pass-badge")
        return f'<span class="{cls}">■ {label.get(verdict, verdict)}</span>'
    else:
        muted = {
            "BUY":       "background:#0a1a0f; color:#1a4a2a; border:1px solid #0f2a18;",
            "HOLD":      "background:#1a1200; color:#3a2e00; border:1px solid #2a1e00;",
            "PASS":      "background:#1a0808; color:#3a1010; border:1px solid #2a0808;",
            "HARD_PASS": "background:#110606; color:#2a0a0a; border:1px solid #1f0606;",
        }
        style = muted.get(verdict, muted["PASS"])
        return f'<span style="padding:2px 8px; border-radius:3px; font-family:JetBrains Mono,monospace; font-size:0.78rem; font-weight:700; {style}">{label.get(verdict, verdict)}</span>'

# ─────────────────────────────────────────────────────────────────────────────

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
        next_review TEXT DEFAULT 'Trigger-phrase governed',
        is_unified INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, price REAL, fetched_at TEXT)""")
    try:
        c.execute("ALTER TABLE master_log ADD COLUMN is_unified INTEGER DEFAULT 1")
    except Exception:
        pass
    conn.commit()
    conn.close()

def is_seeded():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM buy_list")
    n = c.fetchone()[0]
    conn.close()
    return n > 0

def seed_v55():
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
    for ticker, dt in [("GTLB","May 4, 2026"),("ADBE","May 4, 2026"),("NKE","May 4, 2026"),("CRM","May 4, 2026")]:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict,is_unified) VALUES (?,?,'BUY',1)", (ticker, dt))
    hold_log = [
        ("AMZN","May 4, 2026",0),("INTU","May 4, 2026",0),("NOW","May 4, 2026",0),("SNOW","May 4, 2026",0),
        ("HALO","May 5, 2026",1),("GFI","May 5, 2026",1),("TW","May 5, 2026",1),("NEM","May 11, 2026",1),
        ("NDAQ","May 12, 2026",1),("EQIX","May 12, 2026",1),("AME","May 12, 2026",1),("CRWD","May 12, 2026",1),
    ]
    for ticker, dt, iu in hold_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict,is_unified) VALUES (?,?,'HOLD',?)", (ticker, dt, iu))
    hard_pass_log = [
        ("CNXC","May 4, 2026",0),("G","May 4, 2026",0),("EPAM","May 4, 2026",0),("SAIC","May 4, 2026",0),
        ("CTSH","May 4, 2026",0),("GIB","May 4, 2026",0),("DOX","May 4, 2026",0),("XOM","May 12, 2026",1),
        ("INTC","May 12, 2026",1),("CRUS","May 11, 2026",1),("CTRA","May 11, 2026",1),("BRKB","May 11, 2026",1),
        ("PK","May 11, 2026",1),("VNO","May 11, 2026",1),("ROCK","May 11, 2026",1),("PDD","May 11, 2026",1),
        ("GNL","May 11, 2026",1),("PEB","May 11, 2026",1),("EQNR","May 11, 2026",1),("CBT","May 11, 2026",1),
        ("WHD","May 11, 2026",1),("SRI","May 12, 2026",1),("VNOM","May 12, 2026",1),("MBLY","May 12, 2026",1),
        ("LYFT","May 12, 2026",1),("FANUY","May 12, 2026",1),("HNNA","May 11, 2026",1),("ODFL","May 12, 2026",1),
        ("MLM","May 12, 2026",1),("POOL","May 12, 2026",1),("TTC","May 12, 2026",1),("CSU","May 12, 2026",1),
        ("NVR","May 12, 2026",1),("EXPD","May 12, 2026",1),
    ]
    for ticker, dt, iu in hard_pass_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict,is_unified) VALUES (?,?,'HARD_PASS',?)", (ticker, dt, iu))
    pass_log = [
        ("CSWI","May 4, 2026",0),("TRU","May 4, 2026",0),("FIS","May 4, 2026",0),("MSFT","May 4, 2026",0),
        ("CRWV","May 4, 2026",0),("PANW","May 4, 2026",0),("SOFI","May 4, 2026",0),("PLTR","May 4, 2026",0),
        ("DDOG","May 4, 2026",0),("COST","May 4, 2026",0),("MCD","May 4, 2026",0),("HSY","May 4, 2026",0),
        ("CL","May 4, 2026",0),("AXP","May 4, 2026",0),("PG","May 4, 2026",0),("JNJ","May 4, 2026",0),
        ("PEP","May 4, 2026",0),("WM","May 4, 2026",0),("MNST","May 4, 2026",0),("AZO","May 4, 2026",0),
        ("HD","May 4, 2026",0),("ROST","May 4, 2026",0),("LULU","May 4, 2026",0),("BKNG","May 4, 2026",0),
        ("SBUX","May 4, 2026",0),("CMG","May 4, 2026",0),("CPRT","May 4, 2026",0),("FAST","May 4, 2026",0),
        ("CTAS","May 4, 2026",0),("CHWY","May 4, 2026",0),("ITW","May 4, 2026",0),("ROK","May 4, 2026",0),
        ("GEV","May 4, 2026",0),("KEYS","May 4, 2026",0),("VRT","May 4, 2026",0),("LMT","May 4, 2026",0),
        ("HON","May 4, 2026",0),("TXN","May 4, 2026",0),("AMAT","May 4, 2026",0),("DIS","May 4, 2026",0),
        ("VST","May 4, 2026",0),("DVN","May 4, 2026",0),("APA","May 4, 2026",0),("ET","May 4, 2026",0),
        ("CEG","May 4, 2026",0),("NEE","May 4, 2026",0),("NVT","May 4, 2026",0),("ORA","May 4, 2026",0),
        ("FSLR","May 4, 2026",0),("LNG","May 4, 2026",0),("CVX","May 4, 2026",0),("AM","May 4, 2026",0),
        ("FLNG","May 4, 2026",0),("CRSP","May 4, 2026",0),("LZAGY","May 4, 2026",0),("NTLA","May 4, 2026",0),
        ("TWST","May 4, 2026",0),("SEV","May 4, 2026",0),("GRAIL","May 4, 2026",0),("GH","May 4, 2026",0),
        ("ASML","May 4, 2026",0),("KGC","May 4, 2026",0),("UBER","May 4, 2026",0),("CERT","May 4, 2026",0),
        ("RKLB","May 4, 2026",0),("RGTI","May 4, 2026",0),("LLY","May 4, 2026",0),("TMO","May 4, 2026",0),
        ("DHR","May 4, 2026",0),("ISRG","May 4, 2026",0),("SPGI","May 4, 2026",0),("MCO","May 4, 2026",0),
        ("CSGP","May 4, 2026",0),("TRUE","May 5, 2026",1),("EFX","May 5, 2026",1),("IT","May 5, 2026",1),
        ("ROP","May 5, 2026",1),("MSCI","May 5, 2026",1),("BR","May 5, 2026",1),("FDS","May 5, 2026",1),
        ("RSG","May 5, 2026",1),("TYL","May 5, 2026",1),("SSNC","May 5, 2026",1),("LDOS","May 5, 2026",1),
        ("J","May 5, 2026",1),("BAH","May 5, 2026",1),("CACI","May 5, 2026",1),("EXPO","May 5, 2026",1),
        ("FCN","May 5, 2026",1),("MORN","May 5, 2026",1),("JKHY","May 5, 2026",1),("CDW","May 5, 2026",1),
        ("PAYX","May 5, 2026",1),("LUNR","May 5, 2026",1),("BBAI","May 5, 2026",1),("OMAB","May 5, 2026",1),
        ("LOPE","May 5, 2026",1),("IDCC","May 11, 2026",1),("FCFS","May 11, 2026",1),("BRO","May 11, 2026",1),
        ("PRPO","May 11, 2026",1),("CCEL","May 11, 2026",1),("FRPT","May 11, 2026",1),("OPFI","May 11, 2026",1),
        ("VEON","May 11, 2026",1),("ENS","May 11, 2026",1),("NUTX","May 11, 2026",1),("WRB","May 12, 2026",1),
        ("ABBNY","May 12, 2026",1),("MRVL","May 12, 2026",1),("OR","May 12, 2026",1),("ROKU","May 12, 2026",1),
        ("CART","May 12, 2026",1),("ALVO","May 12, 2026",1),("TTWO","May 12, 2026",1),("MSI","May 12, 2026",1),
        ("ZBRA","May 12, 2026",1),("AJG","May 12, 2026",1),("HEI","May 12, 2026",1),("IDXX","May 12, 2026",1),
        ("WCN","May 12, 2026",1),("BFAM","May 12, 2026",1),("CLH","May 12, 2026",1),("WSO","May 12, 2026",1),
        ("LII","May 12, 2026",1),("CSL","May 12, 2026",1),
    ]
    for ticker, dt, iu in pass_log:
        c.execute("INSERT OR IGNORE INTO master_log (ticker,date_analyzed,verdict,is_unified) VALUES (?,?,'PASS',?)", (ticker, dt, iu))
    conn.commit()
    conn.close()

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
    c.execute("SELECT verdict, date_analyzed, notes, is_unified, id FROM master_log WHERE ticker=? ORDER BY id DESC LIMIT 1", (ticker,))
    row = c.fetchone()
    conn.close()
    return row

def add_master_log(ticker, date_str, verdict, notes="", is_unified=1):
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM master_log WHERE ticker=?", (ticker,))
    existing = c.fetchone()
    if existing:
        c.execute("""UPDATE master_log
                     SET date_analyzed=?, verdict=?, notes=?, is_unified=?
                     WHERE ticker=?""",
                  (date_str, verdict, notes, is_unified, ticker))
    else:
        c.execute("INSERT INTO master_log (ticker, date_analyzed, verdict, notes, is_unified) VALUES (?,?,?,?,?)",
                  (ticker, date_str, verdict, notes, is_unified))
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
    add_master_log(ticker, date_str, "BUY", notes, is_unified=1)

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
    add_master_log(ticker, date_str, "HOLD", notes, is_unified=1)

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
    seed_v55()

with st.sidebar:
    st.markdown("### 💙🦋 DREAM TEAM")
    st.markdown('<p class="mono" style="color:#8899aa;">Investment Analysis System</p>', unsafe_allow_html=True)
    st.markdown('<p class="mono" style="color:#555e6e; font-size:0.75rem;">V55 — Unified 7 Points</p>', unsafe_allow_html=True)
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
    st.markdown(f'<p class="mono" style="color:#2a7fff;">Log: {log_count}</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<p class="mono" style="color:#e8e4d9; font-size:0.72rem; font-weight:600;">Fundamentals first. Always.</p>', unsafe_allow_html=True)
    st.markdown('<p class="mono" style="color:#e8e4d9; font-size:0.72rem; font-weight:600;">We are not desperate. We wait. 🐟</p>', unsafe_allow_html=True)

if page == "Dashboard":
    st.markdown('<div class="header-block"><h1>Investment Analysis System</h1><p class="mono" style="color:#8899aa;">Unified 7 Points Standards | V55 | Dream Team</p></div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    log_df = get_master_log()
    # Dashboard counter cards — 7px left border, bright category color
    with col1:
        st.markdown(dash_card("#3ddc84", "BUY LIST", buy_count, "active positions"), unsafe_allow_html=True)
    with col2:
        st.markdown(dash_card("#ffc947", "HOLD LIST", hold_count, "awaiting trigger"), unsafe_allow_html=True)
    with col3:
        pass_n = len(log_df[log_df["verdict"] == "PASS"])
        st.markdown(dash_card("#ff6b6b", "PASSED", pass_n, "did not qualify"), unsafe_allow_html=True)
    with col4:
        hp_n = len(log_df[log_df["verdict"] == "HARD_PASS"])
        st.markdown(dash_card("#cc3333", "HARD PASS", hp_n, "permanent exclusion"), unsafe_allow_html=True)
    st.markdown("<hr style='border-top:1px solid #2a3344; margin:1.5rem 0;'>", unsafe_allow_html=True)
    col_b, col_h = st.columns(2)
    with col_b:
        st.markdown("#### Buy List — Ranked by Efficiency")
        buy_df = get_buy_list()
        for _, row in buy_df.iterrows():
            nm = " <- NEW" if row["is_new"] else ""
            st.markdown(f'<div class="metric-card" style="border-left:3px solid #3ddc84; padding:0.8rem 1rem;"><span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span><span style="color:#3ddc84;">{nm}</span> &nbsp;<span class="mono" style="color:#e8e4d9;">${row["current_price"]:.2f}</span><span style="float:right;" class="mono"><span style="color:#3ddc84;">{row["upside_low"]:.0f}-{row["upside_high"]:.0f}% upside</span> &nbsp;Score: <em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em></span></div>', unsafe_allow_html=True)
    with col_h:
        st.markdown("#### Hold List — Ranked by Efficiency")
        hold_df = get_hold_list()
        for _, row in hold_df.iterrows():
            nm = " <- NEW" if row["is_new"] else ""
            st.markdown(f'<div class="metric-card" style="border-left:3px solid #ffc947; padding:0.8rem 1rem;"><span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span><span style="color:#ffc947;">{nm}</span> &nbsp;<span class="mono" style="color:#e8e4d9;">${row["current_price"]:.2f}</span><span style="float:right;" class="mono"><span style="color:#ffc947;">Entry: ${row["fair_entry_low"]:.0f}-${row["fair_entry_high"]:.0f}</span> &nbsp;Score: <em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em></span></div>', unsafe_allow_html=True)

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
    st.markdown('<div class="header-block"><h1>Master Consolidated Log</h1><p class="mono" style="color:#8899aa;">Cross-reference every ticker here first. All sessions. All verdicts.</p><p class="mono" style="color:#555e6e; font-size:0.78rem;">Full brightness = post-Unified (Unified 7 Points) &nbsp;|&nbsp; Muted = pre-Unified (legacy standard)</p></div>', unsafe_allow_html=True)
    col_filter, col_search = st.columns([2, 3])
    with col_filter:
        verdict_filter = st.selectbox("Filter by Verdict", ["ALL", "BUY", "HOLD", "PASS", "HARD_PASS"])
    with col_search:
        search_term = st.text_input("Search Ticker", placeholder="e.g. GTLB")
    log_df = get_master_log(verdict_filter if verdict_filter != "ALL" else None)
    if search_term:
        log_df = log_df[log_df["ticker"].str.upper().str.contains(search_term.upper())]
    all_log = get_master_log()

    # Master Log counter cards — full frame 2px + 7px left
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(log_counter_card("#3ddc84", f"BUY: {len(all_log[all_log.verdict=='BUY'])}"), unsafe_allow_html=True)
    with c2: st.markdown(log_counter_card("#ffc947", f"HOLD: {len(all_log[all_log.verdict=='HOLD'])}"), unsafe_allow_html=True)
    with c3: st.markdown(log_counter_card("#ff6b6b", f"PASS: {len(all_log[all_log.verdict=='PASS'])}"), unsafe_allow_html=True)
    with c4: st.markdown(log_counter_card("#cc3333", f"HARD PASS: {len(all_log[all_log.verdict=='HARD_PASS'])}"), unsafe_allow_html=True)

    st.markdown(f'<p class="mono" style="color:#8899aa; font-size:0.8rem;">Showing {len(log_df)} records</p>', unsafe_allow_html=True)

    if log_df.empty:
        st.info("No records found.")
    else:
        # Show records: post-Unified = full frame + 7px left | pre-Unified = 7px left only
        border_full  = {"BUY": "#3ddc84", "HOLD": "#ffc947", "PASS": "#ff6b6b", "HARD_PASS": "#cc3333"}
        border_muted = {"BUY": "#1a4a2a", "HOLD": "#3a2e00", "PASS": "#3a1010", "HARD_PASS": "#2a0a0a"}
        for _, row in log_df.iterrows():
            v          = row["verdict"]
            is_unified = int(row.get("is_unified", 1))
            border_col = border_full.get(v, "#2a3344") if is_unified else border_muted.get(v, "#2a3344")
            ticker_col = "#e8e4d9" if is_unified else "#4a5568"
            date_col   = "#8899aa" if is_unified else "#3a4252"
            badge      = verdict_badge_html(v, is_unified)
            st.markdown(
                log_record_row(is_unified, border_col, ticker_col, date_col,
                               row["id"], row["ticker"], row["date_analyzed"], badge, row["next_review"]),
                unsafe_allow_html=True)

elif page == "Ticker Lookup":
    st.markdown('<div class="header-block"><h1>Ticker Cross-Reference</h1><p class="mono" style="color:#8899aa;">Check Master Consolidated Log instantly before any analysis.</p></div>', unsafe_allow_html=True)
    ticker_input = st.text_input("Enter Ticker Symbol", placeholder="e.g. CRWD, NKE, MSFT").upper().strip()
    if ticker_input:
        result = lookup_ticker(ticker_input)
        if result:
            verdict, dt, notes, is_unified, row_id = result
            is_unified = int(is_unified) if is_unified is not None else 1
            border_full  = {"BUY": "#3ddc84", "HOLD": "#ffc947", "PASS": "#ff6b6b", "HARD_PASS": "#cc3333"}
            border_muted = {"BUY": "#1a4a2a", "HOLD": "#3a2e00", "PASS": "#3a1010", "HARD_PASS": "#2a0a0a"}
            labels  = {"BUY": "ALREADY ON BUY LIST", "HOLD": "ALREADY ON HOLD LIST", "PASS": "PREVIOUSLY PASSED", "HARD_PASS": "HARD PASS — PERMANENT"}
            actions = {"BUY": "Already approved and active. Report position + skip.", "HOLD": "Already analyzed, waiting for price trigger. Report + skip.", "PASS": "Did not meet standards. Re-evaluation Triggers quarterly.", "HARD_PASS": "Permanent exclusion. BPO/AI-vulnerable or full cyclical fail."}
            border_col  = border_full.get(verdict, "#2a3344") if is_unified else border_muted.get(verdict, "#2a3344")
            ticker_col  = "#e8e4d9" if is_unified else "#4a5568"
            date_col    = "#8899aa" if is_unified else "#3a4252"
            border_style = f"border: 2px solid {border_col}; border-left: 7px solid {border_col};" if is_unified else f"border-left: 7px solid {border_col};"
            badge_html  = verdict_badge_html(verdict, is_unified)
            action_text = actions.get(verdict, "")
            notes_html  = f'<p class="mono" style="color:#8899aa;">{notes}</p>' if notes else ""
            st.markdown(
                f'<div class="metric-card" style="{border_style} padding: 1rem 1.4rem;">' 
                f'<div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.5rem;"><span class="mono" style="color:#555e6e; font-size:0.72rem;">#{row_id}</span><h3 style="color:{ticker_col}; font-family:JetBrains Mono,monospace; margin:0;">{ticker_input} — {labels.get(verdict, verdict)}</h3></div>'
                f'<div style="margin-bottom:0.4rem;">{badge_html}</div>'
                f'<p class="mono" style="color:{date_col}; margin:0.3rem 0;">Date analyzed: {dt}</p>'
                f'<p class="mono" style="color:{border_col}; margin:0.3rem 0;">{action_text}</p>'
                f'{notes_html}'
                f'</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-card" style="border-left:7px solid #2a7fff;"><h3 style="color:#2a7fff; font-family:JetBrains Mono,monospace;">{ticker_input} — NOT FOUND IN LOG</h3><p class="mono">Proceed with full Unified 7 Points deep-dive analysis.</p><p class="mono" style="color:#8899aa;">After analysis: add verdict via Add / Update page.</p></div>', unsafe_allow_html=True)

elif page == "Add / Update":
    st.markdown('<div class="header-block"><h1>Add / Update Ticker</h1><p class="mono" style="color:#8899aa;">HANDOFF line — auto-logs to correct table with Capital Efficiency Score.</p></div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Add to Buy List", "Add to Hold List", "Log PASS / HARD PASS", "Re-evaluate / Update Verdict", "Remove Ticker"])

    with tab1:
        st.markdown("#### Add / Update — Buy List")
        with st.form("add_buy_form"):
            col1, col2 = st.columns(2)
            with col1:
                b_ticker = st.text_input("Ticker Symbol *").upper().strip()
                b_price  = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
            with col2:
                b_ul = st.number_input("Upside Low (%)", min_value=0.0, value=50.0, step=1.0)
                b_uh = st.number_input("Upside High (%)", min_value=0.0, value=70.0, step=1.0)
            b_inst  = st.selectbox("Institutional Money / Tape Reading",
                ["Pending", "Strong absorption / aggressive buying",
                 "Neutral / choppy flow", "Distribution / selling pressure"])
            b_notes = st.text_area("Notes (optional)")
            b_date  = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
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
                h_price  = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
                h_ul = st.number_input("Upside Low (%)", min_value=0.0, value=35.0, step=1.0)
                h_uh = st.number_input("Upside High (%)", min_value=0.0, value=50.0, step=1.0)
            with col2:
                h_fel = st.number_input("Fair Entry Price Low ($) *", min_value=0.01, value=80.00, step=0.01)
                h_feh = st.number_input("Fair Entry Price High ($) *", min_value=0.01, value=90.00, step=0.01)
            h_notes = st.text_area("Notes (optional)")
            h_date  = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
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
            p_ticker  = st.text_input("Ticker Symbol *").upper().strip()
            p_verdict = st.radio("Verdict", ["PASS", "HARD_PASS"])
            p_notes   = st.text_area("Notes / reason")
            p_date    = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            if st.form_submit_button("Log to Master Consolidated Log"):
                if not p_ticker:
                    st.error("Ticker is required.")
                else:
                    add_master_log(p_ticker, p_date, p_verdict, p_notes, is_unified=1)
                    st.success(f"{p_ticker} added — {p_date} — {'HARD PASS' if p_verdict == 'HARD_PASS' else 'PASS'}")

    with tab4:
        st.markdown("#### Re-evaluate / Update Verdict")
        st.markdown(
            '<p class="mono" style="color:#8899aa; font-size:0.83rem;">'
            'Use when a ticker is being re-analyzed and its verdict changes. '
            'A new row is appended to the Master Log — history always preserved. '
            'If the new verdict is BUY or HOLD, also fill in the active list fields below.'
            '</p>', unsafe_allow_html=True)
        with st.form("re_eval_form"):
            re_ticker  = st.text_input("Ticker Symbol *").upper().strip()
            re_verdict = st.selectbox("New Verdict", ["BUY", "HOLD", "PASS", "HARD_PASS"])
            re_notes   = st.text_area("Re-evaluation notes / reason for change")
            re_date    = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            st.markdown("---")
            st.markdown('<p class="mono" style="color:#555e6e; font-size:0.8rem;">Fill in below ONLY if new verdict is BUY or HOLD — otherwise leave defaults.</p>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                re_price = st.number_input("Current Price ($)", min_value=0.01, value=100.00, step=0.01)
                re_ul    = st.number_input("Upside Low (%)", min_value=0.0, value=35.0, step=1.0)
                re_uh    = st.number_input("Upside High (%)", min_value=0.0, value=50.0, step=1.0)
            with col2:
                re_fel  = st.number_input("Fair Entry Low ($) — Hold only", min_value=0.01, value=80.00, step=0.01)
                re_feh  = st.number_input("Fair Entry High ($) — Hold only", min_value=0.01, value=90.00, step=0.01)
                re_inst = st.selectbox("Institutional Money — Buy only",
                    ["Pending", "Strong absorption / aggressive buying",
                     "Neutral / choppy flow", "Distribution / selling pressure"])
            if st.form_submit_button("Submit Re-evaluation"):
                if not re_ticker:
                    st.error("Ticker is required.")
                else:
                    if re_verdict == "BUY":
                        add_or_update_buy(re_ticker, re_price, re_ul, re_uh, re_inst, re_date, re_notes)
                        score = round((re_ul + re_uh) / 2 / re_price, 2)
                        st.success(f"✅ {re_ticker} → BUY | Added to Buy List | CE Score: {score:.2f} | Master Log updated.")
                    elif re_verdict == "HOLD":
                        add_or_update_hold(re_ticker, re_price, re_ul, re_uh, re_fel, re_feh, re_date, re_notes)
                        fep_mid = (re_fel + re_feh) / 2
                        score   = round((re_ul + re_uh) / 2 / fep_mid, 2)
                        st.success(f"⚠️ {re_ticker} → HOLD | Added to Hold List | CE Score: {score:.2f} | Master Log updated.")
                    elif re_verdict == "PASS":
                        add_master_log(re_ticker, re_date, "PASS", re_notes, is_unified=1)
                        st.success(f"❌ {re_ticker} → PASS | Master Log updated. Old entry preserved as history.")
                    elif re_verdict == "HARD_PASS":
                        add_master_log(re_ticker, re_date, "HARD_PASS", re_notes, is_unified=1)
                        st.success(f"🚫 {re_ticker} → HARD PASS | Master Log updated. Old entry preserved as history.")

    with tab5:
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
        st.markdown("---")
        st.markdown("#### Delete Entry from Master Log")
        st.markdown('<p class="mono" style="color:#cc3333; font-size:0.85rem;">⚠️ Admin only — use to remove duplicate or erroneous rows. Check Master Log page for the correct row ID first.</p>', unsafe_allow_html=True)
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            d_id = st.number_input("Master Log Row ID", min_value=1, step=1, value=1)
        with col_d2:
            d_confirm = st.text_input("Type ticker to confirm deletion").upper().strip()
        if st.button("Delete Master Log Entry"):
            if d_id and d_confirm:
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT ticker, verdict, date_analyzed FROM master_log WHERE id=?", (int(d_id),))
                row = c.fetchone()
                if row and row[0] == d_confirm:
                    c.execute("DELETE FROM master_log WHERE id=?", (int(d_id),))
                    conn.commit()
                    st.success(f"Deleted: ID {int(d_id)} — {row[0]} | {row[1]} | {row[2]}")
                elif row and row[0] != d_confirm:
                    st.error(f"Ticker mismatch — row ID {int(d_id)} belongs to {row[0]}, not {d_confirm}. Double-check before deleting.")
                else:
                    st.error(f"No row found with ID {int(d_id)}.")
                conn.close()

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
