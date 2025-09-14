import streamlit as st
from chat_engine import generate_response, log_conversation
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import uuid

st.title("FoodieBot Chat & Analytics")

# Track context + session
if 'context' not in st.session_state:
    st.session_state.context = ""
    st.session_state.session_id = str(uuid.uuid4())

user_input = st.text_input("Chat with FoodieBot:")
if user_input:
    response, interest = generate_response(user_input, st.session_state.context)
    st.write(f"Bot: {response}")
    st.write(f"Interest Score: {interest}%")
    log_conversation(user_input, response, interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"

# Analytics Sidebar
st.sidebar.title("Analytics Dashboard")

conn = sqlite3.connect('foodiebot.db')
df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id", conn)
conn.close()

if not df.empty:
    st.sidebar.write("Interest Progression Graph:")
    fig, ax = plt.subplots()
    ax.plot(range(1, len(df) + 1), df['interest_score'])
    ax.set_xlabel('Conversation Turns')
    ax.set_ylabel('Interest Score')
    st.sidebar.pyplot(fig)

    valid_scores = df['interest_score'][df['interest_score'] > 0]
    avg_interest = valid_scores.mean() if not valid_scores.empty else 0.00
    st.sidebar.write(f"Average Interest: {avg_interest:.2f}%")

    dietary_mentions = set()
    for msg in df['user_message']:
        if 'vegetarian' in msg.lower():
            dietary_mentions.add('vegetarian')
        if 'spicy' in msg.lower():
            dietary_mentions.add('spicy')
        if 'curry' in msg.lower():
            dietary_mentions.add('curry')
    st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_mentions) if dietary_mentions else 'None'}")

# DB Healthcheck
st.sidebar.title("Database Status")
try:
    conn = sqlite3.connect('foodiebot.db')
    products_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category", conn)
    total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
    conn.close()

    st.sidebar.write(f"Total Products: {total_products}")
    st.sidebar.dataframe(products_df)
except sqlite3.Error as e:
    st.sidebar.error(f"Error loading products: {e}. Run setup_db.py to create DB.")
