import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))
from app.database import Base
import app.models

models = Base.metadata.tables

print("Checking presence in Base.metadata:")
print("1. token_blacklist:", "token_blacklist" in models)
if "token_blacklist" in models:
    tb = models["token_blacklist"]
    print("   cols:", [c.name for c in tb.columns])
    print("   indexes:", [i.name for i in tb.indexes])

print("2. brokers.auth_version:", "auth_version" in [c.name for c in models["brokers"].columns])
print("   brokers.google_subject:", "google_subject" in [c.name for c in models["brokers"].columns])
print("   brokers.ix_brokers_google_subject:", any(i.name == "ix_brokers_google_subject" for i in models["brokers"].indexes))

print("3. webhook_event_claims:", "webhook_event_claims" in models)
if "webhook_event_claims" in models:
    wc = models["webhook_event_claims"]
    print("   cols:", [c.name for c in wc.columns])
    print("   indexes:", [i.name for i in wc.indexes])
    print("   uniques:", [u.name for u in wc.constraints if hasattr(u, "columns")])

print("4. knowledge_embeddings.embedding:", "embedding" in [c.name for c in models["knowledge_embeddings"].columns])
if "embedding" in [c.name for c in models["knowledge_embeddings"].columns]:
    print("   type:", models["knowledge_embeddings"].columns["embedding"].type)
print("   knowledge_embeddings indexes:", [i.name for i in models["knowledge_embeddings"].indexes])

print("5. pilot_tenants constraints:", [c.name for c in models["pilot_tenants"].constraints])
print("6. conversation_states constraints:", [c.name for c in models["conversation_states"].constraints])
print("7. knowledge_document_versions constraints:", [c.name for c in models["knowledge_document_versions"].constraints])
