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

def calculate_interest_score(message, product_match=True):
    score = 0
    if any(word in message.lower() for word in ['love', 'spicy', 'korean', 'fusion']):
        score += ENGAGEMENT_FACTORS['specific_preferences']
    if 'vegetarian' in message.lower() or 'vegan' in message.lower():
        score += ENGAGEMENT_FACTORS['dietary_restrictions']
    if 'under $' in message.lower():
        score += ENGAGEMENT_FACTORS['budget_mention']
    if 'adventurous' in message.lower():
        score += ENGAGEMENT_FACTORS['mood_indication']
    if '?' in message:
        score += ENGAGEMENT_FACTORS['question_asking']
    if any(word in message.lower() for word in ['amazing', 'perfect', 'love']):
        score += ENGAGEMENT_FACTORS['enthusiasm_words']
    if 'how much' in message.lower():
        score += ENGAGEMENT_FACTORS['price_inquiry']
    if any(word in message.lower() for word in ['take it', 'add to cart']):
        score += ENGAGEMENT_FACTORS['order_intent']

    if any(word in message.lower() for word in ['maybe', 'not sure']):
        score += NEGATIVE_FACTORS['hesitation']
    if 'too expensive' in message.lower():
        score += NEGATIVE_FACTORS['budget_concern']
    if not product_match:
        score += NEGATIVE_FACTORS['dietary_conflict']
    if "don't like" in message.lower():
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
    if 'vegetarian' in filters.get('context', '').lower() or 'vegan' in filters.get('context', '').lower():
        query += " AND (dietary_tags LIKE ? OR dietary_tags LIKE ?)"
        params.extend(['%vegetarian%', '%vegan%'])
    query += " ORDER BY popularity_score DESC LIMIT 3"
    results = c.execute(query, params).fetchall()
    conn.close()
    return results

def generate_response(user_message, context=""):
    interest = calculate_interest_score(user_message)
    filters = {'context': context}  
    if 'spicy' in user_message.lower() or 'curry' in user_message.lower():
        filters['spice_min'] = 5
        filters['dietary_tags'] = 'spicy'
    if 'under $10' in user_message.lower():
        filters['price_max'] = 10
    if 'vegetarian' in user_message.lower() or 'vegan' in user_message.lower():
        filters['dietary_tags'] = 'vegetarian' 

    results = query_database(filters)
    product_match = bool(results)  
    if not results:
        product_info = "No matches found."
    else:
        product_info = "\n".join([f"- {r[1]}: ${r[2]}, Spice: {r[3]}/10 - {r[4]} (Tags: {r[5]})" for r in results])
    prompt = f"""
    You are FoodieBot. Use context: {context}.
    User: {user_message}.
    Recommend ONLY from these exact database products (do not invent or add any): {product_info}.
    Keep natural dialogue, extract preferences, maintain memory, and recommend based on mood/diet/budget.
    If no matches, politely say "No matching products found in our database. What else can I help with?" Do NOT suggest non-existent items.
    """
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.7, "max_output_tokens": 300}
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