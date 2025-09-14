import streamlit as st
from chat_engine import generate_response, log_conversation, query_database
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import uuid

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- Session State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ---------- Main UI ----------
st.title("🍔 FoodieBot Chat & Analytics")
user_input = st.text_input("Chat with FoodieBot:", "")

if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input)
    log_conversation(user_input, response, interest)
    st.session_state.chat_history.append(("User", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)

# Display chat
for role, msg in st.session_state.chat_history:
    if role == "User":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ---------- Sidebar ----------
st.sidebar.title("📊 Analytics Dashboard")

# Load conversations from DB
try:
    conn = sqlite3.connect('foodiebot.db')
    df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id", conn)
    conn.close()
except Exception as e:
    st.sidebar.error(f"Failed to load conversations: {e}")
    df = pd.DataFrame()

# Interest metrics
if not df.empty:
    st.sidebar.subheader("Interest Progression")
    fig, ax = plt.subplots()
    ax.plot(range(1, len(df)+1), df['interest_score'], marker='o', color='green')
    ax.set_xlabel('Conversation Turns')
    ax.set_ylabel('Interest Score (%)')
    ax.set_ylim(0, 100)
    st.sidebar.pyplot(fig)

    avg_interest = df['interest_score'].mean()
    st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")

    # Unique dietary mentions
    dietary_mentions = set()
    for msg in df['user_message']:
        for tag in ['vegetarian', 'vegan', 'spicy', 'curry']:
            if tag in msg.lower():
                dietary_mentions.add(tag)
    st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_mentions) if dietary_mentions else 'None'}")

    # Last 5 queries
    st.sidebar.subheader("Last 5 User Queries")
    st.sidebar.write(df[['user_message', 'bot_response']].tail(5))
else:
    st.sidebar.write("No conversation data yet.")

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
    st.sidebar.error(f"Error loading products: {e}")

# Optional: Scrollable display of last DB matches
st.sidebar.subheader("Last 5 Matches")
if user_input.strip():
    filters = {"keyword": user_input}
    products_list = query_database(filters)
    if products_list:
        for prod in products_list[:5]:
            st.sidebar.markdown(f"**{prod[1]}** ({prod[2]}) — ${prod[3]}, Spice {prod[4]}/10")
            st.sidebar.markdown(f"*Tags:* {prod[6]}")
            st.sidebar.markdown("---")
    else:
        st.sidebar.write("No matching products found.")
