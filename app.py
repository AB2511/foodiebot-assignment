import streamlit as st
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

# ---------- UI ----------
st.title("🍔 FoodieBot Chat & Analytics")
st.write("Chat with FoodieBot:")

user_input = st.text_input("Type your message here:", "")

if st.button("Send") and user_input.strip():
    # Generate response from chat_engine
    response, interest = generate_response(user_input)

    # Log conversation
    log_conversation(user_input, response, interest)

    # Save to session
    st.session_state.chat_history.append(("User", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)

# ---------- Chat Display ----------
for role, msg in st.session_state.chat_history:
    if role == "User":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ---------- Analytics ----------
st.subheader("📊 Analytics Dashboard")

if st.session_state.interest_scores:
    avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
    st.metric("Average Interest", f"{avg_interest:.2f}%")
else:
    st.metric("Average Interest", "0.00%")

# Interest progression graph
if st.session_state.interest_scores:
    st.line_chart(st.session_state.interest_scores)

# ---------- DB Status ----------
st.subheader("📦 Database Status")

try:
    products = query_database({"keyword": ""})
    st.write(f"Total Products: {len(products)}")
except Exception as e:
    st.error(f"Database check failed: {e}")
