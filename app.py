import streamlit as st
from datetime import datetime
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt

from chat_engine import generate_response, log_conversation

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
st.title("🍔 FoodieBot Chat & Analytics")

# Session state
if "context" not in st.session_state:
    st.session_state.context = ""
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {role, text, interest, ts}
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "dietary_mentions" not in st.session_state:
    st.session_state.dietary_mentions = set()

left, right = st.columns([2.5, 1])

with left:
    st.subheader("Chat")
    user_input = st.text_input("Type your message here:", key="user_input")

    if st.button("Send") and user_input.strip():
        bot_text, interest, results = generate_response(user_input, st.session_state.context)

        ts = datetime.now().isoformat(timespec="seconds")
        st.session_state.history.append({"role": "user", "text": user_input, "interest": None, "ts": ts})
        st.session_state.history.append({"role": "bot", "text": bot_text, "interest": int(interest), "ts": ts})
        st.session_state.last_results = results
        st.session_state.context += f"User: {user_input}\nBot: {bot_text}\n"

        # update dietary mentions
        for r in results:
            tags = (r[6] or "").lower()
            if "vegetarian" in tags:
                st.session_state.dietary_mentions.add("vegetarian")
            if "vegan" in tags:
                st.session_state.dietary_mentions.add("vegan")
            if "spicy" in tags:
                st.session_state.dietary_mentions.add("spicy")

        try:
            log_conversation(user_input, bot_text, interest)
        except Exception:
            st.warning("Failed to log conversation (non-blocking).")

    st.markdown("### Conversation")
    if not st.session_state.history:
        st.info("Try: `show me burgers`, `I want vegan wraps`, `Any spicy vegetarian curry under $8?`")
    else:
        for turn in st.session_state.history[-30:]:
            if turn["role"] == "user":
                st.markdown(f"**You:** {turn['text']}")
            else:
                st.markdown(f"**Bot:** {turn['text']}")
                st.caption(f"Interest: {turn['interest']}%")

    st.markdown("### Results preview from database")
    if st.session_state.last_results:
        for r in st.session_state.last_results[:20]:
            pid, name, category, price, spice, desc, tags = r
            st.markdown(f"**{name}** — *{category}* — ${price:.2f} — Spice {spice}/10")
            if desc:
                st.caption(desc if len(desc) <= 200 else desc[:200].rsplit(" ", 1)[0] + "...")
            if tags:
                st.markdown(f"*Tags:* `{tags}`")
            st.markdown("---")
    else:
        st.info("No matching products found in database. Try different keywords or relax constraints.")

with right:
    st.subheader("📊 Analytics")
    # load conversation logs (persistent)
    try:
        conn = sqlite3.connect("foodiebot.db")
        conv_df = pd.read_sql_query("SELECT * FROM conversations ORDER BY id", conn)
        conn.close()
    except Exception:
        conv_df = pd.DataFrame()

    if not conv_df.empty:
        valid = conv_df[conv_df["interest_score"] > 0]["interest_score"]
        avg = valid.mean() if not valid.empty else 0.0
        st.metric("Average Interest", f"{avg:.2f}%")
        fig, ax = plt.subplots()
        ax.plot(list(range(1, len(conv_df) + 1)), conv_df["interest_score"], marker="o")
        ax.set_xlabel("Turn")
        ax.set_ylabel("Interest (%)")
        ax.set_ylim(0, 100)
        st.pyplot(fig)
    else:
        st.metric("Average Interest", "0.00%")
        st.info("No conversation logs yet.")

    st.markdown("**Dietary mentions (seen in results)**")
    st.write(", ".join(sorted(st.session_state.dietary_mentions)) or "None")

    st.markdown("**Database status**")
    try:
        conn = sqlite3.connect("foodiebot.db")
        total = pd.read_sql_query("SELECT COUNT(*) AS total FROM products", conn)["total"].iloc[0]
        cat_counts = pd.read_sql_query("SELECT category, COUNT(*) as count FROM products GROUP BY category", conn)
        conn.close()
        st.write(f"Total Products: **{int(total)}**")
        st.dataframe(cat_counts, height=200)
    except Exception:
        st.error("Failed to read products DB. Run setup_db.py locally to create/populate database.")

st.markdown("---")
st.caption("Quick tests: `show me burgers`, `I want vegan wraps`, `Any spicy vegetarian curry under $8?`, `Less than 10 dollars pasta`") 
