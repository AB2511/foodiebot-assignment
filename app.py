import streamlit as st
import pandas as pd
from chat_engine import get_response  # Your existing chat logic

# ----------------------------
# Initialize session state
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

if "user_input_box" not in st.session_state:
    st.session_state.user_input_box = ""

# ----------------------------
# Sidebar - Analytics Dashboard
# ----------------------------
st.sidebar.header("📊 Analytics Dashboard")

if st.session_state.interest_scores:
    avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
    st.sidebar.write(f"Average Interest: {avg_interest:.2f}%")
    
    # Line chart of interest over conversation turns
    df = pd.DataFrame({
        "Turn": list(range(1, len(st.session_state.interest_scores) + 1)),
        "Interest Score": st.session_state.interest_scores
    })
    st.sidebar.line_chart(df.set_index("Turn"))
else:
    st.sidebar.write("No conversation data yet.")

# Database status (static for now)
st.sidebar.write("Database Status")
st.sidebar.write("Total Products: 100")

st.sidebar.markdown("**Quick tests**")
st.sidebar.write("Try typing queries like:\n- show me burgers\n- I want vegan wraps\n- Any spicy vegetarian curry under $8?\n- Less than 10 dollars pasta")

# ----------------------------
# Main app
# ----------------------------
st.title("🍔 FoodieBot Chat & Analytics")
st.subheader("Chat with FoodieBot")

# User input box
user_input = st.text_input("Type your message here:", value=st.session_state.user_input_box)
st.session_state.user_input_box = user_input  # Save input to session

if st.button("Send") and user_input.strip() != "":
    # Get bot response and interest score
    bot_response, interest_score = get_response(user_input)
    
    # Update session state
    st.session_state.chat_history.append({"user": user_input, "bot": bot_response})
    st.session_state.interest_scores.append(interest_score)
    st.session_state.user_input_box = ""  # clear input box
    
    st.experimental_rerun()  # Refresh app to show updated chat

# Display chat history
for turn in st.session_state.chat_history:
    st.markdown(f"**You:** {turn['user']}")
    st.markdown(f"**Bot:** {turn['bot']}")
