# app.py
import streamlit as st
import uuid
import sqlite3
import pandas as pd
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# ---------- Session state ----------
if "context" not in st.session_state:
    st.session_state.context = ""
    st.session_state.session_id = str(uuid.uuid4())
if "last_user" not in st.session_state:
    st.session_state.last_user = ""
if "last_response" not in st.session_state:
    st.session_state.last_response = ""
if "last_interest" not in st.session_state:
    st.session_state.last_interest = 0
# This holds a queued input coming from sidebar quick-tests (no rerun needed)
if "queued_input" not in st.session_state:
    st.session_state.queued_input = None

# ---------- Layout: input area ----------
col_main, col_side = st.columns([3, 1])

with col_main:
    st.subheader("Chat")
    user_input = st.text_input("Type your message here:", key="user_input_box")
    send_clicked = st.button("Send")

    # If a queued input exists (clicked in sidebar), treat it as if the user typed it
    if st.session_state.queued_input:
        # move it into the input box (show to user) and process immediately
        user_input = st.session_state.queued_input
        st.session_state.queued_input = None
        # also update the visible input box so user sees it
        st.session_state.user_input_box = user_input
        send_clicked = True

    if send_clicked and user_input and user_input.strip():
        response, interest = generate_response(user_input, st.session_state.context)
        log_conversation(user_input, response, interest)
        # update session
        st.session_state.last_user = user_input
        st.session_state.last_response = response
        st.session_state.last_interest = interest
        st.session_state.context += f"User: {user_input}\nBot: {response}\n"
        # clear text input for convenience
        st.session_state.user_input_box = ""

    # Display last conversation turn if exists
    if st.session_state.last_user:
        st.markdown(f"**You:** {st.session_state.last_user}")
        st.markdown(f"**Bot:** {st.session_state.last_response}")
        st.markdown(f"**Interest Score:** {st.session_state.last_interest}%")
    else:
        st.info("Start a conversation with FoodieBot (try the Quick tests in the sidebar).")

    # Show database search preview for the last user input (or live input)
    preview_query = st.session_state.last_user or user_input
    if preview_query:
        st.subheader("Search Preview (top matches)")
        preview_results = query_database({'keyword': preview_query, 'context': st.session_state.context})
        if not preview_results:
            st.info("No matching products found in database. Try different keywords or relax constraints.")
        else:
            for r in preview_results:
                pid, name, category, price, spice, descr, tags = r
                st.markdown(f"**{name}** — *{category}* — ${price:.2f} — Spice {spice}/10")
                st.caption(descr)
                if tags:
                    st.write(f"**Tags:** {tags}")
                st.markdown("---")

# ---------- Sidebar: Analytics + Quick tests ----------
with col_side:
    st.sidebar.title("📊 Analytics Dashboard")

    # Load conversation log from DB (latest first)
    try:
        conn = sqlite3.connect("foodiebot.db")
        conv_df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id DESC LIMIT 200", conn)
        conn.close()
    except Exception as e:
        conv_df = pd.DataFrame()
        st.sidebar.error(f"Error loading conversation log: {e}")

    if not conv_df.empty:
        # show interest progression (chronological)
        scores = conv_df['interest_score'].fillna(0).astype(int).tolist()[::-1]
        st.sidebar.subheader("Interest Progression")
        st.sidebar.line_chart(scores)

        # average interest across non-zero entries
        valid = [s for s in conv_df['interest_score'] if s and s > 0]
        avg_interest = sum(valid) / len(valid) if valid else 0.0
        st.sidebar.metric("Average Interest", f"{avg_interest:.2f}%")

        # unique dietary mentions
        dietary = set()
        for msg in conv_df['user_message'].astype(str).tolist():
            m = msg.lower()
            if 'vegetarian' in m:
                dietary.add('vegetarian')
            if 'vegan' in m:
                dietary.add('vegan')
            if 'spicy' in m:
                dietary.add('spicy')
            if 'curry' in m:
                dietary.add('curry')
        st.sidebar.write("Unique Dietary Mentions:")
        st.sidebar.write(", ".join(sorted(dietary)) if dietary else "None")

        # show last 5 queries
        st.sidebar.subheader("Last 5 Queries")
        last5 = conv_df[['user_message', 'bot_response', 'interest_score']].head(5)
        for _, row in last5.iterrows():
            st.sidebar.write(f"User: {row['user_message'][:40]}…")
            st.sidebar.write(f"Bot: {str(row['bot_response'])[:60]}…")
            st.sidebar.write(f"Interest: {row['interest_score']}%")
            st.sidebar.markdown("---")
    else:
        st.sidebar.info("No conversation data yet.")

    # DB Status
    st.sidebar.subheader("Database Status")
    try:
        conn = sqlite3.connect("foodiebot.db")
        prod_df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category ORDER BY count DESC", conn)
        total_products = pd.read_sql_query("SELECT COUNT(*) as total FROM products", conn)["total"].iloc[0]
        conn.close()
        st.sidebar.write(f"Total Products: **{total_products}**")
        st.sidebar.dataframe(prod_df, height=220)
    except Exception as e:
        st.sidebar.error(f"Error loading products: {e}")

    # Quick test buttons (no rerun — we queue the input)
    st.sidebar.subheader("Quick tests")
    if st.sidebar.button("Show me burgers"):
        st.session_state.queued_input = "show me burgers"
    if st.sidebar.button("I want vegan wraps"):
        st.session_state.queued_input = "I want vegan wraps"
    if st.sidebar.button("Any spicy vegetarian curry under $8?"):
        st.session_state.queued_input = "Any spicy vegetarian curry under $8?"
    if st.sidebar.button("Less than 10 dollars pasta"):
        st.session_state.queued_input = "Less than 10 dollars pasta"

    st.sidebar.caption("Tip: the quick tests queue the message and it will be processed in the chat area above.")
