import psycopg2

# Paste your password from Supabase dashboard
DB_URL = "postgresql://postgres:$Cville2016$@db.yhyaslxqzwqptknmybqa.supabase.co:5432/postgres"

conn = psycopg2.connect(DB_URL)
conn.autocommit = True  # No transaction timeout issues
cur = conn.cursor()

# Get distinct junk retailers first
cur.execute("SELECT DISTINCT retailer FROM store_locations WHERE retailer NOT IN ('Kroger', 'Smart & Final');")
junk = [row[0] for row in cur.fetchall()]
print(f"Junk retailers to delete: {junk}")

# Delete each one with no timeout
for retailer in junk:
    cur.execute("DELETE FROM store_locations WHERE retailer = %s;", (retailer,))
    print(f"  Deleted '{retailer}'")

# Verify
cur.execute("SELECT retailer, COUNT(*) FROM store_locations GROUP BY retailer ORDER BY COUNT(*) DESC;")
print("\nRemaining:")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]}")

cur.close()
conn.close()