# app.py
import streamlit as st
from chat_engine import generate_response, log_conversation, query_database
import sqlite3
import pandas as pd
import uuid

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

# ---------- session scaffolding ----------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # list of (role, text)
if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []
if "dietary_mentions" not in st.session_state:
    st.session_state.dietary_mentions = set()
if "last_queries" not in st.session_state:
    st.session_state.last_queries = []

# ---------- layout ----------
st.title("🍔 FoodieBot Chat & Analytics")
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Chat with FoodieBot")
    user_input = st.text_input("Type your message here:", key="user_input")
    send = st.button("Send")

    if send and user_input.strip():
        response, interest = generate_response(user_input, context=" ".join([m for _, m in st.session_state.chat_history]))
        # log into conversations table
        log_conversation(user_input, response, interest)

        # update session
        st.session_state.chat_history.append(("You", user_input))
        st.session_state.chat_history.append(("Bot", response))
        st.session_state.interest_scores.append(interest)
        st.session_state.last_queries.append(f"User: {user_input} | Interest: {interest}%")

        # track dietary mentions
        if "vegan" in user_input.lower():
            st.session_state.dietary_mentions.add("vegan")
        if "vegetarian" in user_input.lower():
            st.session_state.dietary_mentions.add("vegetarian")
        if "spicy" in user_input.lower():
            st.session_state.dietary_mentions.add("spicy")

    # show chat history
    for role, text in st.session_state.chat_history[-20:]:
        if role == "You":
            st.markdown(f"**You:** {text}")
        else:
            st.markdown(f"**Bot:** {text}")

with right_col:
    st.sidebar.title("📊 Analytics")
    if st.session_state.interest_scores:
        avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
        st.metric("Average Interest", f"{avg_interest:.2f}%")
        st.line_chart(st.session_state.interest_scores)
    else:
        st.metric("Average Interest", "0.00%")

    st.subheader("Dietary Mentions")
    st.write(", ".join(sorted(st.session_state.dietary_mentions)) if st.session_state.dietary_mentions else "None")

    st.subheader("Database status")
    try:
        # quick DB count (shows total products)
        conn = sqlite3.connect("foodiebot.db")
        total = pd.read_sql_query("SELECT COUNT(*) AS total FROM products", conn)["total"].iloc[0]
        conn.close()
        st.write(f"Total Products: **{int(total)}**")
    except Exception as e:
        st.error("Database unavailable. Run setup_db.py to generate foodiebot.db")

    st.subheader("Last queries")
    for q in st.session_state.last_queries[-6:][::-1]:
        st.write(q)

    # optional preview of product search for the last user message
    st.subheader("Search Preview (last message)")
    if st.session_state.chat_history:
        last_user = ""
        # find last user message
        for r, t in reversed(st.session_state.chat_history):
            if r == "You":
                last_user = t
                break
        if last_user:
            try:
                preview = query_database({"keyword": last_user})
                if preview:
                    for p in preview[:6]:
                        st.markdown(f"**{p[1]}** — {p[2]} — ${p[3]:.2f} — Spice {p[4]}/10")
                        if p[5]:
                            st.caption(p[5][:200] + ("..." if len(p[5]) > 200 else ""))
                else:
                    st.info("No matching products found in database.")
            except Exception as e:
                st.error("Preview query failed.")

# ---------- helpful tips ----------
st.markdown("---")
st.markdown("**Quick test queries** you can paste into the chat:")
st.markdown(
    "- `show me burgers`\n"
    "- `I want vegan wraps`\n"
    "- `Any spicy vegetarian curry under $8?`\n"
    "- `Less than 10 dollars pasta`\n"
    "- `extra spicy wrap`\n"
    "- `I will take the Spicy Korean Fried Cauliflower`"
)
