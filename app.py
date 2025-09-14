import streamlit as st
from chat_engine import generate_response, log_conversation
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

st.title("FoodieBot Chat & Analytics")

if 'context' not in st.session_state:
    st.session_state.context = ""
    st.session_state.interest = 0
    st.session_state.turn = 0

user_input = st.text_input("Chat with FoodieBot:")
if user_input:
    response, interest = generate_response(user_input, st.session_state.context)
    st.write(f"Bot: {response}")
    st.write(f"Interest Score: {interest}%")
    log_conversation(user_input, response, interest)
    st.session_state.context += f"User: {user_input}\nBot: {response}\n"
    st.session_state.interest = interest
    st.session_state.turn += 1

# Analytics Sidebar
st.sidebar.title("Analytics Dashboard")
# Ensure database is created if not exists
conn = sqlite3.connect('foodiebot.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_message TEXT,
        bot_response TEXT,
        interest_score INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id", conn)  # Use id for turn order
conn.close()

if not df.empty:
    st.sidebar.write("Interest Progression Graph:")
    fig, ax = plt.subplots()
    ax.plot(range(len(df)), df['interest_score'])  # Use range for turns
    ax.set_xlabel('Conversation Turns')
    ax.set_ylabel('Interest Score')
    st.sidebar.pyplot(fig)

    # Calculate average excluding 0% scores
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

# Database Admin Panel with error handling
st.sidebar.title("Product Admin")
try:
    conn = sqlite3.connect('foodiebot.db')
    products_df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    st.sidebar.dataframe(products_df)
except sqlite3.Error as e:
    st.sidebar.write("Error loading products: Database or table 'products' may not be initialized. Run setup_db.py locally to create it.")
