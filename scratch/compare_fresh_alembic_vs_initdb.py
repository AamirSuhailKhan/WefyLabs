import os
import sys
import json
import asyncio
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.database import engine, Base
import app.models

async def inspect_schema(conn, schema_name):
    # 1. Tables
    tbl_res = await conn.execute(text(f"""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = '{schema_name}' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """))
    tables = set(r[0] for r in tbl_res.fetchall())

    # 2. Columns
    col_res = await conn.execute(text(f"""
        SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = '{schema_name}'
        ORDER BY table_name, column_name
    """))
    columns = {}
    for r in col_res.fetchall():
        tname, cname, dtype, udt, nullable, default = r
        columns.setdefault(tname, {})[cname] = {
            "data_type": dtype,
            "udt_name": udt,
            "is_nullable": nullable == "YES",
            "column_default": default
        }

    # 3. Constraints
    con_res = await conn.execute(text(f"""
        SELECT cl.relname, c.conname, c.contype, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        JOIN pg_class cl ON cl.oid = c.conrelid
        WHERE n.nspname = '{schema_name}'
        ORDER BY cl.relname, c.conname
    """))
    constraints = {}
    for r in con_res.fetchall():
        relname, conname, contype, condef = r
        ctype = contype.decode() if isinstance(contype, bytes) else str(contype)
        constraints.setdefault(relname, []).append({
            "conname": conname,
            "contype": ctype,
            "condef": condef
        })

    # 4. Indexes
    idx_res = await conn.execute(text(f"""
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = '{schema_name}'
        ORDER BY tablename, indexname
    """))
    indexes = {}
    for r in idx_res.fetchall():
        tname, iname, idef = r
        indexes.setdefault(tname, {})[iname] = idef

    # 5. Alembic Version
    v_res = await conn.execute(text(f"""
        SELECT table_schema FROM information_schema.tables 
        WHERE table_schema IN ('{schema_name}', 'public') AND table_name = 'alembic_version'
        LIMIT 1
    """))
    av_schema = v_res.scalar()
    if av_schema:
        v_res2 = await conn.execute(text(f"SELECT version_num FROM {av_schema}.alembic_version"))
        head = v_res2.scalar()
    else:
        head = None

    return {
        "tables": tables,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "alembic_head": head
    }

async def run_comparison():
    async with engine.begin() as conn:
        schema_alembic = await inspect_schema(conn, "test_canonical_p7")
        schema_initdb = await inspect_schema(conn, "phase9_fresh_disposable")

    print(f"=== Alembic Schema (test_canonical_p7) ===")
    print(f"Tables: {len(schema_alembic['tables'])}")
    print(f"Alembic Head: {schema_alembic['alembic_head']}")
    total_cols_alembic = sum(len(c) for c in schema_alembic['columns'].values())
    total_cons_alembic = sum(len(c) for c in schema_alembic['constraints'].values())
    total_idxs_alembic = sum(len(i) for i in schema_alembic['indexes'].values())
    print(f"Columns: {total_cols_alembic}, Constraints: {total_cons_alembic}, Indexes: {total_idxs_alembic}")

    print(f"\n=== InitDB Schema (phase9_fresh_disposable) ===")
    print(f"Tables: {len(schema_initdb['tables'])}")
    print(f"Alembic Head: {schema_initdb['alembic_head']}")
    total_cols_initdb = sum(len(c) for c in schema_initdb['columns'].values())
    total_cons_initdb = sum(len(c) for c in schema_initdb['constraints'].values())
    total_idxs_initdb = sum(len(i) for i in schema_initdb['indexes'].values())
    print(f"Columns: {total_cols_initdb}, Constraints: {total_cons_initdb}, Indexes: {total_idxs_initdb}")

    # Table differences
    missing_in_initdb = schema_alembic['tables'] - schema_initdb['tables']
    missing_in_alembic = schema_initdb['tables'] - schema_alembic['tables']
    print(f"\n--- Table Differences ---")
    print(f"Missing in initdb: {missing_in_initdb}")
    print(f"Missing in alembic: {missing_in_alembic}")

    # Column differences
    col_diffs = []
    for tname in sorted(schema_alembic['tables'] & schema_initdb['tables']):
        alembic_tcols = schema_alembic['columns'].get(tname, {})
        initdb_tcols = schema_initdb['columns'].get(tname, {})
        for col, info in alembic_tcols.items():
            if col not in initdb_tcols:
                col_diffs.append(f"Table {tname}: column {col} in alembic but missing in initdb")
            else:
                i_info = initdb_tcols[col]
                # Compare nullability or udt
                if info['udt_name'] != i_info['udt_name']:
                    col_diffs.append(f"Table {tname}.{col}: type mismatch (alembic: {info['udt_name']}, initdb: {i_info['udt_name']})")
        for col in initdb_tcols:
            if col not in alembic_tcols:
                col_diffs.append(f"Table {tname}: column {col} in initdb but missing in alembic")

    print(f"\n--- Column Differences ({len(col_diffs)}) ---")
    for d in col_diffs[:20]:
        print(f"  {d}")
    if len(col_diffs) > 20:
        print(f"  ... and {len(col_diffs) - 20} more")

    # Index differences
    idx_diffs = []
    for tname in sorted(schema_alembic['tables'] & schema_initdb['tables']):
        a_idxs = schema_alembic['indexes'].get(tname, {})
        i_idxs = schema_initdb['indexes'].get(tname, {})
        for iname, idef in a_idxs.items():
            if iname not in i_idxs:
                idx_diffs.append(f"Table {tname}: index {iname} in alembic but not in initdb")
        for iname, idef in i_idxs.items():
            if iname not in a_idxs:
                idx_diffs.append(f"Table {tname}: index {iname} in initdb but not in alembic")

    print(f"\n--- Index Differences ({len(idx_diffs)}) ---")
    for d in idx_diffs[:20]:
        print(f"  {d}")
    if len(idx_diffs) > 20:
        print(f"  ... and {len(idx_diffs) - 20} more")

    # Constraint differences
    con_diffs = []
    for tname in sorted(schema_alembic['tables'] & schema_initdb['tables']):
        a_c = {c['conname']: c for c in schema_alembic['constraints'].get(tname, [])}
        i_c = {c['conname']: c for c in schema_initdb['constraints'].get(tname, [])}
        for cname in a_c:
            if cname not in i_c:
                con_diffs.append(f"Table {tname}: constraint {cname} ({a_c[cname]['contype']}) in alembic but not in initdb")
        for cname in i_c:
            if cname not in a_c:
                con_diffs.append(f"Table {tname}: constraint {cname} ({i_c[cname]['contype']}) in initdb but not in alembic")

    summary = {
        "alembic": {
            "tables": len(schema_alembic['tables']),
            "head": schema_alembic['alembic_head'],
            "columns": total_cols_alembic,
            "constraints": total_cons_alembic,
            "indexes": total_idxs_alembic
        },
        "initdb": {
            "tables": len(schema_initdb['tables']),
            "head": schema_initdb['alembic_head'],
            "columns": total_cols_initdb,
            "constraints": total_cons_initdb,
            "indexes": total_idxs_initdb
        },
        "table_differences": {
            "missing_in_initdb": list(missing_in_initdb),
            "missing_in_alembic": list(missing_in_alembic)
        },
        "column_diff_count": len(col_diffs),
        "index_diff_count": len(idx_diffs),
        "constraint_diff_count": len(con_diffs)
    }
    with open("scratch/comparison_results.json", "w") as fp:
        json.dump(summary, fp, indent=2)

    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    asyncio.run(run_comparison())
