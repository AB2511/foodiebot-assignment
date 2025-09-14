import streamlit as st
from chat_engine import get_response  # your existing chat logic

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# --- Initialize session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "queued_input" not in st.session_state:
    st.session_state.queued_input = None

if "user_input_box" not in st.session_state:
    st.session_state.user_input_box = ""

# --- Quick test buttons ---
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Test Query 1: Burgers"):
        st.session_state.queued_input = "show me burgers"
with col2:
    if st.button("Test Query 2: Vegan Wraps"):
        st.session_state.queued_input = "I want vegan wraps"
with col3:
    if st.button("Test Query 3: Spicy Curry <$8"):
        st.session_state.queued_input = "Any spicy vegetarian curry under $8?"

# --- Determine input to process ---
user_input = st.text_input(
    "Type your message here:",
    value=st.session_state.user_input_box,
    key="input_box"
)

send_clicked = st.button("Send")

# If a queued input exists, process it automatically
if st.session_state.queued_input:
    user_input = st.session_state.queued_input
    st.session_state.queued_input = None
    send_clicked = True

# --- Process user input ---
if send_clicked and user_input.strip() != "":
    response, interest_score = get_response(user_input)
    st.session_state.chat_history.append({"user": user_input, "bot": response, "interest": interest_score})
    st.session_state.user_input_box = ""  # clear input box after send

# --- Display chat ---
for turn in st.session_state.chat_history:
    st.markdown(f"**You:** {turn['user']}")
    st.markdown(f"**Bot:** {turn['bot']} _(Interest Score: {turn['interest']}%)_")
    st.markdown("---")

# --- Analytics Dashboard ---
st.subheader("📊 Analytics Dashboard")
if st.session_state.chat_history:
    avg_interest = sum(turn['interest'] for turn in st.session_state.chat_history) / len(st.session_state.chat_history)
    st.write(f"Average Interest: {avg_interest:.2f}%")
    dietary_tags = set()
    for turn in st.session_state.chat_history:
        if "tags" in turn:
            dietary_tags.update(turn["tags"])
    st.write(f"Dietary Mentions: {', '.join(dietary_tags) if dietary_tags else 'None'}")
else:
    st.write("No conversation data yet.")

# --- Database Status ---
st.subheader("Database Status")
st.write("Total Products: 100")
