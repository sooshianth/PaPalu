import sqlite3
import json

def export_data(db_path, out_file):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # get all real tables (skip sqlite internal ones)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [t[0] for t in cur.fetchall()]

    # exclude django migrations and admin logs
    excluded_tables = {'django_migrations', 'django_admin_log'}
    tables = [t for t in tables if t not in excluded_tables]

    export_obj = {}

    for table in tables:
        cur.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cur.fetchall()]

        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()

        # store data as list of dicts for resilience
        export_obj[table] = [
            dict(zip(columns, row))
            for row in rows
        ]

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(export_obj, f, indent=2)

    conn.close()
    print("Data exported to", out_file)

if __name__ == "__main__":
    export_data("db.sqlite3", "db.json")