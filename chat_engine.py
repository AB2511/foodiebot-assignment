import os
from dotenv import load_dotenv
import google.generativeai as genai
import sqlite3

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

ENGAGEMENT_FACTORS = {
    'specific_preferences': 15,
    'dietary_restrictions': 10,
    'budget_mention': 5,
    'mood_indication': 20,
    'question_asking': 10,
    'enthusiasm_words': 8,
    'price_inquiry': 25,
    'order_intent': 30,
}

NEGATIVE_FACTORS = {
    'hesitation': -10,
    'budget_concern': -15,
    'dietary_conflict': -20,
    'rejection': -25,
    'delay_response': -5,
}

# 🔑 Mapping user words → DB filters
RULES = {
    "burger": {"category": "Burgers"},
    "pizza": {"category": "Pizza"},
    "wrap": {"category": "Tacos & Wraps"},
    "taco": {"category": "Tacos & Wraps"},
    "salad": {"category": "Salads & Healthy Options"},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
}

def calculate_interest_score(message, product_match=True):
    score = 0
    m = message.lower()

    # Engagement factors
    if any(word in m for word in ['love', 'spicy', 'korean', 'fusion', 'burger', 'pizza', 'wrap']):
        score += ENGAGEMENT_FACTORS['specific_preferences']
    if 'vegetarian' in m or 'vegan' in m:
        score += ENGAGEMENT_FACTORS['dietary_restrictions']
    if 'under $' in m:
        score += ENGAGEMENT_FACTORS['budget_mention']
    if 'adventurous' in m:
        score += ENGAGEMENT_FACTORS['mood_indication']
    if '?' in message:
        score += ENGAGEMENT_FACTORS['question_asking']
    if any(word in m for word in ['amazing', 'perfect', 'love']):
        score += ENGAGEMENT_FACTORS['enthusiasm_words']
    if 'how much' in m:
        score += ENGAGEMENT_FACTORS['price_inquiry']
    if any(phrase in m for phrase in ["i'll take", "i will take", "order", "add to cart"]):
        score += ENGAGEMENT_FACTORS['order_intent']

    # Negative factors
    if any(word in m for word in ['maybe', 'not sure']):
        score += NEGATIVE_FACTORS['hesitation']
    if 'too expensive' in m:
        score += NEGATIVE_FACTORS['budget_concern']
    if not product_match and any(word in m for word in ['spicy', 'vegetarian', 'vegan', 'burger', 'pizza']):
        score += NEGATIVE_FACTORS['dietary_conflict']
    if "don't like" in m or "not interested" in m:
        score += NEGATIVE_FACTORS['rejection']

    return max(0, min(100, score))

def query_database(filters):
    conn = sqlite3.connect('foodiebot.db')
    c = conn.cursor()
    query = "SELECT product_id, name, price, spice_level, description, dietary_tags FROM products WHERE 1=1"
    params = []

    if 'category' in filters:
        query += " AND category = ?"
        params.append(filters['category'])
    if 'price_max' in filters:
        query += " AND price <= ?"
        params.append(filters['price_max'])
    if 'spice_min' in filters:
        query += " AND spice_level >= ?"
        params.append(filters['spice_min'])
    if 'dietary_tags' in filters:
        query += " AND dietary_tags LIKE ?"
        params.append(f'%{filters["dietary_tags"]}%')

    # Context-aware dietary filtering
    if 'vegetarian' in filters.get('context', '').lower() or 'vegan' in filters.get('context', '').lower():
        query += " AND (dietary_tags LIKE ? OR dietary_tags LIKE ?)"
        params.extend(['%vegetarian%', '%vegan%'])

    query += " ORDER BY popularity_score DESC LIMIT 3"
    results = c.execute(query, params).fetchall()
    conn.close()

    if not results:
        print("[DEBUG] No DB matches with filters:", filters)
    return results

def generate_response(user_message, context=""):
    # Step 1: Build filters from RULES
    filters = {'context': context}
    for keyword, rule in RULES.items():
        if keyword in user_message.lower():
            filters.update(rule)

    # Step 2: Extract budget
    if 'under $' in user_message.lower():
        for word in user_message.lower().split():
            if word.startswith('$'):
                try:
                    filters['price_max'] = float(word[1:])
                    break
                except ValueError:
                    pass

    # Step 3: Query DB
    results = query_database(filters)
    product_match = bool(results)

    # Step 4: Recalculate interest *after* DB results
    interest = calculate_interest_score(user_message, product_match)

    # Step 5: Build response
    if not results:
        product_info = "No matches found."
    else:
        product_info = "\n".join(
            [f"- {r[1]}: ${r[2]}, Spice {r[3]}/10 - {r[4]} (Tags: {r[5]})" for r in results]
        )

    prompt = f"""
    You are FoodieBot. Context: {context}.
    User: {user_message}.
    Recommend ONLY from these database products:
    {product_info}

    If no matches, say: "No matching products found in our database. What else can I help with?"
    Never invent products. Respect previous preferences (vegetarian, vegan, budget).
    """
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.6, "max_output_tokens": 250}
    ).text
    return response, interest

def log_conversation(user_message, response, interest):
    conn = sqlite3.connect('foodiebot.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_message TEXT,
        bot_response TEXT,
        interest_score INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    c.execute("INSERT INTO conversations (user_message, bot_response, interest_score) VALUES (?, ?, ?)",
              (user_message, response, interest))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    context = ""
    while True:
        user = input("User: ")
        if user.lower() == 'exit':
            break
        resp, score = generate_response(user, context)
        print(f"Bot: {resp} (Interest: {score}%)")
        log_conversation(user, resp, score)
        context += f"User: {user}\nBot: {resp}\n"
