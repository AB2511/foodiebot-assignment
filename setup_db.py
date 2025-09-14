import sqlite3
import json

# Load the generated products
with open('products.json', 'r') as f:
    products = json.load(f)['products']

# Create/connect to SQLite database
conn = sqlite3.connect('foodiebot.db')
c = conn.cursor()

# Create the products table with proper schema
c.execute('''
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    ingredients TEXT NOT NULL,
    price REAL NOT NULL,
    calories INTEGER NOT NULL,
    prep_time TEXT NOT NULL,
    dietary_tags TEXT,
    mood_tags TEXT,
    allergens TEXT,
    popularity_score INTEGER NOT NULL,
    chef_special INTEGER NOT NULL,
    limited_time INTEGER NOT NULL,
    spice_level INTEGER NOT NULL,
    image_prompt TEXT NOT NULL
)
''')

# Create the conversations table
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
c.execute('CREATE INDEX IF NOT EXISTS idx_spice_level ON products(spice_level)')
c.execute('CREATE INDEX IF NOT EXISTS idx_dietary_tags ON products(dietary_tags)')
c.execute('CREATE INDEX IF NOT EXISTS idx_mood_tags ON products(mood_tags)')

# Insert the products
for p in products:
    c.execute('''
    INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        p['product_id'],
        p['name'],
        p['category'],
        p['description'],
        ','.join(p['ingredients']),
        p['price'],
        p['calories'],
        p['prep_time'],
        ','.join(p['dietary_tags']),
        ','.join(p['mood_tags']),
        ','.join(p['allergens']),
        p['popularity_score'],
        1 if p['chef_special'] else 0,
        1 if p['limited_time'] else 0,
        p['spice_level'],
        p['image_prompt']
    ))

conn.commit()
conn.close()
print("Database 'foodiebot.db' created and populated with 100 products. Indexes and conversations table added for optimization.")