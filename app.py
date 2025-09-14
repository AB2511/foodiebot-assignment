# app.py
import streamlit as st
import uuid
import sqlite3
import pandas as pd
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# ---------- session state ----------
if "context" not in st.session_state:
    st.session_state.context = ""
    st.session_state.session_id = str(uuid.uuid4())
if "last_results" not in st.session_state:
    st.session_state.last_results = []

# ---------- user input ----------
col1, col2 = st.columns([3, 1])
with col1:
    user_input = st.text_input("Type your message here:", key="user_input")
with col2:
    send = st.button("Send")

if send and user_input and user_input.strip():
    response, interest = generate_response(user_input, st.session_state.context)
    log_conversation(user_input, response, interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"
    st.session_state.last_user = user_input
    st.session_state.last_response = response
    st.session_state.last_interest = interest

# ---------- main chat area ----------
st.subheader("Chat")
if 'last_response' in st.session_state and st.session_state.get('last_user'):
    st.markdown(f"**You:** {st.session_state.get('last_user')}")
    st.markdown(f"**Bot:** {st.session_state.get('last_response')}")
    st.markdown(f"**Interest Score:** {st.session_state.get('last_interest', 0)}%")

# Also show quick search preview (db results)
if user_input:
    filters = {'keyword': user_input, 'context': st.session_state.context}
    # We rely on chat_engine.RULES in chat_engine; but keep this minimal - we only want preview
    results = query_database(filters)
    st.subheader("Search Preview (top matches)")
    if not results:
        st.info("No matching products found in database. Try different keywords or relax constraints.")
    else:
        for r in results:
            pid, name, category, price, spice, descr, tags = r
            st.markdown(f"**{name}** — *{category}* — ${price:.2f} — Spice {spice}/10")
            st.caption(f"{descr}")
            if tags:
                st.write(f"**Tags:** {tags}")
            st.markdown("---")

# ---------- Analytics sidebar ----------
st.sidebar.title("📊 Analytics Dashboard")

# Conversations table
try:
    conn = sqlite3.connect("foodiebot.db")
    df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id DESC", conn)
    conn.close()
except Exception as e:
    st.sidebar.error(f"Error loading conversation log: {e}")
    df = pd.DataFrame()

if not df.empty:
    # Interest progression (latest 30)
    interest_series = df['interest_score'].fillna(0).astype(int).tolist()[::-1]  # chronological
    st.sidebar.subheader("Interest Progression")
    st.sidebar.line_chart(interest_series)

    # Average interest (non-zero)
    valid_scores = [x for x in df['interest_score'] if x and x > 0]
    avg_interest = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
    st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")

    # Dietary mentions extraction
    dietary = set()
    for msg in df['user_message'].astype(str):
        m = msg.lower()
        if 'vegetarian' in m:
            dietary.add('vegetarian')
        if 'vegan' in m:
            dietary.add('vegan')
        if 'spicy' in m:
            dietary.add('spicy')
        if 'curry' in m:
            dietary.add('curry')
    st.sidebar.write("Unique Dietary Mentions:")
    st.sidebar.write(", ".join(sorted(dietary)) if dietary else "None")
else:
    st.sidebar.info("No conversation data yet.")

# DB health
st.sidebar.subheader("Database Status")
try:
    conn = sqlite3.connect("foodiebot.db")
    products_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category ORDER BY count DESC", conn)
    total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
    conn.close()
    st.sidebar.write(f"Total Products: **{total_products}**")
    st.sidebar.dataframe(products_df, height=220)
except Exception as e:
    st.sidebar.error(f"Error loading products: {e}")

# ---------- quick test buttons ----------
st.sidebar.subheader("Quick tests")
if st.sidebar.button("Show me burgers"):
    st.session_state['user_input_temp'] = "show me burgers"
    st.experimental_rerun()
if st.sidebar.button("I want vegan wraps"):
    st.session_state['user_input_temp'] = "I want vegan wraps"
    st.experimental_rerun()

# If sidebar quick test used
if 'user_input_temp' in st.session_state:
    ui = st.session_state.pop('user_input_temp')
    resp, score = generate_response(ui, st.session_state.context)
    log_conversation(ui, resp, score)
    st.session_state.context += f"User: {ui}\nBot: {resp}\n"
    st.markdown(f"**You:** {ui}")
    st.markdown(f"**Bot:** {resp}")
    st.markdown(f"**Interest Score:** {score}%")
