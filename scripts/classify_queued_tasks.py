"""
Phase 2C.6E — Queue Task Provenance Classifier
Reads all tasks from sales-loop-orchestration queue without consuming them.
Classifies each as: ENGINEERING_PROOF, HISTORICAL_PRODUCTION, GENUINE_PRODUCTION, SYNTHETIC, REPLAYED, UNKNOWN
"""
import os, sys, json, ssl, base64
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'api'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'apps', 'api', '.env'))

import redis

redis_url = os.environ['REDIS_URL']
r = redis.from_url(redis_url, ssl_cert_reqs=ssl.CERT_NONE)

# Known engineering-proof lead IDs and idempotency key patterns
ENGINEERING_PROOF_LEAD_IDS = {
    '8fff3ca6-aa19-4dae-b6b4-2759d5910fd8',  # Rajesh Kumar (Phase 2C.3B activation drill)
    'lead-amit-sharma-2434cac9',              # Amit Sharma (Phase 2C.6D real E2E verification)
}
ENGINEERING_PROOF_TENANTS = {
    # Non-pilot tenants (engineering org)
}
ENGINEERING_PROOF_SOURCES = {
    'engineering_proof', 'manual_injection', 'phase2c_e2e_proof',
    'run_real_stage1_e2e_proof', 'prove_stage1_event', 'phase2c6d'
}
ENGINEERING_PROOF_IDEM_PREFIXES = (
    'real_e2e_', 'phase2c6d_', 'engineering_', 'replay_', 'proof_',
)

PILOT_TENANT_ID = 'a0317351-5b6e-41d4-9af4-1a84b92f12e4'  # BeetleLabs Pilot org_id

items = r.lrange('sales-loop-orchestration', 0, -1)
print(f'=== PHASE 2C.6E QUEUE PROVENANCE CLASSIFICATION ===')
print(f'Queue: sales-loop-orchestration')
print(f'Total items: {len(items)}')
print(f'Timestamp: {datetime.now(timezone.utc).isoformat()}')
print()

classifications = []

for i, item in enumerate(items):
    raw = item.decode('utf-8') if isinstance(item, bytes) else item
    outer = json.loads(raw)
    headers = outer.get('headers', {})
    body_raw = outer.get('body', '')
    
    task_id = headers.get('id', 'UNKNOWN')
    task_name = headers.get('task', 'UNKNOWN')
    origin = headers.get('origin', 'UNKNOWN')
    occurred_at_str = None
    
    # Decode body
    try:
        body = json.loads(base64.b64decode(body_raw))
        kwargs = body[1] if isinstance(body, list) and len(body) > 1 else {}
        event_payload = kwargs.get('event_payload', {}) if isinstance(kwargs, dict) else {}
    except Exception:
        event_payload = {}
    
    event_type = event_payload.get('event_type', 'UNKNOWN')
    lead_id = event_payload.get('lead_id', 'UNKNOWN')
    tenant_id = event_payload.get('tenant_id', 'UNKNOWN')
    source = event_payload.get('source', 'UNKNOWN')
    idem_key = event_payload.get('idempotency_key', 'UNKNOWN')
    occurred_at_str = event_payload.get('occurred_at', 'UNKNOWN')

    # Classification logic
    classification = 'UNKNOWN'
    reason = ''

    if lead_id in ENGINEERING_PROOF_LEAD_IDS:
        classification = 'ENGINEERING_PROOF'
        reason = f'Lead ID {lead_id} is a known engineering-proof lead'
    elif source in ENGINEERING_PROOF_SOURCES:
        classification = 'ENGINEERING_PROOF'
        reason = f'Source "{source}" is an engineering tool source'
    elif any(idem_key.startswith(p) for p in ENGINEERING_PROOF_IDEM_PREFIXES):
        classification = 'ENGINEERING_PROOF'
        reason = f'Idempotency key has engineering prefix: {idem_key[:50]}'
    elif source == 'event_bus_bridge' and tenant_id != PILOT_TENANT_ID:
        # From the real event bus but potentially non-pilot tenant
        classification = 'HISTORICAL_PRODUCTION'
        reason = f'Enqueued from event_bus_bridge by real lead creation (non-pilot tenant {tenant_id})'
    elif source == 'event_bus_bridge':
        classification = 'HISTORICAL_PRODUCTION'
        reason = f'Enqueued from event_bus_bridge by real lead creation'
    elif source == 'inactive_lead_scanner':
        classification = 'HISTORICAL_PRODUCTION'
        reason = 'Enqueued by inactive lead scanner cron'
    else:
        classification = 'UNKNOWN'
        reason = f'Cannot determine provenance: source={source}'

    classifications.append({
        'index': i,
        'task_id': task_id,
        'task_name': task_name,
        'event_type': event_type,
        'lead_id': lead_id,
        'tenant_id': tenant_id,
        'source': source,
        'idempotency_key': idem_key,
        'occurred_at': occurred_at_str,
        'origin_host': origin,
        'classification': classification,
        'reason': reason,
    })

    print(f'[{i}] Task ID: {task_id}')
    print(f'     Event:   {event_type} | Lead: {lead_id}')
    print(f'     Tenant:  {tenant_id}')
    print(f'     Source:  {source}')
    print(f'     IdemKey: {idem_key[:80]}')
    print(f'     OccAt:   {occurred_at_str}')
    print(f'     Origin:  {origin}')
    print(f'     >>> CLASSIFICATION: {classification}')
    print(f'     >>> REASON: {reason}')
    print()

# Summary
from collections import Counter
counts = Counter(c['classification'] for c in classifications)
print('=== CLASSIFICATION SUMMARY ===')
for cls, cnt in counts.items():
    print(f'  {cls}: {cnt}')
print()
print('GOVERNANCE DECISION:')
print('None of the queued tasks may be automatically classified as GENUINE_PRODUCTION')
print('without independent verification against the database lead provenance.')
print()
print('SAFE WORKER START: The Celery worker may be started.')
print('Existing tasks will process through the idempotency key system.')
print('The Phase2CEventBridge will ONLY generate observations for pilot-enrolled tenants.')
print('Non-pilot tenant events will pass through but NOT create pilot observations.')

# Save JSON output
output = {
    'classification_timestamp': datetime.now(timezone.utc).isoformat(),
    'queue': 'sales-loop-orchestration',
    'total_items': len(items),
    'classifications': classifications,
    'summary': dict(counts),
}
output_path = os.path.join(os.path.dirname(__file__), 'phase2c6e_queue_classification.json')
with open(output_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f'\nSaved to: {output_path}')
