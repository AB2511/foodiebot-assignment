import streamlit as st
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- Session State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

# ---------- Sidebar ----------
st.sidebar.title("📊 Analytics Dashboard")
if st.session_state.interest_scores:
    avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
    st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")
    st.sidebar.line_chart(st.session_state.interest_scores)
else:
    st.sidebar.metric("Average Interest", "0.00%")

# Unique dietary mentions
dietary_mentions = set()
for _, msg in st.session_state.chat_history:
    for keyword in ["vegan", "vegetarian"]:
        if keyword in msg.lower():
            dietary_mentions.add(keyword)
st.sidebar.write(f"Unique Dietary Mentions: {', '.join(dietary_mentions) or 'None'}")

# Database status
try:
    products = query_database({"keyword": ""})
    st.sidebar.write(f"Total Products: {len(products)}")
except:
    st.sidebar.write("Database check failed")

# ---------- Main Chat ----------
st.title("🍔 FoodieBot Chat & Analytics")
user_input = st.text_input("Type your message here:", "")

if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input)
    log_conversation(user_input, response, interest)
    st.session_state.chat_history.append(("You", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)

# ---------- Display Chat ----------
for role, msg in st.session_state.chat_history:
    if role == "You":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")
