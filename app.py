import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime, date, timedelta

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from edgar import Company
    EDGAR_AVAILABLE = True
except ImportError:
    EDGAR_AVAILABLE = False

st.set_page_config(
    page_title="Investment Analysis System",
    page_icon="💙",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
.trigger-block { color: #ff6b6b; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.header-block { border-left: 3px solid #2a7fff; padding-left: 1rem; margin-bottom: 1.5rem; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
div[data-testid="stSidebarContent"] { background-color: #0a0c10; border-right: 1px solid #1e2736; }
.stSelectbox label, .stTextInput label, .stNumberInput label, .stTextArea label { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8899aa; }
.stButton button { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; background-color: #1a2436; color: #e8e4d9; border: 1px solid #2a3344; border-radius: 3px; }
.stButton button:hover { background-color: #2a3a56; border-color: #2a7fff; }
</style>
""", unsafe_allow_html=True)

# ── DISPLAY HELPERS ───────────────────────────────────────────────────────────

def dash_card(color, label, value, sub):
    return (
        f'<div class="metric-card" style="border-left: 7px solid {color};">'
        f'<p class="mono" style="color:#e8e4d9; margin:0; font-size:0.75rem;">{label}</p>'
        f'<h2 style="color:{color}; margin:0; font-family:JetBrains Mono,monospace;">{value}</h2>'
        f'<p class="mono" style="color:#555e6e; margin:0; font-size:0.75rem;">{sub}</p>'
        f'</div>'
    )

def log_counter_card(color, text):
    return (
        f'<div class="metric-card" style="border: 2px solid {color}; border-left: 7px solid {color};">'
        f'<p class="mono" style="color:{color}; margin:0;">{text}</p>'
        f'</div>'
    )

def log_record_row(is_unified, border_color, ticker_color, date_color, row_id, ticker, date_str, badge_html, next_review):
    border_style = (
        f"border: 2px solid {border_color}; border-left: 7px solid {border_color};"
        if is_unified else
        f"border-left: 7px solid {border_color};"
    )
    return (
        f'<div class="metric-card" style="{border_style} padding: 0.7rem 1.2rem; margin-bottom: 0.4rem;">'
        f'<div style="display:flex; align-items:center; gap:1.2rem; flex-wrap:wrap;">'
        f'<span class="mono" style="color:#555e6e; font-size:0.72rem; min-width:2rem;">#{row_id}</span>'
        f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1rem; color:{ticker_color}; min-width:4rem;">{ticker}</span>'
        f'{badge_html}'
        f'<span class="mono" style="color:{date_color};">{date_str}</span>'
        f'<span class="mono" style="color:#555e6e; font-size:0.78rem; margin-left:auto;">{next_review}</span>'
        f'</div></div>'
    )

def verdict_badge_html(verdict, is_unified):
    label = {"BUY": "BUY", "HOLD": "HOLD", "PASS": "PASS", "HARD_PASS": "HARD PASS"}
    if is_unified:
        css = {"BUY": "buy-badge", "HOLD": "hold-badge", "PASS": "pass-badge", "HARD_PASS": "hardpass-badge"}
        cls = css.get(verdict, "pass-badge")
        return f'<span class="{cls}">&#9632; {label.get(verdict, verdict)}</span>'
    else:
        muted = {
            "BUY":       "background:#0a1a0f; color:#1a4a2a; border:1px solid #0f2a18;",
            "HOLD":      "background:#1a1200; color:#3a2e00; border:1px solid #2a1e00;",
            "PASS":      "background:#1a0808; color:#3a1010; border:1px solid #2a0808;",
            "HARD_PASS": "background:#110606; color:#2a0a0a; border:1px solid #1f0606;",
        }
        style = muted.get(verdict, muted["PASS"])
        return f'<span style="padding:2px 8px; border-radius:3px; font-family:JetBrains Mono,monospace; font-size:0.78rem; font-weight:700; {style}">{label.get(verdict, verdict)}</span>'

# ── DB CONNECTION (SUPABASE / POSTGRESQL) ─────────────────────────────────────
# Connection string stored in Streamlit Secrets as:
#   [supabase]
#   db_url = "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres"

def get_conn():
    db_url = st.secrets["supabase"]["db_url"]
    conn = psycopg2.connect(db_url)
    return conn

# ── DB INIT ───────────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS buy_list (
        ticker TEXT PRIMARY KEY,
        current_price REAL,
        mid_upside REAL,
        mid_fair_target REAL DEFAULT 0,
        capital_efficiency_score REAL,
        institutional_money TEXT DEFAULT 'Pending',
        date_added TEXT,
        is_new INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS hold_list (
        ticker TEXT PRIMARY KEY,
        current_price REAL,
        mid_upside REAL,
        mid_fair_entry REAL,
        mid_fair_target REAL DEFAULT 0,
        capital_efficiency_score REAL,
        date_added TEXT,
        is_new INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS master_log (
        id SERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        date_analyzed TEXT,
        verdict TEXT,
        notes TEXT DEFAULT '',
        next_review TEXT DEFAULT 'Trigger-phrase governed',
        is_unified INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id SERIAL PRIMARY KEY,
        ticker TEXT UNIQUE,
        price REAL,
        market_cap REAL DEFAULT 0,
        shares_outstanding REAL DEFAULT 0,
        baseline_date TEXT
    )""")

    # Safe migrations — add columns if not already present
    safe_alters = [
        "ALTER TABLE buy_list ADD COLUMN IF NOT EXISTS mid_fair_target REAL DEFAULT 0",
        "ALTER TABLE hold_list ADD COLUMN IF NOT EXISTS mid_fair_target REAL DEFAULT 0",
        "ALTER TABLE master_log ADD COLUMN IF NOT EXISTS is_unified INTEGER DEFAULT 1",
        "ALTER TABLE price_history ADD COLUMN IF NOT EXISTS shares_outstanding REAL DEFAULT 0",
        "ALTER TABLE price_history ADD COLUMN IF NOT EXISTS baseline_date TEXT",
        "ALTER TABLE price_history ADD COLUMN IF NOT EXISTS market_cap REAL DEFAULT 0",
    ]
    for ddl in safe_alters:
        try:
            c.execute(ddl)
        except Exception:
            conn.rollback()

    conn.commit()
    conn.close()

def is_seeded():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM master_log WHERE verdict='BUY'")
        n = c.fetchone()[0]
    except Exception:
        n = 0
    conn.close()
    return n >= 4

def seed_v55():
    conn = get_conn()
    c = conn.cursor()

    buy_data = [
        ("GTLB", 25.98, 50.0, 39.0,  "Pending", "May 11, 2026", 0),
        ("NKE",  44.14, 60.0, 70.6,  "Pending", "May 11, 2026", 1),
        ("CRM",  181.82, 52.5, 277.3, "Pending", "May 11, 2026", 0),
        ("ADBE", 247.36, 60.0, 395.8, "Pending", "May 11, 2026", 0),
    ]
    for ticker, price, mid_up, mid_ft, inst, dt, is_new in buy_data:
        score = round(mid_up / price, 2)
        c.execute("""INSERT INTO buy_list
            (ticker,current_price,mid_upside,mid_fair_target,capital_efficiency_score,
             institutional_money,date_added,is_new)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ticker) DO NOTHING""",
            (ticker, price, mid_up, mid_ft, score, inst, dt, is_new))

    hold_data = [
        ("GFI",   44.86,   40.0, 30.5,  45.7,   "May 11, 2026", 0),
        ("HALO",  66.41,   50.0, 55.0,  82.5,   "May 11, 2026", 0),
        ("TW",   108.81,   50.0, 87.5,  163.2,  "May 11, 2026", 0),
        ("NOW",   92.50,   42.5, 76.0,  131.8,  "May 11, 2026", 0),
        ("NEM",  120.67,   52.5, 96.5,  184.0,  "May 11, 2026", 0),
        ("NDAQ",  88.48,   52.5, 80.5,  135.0,  "May 12, 2026", 0),
        ("SNOW", 154.06,   37.5, 110.0, 211.8,  "May 11, 2026", 0),
        ("AMZN", 271.82,   32.5, 202.5, 360.2,  "May 11, 2026", 0),
        ("INTU", 397.54,   37.5, 330.0, 546.6,  "May 11, 2026", 0),
        ("EQIX", 1073.23,  37.5, 740.0, 1475.7, "May 12, 2026", 0),
        ("AME",  231.61,   42.5, 165.0, 330.0,  "May 12, 2026", 0),
        ("CRWD", 548.02,   42.5, 335.0, 781.4,  "May 12, 2026", 1),
    ]
    for ticker, price, mid_up, mid_fe, mid_ft, dt, is_new in hold_data:
        score = round(mid_up / mid_fe, 2)
        c.execute("""INSERT INTO hold_list
            (ticker,current_price,mid_upside,mid_fair_entry,mid_fair_target,
             capital_efficiency_score,date_added,is_new)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ticker) DO NOTHING""",
            (ticker, price, mid_up, mid_fe, mid_ft, score, dt, is_new))

    for ticker, dt in [("GTLB","May 4, 2026"),("ADBE","May 4, 2026"),("NKE","May 4, 2026"),("CRM","May 4, 2026")]:
        c.execute("""INSERT INTO master_log (ticker,date_analyzed,verdict,is_unified)
            VALUES (%s,%s,'BUY',1) ON CONFLICT DO NOTHING""", (ticker, dt))

    hold_log = [
        ("AMZN","May 4, 2026",0),("INTU","May 4, 2026",0),("NOW","May 4, 2026",0),("SNOW","May 4, 2026",0),
        ("HALO","May 5, 2026",1),("GFI","May 5, 2026",1),("TW","May 5, 2026",1),("NEM","May 11, 2026",1),
        ("NDAQ","May 12, 2026",1),("EQIX","May 12, 2026",1),("AME","May 12, 2026",1),("CRWD","May 12, 2026",1),
    ]
    for ticker, dt, iu in hold_log:
        c.execute("""INSERT INTO master_log (ticker,date_analyzed,verdict,is_unified)
            VALUES (%s,%s,'HOLD',%s) ON CONFLICT DO NOTHING""", (ticker, dt, iu))

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
        c.execute("""INSERT INTO master_log (ticker,date_analyzed,verdict,is_unified)
            VALUES (%s,%s,'HARD_PASS',%s) ON CONFLICT DO NOTHING""", (ticker, dt, iu))

    pass_log = [
        ("CSWI","May 4, 2026",0),("TRU","May 4, 2026",0),("FIS","May 4, 2026",0),("MSFT","May 4, 2026",0),
        ("CRWV","May 4, 2026",0),("PANW","May 18, 2026",1),("SOFI","May 4, 2026",0),("PLTR","May 4, 2026",0),
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
        ("LII","May 12, 2026",1),("CSL","May 12, 2026",1),("VRSK","May 4, 2026",0),
        ("ACGL","May 4, 2026",0),("V","May 4, 2026",0),("ACN","May 4, 2026",0),
        ("ADP","May 4, 2026",0),("ORLY","May 4, 2026",0),
    ]
    for ticker, dt, iu in pass_log:
        c.execute("""INSERT INTO master_log (ticker,date_analyzed,verdict,is_unified)
            VALUES (%s,%s,'PASS',%s) ON CONFLICT DO NOTHING""", (ticker, dt, iu))

    conn.commit()
    conn.close()

# ── DB HELPERS ────────────────────────────────────────────────────────────────

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
            "SELECT * FROM master_log WHERE verdict=%s ORDER BY date_analyzed DESC, id DESC",
            conn, params=(verdict_filter,))
    else:
        df = pd.read_sql("SELECT * FROM master_log ORDER BY date_analyzed DESC, id DESC", conn)
    conn.close()
    return df

def lookup_ticker(ticker):
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT verdict,date_analyzed,notes,is_unified,id FROM master_log WHERE ticker=%s ORDER BY id DESC LIMIT 1", (ticker,))
    row = c.fetchone()
    conn.close()
    return row

def add_master_log(ticker, date_str, verdict, notes="", is_unified=1):
    ticker = ticker.upper().strip()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM master_log WHERE ticker=%s ORDER BY id DESC LIMIT 1", (ticker,))
    existing = c.fetchone()
    if existing:
        c.execute("""UPDATE master_log SET date_analyzed=%s, verdict=%s, notes=%s, is_unified=%s
                     WHERE id=%s""",
                  (date_str, verdict, notes, is_unified, existing[0]))
    else:
        c.execute("""INSERT INTO master_log (ticker,date_analyzed,verdict,notes,is_unified)
                     VALUES (%s,%s,%s,%s,%s)""",
                  (ticker, date_str, verdict, notes, is_unified))
    conn.commit()
    conn.close()

# ── BASELINE SNAPSHOT ─────────────────────────────────────────────────────────

def reset_baseline_snapshot(ticker, price, market_cap, shares_outstanding):
    baseline_date = date.today().strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO price_history (ticker, price, market_cap, shares_outstanding, baseline_date)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (ticker) DO UPDATE SET
            price=EXCLUDED.price,
            market_cap=EXCLUDED.market_cap,
            shares_outstanding=EXCLUDED.shares_outstanding,
            baseline_date=EXCLUDED.baseline_date
    """, (ticker, price, market_cap or 0, shares_outstanding or 0, baseline_date))
    conn.commit()
    conn.close()

# ── FUNDAMENTALS FETCH ────────────────────────────────────────────────────────

def fetch_current_fundamentals(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info

        price = None
        try:
            price = round(float(info.last_price), 2)
        except Exception:
            pass

        market_cap = None
        try:
            market_cap = float(info.market_cap)
        except Exception:
            pass

        shares_outstanding = None
        try:
            shares_outstanding = float(info.shares)
        except Exception:
            pass

        fcf_values = []
        try:
            cf = t.quarterly_cashflow
            if cf is not None and not cf.empty:
                op_cf_row = capex_row = None
                for label in cf.index:
                    ll = str(label).lower()
                    if "operating" in ll and "cash" in ll:
                        op_cf_row = label
                    if "capital expenditure" in ll or "capex" in ll:
                        capex_row = label
                if op_cf_row is not None:
                    op_cf = cf.loc[op_cf_row].dropna().values
                    if capex_row is not None:
                        capex = cf.loc[capex_row].dropna().values
                        min_len = min(len(op_cf), len(capex))
                        fcf_values = [float(op_cf[i]) + float(capex[i]) for i in range(min_len)]
                    else:
                        fcf_values = [float(v) for v in op_cf]
        except Exception:
            pass

        revenue_growth_rates = []
        try:
            income = t.financials
            if income is not None and not income.empty:
                rev_row = None
                for label in income.index:
                    ll = str(label).lower()
                    if "total revenue" in ll or "revenue" in ll:
                        rev_row = label
                        break
                if rev_row is not None:
                    rev_series = income.loc[rev_row].dropna()
                    rev_values = list(reversed([float(v) for v in rev_series.values]))
                    for i in range(1, len(rev_values)):
                        prior = rev_values[i - 1]
                        current = rev_values[i]
                        if prior > 0:
                            revenue_growth_rates.append(round(((current - prior) / prior) * 100, 2))
        except Exception:
            pass

        return {
            "price": price,
            "market_cap": market_cap,
            "shares_outstanding": shares_outstanding,
            "fcf_values": fcf_values,
            "revenue_growth_rates": revenue_growth_rates,
        }
    except Exception:
        return None

# ── WRITE HELPERS ─────────────────────────────────────────────────────────────

def add_or_update_buy(ticker, price, mid_up, mid_ft, inst, date_str, notes):
    ticker = ticker.upper().strip()
    score = round(mid_up / price, 2) if price > 0 else 0
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE buy_list SET is_new=0")
    c.execute("""INSERT INTO buy_list
        (ticker,current_price,mid_upside,mid_fair_target,capital_efficiency_score,
         institutional_money,date_added,is_new,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)
        ON CONFLICT (ticker) DO UPDATE SET
            current_price=EXCLUDED.current_price,
            mid_upside=EXCLUDED.mid_upside,
            mid_fair_target=EXCLUDED.mid_fair_target,
            capital_efficiency_score=EXCLUDED.capital_efficiency_score,
            institutional_money=EXCLUDED.institutional_money,
            date_added=EXCLUDED.date_added,
            is_new=1,
            notes=EXCLUDED.notes""",
        (ticker, price, mid_up, mid_ft, score, inst, date_str, notes))
    conn.commit()
    conn.close()
    add_master_log(ticker, date_str, "BUY", notes, is_unified=1)
    if YFINANCE_AVAILABLE:
        try:
            f = fetch_current_fundamentals(ticker)
            if f:
                reset_baseline_snapshot(ticker, price, f.get("market_cap"), f.get("shares_outstanding"))
        except Exception:
            pass

def add_or_update_hold(ticker, price, mid_up, mid_fe, mid_ft, date_str, notes):
    ticker = ticker.upper().strip()
    score = round(mid_up / mid_fe, 2) if mid_fe > 0 else 0
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE hold_list SET is_new=0")
    c.execute("""INSERT INTO hold_list
        (ticker,current_price,mid_upside,mid_fair_entry,mid_fair_target,
         capital_efficiency_score,date_added,is_new,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)
        ON CONFLICT (ticker) DO UPDATE SET
            current_price=EXCLUDED.current_price,
            mid_upside=EXCLUDED.mid_upside,
            mid_fair_entry=EXCLUDED.mid_fair_entry,
            mid_fair_target=EXCLUDED.mid_fair_target,
            capital_efficiency_score=EXCLUDED.capital_efficiency_score,
            date_added=EXCLUDED.date_added,
            is_new=1,
            notes=EXCLUDED.notes""",
        (ticker, price, mid_up, mid_fe, mid_ft, score, date_str, notes))
    conn.commit()
    conn.close()
    add_master_log(ticker, date_str, "HOLD", notes, is_unified=1)
    if YFINANCE_AVAILABLE:
        try:
            f = fetch_current_fundamentals(ticker)
            if f:
                reset_baseline_snapshot(ticker, price, f.get("market_cap"), f.get("shares_outstanding"))
        except Exception:
            pass

def remove_from_buy(ticker):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM buy_list WHERE ticker=%s", (ticker.upper(),))
    conn.commit()
    conn.close()

def remove_from_hold(ticker):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM hold_list WHERE ticker=%s", (ticker.upper(),))
    conn.commit()
    conn.close()

def update_price_in_db(table, ticker, new_price, new_score, new_mid_upside=None):
    conn = get_conn()
    c = conn.cursor()
    today = date.today().strftime("%b %d, %Y")
    if new_mid_upside is not None:
        c.execute(f"UPDATE {table} SET current_price=%s, capital_efficiency_score=%s, mid_upside=%s, date_added=%s WHERE ticker=%s",
                  (new_price, new_score, new_mid_upside, today, ticker))
    else:
        c.execute(f"UPDATE {table} SET current_price=%s, capital_efficiency_score=%s, date_added=%s WHERE ticker=%s",
                  (new_price, new_score, today, ticker))
    conn.commit()
    conn.close()

# ── 8-K TRIGGER ITEMS ────────────────────────────────────────────────────────

EIGHT_K_TRIGGERS = {
    "5.02": ("Leadership Change",         "🚩"),
    "1.01": ("Material Agreement / M&A",  "🚩"),
    "2.01": ("Acquisition / Disposal",    "🚩"),
    "8.01": ("Regulatory / Legal Action", "🚩"),
    "2.02": ("Guidance / Earnings Event", "⚠️"),
    "7.01": ("Reg FD / Guidance Update",  "⚠️"),
    "3.02": ("Share Dilution Event",      "🚩"),
    "2.03": ("Debt / Credit Obligation",  "🚩"),
}

def check_8k_triggers(ticker):
    if not EDGAR_AVAILABLE:
        return ["⚠️ EdgarTools not installed — 8-K checks skipped. Run: pip install edgartools"]
    flags = []
    cutoff = date.today() - timedelta(days=90)
    try:
        company = Company(ticker)
        filings = company.get_filings(form="8-K")
        if filings is None:
            return []
        for filing in filings:
            try:
                filing_date = datetime.strptime(str(filing.filing_date)[:10], "%Y-%m-%d").date()
                if filing_date < cutoff:
                    break
                items_str = str(getattr(filing, "items", "") or "")
                filing_date_fmt = filing_date.strftime("%b %d, %Y")
                for item_num, (label, emoji) in EIGHT_K_TRIGGERS.items():
                    if item_num in items_str:
                        flags.append(
                            f"{emoji} {ticker} — 8-K Item {item_num}: {label} "
                            f"detected — Filed {filing_date_fmt} — review 8-K filing"
                        )
            except Exception:
                continue
    except Exception:
        flags.append(
            f"⚠️ {ticker} — 8-K lookup failed — manual SEC EDGAR check required "
            f"— ticker held pending review"
        )
    return flags

# ── HARD TRIGGER GATE ─────────────────────────────────────────────────────────

def run_hard_trigger_gate(all_tickers_df):
    blocked = {}
    clear = []
    conn = get_conn()
    c = conn.cursor()

    for _, row in all_tickers_df.iterrows():
        t = row["ticker"]
        current_price = row["current_price"]
        ticker_flags = []

        c.execute("""SELECT price, market_cap, shares_outstanding, baseline_date
                     FROM price_history WHERE ticker=%s""", (t,))
        bl = c.fetchone()
        baseline_price  = bl[0] if bl else None
        baseline_shares = bl[2] if bl else None
        baseline_date_str = bl[3] if bl else "unknown"

        if baseline_price and baseline_price > 0:
            pct_move = abs(current_price - baseline_price) / baseline_price * 100
            if pct_move >= 20:
                direction = "+" if current_price > baseline_price else "-"
                ticker_flags.append(
                    f"🚩 {t} — Flag #1: Price moved {direction}{pct_move:.1f}% from baseline "
                    f"(${baseline_price:.2f} on {baseline_date_str} → ${current_price:.2f}) — review required"
                )

        fundamentals = None
        if YFINANCE_AVAILABLE:
            fundamentals = fetch_current_fundamentals(t)

        if fundamentals is None:
            ticker_flags.append(
                f"⚠️ {t} — Fundamentals unavailable from yfinance — manual review required"
            )
        else:
            current_shares = fundamentals.get("shares_outstanding")
            fcf_values     = fundamentals.get("fcf_values", [])
            rev_growth     = fundamentals.get("revenue_growth_rates", [])

            if len(rev_growth) >= 2:
                latest   = rev_growth[-1]
                previous = rev_growth[-2]
                decel    = previous - latest
                below8   = latest < 8.0
                consec   = len(rev_growth) >= 3 and (rev_growth[-2] - rev_growth[-3]) > 0
                cn       = " (2+ consecutive periods)" if consec else ""

                if decel >= 5.0 and below8:
                    ticker_flags.append(
                        f"🚩 {t} — Flag #2: Revenue deceleration{cn}: "
                        f"{previous:.1f}% → {latest:.1f}% YoY ({decel:.1f}pt drop) "
                        f"— BELOW 8% CRITICAL THRESHOLD — AUTOMATIC FAIL"
                    )
                elif decel >= 5.0:
                    ticker_flags.append(
                        f"🚩 {t} — Flag #2: Revenue deceleration{cn}: "
                        f"{previous:.1f}% → {latest:.1f}% YoY ({decel:.1f}pt drop) "
                        f"— Hard Trigger — deeper review required"
                    )
                elif 3.0 <= decel < 5.0:
                    crit = " — CRITICAL NOTE: also below 8% low growth tier" if below8 else ""
                    ticker_flags.append(
                        f"⚠️ {t} — Flag #2: Yellow Flag — mild revenue deceleration: "
                        f"{previous:.1f}% → {latest:.1f}% YoY ({decel:.1f}pt drop){crit}"
                    )
                elif below8 and decel >= 0:
                    ticker_flags.append(
                        f"⚠️ {t} — Flag #2: Yellow Flag — revenue growth at {latest:.1f}% "
                        f"— Critical note: low growth tier (below 8% threshold)"
                    )

            if fcf_values:
                mrq = fcf_values[0]
                if mrq < 0:
                    if len(fcf_values) >= 2 and fcf_values[1] < 0:
                        ticker_flags.append(
                            f"🚩 {t} — Flag #3: FCF NEGATIVE 2+ CONSECUTIVE QUARTERS "
                            f"(most recent: ${mrq/1e6:.1f}M | prior: ${fcf_values[1]/1e6:.1f}M) "
                            f"— AUTOMATIC FAIL"
                        )
                    else:
                        ticker_flags.append(
                            f"🚩 {t} — Flag #3: FCF NEGATIVE "
                            f"(most recent quarter: ${mrq/1e6:.1f}M) — immediate review required"
                        )

            if baseline_shares and baseline_shares > 0 and current_shares and current_shares > 0:
                expected_mktcap = current_price * baseline_shares
                actual_mktcap   = current_price * current_shares
                share_pct = (actual_mktcap - expected_mktcap) / expected_mktcap * 100
                if abs(share_pct) >= 5.0:
                    if share_pct > 0:
                        ticker_flags.append(
                            f"🚩 {t} — Flag #5: Share count increased {share_pct:.1f}% since baseline "
                            f"(baseline: {baseline_shares/1e6:.1f}M → current: {current_shares/1e6:.1f}M) "
                            f"— potential dilution event — review required"
                        )
                    else:
                        ticker_flags.append(
                            f"✅ {t} — Flag #5: Share count decreased {abs(share_pct):.1f}% since baseline "
                            f"(baseline: {baseline_shares/1e6:.1f}M → current: {current_shares/1e6:.1f}M) "
                            f"— significant buyback — noted"
                        )

        ticker_flags.extend(check_8k_triggers(t))

        if ticker_flags:
            blocked[t] = ticker_flags
        else:
            clear.append(t)

    conn.close()
    return blocked, clear

# ── MAIN MARKET DATA UPDATE ───────────────────────────────────────────────────

def run_market_data_update():
    buy_df  = get_buy_list()
    hold_df = get_hold_list()
    if not YFINANCE_AVAILABLE:
        return None, "yfinance not installed."

    today  = date.today().strftime("%b %d, %Y")
    all_df = pd.concat([buy_df, hold_df], ignore_index=True)

    blocked, clear_tickers = run_hard_trigger_gate(all_df)

    prices = {}
    for t in clear_tickers:
        try:
            prices[t] = round(float(yf.Ticker(t).fast_info.last_price), 2)
        except Exception:
            prices[t] = None

    updated_buy = []
    updated_hold = []
    auto_downgraded = []
    auto_upgraded = []
    auto_retired_buy = []
    auto_retired_hold = []

    for _, row in buy_df.iterrows():
        t = row["ticker"]
        if t in blocked:
            continue
        new_price = prices.get(t)
        if not new_price:
            updated_buy.append((t, row["current_price"], None, row["mid_upside"], "unchanged"))
            continue
        mid_ft = row["mid_fair_target"]
        new_mid_up = round((mid_ft - new_price) / new_price * 100, 2) if new_price > 0 and mid_ft > 0 else row["mid_upside"]

        if new_mid_up >= 50.0:
            update_price_in_db("buy_list", t, new_price, round(new_mid_up / new_price, 2), new_mid_up)
            updated_buy.append((t, row["current_price"], new_price, new_mid_up, "active"))
        elif new_mid_up >= 35.0:
            mid_fe_new = round(mid_ft / 1.5, 2)
            remove_from_buy(t)
            score = round(new_mid_up / mid_fe_new, 2) if mid_fe_new > 0 else 0
            conn = get_conn()
            cc = conn.cursor()
            cc.execute("UPDATE hold_list SET is_new=0")
            cc.execute("""INSERT INTO hold_list
                (ticker,current_price,mid_upside,mid_fair_entry,mid_fair_target,
                 capital_efficiency_score,date_added,is_new,notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)
                ON CONFLICT (ticker) DO UPDATE SET
                    current_price=EXCLUDED.current_price,mid_upside=EXCLUDED.mid_upside,
                    mid_fair_entry=EXCLUDED.mid_fair_entry,mid_fair_target=EXCLUDED.mid_fair_target,
                    capital_efficiency_score=EXCLUDED.capital_efficiency_score,
                    date_added=EXCLUDED.date_added,is_new=1,notes=EXCLUDED.notes""",
                (t.upper(), new_price, new_mid_up, mid_fe_new, mid_ft, score, today,
                 f"Auto-downgraded from Buy List — Mid Upside compressed to {new_mid_up:.1f}% — {today}"))
            conn.commit()
            conn.close()
            add_master_log(t, today, "HOLD", is_unified=1,
                           notes=f"Auto-downgraded from Buy List — Mid Upside compressed to {new_mid_up:.1f}% — {today}")
            auto_downgraded.append((t, row["current_price"], new_price, new_mid_up, mid_fe_new))
        else:
            remove_from_buy(t)
            add_master_log(t, today, "PASS", is_unified=1,
                           notes=f"Auto-retired from Buy List — Mid Upside fell to {new_mid_up:.1f}% (below 35%) — {today}")
            auto_retired_buy.append((t, row["current_price"], new_price, new_mid_up))

    for _, row in hold_df.iterrows():
        t = row["ticker"]
        if t in blocked:
            continue
        new_price = prices.get(t)
        if not new_price:
            updated_hold.append((t, row["current_price"], None, row["mid_upside"], "unchanged"))
            continue
        mid_ft = row["mid_fair_target"]
        new_mid_up = round((mid_ft - new_price) / new_price * 100, 2) if new_price > 0 and mid_ft > 0 else row["mid_upside"]

        if new_mid_up >= 50.0:
            remove_from_hold(t)
            score = round(new_mid_up / new_price, 2)
            conn = get_conn()
            cc = conn.cursor()
            cc.execute("UPDATE buy_list SET is_new=0")
            cc.execute("""INSERT INTO buy_list
                (ticker,current_price,mid_upside,mid_fair_target,capital_efficiency_score,
                 institutional_money,date_added,is_new,notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)
                ON CONFLICT (ticker) DO UPDATE SET
                    current_price=EXCLUDED.current_price,mid_upside=EXCLUDED.mid_upside,
                    mid_fair_target=EXCLUDED.mid_fair_target,
                    capital_efficiency_score=EXCLUDED.capital_efficiency_score,
                    institutional_money=EXCLUDED.institutional_money,
                    date_added=EXCLUDED.date_added,is_new=1,notes=EXCLUDED.notes""",
                (t.upper(), new_price, new_mid_up, mid_ft, score, "Pending", today,
                 f"Auto-upgraded from Hold List — Mid Upside reached {new_mid_up:.1f}% — {today}"))
            conn.commit()
            conn.close()
            add_master_log(t, today, "BUY", is_unified=1,
                           notes=f"Auto-upgraded from Hold List — Mid Upside reached {new_mid_up:.1f}% — {today}")
            auto_upgraded.append((t, row["current_price"], new_price, new_mid_up))
        elif new_mid_up >= 35.0:
            mid_fe_new = round(mid_ft / 1.5, 2)
            new_score  = round(new_mid_up / mid_fe_new, 2) if mid_fe_new > 0 else 0
            update_price_in_db("hold_list", t, new_price, new_score, new_mid_up)
            conn = get_conn()
            cc = conn.cursor()
            cc.execute("UPDATE hold_list SET mid_fair_entry=%s WHERE ticker=%s", (mid_fe_new, t))
            conn.commit()
            conn.close()
            updated_hold.append((t, row["current_price"], new_price, new_mid_up, "active"))
        else:
            remove_from_hold(t)
            add_master_log(t, today, "PASS", is_unified=1,
                           notes=f"Auto-retired from Hold List — Mid Upside fell to {new_mid_up:.1f}% (below 35%) — {today}")
            auto_retired_hold.append((t, row["current_price"], new_price, new_mid_up))

    return {
        "buy": updated_buy, "hold": updated_hold,
        "auto_downgraded": auto_downgraded, "auto_upgraded": auto_upgraded,
        "auto_retired_buy": auto_retired_buy, "auto_retired_hold": auto_retired_hold,
        "blocked": blocked, "timestamp": today,
    }, None

# ── STARTUP ───────────────────────────────────────────────────────────────────
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
    buy_count  = len(get_buy_list())
    hold_count = len(get_hold_list())
    log_count  = len(get_master_log())
    st.markdown(f'<p class="mono" style="color:#3ddc84;">Buy: {buy_count}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#ffc947;">Hold: {hold_count}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#2a7fff;">Log: {log_count}</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<p class="mono" style="color:#e8e4d9; font-size:0.72rem; font-weight:600;">Fundamentals first. Always.</p>', unsafe_allow_html=True)
    st.markdown('<p class="mono" style="color:#e8e4d9; font-size:0.72rem; font-weight:600;">We are not desperate. We wait. 🐟</p>', unsafe_allow_html=True)

# ── PAGES ─────────────────────────────────────────────────────────────────────

if page == "Dashboard":
    st.markdown('<div class="header-block" style="border-left:7px solid #2a7fff;"><h1 style="color:#2a7fff;">Investment Analysis System</h1><p class="mono" style="color:#8899aa;">Unified 7 Points Standards | V55 | Dream Team</p></div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    log_df = get_master_log()
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
    col_b, col_h = st.columns([4, 5])
    with col_b:
        st.markdown("#### :green[Buy List — Ranked by Efficiency]")
        buy_df = get_buy_list()
        for _, row in buy_df.iterrows():
            new_badge_b = "&nbsp;<span style='color:#3ddc84; font-family:JetBrains Mono,monospace; font-size:0.68rem; font-style:italic;'>← NEW</span>" if row["is_new"] else ""
            st.markdown(
                f'<div class="metric-card" style="border-left:7px solid #3ddc84; padding:0.7rem 1rem;">'
                f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span>'
                f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="mono" style="color:#e8e4d9; font-size:0.78rem;">${row["current_price"]:.2f}</span>'
                f'{new_badge_b}'
                f'<span style="float:right; font-family:JetBrains Mono,monospace; font-size:0.72rem;">'
                f'<span style="color:#e8e4d9;">Upside: </span><span style="color:#3ddc84;">{row["mid_upside"]:.1f}%</span>'
                f'&nbsp;&nbsp;&nbsp;<span style="color:#e8e4d9;">Target: </span><span style="color:#3ddc84;">${row["mid_fair_target"]:.2f}</span>'
                f'&nbsp;&nbsp;&nbsp;<span style="color:#e8e4d9;">Score: </span><em style="color:#3ddc84;">{row["capital_efficiency_score"]:.2f}</em>'
                f'</span></div>', unsafe_allow_html=True)
    with col_h:
        st.markdown("#### :orange[Hold List — Ranked by Efficiency]")
        hold_df = get_hold_list()
        for _, row in hold_df.iterrows():
            new_badge_h = "&nbsp;<span style='color:#ffc947; font-family:JetBrains Mono,monospace; font-size:0.68rem; font-style:italic;'>← NEW</span>" if row["is_new"] else ""
            st.markdown(
                f'<div class="metric-card" style="border-left:7px solid #ffc947; padding:0.7rem 1rem;">'
                f'<span style="font-family:JetBrains Mono,monospace; font-weight:700; color:#e8e4d9;">{row["ticker"]}</span>'
                f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="mono" style="color:#e8e4d9; font-size:0.78rem;">${row["current_price"]:.2f}</span>'
                f'{new_badge_h}'
                f'<span style="float:right; font-family:JetBrains Mono,monospace; font-size:0.72rem;">'
                f'<span style="color:#e8e4d9;">Upside: </span><span style="color:#ffc947;">{row["mid_upside"]:.1f}%</span>'
                f'&nbsp;&nbsp;&nbsp;<span style="color:#e8e4d9;">Entry: </span><span style="color:#ffc947;">${row["mid_fair_entry"]:.2f}</span>'
                f'&nbsp;&nbsp;&nbsp;<span style="color:#e8e4d9;">Target: </span><span style="color:#ffc947;">${row["mid_fair_target"]:.2f}</span>'
                f'&nbsp;&nbsp;&nbsp;<span style="color:#e8e4d9;">Score: </span><em style="color:#ffc947;">{row["capital_efficiency_score"]:.2f}</em>'
                f'</span></div>', unsafe_allow_html=True)

elif page == "Buy List":
    st.markdown('<div class="header-block" style="border-left:7px solid #3ddc84;"><h1 style="color:#3ddc84;">Buy List</h1><p class="mono" style="color:#8899aa;">Ranked by Capital Efficiency Score (Mid Upside% / Current Price)</p></div>', unsafe_allow_html=True)
    buy_df = get_buy_list()
    if buy_df.empty:
        st.info("No tickers in Buy List.")
    else:
        for _, row in buy_df.iterrows():
            st.markdown(
                f'<div class="metric-card" style="border-left:7px solid #3ddc84;">'
                f'<div style="display:flex; justify-content:space-between;">'
                f'<div><span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1.15rem; color:#e8e4d9;">{row["ticker"]}</span>'
                f'<span style="color:#3ddc84;">{"&nbsp;<em>← NEW</em>" if row["is_new"] else ""}</span> &nbsp;<span class="mono" style="color:#3ddc84;">BUY</span></div>'
                f'<div class="mono" style="color:#e8e4d9; font-size:0.78rem;">{row["date_added"]}</div></div>'
                f'<div style="margin-top:0.8rem; display:flex; gap:2.8rem; flex-wrap:wrap;">'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">CURRENT PRICE</p><p class="mono" style="color:#e8e4d9; margin:0;">${row["current_price"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">MID UPSIDE</p><p class="mono" style="color:#3ddc84; margin:0;">{row["mid_upside"]:.1f}%</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">MID FAIR TARGET</p><p class="mono" style="color:#3ddc84; margin:0;">${row["mid_fair_target"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">CE SCORE</p><p class="mono" style="color:#3ddc84; margin:0; font-style:italic;">{row["capital_efficiency_score"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">INSTITUTIONAL $</p><p class="mono" style="color:#e8e4d9; margin:0;">{row["institutional_money"]}</p></div>'
                f'</div></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="mono" style="color:#3ddc84;">Total: {len(buy_df)} tickers</p>', unsafe_allow_html=True)

elif page == "Hold List":
    st.markdown('<div class="header-block" style="border-left:7px solid #ffc947;"><h1 style="color:#ffc947;">Hold List</h1><p class="mono" style="color:#8899aa;">Ranked by Capital Efficiency Score (Mid Upside% / Mid Fair Entry)</p></div>', unsafe_allow_html=True)
    hold_df = get_hold_list()
    if hold_df.empty:
        st.info("No tickers in Hold List.")
    else:
        for _, row in hold_df.iterrows():
            st.markdown(
                f'<div class="metric-card" style="border-left:7px solid #ffc947;">'
                f'<div style="display:flex; justify-content:space-between;">'
                f'<div><span style="font-family:JetBrains Mono,monospace; font-weight:700; font-size:1.15rem; color:#e8e4d9;">{row["ticker"]}</span>'
                f'<span style="color:#ffc947;">{"&nbsp;<em>← NEW</em>" if row["is_new"] else ""}</span> &nbsp;<span class="mono" style="color:#ffc947;">HOLD</span></div>'
                f'<div class="mono" style="color:#e8e4d9; font-size:0.78rem;">{row["date_added"]}</div></div>'
                f'<div style="margin-top:0.8rem; display:flex; gap:2.8rem; flex-wrap:wrap;">'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">CURRENT PRICE</p><p class="mono" style="color:#e8e4d9; margin:0;">${row["current_price"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">MID UPSIDE</p><p class="mono" style="color:#ffc947; margin:0;">{row["mid_upside"]:.1f}%</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">MID FAIR ENTRY</p><p class="mono" style="color:#ffc947; margin:0;">${row["mid_fair_entry"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">MID FAIR TARGET</p><p class="mono" style="color:#ffc947; margin:0;">${row["mid_fair_target"]:.2f}</p></div>'
                f'<div><p class="mono" style="color:#e8e4d9; margin:0; font-size:0.72rem;">CE SCORE</p><p class="mono" style="color:#ffc947; margin:0; font-style:italic;">{row["capital_efficiency_score"]:.2f}</p></div>'
                f'</div></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="mono" style="color:#ffc947;">Total: {len(hold_df)} tickers</p>', unsafe_allow_html=True)

elif page == "Master Log":
    st.markdown('<div class="header-block" style="border-left:7px solid #2a7fff;"><h1 style="color:#2a7fff;">Master Consolidated Log</h1><p class="mono" style="color:#8899aa;">Cross-reference every ticker here first. All sessions. All verdicts.</p><p class="mono" style="color:#555e6e; font-size:0.78rem;">Full brightness = post-Unified &nbsp;|&nbsp; Muted = pre-Unified (legacy standard)</p></div>', unsafe_allow_html=True)
    col_filter, col_search = st.columns([2, 3])
    with col_filter:
        verdict_filter = st.selectbox("Filter by Verdict", ["ALL", "BUY", "HOLD", "PASS", "HARD_PASS"])
    with col_search:
        search_term = st.text_input("Search Ticker", placeholder="e.g. GTLB")
    log_df = get_master_log(verdict_filter if verdict_filter != "ALL" else None)
    if search_term:
        log_df = log_df[log_df["ticker"].str.upper().str.contains(search_term.upper())]
    all_log = get_master_log()
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(log_counter_card("#3ddc84", f"BUY: {len(all_log[all_log.verdict=='BUY'])}"), unsafe_allow_html=True)
    with c2: st.markdown(log_counter_card("#ffc947", f"HOLD: {len(all_log[all_log.verdict=='HOLD'])}"), unsafe_allow_html=True)
    with c3: st.markdown(log_counter_card("#ff6b6b", f"PASS: {len(all_log[all_log.verdict=='PASS'])}"), unsafe_allow_html=True)
    with c4: st.markdown(log_counter_card("#cc3333", f"HARD PASS: {len(all_log[all_log.verdict=='HARD_PASS'])}"), unsafe_allow_html=True)
    st.markdown(f'<p class="mono" style="color:#8899aa; font-size:0.8rem;">Showing {len(log_df)} records</p>', unsafe_allow_html=True)
    if log_df.empty:
        st.info("No records found.")
    else:
        border_full  = {"BUY": "#3ddc84", "HOLD": "#ffc947", "PASS": "#ff6b6b", "HARD_PASS": "#cc3333"}
        border_muted = {"BUY": "#1a4a2a", "HOLD": "#3a2e00", "PASS": "#3a1010", "HARD_PASS": "#2a0a0a"}
        for _, row in log_df.iterrows():
            v          = row["verdict"]
            is_unified = int(row.get("is_unified", 1))
            border_col = border_full.get(v, "#2a3344") if is_unified else border_muted.get(v, "#2a3344")
            ticker_col = "#e8e4d9" if is_unified else "#4a5568"
            date_col   = "#8899aa" if is_unified else "#3a4252"
            badge      = verdict_badge_html(v, is_unified)
            st.markdown(log_record_row(is_unified, border_col, ticker_col, date_col,
                               row["id"], row["ticker"], row["date_analyzed"], badge, row["next_review"]),
                unsafe_allow_html=True)

elif page == "Ticker Lookup":
    st.markdown('<div class="header-block" style="border-left:7px solid #2a7fff;"><h1 style="color:#2a7fff;">Ticker Cross-Reference</h1><p class="mono" style="color:#8899aa;">Check Master Consolidated Log instantly before any analysis.</p></div>', unsafe_allow_html=True)
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
            border_col   = border_full.get(verdict, "#2a3344") if is_unified else border_muted.get(verdict, "#2a3344")
            ticker_col   = "#e8e4d9" if is_unified else "#4a5568"
            date_col     = "#8899aa" if is_unified else "#3a4252"
            border_style = f"border: 2px solid {border_col}; border-left: 7px solid {border_col};" if is_unified else f"border-left: 7px solid {border_col};"
            badge_html   = verdict_badge_html(verdict, is_unified)
            notes_html   = f'<p class="mono" style="color:#8899aa;">{notes}</p>' if notes else ""
            st.markdown(
                f'<div class="metric-card" style="{border_style} padding: 1rem 1.4rem;">'
                f'<div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.5rem;">'
                f'<span class="mono" style="color:#555e6e; font-size:0.72rem;">#{row_id}</span>'
                f'<h3 style="color:{ticker_col}; font-family:JetBrains Mono,monospace; margin:0;">{ticker_input} — {labels.get(verdict, verdict)}</h3>'
                f'</div><div style="margin-bottom:0.4rem;">{badge_html}</div>'
                f'<p class="mono" style="color:{date_col}; margin:0.3rem 0;">Date analyzed: {dt}</p>'
                f'<p class="mono" style="color:{border_col}; margin:0.3rem 0;">{actions.get(verdict, "")}</p>'
                f'{notes_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="metric-card" style="border-left:7px solid #2a7fff;">'
                f'<h3 style="color:#2a7fff; font-family:JetBrains Mono,monospace;">{ticker_input} — NOT FOUND IN LOG</h3>'
                f'<p class="mono">Proceed with full Unified 7 Points deep-dive analysis.</p>'
                f'<p class="mono" style="color:#8899aa;">After analysis: add verdict via Add / Update page.</p></div>',
                unsafe_allow_html=True)

elif page == "Add / Update":
    st.markdown('<div class="header-block" style="border-left:7px solid #2a7fff;"><h1 style="color:#2a7fff;">Add / Update Ticker</h1><p class="mono" style="color:#8899aa;">HANDOFF line — auto-logs to correct table with Capital Efficiency Score. Resets baseline snapshot on BUY/HOLD entries.</p></div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Add to Buy List", "Add to Hold List", "Log PASS / HARD PASS", "Re-evaluate / Update Verdict", "Remove Ticker"])

    with tab1:
        st.markdown("#### Add / Update — Buy List")
        with st.form("add_buy_form"):
            col1, col2 = st.columns(2)
            with col1:
                b_ticker = st.text_input("Ticker Symbol *").upper().strip()
                b_price  = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
                b_mid_up = st.number_input("Mid Upside (%)", min_value=0.0, value=50.0, step=0.5)
            with col2:
                b_mid_ft = st.number_input("Mid Fair Target ($) *", min_value=0.01, value=150.00, step=0.01)
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
                    add_or_update_buy(b_ticker, b_price, b_mid_up, b_mid_ft, b_inst, b_date, b_notes)
                    score = round(b_mid_up / b_price, 2)
                    st.success(f"{b_ticker} added to Buy List — CE Score: {score:.2f} — Mid Fair Target: ${b_mid_ft:.2f} — Baseline snapshot reset ✅")

    with tab2:
        st.markdown("#### Add / Update — Hold List")
        with st.form("add_hold_form"):
            col1, col2 = st.columns(2)
            with col1:
                h_ticker = st.text_input("Ticker Symbol *").upper().strip()
                h_price  = st.number_input("Current Price ($) *", min_value=0.01, value=100.00, step=0.01)
                h_mid_up = st.number_input("Mid Upside (%)", min_value=0.0, value=40.0, step=0.5)
            with col2:
                h_mid_fe = st.number_input("Mid Fair Entry ($) *", min_value=0.01, value=80.00, step=0.01)
                h_mid_ft = st.number_input("Mid Fair Target ($) *", min_value=0.01, value=120.00, step=0.01)
            h_notes = st.text_area("Notes (optional)")
            h_date  = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            if st.form_submit_button("Add to Hold List"):
                if not h_ticker:
                    st.error("Ticker is required.")
                else:
                    add_or_update_hold(h_ticker, h_price, h_mid_up, h_mid_fe, h_mid_ft, h_date, h_notes)
                    score = round(h_mid_up / h_mid_fe, 2)
                    st.success(f"{h_ticker} added to Hold List — CE Score: {score:.2f} — Mid Fair Entry: ${h_mid_fe:.2f} — Mid Fair Target: ${h_mid_ft:.2f} — Baseline snapshot reset ✅")

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
        st.markdown('<p class="mono" style="color:#8899aa; font-size:0.83rem;">A new verdict updates the Master Log in place. If BUY or HOLD, baseline snapshot resets automatically.</p>', unsafe_allow_html=True)
        with st.form("re_eval_form"):
            re_ticker  = st.text_input("Ticker Symbol *").upper().strip()
            re_verdict = st.selectbox("New Verdict", ["BUY", "HOLD", "PASS", "HARD_PASS"])
            re_notes   = st.text_area("Re-evaluation notes / reason for change")
            re_date    = st.text_input("Date", value=date.today().strftime("%b %d, %Y"))
            st.markdown("---")
            st.markdown('<p class="mono" style="color:#555e6e; font-size:0.8rem;">Fill in below ONLY if new verdict is BUY or HOLD — otherwise leave defaults.</p>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                re_price  = st.number_input("Current Price ($)", min_value=0.01, value=100.00, step=0.01)
                re_mid_up = st.number_input("Mid Upside (%)", min_value=0.0, value=40.0, step=0.5)
                re_mid_ft = st.number_input("Mid Fair Target ($)", min_value=0.01, value=150.00, step=0.01)
            with col2:
                re_mid_fe = st.number_input("Mid Fair Entry ($) — Hold only", min_value=0.01, value=80.00, step=0.01)
                re_inst   = st.selectbox("Institutional Money — Buy only",
                    ["Pending", "Strong absorption / aggressive buying",
                     "Neutral / choppy flow", "Distribution / selling pressure"])
            if st.form_submit_button("Submit Re-evaluation"):
                if not re_ticker:
                    st.error("Ticker is required.")
                else:
                    if re_verdict == "BUY":
                        add_or_update_buy(re_ticker, re_price, re_mid_up, re_mid_ft, re_inst, re_date, re_notes)
                        score = round(re_mid_up / re_price, 2)
                        st.success(f"✅ {re_ticker} → BUY | CE Score: {score:.2f} | Mid Fair Target: ${re_mid_ft:.2f} | Baseline reset ✅")
                    elif re_verdict == "HOLD":
                        add_or_update_hold(re_ticker, re_price, re_mid_up, re_mid_fe, re_mid_ft, re_date, re_notes)
                        score = round(re_mid_up / re_mid_fe, 2)
                        st.success(f"⚠️ {re_ticker} → HOLD | CE Score: {score:.2f} | Mid Fair Target: ${re_mid_ft:.2f} | Baseline reset ✅")
                    elif re_verdict == "PASS":
                        add_master_log(re_ticker, re_date, "PASS", re_notes, is_unified=1)
                        st.success(f"❌ {re_ticker} → PASS | Master Log updated.")
                    elif re_verdict == "HARD_PASS":
                        add_master_log(re_ticker, re_date, "HARD_PASS", re_notes, is_unified=1)
                        st.success(f"🚫 {re_ticker} → HARD PASS | Master Log updated.")

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
                c.execute("SELECT ticker,verdict,date_analyzed FROM master_log WHERE id=%s", (int(d_id),))
                row = c.fetchone()
                if row and row[0] == d_confirm:
                    c.execute("DELETE FROM master_log WHERE id=%s", (int(d_id),))
                    conn.commit()
                    st.success(f"Deleted: ID {int(d_id)} — {row[0]} | {row[1]} | {row[2]}")
                elif row and row[0] != d_confirm:
                    st.error(f"Ticker mismatch — row ID {int(d_id)} belongs to {row[0]}, not {d_confirm}.")
                else:
                    st.error(f"No row found with ID {int(d_id)}.")
                conn.close()

elif page == "Market Data Updates":
    st.markdown(
        '<div class="header-block" style="border-left:7px solid #2a7fff;">'
        '<h1 style="color:#2a7fff;">Market Data Updates</h1>'
        '<p class="mono" style="color:#8899aa; font-size:0.72rem;">'
        'Step 1: Hard Trigger Gate screens ALL tickers before any DB writes. '
        'Steps 2+: Price refresh + CE Score recalc + 3-tier routing — ✅ All Clear tickers only.'
        '</p></div>', unsafe_allow_html=True)

    if not YFINANCE_AVAILABLE:
        st.error("yfinance not installed. Run: pip install yfinance")
    else:
        st.markdown('<p class="mono" style="color:#3ddc84; font-size:0.72rem;">yfinance available ✅</p>', unsafe_allow_html=True)
    if not EDGAR_AVAILABLE:
        st.warning("EdgarTools not installed — SEC 8-K checks disabled. Run: pip install edgartools")
    else:
        st.markdown('<p class="mono" style="color:#3ddc84; font-size:0.72rem;">EdgarTools available ✅ — SEC 8-K monitor active (90-day lookback)</p>', unsafe_allow_html=True)

    def buy_html_table(df):
        hdr  = "background:#0a1f10; color:#e8e4d9; font-family:JetBrains Mono,monospace; font-size:0.82rem; font-weight:700; text-align:center; padding:0.5rem 0.4rem; border-bottom:2px solid #3ddc84;"
        cell = "color:#e8e4d9; font-family:JetBrains Mono,monospace; font-size:0.82rem; text-align:center; padding:0.6rem 0.5rem; border-bottom:1px solid #1a2a1a;"
        rows = "".join(
            f'<tr><td style="{cell}">{r["ticker"]}</td><td style="{cell}">${r["current_price"]:.2f}</td>'
            f'<td style="{cell}">{r["mid_upside"]:.1f}%</td><td style="{cell}">${r["mid_fair_target"]:.2f}</td>'
            f'<td style="{cell}"><em>{r["capital_efficiency_score"]:.2f}</em></td><td style="{cell}">{r["date_added"]}</td></tr>'
            for _, r in df.iterrows()
        )
        return (f'<div style="border:3px solid #3ddc84; border-left:7px solid #3ddc84; border-radius:5px; overflow:hidden;">'
                f'<table style="width:100%; border-collapse:collapse; background:#0d0f14;">'
                f'<thead><tr><th style="{hdr}">Ticker</th><th style="{hdr}">Price</th>'
                f'<th style="{hdr}">Mid Upside %</th><th style="{hdr}">Mid Fair Target</th>'
                f'<th style="{hdr}">CE Score</th><th style="{hdr}">Date</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div>')

    def hold_html_table(df):
        hdr  = "background:#2b2200; color:#e8e4d9; font-family:JetBrains Mono,monospace; font-size:0.82rem; font-weight:700; text-align:center; padding:0.5rem 0.4rem; border-bottom:2px solid #ffc947;"
        cell = "color:#e8e4d9; font-family:JetBrains Mono,monospace; font-size:0.82rem; text-align:center; padding:0.6rem 0.4rem; border-bottom:1px solid #2a2000;"
        rows = "".join(
            f'<tr><td style="{cell}">{r["ticker"]}</td><td style="{cell}">${r["current_price"]:.2f}</td>'
            f'<td style="{cell}">{r["mid_upside"]:.1f}%</td><td style="{cell}">${r["mid_fair_entry"]:.2f}</td>'
            f'<td style="{cell}">${r["mid_fair_target"]:.2f}</td><td style="{cell}"><em>{r["capital_efficiency_score"]:.2f}</em></td></tr>'
            for _, r in df.iterrows()
        )
        return (f'<div style="border:3px solid #ffc947; border-left:7px solid #ffc947; border-radius:5px; overflow:hidden;">'
                f'<table style="width:100%; border-collapse:collapse; background:#0d0f14;">'
                f'<thead><tr><th style="{hdr}">Ticker</th><th style="{hdr}">Price</th>'
                f'<th style="{hdr}">Mid Upside %</th><th style="{hdr}">Mid Fair Entry</th>'
                f'<th style="{hdr}">Mid Fair Target</th><th style="{hdr}">CE Score</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div>')

    col_a, col_b = st.columns([4, 5])
    with col_a:
        st.markdown('<h3 style="color:#3ddc84; font-family:JetBrains Mono,monospace; font-size:1.8rem; margin-bottom:0.4rem;">Current — Buy List</h3>', unsafe_allow_html=True)
        buy_df = get_buy_list()
        if not buy_df.empty:
            st.markdown(buy_html_table(buy_df), unsafe_allow_html=True)
    with col_b:
        st.markdown('<h3 style="color:#ffc947; font-family:JetBrains Mono,monospace; font-size:1.8rem; margin-bottom:0.4rem;">Current — Hold List</h3>', unsafe_allow_html=True)
        hold_df = get_hold_list()
        if not hold_df.empty:
            st.markdown(hold_html_table(hold_df), unsafe_allow_html=True)

    st.markdown("---")

    if st.button("RUN MARKET DATA UPDATE", type="primary"):
        with st.spinner("Step 1: Hard Trigger Gate — screening all tickers before any updates..."):
            result, error = run_market_data_update()

        if error:
            st.error(f"Error: {error}")
        elif result:
            st.success(f"Market Data Update complete — {result['timestamp']}")

            if result["blocked"]:
                st.markdown("---")
                st.markdown(
                    '<div class="metric-card" style="border:2px solid #ff6b6b; border-left:7px solid #ff6b6b;">'
                    '<p class="mono" style="color:#ff6b6b; font-weight:700; margin:0;">🚫 HARD TRIGGER GATE — TICKERS HELD PENDING MANUAL REVIEW</p>'
                    '<p class="mono" style="color:#8899aa; font-size:0.78rem; margin:0.3rem 0;">Frozen in current position. Zero DB writes. Resolve flags before next update.</p>'
                    '</div>', unsafe_allow_html=True)
                for ticker, flags in result["blocked"].items():
                    flag_html = "".join(
                        f'<p class="trigger-block" style="margin:0.2rem 0 0.2rem 1rem;">{f}</p>'
                        for f in flags
                    )
                    st.markdown(
                        f'<div class="metric-card" style="border-left:7px solid #ff6b6b; margin-bottom:0.4rem;">'
                        f'<p class="mono" style="color:#ff6b6b; font-weight:700; margin:0 0 0.4rem 0;">🔒 {ticker} — FROZEN</p>'
                        f'{flag_html}</div>', unsafe_allow_html=True)

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ✅ Buy List Updates")
                if result["buy"]:
                    for t, old, new, upside, status in result["buy"]:
                        if new:
                            delta = new - old
                            color = "#3ddc84" if delta >= 0 else "#ff6b6b"
                            ds = f"+${delta:.2f}" if delta >= 0 else f"-${abs(delta):.2f}"
                            st.markdown(f'<p class="mono"><strong>{t}</strong>: ${old:.2f} → <span style="color:{color};">${new:.2f} ({ds})</span> &nbsp;|&nbsp; Upside: <span style="color:#3ddc84;">{upside:.1f}%</span></p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p class="mono" style="color:#8899aa;"><strong>{t}</strong>: price unavailable</p>', unsafe_allow_html=True)
                else:
                    st.markdown('<p class="mono" style="color:#8899aa;">No clear Buy tickers this cycle.</p>', unsafe_allow_html=True)
            with col2:
                st.markdown("#### ✅ Hold List Updates")
                if result["hold"]:
                    for t, old, new, upside, status in result["hold"]:
                        if new:
                            delta = new - old
                            color = "#3ddc84" if delta >= 0 else "#ff6b6b"
                            ds = f"+${delta:.2f}" if delta >= 0 else f"-${abs(delta):.2f}"
                            st.markdown(f'<p class="mono"><strong>{t}</strong>: ${old:.2f} → <span style="color:{color};">${new:.2f} ({ds})</span> &nbsp;|&nbsp; Upside: <span style="color:#ffc947;">{upside:.1f}%</span></p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p class="mono" style="color:#8899aa;"><strong>{t}</strong>: price unavailable</p>', unsafe_allow_html=True)
                else:
                    st.markdown('<p class="mono" style="color:#8899aa;">No clear Hold tickers this cycle.</p>', unsafe_allow_html=True)

            st.markdown("---")
            has_tier = any([result["auto_upgraded"], result["auto_downgraded"],
                            result["auto_retired_buy"], result["auto_retired_hold"]])
            if has_tier:
                st.markdown("#### 🔀 Universal 3-Tier Defense — Auto-Actions (✅ All Clear tickers only)")
                if result["auto_upgraded"]:
                    st.markdown('<p class="mono" style="color:#3ddc84; font-weight:700;">✅ AUTO-UPGRADED → Buy List</p>', unsafe_allow_html=True)
                    for t, old, new, upside in result["auto_upgraded"]:
                        st.markdown(f'<p class="mono" style="color:#3ddc84;">▲ <strong>{t}</strong>: ${old:.2f} → ${new:.2f} &nbsp;|&nbsp; Mid Upside reached {upside:.1f}% — moved to Buy List. Institutional: Pending.</p>', unsafe_allow_html=True)
                if result["auto_downgraded"]:
                    st.markdown('<p class="mono" style="color:#ffc947; font-weight:700;">⚠️ AUTO-DOWNGRADED → Hold List</p>', unsafe_allow_html=True)
                    for t, old, new, upside, mid_fe in result["auto_downgraded"]:
                        st.markdown(f'<p class="mono" style="color:#ffc947;">▼ <strong>{t}</strong>: ${old:.2f} → ${new:.2f} &nbsp;|&nbsp; Mid Upside compressed to {upside:.1f}% — moved to Hold List. Mid Fair Entry: ${mid_fe:.2f}</p>', unsafe_allow_html=True)
                if result["auto_retired_buy"]:
                    st.markdown('<p class="mono" style="color:#ff6b6b; font-weight:700;">🚫 AUTO-RETIRED from Buy List → Master Log (PASS)</p>', unsafe_allow_html=True)
                    for t, old, new, upside in result["auto_retired_buy"]:
                        st.markdown(f'<p class="mono" style="color:#ff6b6b;">✗ <strong>{t}</strong>: ${old:.2f} → ${new:.2f} &nbsp;|&nbsp; Mid Upside fell to {upside:.1f}% — below 35% threshold.</p>', unsafe_allow_html=True)
                if result["auto_retired_hold"]:
                    st.markdown('<p class="mono" style="color:#ff6b6b; font-weight:700;">🚫 AUTO-RETIRED from Hold List → Master Log (PASS)</p>', unsafe_allow_html=True)
                    for t, old, new, upside in result["auto_retired_hold"]:
                        st.markdown(f'<p class="mono" style="color:#ff6b6b;">✗ <strong>{t}</strong>: ${old:.2f} → ${new:.2f} &nbsp;|&nbsp; Mid Upside fell to {upside:.1f}% — below 35% threshold.</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="mono" style="color:#3ddc84;">✅ 3-Tier Defense — All Clear — no tier changes this cycle</p>', unsafe_allow_html=True)

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
                    c.execute("SELECT mid_upside, mid_fair_target FROM buy_list WHERE ticker=%s", (mp_ticker,))
                    row = c.fetchone()
                    conn.close()
                    if row:
                        new_mid_up = round((row[1] - mp_price) / mp_price * 100, 2) if mp_price > 0 and row[1] > 0 else row[0]
                        new_score  = round(new_mid_up / mp_price, 2)
                        update_price_in_db("buy_list", mp_ticker, mp_price, new_score, new_mid_up)
                        st.success(f"{mp_ticker} updated to ${mp_price:.2f} — Mid Upside: {new_mid_up:.1f}% — CE Score: {new_score:.2f}")
                    else:
                        st.error(f"{mp_ticker} not found in Buy List.")
                else:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT mid_upside, mid_fair_target, mid_fair_entry FROM hold_list WHERE ticker=%s", (mp_ticker,))
                    row = c.fetchone()
                    conn.close()
                    if row:
                        new_mid_up = round((row[1] - mp_price) / mp_price * 100, 2) if mp_price > 0 and row[1] > 0 else row[0]
                        new_score  = round(new_mid_up / row[2], 2) if row[2] > 0 else 0
                        update_price_in_db("hold_list", mp_ticker, mp_price, new_score, new_mid_up)
                        st.success(f"{mp_ticker} updated to ${mp_price:.2f} — Mid Upside: {new_mid_up:.1f}% — CE Score: {new_score:.2f}")
                    else:
                        st.error(f"{mp_ticker} not found in Hold List.")

# Updated: June 27, 2026 — 11:45 AM — Dream Team 💙🦋
