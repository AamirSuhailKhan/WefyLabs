import sqlite3
conn = sqlite3.connect('apps/api/test_dev.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Try to get brokers
try:
    cur.execute("SELECT id, email, name, subscription_status FROM brokers LIMIT 5")
    rows = cur.fetchall()
    print("\nBrokers:", rows)
except Exception as e:
    print("Error:", e)

# Try organizations
try:
    cur.execute("SELECT id, name FROM organizations LIMIT 5")
    rows = cur.fetchall()
    print("\nOrganizations:", rows)
except Exception as e:
    print("Orgs error:", e)

conn.close()
