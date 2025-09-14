import sqlite3

conn = sqlite3.connect('foodiebot.db')
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM products")
product_count = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM conversations")
convo_count = c.fetchone()[0]  # Should be 0 if no logs yet
print(f"Total products: {product_count}")
print(f"Total conversations: {convo_count}")
conn.close()