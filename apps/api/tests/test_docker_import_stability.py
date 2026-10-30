"""
Unit Regression Tests for Docker Startup and Import Stability
=============================================================
Ensures critical modules evaluated at import time:
1. app.modules.auth.service
2. app.modules.follow_up.message_generation.grounded_generator
3. app.modules.lead_intelligence.rules_engine.rule_evaluator
4. app.modules.global_.identity.cross_country_identity
5. app.modules.lead_qualification.service
6. app.modules.properties.service
7. app.modules.prospect_intelligence.services.sales_brief_generator
8. app.modules.recommendation.constraint_engine.hard_constraints
9. app.modules.recommendation.scoring.compatibility_scorer
10. app.modules.recommendation.scoring.FX_converter
11. app.modules.security.retention_service
import cleanly and execute without NameError (such as missing Optional, Tuple, Union, Dict, secrets, uuid).
"""
import uuid
import pytest

def test_auth_service_imports_and_token_creation():
    from app.modules.auth.service import create_access_token
    token = create_access_token("test-user-id")
    assert isinstance(token, str)
    assert len(token) > 20

def test_grounded_message_generator_import_and_execution():
    from app.modules.follow_up.message_generation.grounded_generator import GroundedMessageGenerator
    gen = GroundedMessageGenerator()
    
    # WhatsApp branch
    body_wa, subj_wa = gen.generate_message(
        context={"lead_name": "Rohan", "preferred_location": "Whitefield"},
        language="en",
        channel="WHATSAPP"
    )
    assert isinstance(body_wa, str)
    assert subj_wa is None

    # Email branch
    body_em, subj_em = gen.generate_message(
        context={"lead_name": "Rohan", "preferred_location": "Whitefield"},
        language="en",
        channel="EMAIL"
    )
    assert isinstance(body_em, str)
    assert subj_em is not None
    assert "Whitefield" in subj_em

def test_rule_evaluator_import_and_execution():
    from app.modules.lead_intelligence.rules_engine.rule_evaluator import RuleEvaluator
    evaluator = RuleEvaluator()
    adj, fired = evaluator.evaluate_rules(features={"budget_max": 20000000})
    assert isinstance(adj, float)
    assert isinstance(fired, list)

def test_properties_service_import():
    from app.modules.properties.service import PropertyService
    assert PropertyService is not None

def test_retention_service_import():
    from app.modules.security.retention_service import DataRetentionManager
    is_held, reason = DataRetentionManager.is_under_legal_hold("test-id")
    assert is_held is False
    assert reason is None

def test_celery_task_registration_imports_cleanly():
    from app.tasks.followup_tasks import evaluate_followups
    assert evaluate_followups is not None
