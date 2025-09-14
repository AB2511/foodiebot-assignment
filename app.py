import streamlit as st
from chat_engine import generate_response, log_conversation, query_database
import pandas as pd
import sqlite3
import uuid
import matplotlib.pyplot as plt

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- Session State ----------
if 'context' not in st.session_state:
    st.session_state.context = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'interest_scores' not in st.session_state:
    st.session_state.interest_scores = []

st.title("🍔 FoodieBot Chat & Analytics")
user_input = st.text_input("Chat with FoodieBot:")

# ---------- Chat Handling ----------
if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input, st.session_state.context)
    log_conversation(user_input, response, interest)
    st.session_state.chat_history.append(("You", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"

# ---------- Display Chat ----------
for role, msg in st.session_state.chat_history:
    if role == "You":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ---------- Analytics Sidebar ----------
st.sidebar.title("📊 Analytics Dashboard")

# Conversation data
conn = sqlite3.connect('foodiebot.db')
df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id", conn)
conn.close()

if not df.empty:
    st.sidebar.subheader("Interest Progression")
    fig, ax = plt.subplots()
    ax.plot(range(1, len(df)+1), df['interest_score'], marker='o', color='green')
    ax.set_xlabel("Conversation Turn")
    ax.set_ylabel("Interest Score (%)")
    ax.set_ylim(0, 100)
    st.sidebar.pyplot(fig)

    avg_interest = df['interest_score'].mean()
    st.sidebar.write(f"Average Interest: **{avg_interest:.2f}%**")

# DB Status
st.sidebar.title("📦 Database Status")
conn = sqlite3.connect('foodiebot.db')
products_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category", conn)
total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
conn.close()
st.sidebar.write(f"Total Products: **{total_products}**")
st.sidebar.dataframe(products_df, height=250)

# Last 5 queries
st.sidebar.subheader("Last 5 Queries")
if not df.empty:
    st.sidebar.write(df[['user_message', 'bot_response']].tail(5))
