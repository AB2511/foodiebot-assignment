import streamlit as st
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- Session State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

if "last_queries" not in st.session_state:
    st.session_state.last_queries = []

if "dietary_mentions" not in st.session_state:
    st.session_state.dietary_mentions = set()

# ---------- Main Chat ----------
st.title("🍔 FoodieBot Chat & Analytics")
st.write("Chat with FoodieBot:")

user_input = st.text_input("Type your message here:", "")

if st.button("Send") and user_input.strip():
    response, interest = generate_response(user_input)

    # Log conversation
    log_conversation(user_input, response, interest)

    # Query DB for product display
    products = query_database({"keyword": user_input})

    # Update dietary mentions
    for p in products:
        if p[6]:  # dietary_tags
            for tag in p[6].split(","):
                st.session_state.dietary_mentions.add(tag.strip().lower())

    # Display chat
    st.session_state.chat_history.append(("You", user_input))
    st.session_state.chat_history.append(("Bot", response))
    st.session_state.interest_scores.append(interest)
    st.session_state.last_queries.append((user_input, response))

# ---------- Chat Display ----------
for role, msg in st.session_state.chat_history:
    if role == "You":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Bot:** {msg}")

# ---------- Product Display ----------
if user_input.strip():
    products = query_database({"keyword": user_input})
    if products:
        st.markdown("**Here are some recommendations from our database:**")
        for p in products:
            name, category, price, spice, desc, tags = p[1], p[2], p[3], p[4], p[5], p[6]
            tag_text = f" (Tags: {tags})" if tags else ""
            st.markdown(f"- **{name}** [{category}]: ${price}, Spice {spice}/10 - {desc}{tag_text}")
    else:
        st.markdown("No matching products found in our database. What else can I help with?")

# ---------- Analytics Sidebar ----------
st.sidebar.title("📊 Analytics Dashboard")

# Average interest
if st.session_state.interest_scores:
    avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
else:
    avg_interest = 0.0
st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")

# Interest progression
if st.session_state.interest_scores:
    st.sidebar.subheader("Interest Progression")
    st.sidebar.line_chart(st.session_state.interest_scores)

# Unique dietary mentions
st.sidebar.subheader("Unique Dietary Mentions")
dietary_text = ", ".join(sorted(st.session_state.dietary_mentions)) if st.session_state.dietary_mentions else "None"
st.sidebar.write(dietary_text)

# ---------- Database Status ----------
st.sidebar.subheader("📦 Database Status")
try:
    products = query_database({"keyword": ""})
    st.sidebar.write(f"Total Products: {len(products)}")
except Exception as e:
    st.sidebar.error(f"Database check failed: {e}")

# ---------- Last 5 Queries ----------
st.sidebar.subheader("Last 5 Queries")
if st.session_state.last_queries:
    for user_msg, bot_msg in st.session_state.last_queries[-5:]:
        st.sidebar.markdown(f"**User:** {user_msg}")
        st.sidebar.markdown(f"**Bot:** {bot_msg}")
