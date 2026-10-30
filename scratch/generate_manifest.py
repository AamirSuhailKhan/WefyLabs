import os
import hashlib
import json
import subprocess

def get_file_info(rel_path):
    full_path = os.path.join(os.getcwd(), rel_path)
    if not os.path.exists(full_path):
        return None
    size = os.path.getsize(full_path)
    h = hashlib.sha256()
    with open(full_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return {
        "path": rel_path.replace("\\", "/"),
        "sha256": h.hexdigest(),
        "size_bytes": size
    }

def main():
    base_head = "0383020a865fe315adfda4549f536a594fb10454"
    branch = "level-3"

    key_files = [
        "apps/api/app/models/acquisition_models.py",
        "apps/api/app/models/broker.py",
        "apps/api/app/models/subscription.py",
        "apps/api/alembic/versions/0048_schema_reconciliation_parity.py",
        "apps/api/alembic/versions/0049_source_attribution_uuid_parity.py",
        "apps/api/alembic/versions/0050_broker_subscription_constraint_parity.py",
        "apps/api/alembic/env.py",
        "apps/api/scripts/release_migration.py",
        "apps/api/entrypoint.sh",
        "apps/api/Dockerfile",
        "apps/api/app/presentation/api/health.py",
        "render.yaml",
        "apps/api/tests/test_source_attribution_regression.py",
        "scratch/test_container_release_candidate_runtime.py",
        "scratch/test_release_invariant_hardening.py",
        "scratch/verify_live_supabase_smoke.py",
        "scratch/restore_and_compare_backup.py",
        "backups/supabase_prod_backup_pre_resolution.dump",
        "backups/supabase_prod_post_0050_20261030_072000.dump"
    ]

    manifest = {
        "manifest_version": "1.0.0",
        "created_at": "2026-10-30T08:15:00Z",
        "git_context": {
            "branch": branch,
            "base_head": base_head,
            "tracking_remote": "origin/level-3"
        },
        "target_release_candidate": {
            "image_tag": "wefylabs-api:rc-0050",
            "image_sha256": "747540e497957c7e937bd3e00925f749c8a5cde4c1a3b95f22572e89839da8c1",
            "authoritative_alembic_head": "0050_broker_subscription_constraint_parity"
        },
        "scope_exclusions": {
            "gemini_api_keys": "DEFERRED_BY_OWNER",
            "ai_provider_configuration": "DEFERRED_BY_OWNER",
            "live_ai_inference": "NOT_VERIFIED_IN_THIS_RUN"
        },
        "critical_artifacts": []
    }

    for k in key_files:
        info = get_file_info(k)
        if info:
            manifest["critical_artifacts"].append(info)

    out_path = "WEFYLABS_FINAL_RELEASE_SOURCE_MANIFEST.json"
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Generated {out_path} with {len(manifest['critical_artifacts'])} artifacts.")

if __name__ == "__main__":
    main()

