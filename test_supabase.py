"""
Run this to find your working Supabase connection.
python test_supabase.py
"""
import psycopg2

PASSWORD = "sCEvLBhvq0lIWeug"
PROJECT  = "nrsgtcvevkwxvmxwhwco"

configs = [
    # Direct connection - different user formats
    f"postgresql://postgres:{PASSWORD}@db.{PROJECT}.supabase.co:5432/postgres?sslmode=require",
    f"postgresql://postgres.{PROJECT}:{PASSWORD}@db.{PROJECT}.supabase.co:5432/postgres?sslmode=require",
    # Pooler - session mode port 5432
    f"postgresql://postgres.{PROJECT}:{PASSWORD}@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require",
    # Pooler - transaction mode port 6543
    f"postgresql://postgres.{PROJECT}:{PASSWORD}@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require",
    # Without project in username
    f"postgresql://postgres:{PASSWORD}@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require",
    f"postgresql://postgres:{PASSWORD}@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require",
]

print("Testing Supabase connections...\n")
for i, url in enumerate(configs, 1):
    display = url[:60] + "..."
    try:
        conn = psycopg2.connect(url, connect_timeout=8)
        conn.close()
        print(f"✅ Config {i} WORKS: {display}")
        print(f"\nCopy this URL to your .env:\nDATABASE_URL={url}\n")
        break
    except Exception as e:
        print(f"❌ Config {i} failed: {str(e)[:80]}")

print("\nDone.")
