import streamlit as st
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# ---------- Session State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

# ---------- User Input ----------
user_input = st.text_input("Type your message here:", "")

if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input)
    log_conversation(user_input, response, interest)
    st.session_state.chat_history.append(("User", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)

# ---------- Chat Display ----------
for role, msg in st.session_state.chat_history:
    if role == "User":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ---------- Sidebar Analytics ----------
st.sidebar.title("📊 Analytics Dashboard")
if st.session_state.interest_scores:
    avg_interest = sum(st.session_state.interest_scores)/len(st.session_state.interest_scores)
    st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")
    st.sidebar.subheader("Interest Progression")
    st.sidebar.line_chart(st.session_state.interest_scores)
else:
    st.sidebar.metric("Average Interest", "0.00%")

# Unique dietary mentions
dietary_set = set()
for msg in [m for r,m in st.session_state.chat_history if r=="User"]:
    for word in ["vegetarian","vegan","spicy"]:
        if word in msg.lower():
            dietary_set.add(word)
st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_set) if dietary_set else 'None'}")

# Database Status
st.sidebar.title("📦 Database Status")
try:
    products = query_database({"keyword": ""})
    st.sidebar.write(f"Total Products: {len(products)}")
except Exception as e:
    st.sidebar.error(f"Database check failed: {e}")

# Last 5 queries
st.sidebar.subheader("Last 5 Queries")
last_5 = st.session_state.chat_history[-10:]  # pairs: User+Bot
for i in range(0,len(last_5),2):
    user_msg = last_5[i][1]
    bot_msg = last_5[i+1][1] if i+1<len(last_5) else ""
    st.sidebar.markdown(f"User: {user_msg}\nBot: {bot_msg}")
