import streamlit as st
from chat_engine import generate_response, query_database
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import uuid

# ---------- Streamlit Setup ----------
st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# ---------- Session State ----------
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # list of tuples (role, message)
if 'interest_scores' not in st.session_state:
    st.session_state.interest_scores = []

# ---------- User Input ----------
user_input = st.text_input("Chat with FoodieBot:", "")
if st.button("Send") and user_input.strip():
    # Generate bot response
    response = generate_response(user_input)
    
    # Log chat in session
    st.session_state.chat_history.append(("User", user_input))
    st.session_state.chat_history.append(("Bot", response))
    
    # Reset input box
    st.experimental_rerun()

# ---------- Chat Display ----------
st.subheader("💬 Conversation")
for role, msg in st.session_state.chat_history:
    if role == "User":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ---------- Sidebar: Analytics & DB ----------
st.sidebar.title("📊 Analytics Dashboard")

# Interest Score Progression
if st.session_state.chat_history:
    # Calculate dummy interest: here just a placeholder (you can compute real scores later)
    st.sidebar.subheader("Interest Progression")
    interest_scores = [10 if role=="Bot" else 0 for role, _ in st.session_state.chat_history]
    st.sidebar.line_chart(interest_scores)
    avg_interest = sum(interest_scores)/len(interest_scores)
    st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")
else:
    st.sidebar.metric("Average Interest", "0.00%")

# Unique dietary mentions
dietary_set = set()
for role, msg in st.session_state.chat_history:
    m = msg.lower()
    for tag in ["vegetarian", "vegan", "spicy", "curry", "burger", "pizza", "wrap", "salad"]:
        if tag in m:
            dietary_set.add(tag)
st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_set) if dietary_set else 'None'}")

# Database Status
st.sidebar.title("📦 Database Status")
try:
    conn = sqlite3.connect('foodiebot.db')
    products_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category", conn)
    total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
    conn.close()
    st.sidebar.write(f"Total Products: **{total_products}**")
    st.sidebar.dataframe(products_df, height=200)
except sqlite3.Error as e:
    st.sidebar.error(f"Error loading products: {e}. Make sure 'foodiebot.db' exists.")

# Last 5 User Queries
st.sidebar.subheader("Last 5 Queries")
user_msgs = [msg for role, msg in st.session_state.chat_history if role=="User"]
if user_msgs:
    for msg in user_msgs[-5:]:
        st.sidebar.write(msg)
