import sqlite3
import json

# Load the generated products
with open('products.json', 'r') as f:
    products = json.load(f)['products']

# Create/connect to SQLite database
conn = sqlite3.connect('foodiebot.db')
c = conn.cursor()

# Create the products table with robust schema
c.execute('''
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    ingredients TEXT NOT NULL,
    price REAL NOT NULL,
    calories INTEGER NOT NULL,
    prep_time INTEGER NOT NULL,  -- store in minutes for queries
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

# Conversations table
c.execute('''
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_message TEXT,
    bot_response TEXT,
    interest_score INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Add indexes for efficient querying
c.execute('CREATE INDEX IF NOT EXISTS idx_category ON products(category)')
c.execute('CREATE INDEX IF NOT EXISTS idx_price ON products(price)')
c.execute('CREATE INDEX IF NOT EXISTS idx_spice ON products(spice_level)')
# Note: indexes on TEXT fields with LIKE are mostly useless in SQLite

def safe_join(lst):
    if not lst:
        return ""
    return ','.join([str(x) for x in lst])

# Insert products safely
for p in products:
    c.execute('''
    INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        p.get('product_id'),
        p.get('name', 'Unnamed'),
        p.get('category', 'Misc'),
        p.get('description', ''),
        safe_join(p.get('ingredients', [])),
        float(p.get('price', 0)),
        int(p.get('calories', 0)),
        int(str(p.get('prep_time', '0')).replace('min', '').strip() or 0),  # normalize to int
        safe_join(p.get('dietary_tags', [])),
        safe_join(p.get('mood_tags', [])),
        safe_join(p.get('allergens', [])),
        int(p.get('popularity_score', 0)),
        1 if p.get('chef_special') else 0,
        1 if p.get('limited_time') else 0,
        int(p.get('spice_level', 0)),
        p.get('image_prompt', '')
    ))

conn.commit()
conn.close()
print("✅ Database 'foodiebot.db' populated with products and conversations table ready.")
