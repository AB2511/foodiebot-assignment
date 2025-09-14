import streamlit as st
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

if "last_queries" not in st.session_state:
    st.session_state.last_queries = []

# ---------- Sidebar Analytics ----------
with st.sidebar:
    st.header("📊 Analytics Dashboard")

    # Average Interest
    if st.session_state.interest_scores:
        avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
    else:
        avg_interest = 0.0
    st.metric("Average Interest", f"{avg_interest:.2f}%")

    # Interest progression
    if st.session_state.interest_scores:
        st.line_chart(st.session_state.interest_scores)
    else:
        st.write("Interest Progression: No data yet")

    # Unique dietary mentions
    dietary_mentions = set()
    for msg, _ in st.session_state.chat_history:
        for tag in ["vegan", "vegetarian", "spicy"]:
            if tag in msg.lower():
                dietary_mentions.add(tag)
    st.write("Unique Dietary Mentions:", ", ".join(dietary_mentions) or "None")

    # Database status
    st.subheader("📦 Database Status")
    try:
        products = query_database({"keyword": ""})
        st.write(f"Total Products: {len(products)}")
    except Exception as e:
        st.error(f"Database check failed: {e}")

    # Last 5 queries
    st.subheader("Last 5 Queries")
    for q in st.session_state.last_queries[-5:]:
        st.write(f"User: {q[0]}  |  Bot: {q[1]}")

# ---------- Main Chat ----------
st.title("🍔 FoodieBot Chat & Analytics")
st.write("Chat with FoodieBot:")

user_input = st.text_input("Type your message here:", "")

if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input)

    # Log conversation
    log_conversation(user_input, response, interest)

    # Save to session
    st.session_state.chat_history.append((user_input, response))
    st.session_state.interest_scores.append(interest)
    st.session_state.last_queries.append((user_input, response))

# Display chat history
st.subheader("💬 Chat")
for user_msg, bot_msg in st.session_state.chat_history:
    st.markdown(f"**You:** {user_msg}")
    st.markdown(f"**Bot:** {bot_msg}")
