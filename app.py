import streamlit as st
from chat_engine import generate_response, log_conversation
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

st.title("FoodieBot Chat & Analytics")

if 'context' not in st.session_state:
    st.session_state.context = ""
    st.session_state.interest = 0

user_input = st.text_input("Chat with FoodieBot:")
if user_input:
    response, interest = generate_response(user_input, st.session_state.context)
    st.write(f"Bot: {response}")
    st.write(f"Interest Score: {interest}%")
    log_conversation(user_input, response, interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"
    st.session_state.interest = interest

# Analytics Sidebar
st.sidebar.title("Analytics Dashboard")
conn = sqlite3.connect('foodiebot.db')
df = pd.read_sql_query("SELECT * FROM conversations", conn)
conn.close()

if not df.empty:
    st.sidebar.write("Interest Progression Graph:")
    fig, ax = plt.subplots()
    ax.plot(df['interest_score'])
    ax.set_xlabel('Conversation Turns')
    ax.set_ylabel('Interest Score')
    st.sidebar.pyplot(fig)

    # Calculate average excluding initial 0% if present
    valid_scores = df['interest_score'][df['interest_score'] > 0]
    avg_interest = valid_scores.mean() if not valid_scores.empty else 0.00
    st.sidebar.write(f"Average Interest: {avg_interest:.2f}%")
    # Count unique dietary mentions
    dietary_mentions = set()
    for msg in df['user_message']:
        if 'vegetarian' in msg.lower():
            dietary_mentions.add('vegetarian')
        if 'spicy' in msg.lower():
            dietary_mentions.add('spicy')
        if 'curry' in msg.lower():
            dietary_mentions.add('curry')
    st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_mentions) if dietary_mentions else 'None'}")

# Database Admin Panel
st.sidebar.title("Product Admin")
products_df = pd.read_sql_query("SELECT * FROM products", sqlite3.connect('foodiebot.db'))
st.sidebar.dataframe(products_df)