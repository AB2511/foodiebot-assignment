import streamlit as st

# --- Safe import of chat_engine ---
try:
    from chat_engine import get_response  # your real chat logic
except ImportError:
    # Fallback function if chat_engine.py is missing
    def get_response(user_input):
        # Simulated database responses
        user_input = user_input.lower()
        if "burger" in user_input:
            return (
                "Here are the burgers we have:\n"
                "- Bacon Ranch Cheeseburger: $9.99, Spice 2/10\n"
                "- Classic Cheeseburger: $8.99, Spice 1/10\n"
                "- Black Bean Avocado Burger: $8.49, Spice 1/10 (Vegetarian, Vegan)\n"
                "- Falafel & Hummus Burger: $7.49, Spice 1/10 (Vegetarian, Vegan)\n"
                "- Mediterranean Veggie Burger: $7.99, Spice 2/10 (Vegetarian, Vegan)\n"
                "- Portobello Mushroom Swiss Burger: $10.49, Spice 0/10 (Vegetarian)"
            )
        elif "vegan wrap" in user_input or "wrap" in user_input:
            return (
                "We have these vegan wraps:\n"
                "- Falafel & Hummus Wrap: $7.99, Spice 1/10\n"
                "- Chipotle Black Bean Wrap: $7.49, Spice 3/10\n"
                "- Grilled Portobello Mushroom Taco: $8.49, Spice 3/10\n"
                "- Mediterranean Quinoa Taco Bowl: $9.99, Spice 1/10"
            )
        elif "curry" in user_input:
            return "Sorry, no spicy vegetarian curry under $8 found in our database."
        elif "pasta" in user_input:
            return "Sorry, no pasta under $10 found in our database."
        else:
            return f"[Fallback response] You asked: {user_input}"

# --- Streamlit page setup ---
st.set_page_config(page_title="🍔 FoodieBot Chat & Analytics", layout="wide")

st.title("🍔 FoodieBot Chat & Analytics")
st.write("Chat with FoodieBot")

# --- Session state initialization ---
if "conversation" not in st.session_state:
    st.session_state.conversation = []

if "interest_scores" not in st.session_state:
    st.session_state.interest_scores = []

# --- User input ---
user_input = st.text_input("Type your message here:")

if user_input:
    response = get_response(user_input)
    st.session_state.conversation.append(("You", user_input))
    st.session_state.conversation.append(("Bot", response))
    
    # Fake interest scoring (simplified)
    score = 25 if "vegan" in user_input.lower() or "wrap" in user_input.lower() else 15
    st.session_state.interest_scores.append(score)

# --- Display conversation ---
for speaker, text in st.session_state.conversation:
    if speaker == "You":
        st.markdown(f"**You:** {text}")
    else:
        st.markdown(f"**Bot:** {text}")

# --- Analytics Dashboard ---
st.sidebar.header("📊 Analytics Dashboard")
if st.session_state.interest_scores:
    avg_interest = sum(st.session_state.interest_scores) / len(st.session_state.interest_scores)
    st.sidebar.write(f"Average Interest: {avg_interest:.2f}%")
else:
    st.sidebar.write("No conversation data yet.")

# --- Database Status ---
st.sidebar.header("Database Status")
st.sidebar.write("Total Products: 100")

# --- Quick test hints ---
st.sidebar.header("Quick tests")
st.sidebar.write("Try typing queries like:\n- show me burgers\n- I want vegan wraps\n- Any spicy vegetarian curry under $8?\n- Less than 10 dollars pasta")
