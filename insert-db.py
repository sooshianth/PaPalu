import sqlite3
import json

def import_data(db_path, in_file):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    data = json.load(open(in_file, "r", encoding="utf-8"))

    for table, rows in data.items():
        if not rows:
            continue

        # columns from JSON export
        json_columns = list(rows[0].keys())

        # get current table columns
        cur.execute(f"PRAGMA table_info({table})")
        current_columns = [col[1] for col in cur.fetchall()]

        # keep only columns that exist now
        insert_cols = [c for c in json_columns if c in current_columns]
        
        # skip if no columns to insert
        if not insert_cols:
            print(f"Skipping {table}: no matching columns")
            continue
        
        placeholders = ",".join("?" * len(insert_cols))
        col_string = ",".join(insert_cols)

        for row in rows:
            values = [row.get(c) for c in insert_cols]
            cur.execute(
                f"INSERT OR REPLACE INTO {table} ({col_string}) VALUES ({placeholders})",
                values
            )

    conn.commit()
    conn.close()
    print("Data imported into", db_path)

if __name__ == "__main__":
    import_data("db.sqlite3", "db.json")