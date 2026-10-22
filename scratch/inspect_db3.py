import sqlite3
conn = sqlite3.connect('apps/api/test_dev.db')
cur = conn.cursor()

# Get users columns
cur.execute("PRAGMA table_info(users)")
cols = cur.fetchall()
print("Users columns:", [c[1] for c in cols])

cur.execute("SELECT * FROM users LIMIT 3")
users = cur.fetchall()
print("Users:", users)

# Get leads
cur.execute("SELECT id, name, phone, status, pipeline_stage FROM leads LIMIT 5")
leads = cur.fetchall()
print("Leads:", leads)

# Get properties
cur.execute("PRAGMA table_info(property_listings)")
cols = cur.fetchall()
print("Property columns:", [c[1] for c in cols])

cur.execute("SELECT id, title, price, status FROM property_listings LIMIT 5")
props = cur.fetchall()
print("Properties:", props)

# Get deals
cur.execute("PRAGMA table_info(deal_transactions)")
cols = cur.fetchall()
print("Deal columns:", [c[1] for c in cols])

cur.execute("SELECT id, stage, status FROM deal_transactions LIMIT 5")
deals = cur.fetchall()
print("Deals:", deals)

# Auth method - check if there's a password field
cur.execute("PRAGMA table_info(brokers)")
cols = cur.fetchall()
print("Broker columns:", [c[1] for c in cols])

conn.close()
