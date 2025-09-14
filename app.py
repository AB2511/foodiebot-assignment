# app.py
import streamlit as st
from chat_engine import generate_response, log_conversation, query_database
import sqlite3
import pandas as pd
import uuid

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# Session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # list of (role, text)
if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []
if "last_queries" not in st.session_state:
    st.session_state.last_queries = []
if "dietary_mentions" not in st.session_state:
    st.session_state.dietary_mentions = set()

# Layout
left, right = st.columns([2, 1])

with left:
    st.subheader("Chat")
    user_input = st.text_input("Type your message here:", key="user_input")
    if st.button("Send"):
        if user_input.strip():
            response, interest = generate_response(user_input, context=" ".join([t for _, t in st.session_state.chat_history]))
            log_conversation(user_input, response, interest)

            st.session_state.chat_history.append(("You", user_input))
            st.session_state.chat_history.append(("Bot", response))
            st.session_state.interest_scores.append(interest)
            st.session_state.last_queries.append(f"User: {user_input} | Interest: {interest}%")

            if "vegan" in user_input.lower():
                st.session_state.dietary_mentions.add("vegan")
            if "vegetarian" in user_input.lower():
                st.session_state.dietary_mentions.add("vegetarian")
            if "spicy" in user_input.lower():
                st.session_state.dietary_mentions.add("spicy")

    # Chat display (last 30 lines)
    st.markdown("----")
    for role, text in st.session_state.chat_history[-30:]:
        if role == "You":
            st.markdown(f"**You:** {text}")
        else:
            st.markdown(f"**Bot:** {text}")

with right:
    st.subheader("Analytics")
    if st.session_state.interest_scores:
        avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
        st.metric("Average Interest", f"{avg_interest:.2f}%")
        st.line_chart(st.session_state.interest_scores)
    else:
        st.metric("Average Interest", "0.00%")

    st.write("**Dietary Mentions:**", ", ".join(sorted(st.session_state.dietary_mentions)) if st.session_state.dietary_mentions else "None")

    st.subheader("Database status")
    try:
        conn = sqlite3.connect("foodiebot.db")
        total = pd.read_sql_query("SELECT COUNT(*) AS total FROM products", conn)["total"].iloc[0]
        category_counts = pd.read_sql_query("SELECT category, COUNT(*) as cnt FROM products GROUP BY category", conn)
        conn.close()
        st.write(f"Total Products: **{int(total)}**")
        st.dataframe(category_counts, height=180)
    except Exception as e:
        st.error("Database unavailable. Run setup_db.py to create foodiebot.db")

    st.subheader("Last queries")
    for q in st.session_state.last_queries[-6:][::-1]:
        st.write(q)

    st.subheader("Search preview (last user message)")
    if st.session_state.chat_history:
        last_user = ""
        for role, txt in reversed(st.session_state.chat_history):
            if role == "You":
                last_user = txt
                break
        if last_user:
            preview = query_database({"keyword_tokens": None, "category": None})
            # Build a meaningful preview: call query_database with tokenization via our helper generate_response logic:
            # Simpler approach: just call generate_response and display the bot's preview text
            preview_results = None
            try:
                # try to get direct DB preview by reusing generate_response filters indirectly:
                from chat_engine import _normalize_text, _tokenize_and_filter, RULES as CHAT_RULES
                clean = _normalize_text(last_user)
                tokens = _tokenize_and_filter(clean)
                filters = {"keyword_tokens": tokens, "context": ""}
                for k, rule in CHAT_RULES.items():
                    if k in clean:
                        filters.update(rule)
                preview_results = query_database(filters)
            except Exception:
                preview_results = None

            if preview_results:
                for p in preview_results[:6]:
                    st.markdown(f"**{p[1]}** — {p[2]} — ${p[3]:.2f} — Spice {p[4]}/10")
                    if p[5]:
                        st.caption(p[5][:150] + ("..." if len(p[5]) > 150 else ""))
            else:
                st.info("No matching products found in database.")

st.markdown("---")
st.markdown("**Quick test queries:**")
st.markdown("- `show me burgers`  \n- `burgers`  \n- `I want vegan wraps`  \n- `Any spicy vegetarian curry under $8?`  \n- `Less than 10 dollars pasta`  \n- `extra spicy wrap`  \n- `I will take the Spicy Korean Fried Cauliflower`")
