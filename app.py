import streamlit as st
from chat_engine import generate_response, log_conversation, query_database
import pandas as pd
import sqlite3

# ----------------- Page Config -----------------
st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# ----------------- Session State -----------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

if "context" not in st.session_state:
    st.session_state.context = ""

# ----------------- Chat Input -----------------
user_input = st.text_input("Type your message here:")

if user_input.strip():
    # Generate response
    response, interest = generate_response(user_input, st.session_state.context)

    # Log conversation to DB
    log_conversation(user_input, response, interest)

    # Save in session
    st.session_state.chat_history.append(("User", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"

# ----------------- Display Chat -----------------
st.subheader("💬 Chat")
for role, msg in st.session_state.chat_history:
    if role == "User":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ----------------- Sidebar Analytics -----------------
st.sidebar.title("📊 Analytics Dashboard")

# Interest progression graph
st.sidebar.subheader("Interest Progression")
if st.session_state.interest_scores:
    st.sidebar.line_chart(st.session_state.interest_scores)
    avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
    st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")
else:
    st.sidebar.metric("Average Interest", "0.00%")

# Unique dietary mentions
st.sidebar.subheader("Unique Dietary Mentions")
dietary_mentions = set()
for msg in [m for r, m in st.session_state.chat_history if r=="User"]:
    m = msg.lower()
    for keyword in ['vegetarian', 'vegan', 'spicy', 'curry', 'burger', 'pizza', 'wrap', 'salad']:
        if keyword in m:
            dietary_mentions.add(keyword)
st.sidebar.write(", ".join(dietary_mentions) if dietary_mentions else "None")

# ----------------- Database Status -----------------
st.sidebar.subheader("📦 Database Status")
try:
    conn = sqlite3.connect('foodiebot.db')
    products_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category", conn)
    total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
    conn.close()
    st.sidebar.write(f"Total Products: **{total_products}**")
    st.sidebar.dataframe(products_df, height=200)
except Exception as e:
    st.sidebar.error(f"Database error: {e}")

# ----------------- Last 5 Queries -----------------
st.sidebar.subheader("Last 5 Queries")
if st.session_state.chat_history:
    last5 = [f"{r}: {m}" for r, m in st.session_state.chat_history[-10:]]
    st.sidebar.write("\n".join(last5))

# ----------------- Optional: Display Products -----------------
st.sidebar.subheader("Search Preview")
if user_input.strip():
    filters = {'keyword': user_input, 'context': st.session_state.context}
    products_list = query_database(filters)
    if products_list:
        for prod in products_list:
            st.sidebar.markdown(f"**{prod[1]} ({prod[2]})** — ${prod[3]}, Spice {prod[4]}/10")
            st.sidebar.markdown(f"{prod[5]}")
            st.sidebar.markdown(f"*Tags:* {prod[6]}")
            st.sidebar.markdown("---")
    else:
        st.sidebar.info("No matching products found in database.")
