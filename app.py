import streamlit as st
from chat_engine import generate_response, log_conversation, RULES, query_database
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import uuid

st.set_page_config(page_title="FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# Track session + context
if 'context' not in st.session_state:
    st.session_state.context = ""
    st.session_state.session_id = str(uuid.uuid4())

# ---------- User Chat ----------
user_input = st.text_input("Chat with FoodieBot:", key="user_input")
if user_input:
    response, interest = generate_response(user_input, st.session_state.context)
    st.markdown(f"**Bot:** {response}")
    st.markdown(f"**Interest Score:** {interest}%")
    log_conversation(user_input, response, interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"

# ---------- Analytics Sidebar ----------
st.sidebar.title("📊 Analytics Dashboard")

# Load conversation data
conn = sqlite3.connect('foodiebot.db')
df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id", conn)
conn.close()

if not df.empty:
    # Interest progression graph
    st.sidebar.subheader("Interest Progression Graph")
    fig, ax = plt.subplots()
    ax.plot(range(1, len(df)+1), df['interest_score'], marker='o', color='green')
    ax.set_xlabel('Conversation Turns')
    ax.set_ylabel('Interest Score (%)')
    ax.set_ylim(0, 100)
    st.sidebar.pyplot(fig)

    # Average interest
    valid_scores = df['interest_score'][df['interest_score'] > 0]
    avg_interest = valid_scores.mean() if not valid_scores.empty else 0.0
    st.sidebar.write(f"Average Interest: **{avg_interest:.2f}%**")

    # Unique dietary mentions
    dietary_mentions = set()
    for msg in df['user_message']:
        msg_lower = msg.lower()
        if 'vegetarian' in msg_lower:
            dietary_mentions.add('vegetarian')
        if 'vegan' in msg_lower:
            dietary_mentions.add('vegan')
        if 'spicy' in msg_lower:
            dietary_mentions.add('spicy')
        if 'curry' in msg_lower:
            dietary_mentions.add('curry')
    st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_mentions) if dietary_mentions else 'None'}")

# ---------- Database Status ----------
st.sidebar.title("📦 Database Status")
try:
    conn = sqlite3.connect('foodiebot.db')
    products_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category", conn)
    total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
    conn.close()

    st.sidebar.write(f"Total Products: **{total_products}**")
    st.sidebar.dataframe(products_df, height=200)
except sqlite3.Error as e:
    st.sidebar.error(f"Error loading products: {e}. Run setup_db.py to create DB.")

# ---------- Optional: Show last few queries ----------
st.sidebar.subheader("Last 5 User Queries")
if not df.empty:
    st.sidebar.write(df[['user_message', 'bot_response']].tail(5))

# ---------- Optional: Scrollable product display ----------
def display_products(products_list):
    if not products_list:
        st.info("No matching products found in our database. Try adjusting your query.")
        return
    for prod in products_list:
        st.markdown(f"**{prod[1]}** (${prod[2]:.2f}) — Spice {prod[3]}/10")
        st.markdown(f"{prod[4]}")
        st.markdown(f"*Tags:* {prod[5]}")
        st.markdown("---")

if user_input:
    # Query DB separately to show results neatly
    filters = {'keyword': user_input, 'context': st.session_state.context}
    for keyword, rule in RULES.items():
        if keyword in user_input.lower():
            filters.update(rule)
    products_list = query_database(filters)
    display_products(products_list)
