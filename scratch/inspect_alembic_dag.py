import os
import glob
import re
from alembic.config import Config
from alembic.script import ScriptDirectory

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    alembic_ini = os.path.join(repo_root, "apps", "api", "alembic.ini")
    
    cfg = Config(alembic_ini)
    cfg.set_main_option("script_location", os.path.join(repo_root, "apps", "api", "alembic"))
    
    script = ScriptDirectory.from_config(cfg)
    
    heads = script.get_heads()
    bases = script.get_bases()
    print("=== ALEMBIC GRAPH INSPECTION VIA SCRIPT_DIRECTORY ===")
    print(f"Heads ({len(heads)}): {heads}")
    print(f"Bases ({len(bases)}): {bases}")
    
    # Detailed chain from heads to bases
    for h in heads:
        rev = script.get_revision(h)
        print(f"\nTraceback from Head '{h}':")
        curr = rev
        count = 0
        while curr:
            down = curr.down_revision
            deps = getattr(curr, 'dependencies', None)
            print(f"  [{count}] {curr.revision} (file: {os.path.basename(curr.path)}) -> down: {down}, depends_on: {deps}")
            if curr.down_revision:
                if isinstance(curr.down_revision, tuple):
                    curr = script.get_revision(curr.down_revision[0])
                else:
                    curr = script.get_revision(curr.down_revision)
            else:
                curr = None
            count += 1
            if count > 100:
                print("  ... Loop or limit reached")
                break

    # Look specifically for 0014, 0048, 0049, 9999
    print("\n=== SPECIAL REVISIONS CHECK ===")
    for target in ["0014_global_infrastructure", "0048_schema_reconciliation_parity", "0049_source_attribution_uuid_parity", "9999_production_baseline"]:
        try:
            r = script.get_revision(target)
            if r:
                print(f"Target '{target}': found! down_revision={r.down_revision}, dependencies={getattr(r, 'dependencies', None)}")
            else:
                print(f"Target '{target}': NOT FOUND!")
        except Exception as e:
            print(f"Target '{target}': error: {e}")

if __name__ == "__main__":
    main()

