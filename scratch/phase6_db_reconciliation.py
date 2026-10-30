"""
Phase 6 Forensic Database Reconciliation Script
Strict read-only inspection comparing 'leadscore_verify_phase6' (pre-Phase 5 backup)
with 'leadscore' (active live database).
"""
import asyncio
import hashlib
import json
import uuid
from typing import Dict, List, Set, Any
import asyncpg

LIVE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore"
BACKUP_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore_verify_phase6"

PRIORITY_TABLES = [
    "organizations",
    "organization_members",
    "brokers",
    "leads",
    "conversations",
    "tasks",
    "payment_orders",
    "lead_notes",
    "activities",
    "scores",
    "subscriptions",
]

def hash_val(val: Any) -> str:
    if val is None:
        return "NULL"
    return hashlib.sha256(str(val).encode("utf-8")).hexdigest()[:12]

async def run_forensic_audit():
    live_conn = await asyncpg.connect(LIVE_URL)
    await live_conn.execute("SET default_transaction_read_only = on;")
    backup_conn = await asyncpg.connect(BACKUP_URL)
    await backup_conn.execute("SET default_transaction_read_only = on;")

    audit_result = {
        "timestamp": "2026-10-28T19:20:00+05:30",
        "alembic_version": {},
        "table_counts": {},
        "schema_differences": {},
        "priority_tables_diff": {},
        "non_empty_tables": [],
        "missing_from_live": {},
        "added_in_live": {},
        "content_hash_differences": {},
        "foreign_keys_summary": {},
    }

    # 1. Alembic version
    live_rev = await live_conn.fetchval("SELECT version_num FROM alembic_version")
    backup_rev = await backup_conn.fetchval("SELECT version_num FROM alembic_version")
    audit_result["alembic_version"] = {"live": live_rev, "backup": backup_rev}

    # 2. Enumerate tables
    tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """
    live_tables = set(r["table_name"] for r in await live_conn.fetch(tables_query))
    backup_tables = set(r["table_name"] for r in await backup_conn.fetch(tables_query))

    table_diff = {
        "only_in_live": list(live_tables - backup_tables),
        "only_in_backup": list(backup_tables - live_tables),
        "common_tables": len(live_tables & backup_tables)
    }
    audit_result["schema_differences"]["tables"] = table_diff

    all_tables = sorted(list(live_tables & backup_tables))

    # 3. Check row counts for all common tables
    count_mismatches = []
    non_empty = []

    for tbl in all_tables:
        c_live = await live_conn.fetchval(f'SELECT COUNT(*) FROM "{tbl}"')
        c_backup = await backup_conn.fetchval(f'SELECT COUNT(*) FROM "{tbl}"')
        
        if c_live > 0 or c_backup > 0:
            non_empty.append({
                "table": tbl,
                "backup_count": c_backup,
                "live_count": c_live,
                "match": c_live == c_backup
            })
        if c_live != c_backup:
            count_mismatches.append({
                "table": tbl,
                "backup_count": c_backup,
                "live_count": c_live,
                "diff": c_live - c_backup
            })

    audit_result["non_empty_tables"] = non_empty
    audit_result["table_counts"]["mismatches"] = count_mismatches

    # 4. Detailed Primary Key and Fingerprint Comparison for all non-empty tables and priority tables
    tables_to_check = set([x["table"] for x in non_empty] + PRIORITY_TABLES)

    for tbl in sorted(list(tables_to_check)):
        if tbl not in live_tables or tbl not in backup_tables:
            continue

        # Get primary key column(s)
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'public'
              AND tc.table_name = $1
            ORDER BY kcu.ordinal_position;
        """
        pks = [r["column_name"] for r in await live_conn.fetch(pk_query, tbl)]
        if not pks:
            pk_col = "id"
        else:
            pk_col = pks[0] # assuming single PK for simplicity or first PK

        # Get column list
        cols_query = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position;
        """
        cols = [r["column_name"] for r in await live_conn.fetch(cols_query, tbl)]
        # Filter out volatile/geometry/vector if necessary or cast to text
        col_exprs = [f'COALESCE("{c}"::text, \'\')' for c in cols]
        concat_expr = " || '||' || ".join(col_exprs)

        # Fetch all rows from backup
        q_backup = f'SELECT "{pk_col}"::text as pk_id, md5({concat_expr}) as row_hash FROM "{tbl}"'
        rows_backup = await backup_conn.fetch(q_backup)
        backup_map = {r["pk_id"]: r["row_hash"] for r in rows_backup}

        # Fetch all rows from live
        q_live = f'SELECT "{pk_col}"::text as pk_id, md5({concat_expr}) as row_hash FROM "{tbl}"'
        rows_live = await live_conn.fetch(q_live)
        live_map = {r["pk_id"]: r["row_hash"] for r in rows_live}

        missing_in_live = set(backup_map.keys()) - set(live_map.keys())
        added_in_live = set(live_map.keys()) - set(backup_map.keys())
        common_keys = set(backup_map.keys()) & set(live_map.keys())

        hash_diffs = []
        for k in common_keys:
            if backup_map[k] != live_map[k]:
                hash_diffs.append(hash_val(k))

        if missing_in_live:
            audit_result["missing_from_live"][tbl] = [hash_val(k) for k in missing_in_live]
        if added_in_live:
            audit_result["added_in_live"][tbl] = [hash_val(k) for k in added_in_live]
        if hash_diffs:
            audit_result["content_hash_differences"][tbl] = hash_diffs

        audit_result["priority_tables_diff"][tbl] = {
            "pk_col": pk_col,
            "backup_rows": len(backup_map),
            "live_rows": len(live_map),
            "missing_in_live_count": len(missing_in_live),
            "added_in_live_count": len(added_in_live),
            "content_hash_diff_count": len(hash_diffs)
        }

    # 5. Foreign Key Dependency Graph inspection for Priority tables
    fk_query = """
        SELECT
            tc.table_name as child_table,
            kcu.column_name as fk_column,
            ccu.table_name AS parent_table,
            ccu.column_name AS parent_column,
            rc.delete_rule as on_delete
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON rc.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND (ccu.table_name IN ('organizations', 'brokers', 'leads') 
               OR tc.table_name IN ('organizations', 'brokers', 'leads', 'organization_members'))
        ORDER BY ccu.table_name, tc.table_name;
    """
    fks = await live_conn.fetch(fk_query)
    cascade_fks = []
    restrict_fks = []
    for r in fks:
        entry = {
            "parent_table": r["parent_table"],
            "child_table": r["child_table"],
            "fk_column": r["fk_column"],
            "on_delete": r["on_delete"]
        }
        if r["on_delete"] == "CASCADE":
            cascade_fks.append(entry)
        else:
            restrict_fks.append(entry)
    
    audit_result["foreign_keys_summary"] = {
        "total_relevant_fks": len(fks),
        "cascade_count": len(cascade_fks),
        "restrict_count": len(restrict_fks),
        "cascade_sample": cascade_fks[:15]
    }

    await live_conn.close()
    await backup_conn.close()

    with open("scratch/phase6_forensic_results.json", "w") as f:
        json.dump(audit_result, f, indent=2)

    print("Forensic audit completed successfully. Written to scratch/phase6_forensic_results.json")
    print(f"Summary:")
    print(f"  - Common tables checked: {len(all_tables)}")
    print(f"  - Non-empty tables: {len(non_empty)}")
    print(f"  - Table count mismatches: {len(count_mismatches)}")
    print(f"  - Tables with records missing from live: {len(audit_result['missing_from_live'])}")
    print(f"  - Tables with records added in live: {len(audit_result['added_in_live'])}")
    print(f"  - Tables with row hash differences: {len(audit_result['content_hash_differences'])}")

if __name__ == "__main__":
    asyncio.run(run_forensic_audit())

