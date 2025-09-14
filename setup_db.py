import sqlite3
import json
import re

def normalize_prep_time(raw):
    """Convert prep_time strings into integer minutes."""
    if not raw:
        return 0
    s = str(raw).lower().strip()
    match = re.search(r'(\d+)', s)
    if not match:
        return 0
    val = int(match.group(1))
    if "sec" in s or "s" in s:
        return max(1, round(val / 60))  # seconds → minutes
    return val  # assume already minutes


def safe_join(lst):
    if not lst:
        return ""
    return ','.join([str(x) for x in lst])


# Load products
with open("products.json", "r", encoding="utf-8") as f:
    products = json.load(f)["products"]

# Connect DB
conn = sqlite3.connect("foodiebot.db")
c = conn.cursor()

# Drop old tables for clean rebuild
c.execute("DROP TABLE IF EXISTS products")
c.execute("DROP TABLE IF EXISTS conversations")

# Create products table
c.execute('''
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    ingredients TEXT NOT NULL,
    price REAL NOT NULL,
    calories INTEGER NOT NULL,
    prep_time INTEGER NOT NULL,  -- stored as minutes
    dietary_tags TEXT,
    mood_tags TEXT,
    allergens TEXT,
    popularity_score INTEGER NOT NULL,
    chef_special INTEGER NOT NULL,
    limited_time INTEGER NOT NULL,
    spice_level INTEGER NOT NULL,
    image_prompt TEXT
)
''')

# Create conversations table
c.execute('''
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message TEXT,
    bot_response TEXT,
    interest_score INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Add indexes
c.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(category)")
c.execute("CREATE INDEX IF NOT EXISTS idx_price ON products(price)")
c.execute("CREATE INDEX IF NOT EXISTS idx_spice ON products(spice_level)")

# Insert products
inserted = 0
for p in products:
    try:
        row = (
            p.get("product_id"),
            p.get("name", "Unnamed"),
            p.get("category", "Misc"),
            p.get("description", ""),
            safe_join(p.get("ingredients", [])),
            float(p.get("price", 0)),
            int(p.get("calories", 0)),
            normalize_prep_time(p.get("prep_time", "0")),
            safe_join(p.get("dietary_tags", [])),
            safe_join(p.get("mood_tags", [])),
            safe_join(p.get("allergens", [])),
            int(p.get("popularity_score", 0)),
            1 if p.get("chef_special") else 0,
            1 if p.get("limited_time") else 0,
            int(p.get("spice_level", 0)),
            p.get("image_prompt", "")
        )
        c.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
        inserted += 1
    except Exception as e:
        print(f"⚠️ Failed product {p.get('product_id', 'UNKNOWN')}: {e}")

conn.commit()
conn.close()

print(f"✅ Database 'foodiebot.db' ready. Inserted {inserted}/{len(products)} products successfully.")
