import os

TESTS_DIR = os.path.abspath("apps/api/tests")
all_test_files = sorted([f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")])

p9_test_files = [
    "test_database_bootstrap_and_migrations.py",
    "test_oauth_multiworker_security.py",
    "test_redis_rate_limiter.py",
    "test_tenant_isolation_security.py",
    "test_tenant_matrix_security.py",
    "test_p0_tenant_isolation_remediation.py",
    "test_webhook_security.py",
    "test_whatsapp_webhook_security_hardening.py",
    "test_razorpay_production.py",
    "test_master_build_13_billing.py",
    "test_part21_8_autonomous_sales_loop.py",
    "test_phase2c_production_pilot.py",
    "test_master_build_08_sales_pipeline.py",
    "test_part18_deal_lifecycle.py",
    "test_stage_b_c_security_architecture_consolidation.py",
    "test_stage_f_high_value_product_completion.py",
    "test_master_build_14_intelligence.py",
    "test_master_build_14_security.py"
]

print(f"Total test files in apps/api/tests: {len(all_test_files)}")
print(f"Phase 9 covered files count: {len(p9_test_files)}")

extra = set(all_test_files) - set(p9_test_files)
print(f"\nOther test files in tests dir ({len(extra)}):")
for f in sorted(extra):
    print(f"  {f}")
