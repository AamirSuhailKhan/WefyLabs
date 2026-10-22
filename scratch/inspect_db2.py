import sqlite3
conn = sqlite3.connect('apps/api/test_dev.db')
cur = conn.cursor()

# Get broker details
cur.execute("SELECT id, email, name, subscription_status FROM brokers")
brokers = cur.fetchall()
print("Brokers:", brokers)

# Get organization members
cur.execute("SELECT broker_id, organization_id, role FROM organization_members LIMIT 10")
members = cur.fetchall()
print("Org Members:", members)

# Get users
cur.execute("SELECT id, email, supabase_id FROM users LIMIT 5")
users = cur.fetchall()
print("Users:", users)

# Get leads
cur.execute("SELECT id, name, phone, status, pipeline_stage FROM leads LIMIT 5")
leads = cur.fetchall()
print("Leads:", leads)

# Get properties
cur.execute("SELECT id, title, price, status FROM property_listings LIMIT 5")
props = cur.fetchall()
print("Properties:", props)

# Get deals
cur.execute("SELECT id, stage, status FROM deal_transactions LIMIT 5")
deals = cur.fetchall()
print("Deals:", deals)

conn.close()
