# app.py — FoodieBot Chat & Analytics (clean rewrite)
import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from chat_engine import generate_response, log_conversation, query_database

st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")
TITLE = "🍔 FoodieBot Chat & Analytics"

# ---------- Session state bootstrap ----------
if "context" not in st.session_state:
    st.session_state.context = ""                 # conversation context passed to LLM
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []            # list of tuples (speaker, text, interest, timestamp)
if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []         # list of ints
if "dietary_mentions" not in st.session_state:
    st.session_state.dietary_mentions = set()     # aggregate dietary tags from results
if "last_preview" not in st.session_state:
    st.session_state.last_preview = []            # last DB product rows (for sidebar preview)

# ---------- Helpers ----------
def truncate(text: str, n: int = 160) -> str:
    if not text:
        return ""
    if len(text) <= n:
        return text
    # cut to nearest space to avoid mid-word endings
    short = text[:n].rsplit(" ", 1)[0]
    return short + "..."

def display_products_list(products):
    """Display products (rows returned by query_database) in readable format."""
    if not products:
        st.info("No matching products found in our database. Try adjusting your query.")
        return
    for p in products:
        # p expected: (product_id, name, category, price, spice_level, description, dietary_tags) or similar
        pid = p[0]
        name = p[1] if len(p) > 1 else ""
        category = p[2] if len(p) > 2 else ""
        price = p[3] if len(p) > 3 else 0.0
        spice = p[4] if len(p) > 4 else 0
        desc = p[5] if len(p) > 5 else ""
        tags = p[6] if len(p) > 6 else ""
        st.markdown(f"**{name}** — *{category}* — ${price:.2f} — Spice {spice}/10")
        st.caption(truncate(desc, 180))
        if tags:
            st.markdown(f"*Tags:* `{tags}`")
        st.markdown("---")

def safe_fetch_total_products():
    try:
        conn = sqlite3.connect("foodiebot.db")
        total = pd.read_sql_query("SELECT COUNT(*) AS total FROM products", conn)["total"].iloc[0]
        conn.close()
        return int(total)
    except Exception:
        return None

def fetch_last_queries(n=5):
    try:
        conn = sqlite3.connect("foodiebot.db")
        df = pd.read_sql_query(f"SELECT user_message, bot_response, interest_score, timestamp FROM conversations ORDER BY id DESC LIMIT {n}", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

# ---------- Layout ----------
st.title(TITLE)
cols = st.columns([2, 1])  # left: chat & main, right: sidebar content (we'll still show a proper sidebar below)

# ----- Chat area (left) -----
with cols[0]:
    st.subheader("Chat with FoodieBot")
    user_input = st.text_input("Type your message here:", key="user_input")

    if st.button("Send") and user_input.strip():
        # Generate bot response + interest
        try:
            response_text, interest = generate_response(user_input, st.session_state.context)
        except Exception as e:
            response_text = "Error generating response — check logs."
            interest = 0

        # Log conversation to DB
        try:
            log_conversation(user_input, response_text, int(interest))
        except Exception:
            # don't break UI if logging fails
            pass

        # Save to session state
        timestamp = datetime.now().isoformat(timespec="seconds")
        st.session_state.chat_history.append(("User", user_input, None, timestamp))
        st.session_state.chat_history.append(("Bot", response_text, int(interest), timestamp))
        st.session_state.interest_scores.append(int(round(interest)))
        st.session_state.context += f"User: {user_input}\nBot: {response_text}\n"

        # Query DB separately to get structured product rows (for preview display & tag extraction)
        try:
            filters = {"keyword": user_input, "context": st.session_state.context}
            products = query_database(filters)
        except Exception:
            products = []

        st.session_state.last_preview = products
        # extract dietary tags from product rows
        for p in products:
            tags_field = (p[6] if len(p) > 6 else "") or ""
            tags_lower = tags_field.lower()
            if "vegetarian" in tags_lower:
                st.session_state.dietary_mentions.add("vegetarian")
            if "vegan" in tags_lower:
                st.session_state.dietary_mentions.add("vegan")
            if "spicy" in tags_lower:
                st.session_state.dietary_mentions.add("spicy")

    # Show chat history
    st.markdown("### Conversation")
    if not st.session_state.chat_history:
        st.info("Start the conversation — try: `show me burgers`, `I want vegan wraps`, or `Any spicy vegetarian curry under $8?`")
    else:
        for speaker, text, interest, ts in st.session_state.chat_history[-40:]:
            if speaker == "User":
                st.markdown(f"**You:** {text}")
            else:
                st.markdown(f"**Bot:** {text}")
                if interest is not None:
                    st.caption(f"Interest Score: {int(interest)}%")

    # Display structured results preview under chat (if available)
    if st.session_state.last_preview:
        st.markdown("### Results preview from database")
        display_products_list(st.session_state.last_preview)

# ----- Right column (sidebar-like panel in page) -----
with cols[1]:
    st.subheader("📊 Analytics Dashboard")

    # Interest metrics and plot
    if st.session_state.interest_scores:
        scores = [int(s) for s in st.session_state.interest_scores]
        avg_interest = sum(scores) / len(scores)
        st.metric("Average Interest", f"{avg_interest:.2f}%")
        # Plot using matplotlib for more control
        fig, ax = plt.subplots()
        ax.plot(list(range(1, len(scores) + 1)), scores, marker="o")
        ax.set_xlabel("Conversation Turn")
        ax.set_ylabel("Interest (%)")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.25)
        st.pyplot(fig, use_container_width=True)
    else:
        st.metric("Average Interest", "0.00%")
        st.info("No interest data yet — send a message to start interaction.")

    # Dietary mentions (derived from products returned over time)
    mentions = sorted(list(st.session_state.dietary_mentions))
    st.markdown("**Dietary Mentions (from results)**")
    st.write(", ".join(mentions) if mentions else "None")

    # Database status
    st.subheader("📦 Database Status")
    total_products = safe_fetch_total_products()
    if total_products is None:
        st.error("Unable to read products table. Run setup_db.py to create/populate DB.")
    else:
        st.write(f"Total Products: **{total_products}**")

    # Last queries table
    st.subheader("Last 5 Queries")
    last_queries = fetch_last_queries(5)
    if not last_queries.empty:
        st.dataframe(last_queries, height=200)
    else:
        st.write("No saved queries found in DB (or DB connection failed).")

    # Quick test suggestions
    st.markdown("**Quick test queries:**")
    st.write("- `show me burgers`  \n- `I want vegan wraps`  \n- `Any spicy vegetarian curry under $8?`  \n- `Less than 10 dollars pasta`  \n- `I will take the Spicy Korean Fried Cauliflower`")

# ---------- Footer note ----------
st.markdown("---")
st.caption("Tip: If product previews look empty but you know the DB has items, run `python setup_db.py` locally to re-create the DB and then redeploy. Good luck with submission — you're very close!")

