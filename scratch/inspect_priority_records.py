import asyncio
import asyncpg
import hashlib

def mask_email(email):
    if not email:
        return "None"
    parts = email.split("@")
    if len(parts) == 2:
        return f"{parts[0][:2]}***@{parts[1]}"
    return "***"

def hash_id(id_val):
    if not id_val:
        return "None"
    return hashlib.sha256(str(id_val).encode()).hexdigest()[:10]

async def inspect_priority_records():
    live_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/leadscore")
    backup_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/leadscore_verify_phase6")

    print("=== ORGANIZATIONS ===")
    b_orgs = await backup_conn.fetch("SELECT id, name, slug FROM organizations ORDER BY id")
    l_orgs = await live_conn.fetch("SELECT id, name, slug FROM organizations ORDER BY id")
    print(f"Backup orgs ({len(b_orgs)}), Live orgs ({len(l_orgs)})")
    assert [r["id"] for r in b_orgs] == [r["id"] for r in l_orgs]
    for r in l_orgs:
        print(f"  ID: {r['id']} | Slug: {r['slug']}")

    print("\n=== BROKERS ===")
    b_brokers = await backup_conn.fetch("SELECT id, name, email FROM brokers ORDER BY id")
    l_brokers = await live_conn.fetch("SELECT id, name, email FROM brokers ORDER BY id")
    print(f"Backup brokers ({len(b_brokers)}), Live brokers ({len(l_brokers)})")
    assert [r["id"] for r in b_brokers] == [r["id"] for r in l_brokers]
    for r in l_brokers:
        print(f"  ID: {r['id']} | Email: {mask_email(r['email'])}")

    print("\n=== ORGANIZATION_MEMBERS ===")
    b_members = await backup_conn.fetch("SELECT organization_id, broker_id, role FROM organization_members ORDER BY organization_id, broker_id")
    l_members = await live_conn.fetch("SELECT organization_id, broker_id, role FROM organization_members ORDER BY organization_id, broker_id")
    print(f"Backup members ({len(b_members)}), Live members ({len(l_members)})")
    assert [(r["organization_id"], r["broker_id"]) for r in b_members] == [(r["organization_id"], r["broker_id"]) for r in l_members]
    for r in l_members:
        print(f"  Org: {r['organization_id']} | Broker: {r['broker_id']} | Role: {r['role']}")

    print("\n=== LEADS ===")
    b_leads = await backup_conn.fetch("SELECT id, name, organization_id, broker_id, status FROM leads ORDER BY id")
    l_leads = await live_conn.fetch("SELECT id, name, organization_id, broker_id, status FROM leads ORDER BY id")
    print(f"Backup leads ({len(b_leads)}), Live leads ({len(l_leads)})")
    assert [r["id"] for r in b_leads] == [r["id"] for r in l_leads]
    for r in l_leads:
        print(f"  ID: {r['id']} | Org: {r['organization_id']} | Status: {r['status']}")

    print("\n=== TASKS ===")
    b_tasks = await backup_conn.fetch("SELECT id, title, organization_id, broker_id, status FROM tasks ORDER BY id")
    l_tasks = await live_conn.fetch("SELECT id, title, organization_id, broker_id, status FROM tasks ORDER BY id")
    print(f"Backup tasks ({len(b_tasks)}), Live tasks ({len(l_tasks)})")
    assert [r["id"] for r in b_tasks] == [r["id"] for r in l_tasks]
    for r in l_tasks:
        print(f"  ID: {r['id']} | Org: {r['organization_id']} | Status: {r['status']}")

    print("\n=== CONVERSATIONS ===")
    b_convs = await backup_conn.fetch("SELECT id, lead_id, broker_id, channel FROM conversations ORDER BY id")
    l_convs = await live_conn.fetch("SELECT id, lead_id, broker_id, channel FROM conversations ORDER BY id")
    print(f"Backup convs ({len(b_convs)}), Live convs ({len(l_convs)})")
    assert [r["id"] for r in b_convs] == [r["id"] for r in l_convs]
    for r in l_convs:
        print(f"  ID: {r['id']} | Channel: {r['channel']}")

    await live_conn.close()
    await backup_conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_priority_records())

