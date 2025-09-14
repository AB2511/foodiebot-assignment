import streamlit as st
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(
    page_title="🍔 FoodieBot Chat & Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []
if "dietary_mentions" not in st.session_state:
    st.session_state.dietary_mentions = set()
if "last_queries" not in st.session_state:
    st.session_state.last_queries = []

# ---------- Sidebar ----------
with st.sidebar:
    st.header("📊 Analytics Dashboard")
    if st.session_state.interest_scores:
        avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
        st.metric("Average Interest", f"{avg_interest:.2f}%")
        st.line_chart(st.session_state.interest_scores)
    else:
        st.metric("Average Interest", "0.00%")

    st.subheader("Unique Dietary Mentions")
    st.write(", ".join(st.session_state.dietary_mentions) if st.session_state.dietary_mentions else "None")

    st.subheader("📦 Database Status")
    try:
        products = query_database({"keyword": ""})
        st.write(f"Total Products: {len(products)}")
    except Exception as e:
        st.error(f"Database check failed: {e}")

    st.subheader("Last 5 Queries")
    for query in st.session_state.last_queries[-5:]:
        st.write(query)

# ---------- Main Chat ----------
st.title("🍔 FoodieBot Chat & Analytics")
st.write("Chat with FoodieBot:")

user_input = st.text_input("Type your message here:")

if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input)

    # Update session state
    st.session_state.chat_history.append(("You", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)

    # Track dietary mentions
    for word in ["vegan", "vegetarian", "spicy"]:
        if word in user_input.lower():
            st.session_state.dietary_mentions.add(word)

    # Track last queries
    st.session_state.last_queries.append(f"User: {user_input} | Bot: {response}")

# Display chat
for role, msg in st.session_state.chat_history:
    if role == "You":
        st.markdown(f"**{role}:** {msg}")
    else:
        st.markdown(f"**{role}:** {msg}")
