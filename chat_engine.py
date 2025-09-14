import sqlite3
import re

# ---------- Keyword → DB rules ----------
RULES = {
    "burger": {"category": "Burger"},
    "pizza": {"category": "Pizza"},
    "wrap": {"category": "Wraps"},
    "taco": {"category": "Tacos & Wraps"},
    "salad": {"category": "Salads & Healthy Options"},
    "spicy": {"spice_min": 5},
    "vegetarian": {"dietary_tags": "vegetarian"},
    "vegan": {"dietary_tags": "vegan"},
}

# ---------- Query Database ----------
def query_database(user_message, extra_filters={}):
    conn = sqlite3.connect("foodiebot.db")
    c = conn.cursor()

    # Prepare filters
    filters = extra_filters.copy()

    # Apply RULES based on keywords in user_message
    for keyword, rule in RULES.items():
        if keyword in user_message.lower():
            filters.update(rule)

    conditions = []
    params = []

    # Keyword fallback: match any word in name/category/description/tags
    words = re.findall(r'\w+', user_message.lower())
    if words:
        word_conditions = []
        for w in words:
            word_conditions.append(
                "(LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(description) LIKE ? OR LOWER(dietary_tags) LIKE ?)"
            )
            kw_like = f"%{w}%"
            params.extend([kw_like]*4)
        conditions.append("(" + " OR ".join(word_conditions) + ")")

    # Category filter
    if "category" in filters:
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{filters['category'].lower()}%")

    # Spice filter
    if "spice_min" in filters:
        conditions.append("spice_level >= ?")
        params.append(filters["spice_min"])

    # Dietary filter
    if "dietary_tags" in filters:
        conditions.append("LOWER(dietary_tags) LIKE ?")
        params.append(f"%{filters['dietary_tags'].lower()}%")

    # Budget parsing: "under $X" or "less than X dollars"
    price_match = re.search(r'under \$([0-9]+\.?[0-9]*)', user_message.lower())
    if not price_match:
        price_match = re.search(r'less than ([0-9]+\.?[0-9]*) ?dollars', user_message.lower())
    if price_match:
        filters['price_max'] = float(price_match.group(1))
        conditions.append("price <= ?")
        params.append(filters['price_max'])

    sql = "SELECT product_id, name, category, price, spice_level, description, dietary_tags FROM products"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY popularity_score DESC LIMIT 10"

    results = c.execute(sql, params).fetchall()
    conn.close()
    return results

# ---------- Generate Response ----------
def generate_response(user_message):
    results = query_database(user_message)
    if not results:
        response_text = "No matching products found in our database. What else can I help with?"
    else:
        lines = [f"- {r[1]} ({r[2]}): ${r[3]}, Spice {r[4]}/10 - {r[5]} (Tags: {r[6]})" for r in results]
        response_text = "\n".join(lines)
    return response_text
