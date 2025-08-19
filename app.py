import streamlit as st
import sqlite3
import jwt
import datetime
import pandas as pd

# ==============================
# Config & Demo Users
# ==============================
JWT_SECRET = "change-me-please"
JWT_ALG = "HS256"
JWT_EXP_MIN = 120

USERS = {
    "analyst": {"password": "analyst123", "role": "analyst"},
    "admin": {"password": "admin123", "role": "admin"},
}

DB_PATH = "survey.db"

# ==============================
# DB Setup (auto-seed)
# ==============================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS states (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            name TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY,
            state TEXT,
            age INTEGER,
            gender TEXT,
            unemployed INTEGER
        )
    """)
    conn.commit()

    # seed states
    cur.execute("SELECT COUNT(1) FROM states")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO states (code, name) VALUES (?, ?)", [
            ("TN", "Tamil Nadu"),
            ("KA", "Karnataka"),
            ("MH", "Maharashtra"),
            ("DL", "Delhi"),
        ])
    # seed survey
    cur.execute("SELECT COUNT(1) FROM survey_responses")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO survey_responses (state, age, gender, unemployed) VALUES (?, ?, ?, ?)", [
            ("TN", 22, "Female", 1),
            ("TN", 31, "Male", 0),
            ("KA", 27, "Female", 1),
            ("KA", 45, "Male", 1),
            ("MH", 36, "Female", 0),
            ("DL", 29, "Male", 1),
            ("MH", 19, "Female", 1),
            ("TN", 41, "Female", 0),
            ("DL", 33, "Female", 1),
            ("KA", 28, "Male", 0),
        ])
    conn.commit()
    conn.close()

init_db()

# ==============================
# JWT Helpers
# ==============================
def create_token(username, role):
    exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXP_MIN)
    payload = {"sub": username, "role": role, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None

# ==============================
# Streamlit App
# ==============================
st.set_page_config(page_title="Survey SQL API Gateway", layout="wide")

st.title("📊 Survey SQL API Gateway (Streamlit Edition)")

if "token" not in st.session_state:
    st.session_state.token = None

# --- Login Form ---
if not st.session_state.token:
    with st.form("login_form"):
        st.subheader("🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

    if submit:
        user = USERS.get(username)
        if user and user["password"] == password:
            token = create_token(username, user["role"])
            st.session_state.token = token
            st.success(f"Logged in as {username} ({user['role']})")
        else:
            st.error("Invalid username or password")
    st.stop()

# --- After Login ---
payload = decode_token(st.session_state.token)
if not payload:
    st.error("Session expired. Please login again.")
    st.session_state.token = None
    st.stop()

st.sidebar.success(f"✅ Logged in as {payload['sub']} ({payload['role']})")

# --- Query Input ---
st.subheader("📝 Run SQL Query")
sql = st.text_area("Write a SELECT query (only SELECT allowed):", 
                   "SELECT state, COUNT(*) AS n FROM survey_responses GROUP BY state ORDER BY n DESC")
limit = st.number_input("Limit", 1, 500, 50)
offset = st.number_input("Offset", 0, 1000, 0)

if st.button("▶ Run Query"):
    if not sql.strip().lower().startswith("select"):
        st.error("❌ Only SELECT queries are allowed!")
    else:
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql_query(f"SELECT * FROM ({sql}) LIMIT ? OFFSET ?", conn, params=(limit, offset))
            conn.close()
            st.success(f"✅ Query successful! Rows returned: {len(df)}")
            st.dataframe(df, use_container_width=True)
            st.download_button("⬇ Download JSON", df.to_json(orient="records"), "results.json")
        except Exception as e:
            st.error(f"Query failed: {e}")
