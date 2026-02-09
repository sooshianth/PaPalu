import sqlite3
import json
from datetime import datetime

def get_default_value(col_type, col_name):
    """Generate appropriate default value based on column type and name."""
    col_type_upper = col_type.upper()
    col_name_lower = col_name.lower()
    
    # Boolean fields
    if 'BOOLEAN' in col_type_upper or col_name_lower.startswith('is_') or col_name_lower.startswith('has_'):
        return 0
    
    # Date/time fields
    if 'DATE' in col_type_upper or 'TIME' in col_type_upper:
        if 'date' in col_name_lower or 'time' in col_name_lower:
            return datetime.now().isoformat()
    
    # Foreign key or ID fields (typically end with _id or named 'id')
    if col_name_lower.endswith('_id') or col_name_lower == 'id':
        return None  # Will be handled specially
    
    # Text fields
    if 'CHAR' in col_type_upper or 'TEXT' in col_type_upper or 'CLOB' in col_type_upper:
        # Special handling for specific field patterns
        if 'name' in col_name_lower:
            return 'Unknown'
        elif 'description' in col_name_lower or 'note' in col_name_lower:
            return ''
        elif 'status' in col_name_lower:
            return 'pending'
        elif 'code' in col_name_lower:
            return 'N/A'
        else:
            return ''
    
    # Numeric fields
    if 'INT' in col_type_upper or 'REAL' in col_type_upper or 'FLOAT' in col_type_upper or 'NUMERIC' in col_type_upper or 'DECIMAL' in col_type_upper:
        if 'price' in col_name_lower or 'cost' in col_name_lower or 'amount' in col_name_lower:
            return 0
        elif 'quantity' in col_name_lower or 'count' in col_name_lower:
            return 0
        else:
            return 0
    
    # Default fallback
    return ''

def get_table_schema(cur, table):
    """Get full table schema including constraints."""
    cur.execute(f"PRAGMA table_info({table})")
    columns_info = cur.fetchall()
    
    schema = {}
    for col in columns_info:
        col_id, col_name, col_type, not_null, default_val, is_pk = col
        schema[col_name] = {
            'type': col_type,
            'not_null': not_null == 1,
            'default': default_val,
            'is_pk': is_pk == 1
        }
    
    return schema

def fix_row_data(row, schema, insert_cols, table):
    """Fix row data by adding missing required columns with appropriate defaults."""
    fixed_values = []
    missing_cols = []
    
    for col in insert_cols:
        value = row.get(col)
        col_info = schema.get(col, {})
        
        # If value is missing and column is NOT NULL
        if value is None and col_info.get('not_null', False) and not col_info.get('is_pk', False):
            default = get_default_value(col_info.get('type', ''), col)
            fixed_values.append(default)
            missing_cols.append(col)
        else:
            fixed_values.append(value)
    
    if missing_cols:
        print(f"  ⚠ Fixed missing values in {table}: {', '.join(missing_cols)}")
    
    return fixed_values

def import_data(db_path, in_file):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    data = json.load(open(in_file, "r", encoding="utf-8"))
    
    total_tables = len([t for t, rows in data.items() if rows])
    current_table = 0

    for table, rows in data.items():
        if not rows:
            continue
        
        current_table += 1
        print(f"\n[{current_table}/{total_tables}] Processing table: {table}")

        # columns from JSON export
        json_columns = list(rows[0].keys())

        # get full table schema
        schema = get_table_schema(cur, table)
        current_columns = list(schema.keys())

        # keep only columns that exist now
        insert_cols = [c for c in json_columns if c in current_columns]
        
        # skip if no columns to insert
        if not insert_cols:
            print(f"  ⊗ Skipping: no matching columns")
            continue
        
        placeholders = ",".join("?" * len(insert_cols))
        col_string = ",".join(insert_cols)
        
        success_count = 0
        error_count = 0

        for idx, row in enumerate(rows, 1):
            try:
                # Fix row data with appropriate defaults for missing required fields
                values = fix_row_data(row, schema, insert_cols, table)
                
                cur.execute(
                    f"INSERT OR REPLACE INTO {table} ({col_string}) VALUES ({placeholders})",
                    values
                )
                success_count += 1
                
            except sqlite3.IntegrityError as e:
                error_count += 1
                error_msg = str(e)
                
                # Try to extract which column failed
                if "NOT NULL constraint failed" in error_msg:
                    failed_col = error_msg.split(":")[-1].strip()
                    print(f"  ✗ Row {idx}: NOT NULL constraint on {failed_col}")
                elif "UNIQUE constraint failed" in error_msg:
                    print(f"  ✗ Row {idx}: UNIQUE constraint violation - {error_msg}")
                elif "FOREIGN KEY constraint failed" in error_msg:
                    print(f"  ✗ Row {idx}: FOREIGN KEY constraint - {error_msg}")
                else:
                    print(f"  ✗ Row {idx}: {error_msg}")
                    
            except Exception as e:
                error_count += 1
                print(f"  ✗ Row {idx}: Unexpected error - {str(e)}")
        
        print(f"  ✓ Inserted: {success_count}, Failed: {error_count}")

    conn.commit()
    conn.close()
    print(f"\n{'='*50}")
    print(f"Data import completed to {db_path}")
    print(f"{'='*50}")

if __name__ == "__main__":
    import_data("db.sqlite3", "db.json")