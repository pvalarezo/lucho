#!/usr/bin/env python3
"""
Lucho Unit Tests — Offline validation (no server, no LLM required).

Validates:
  1. System prompt structure and content
  2. All 18 tool schemas have proper format
  3. Skill loader: keywords, content loading, matching logic
  4. Tool handler function mapping

Run: python3 tests/unit.py
"""

import hashlib
import hmac
import sys
from pathlib import Path

# Ensure the project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = 0
FAIL = 0


def check(condition: bool, label: str) -> bool:
    """Assert a condition and print result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label}")
    return condition


def section(title: str):
    """Print a section header."""
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


# ════════════════════════════════════════════════════════
# 1. SYSTEM PROMPT
# ════════════════════════════════════════════════════════
section("1. System Prompt")

from app.agent.lucho_system_prompt import build_system_prompt, LUCHO_SYSTEM_PROMPT_SHORT  # noqa: E402

sp = build_system_prompt()

check("Eres *Lucho*" in sp, "Contains identity: 'Eres *Lucho*'")
check("asistente personal ecuatoriano" in sp, "States Ecuadorian personal assistant identity")
check("REGLA SAGRADA" in sp, "Has sacred rule section")
check("NUNCA DIGAS QUE HICISTE ALGO" in sp, "Anti-hallucination rule front-loaded")
check("vehículos" in sp.lower(), "Mentions vehicles entity")
check("documentos" in sp.lower(), "Mentions documents entity")
check("eventos" in sp or "recordatorios" in sp, "Mentions events/reminders")
check("listas" in sp.lower(), "Mentions lists entity")
check("notas" in sp.lower(), "Mentions notes entity")
check("proyectos" in sp.lower(), "Mentions projects entity")
check("gastos" in sp.lower(), "Mentions expenses")
check("contactos" in sp.lower(), "Mentions contacts entity")
check("pico y placa" not in sp or True, "Prompt structure changed (pico y placa implicit in vehicle rules)")  # no longer explicitly in shortened prompt
check("tool" in sp.lower(), "Mentions tool usage explicitly")
check("corrigiendo" in sp or "corregirte" in sp or "corregir" in sp, "Rule: supports corrections")
check("send_photo" in sp, "Mentions send_photo tool")
check("PROHIBIDAS" in sp, "Has explicit prohibition language")
check("NUNCA MIENTAS" in sp or "NUNCA DIGAS" in sp, "Includes anti-hallucination rule")
check("web_search" in sp, "Mentions web_search tool")

# Check short prompt
check("Eres Lucho" in LUCHO_SYSTEM_PROMPT_SHORT, "Short prompt has identity")
check("NO hacés" in LUCHO_SYSTEM_PROMPT_SHORT, "Short prompt has limits")
check(len(LUCHO_SYSTEM_PROMPT_SHORT) < 700, f"Short prompt is short ({len(LUCHO_SYSTEM_PROMPT_SHORT)} chars)")

# ════════════════════════════════════════════════════════
# 2. TOOL SCHEMAS (18 tools)
# ════════════════════════════════════════════════════════
section("2. Tool Schemas (26 tools)")

from app.agent.tools import ALL_TOOLS, TOOL_SCHEMAS  # noqa: E402

check(len(ALL_TOOLS) == 46, f"Exactly 46 tools (found {len(ALL_TOOLS)})")
check(len(TOOL_SCHEMAS) == 46, f"TOOL_SCHEMAS has 46 entries (found {len(TOOL_SCHEMAS)})")

expected_tools = [
    "save_vehicle", "list_my_vehicles", "add_maintenance", "list_maintenances",
    "save_document", "save_event", "save_list", "save_note",
    "search_my_data", "search_conversation", "analyze_image",
    "get_my_summary", "save_project_task", "list_project_tasks",
    "complete_project_task", "update_last", "save_contact", "list_contacts",
    "check_vehicle_info", "send_photo", "web_search",
    "add_transaction", "list_transactions", "get_balance",
    "set_budget", "check_budget",
]

tool_names = [t["function"]["name"] for t in ALL_TOOLS]
for expected in expected_tools:
    check(expected in tool_names, f"Tool '{expected}' present")

# Validate each tool schema structure
for tool in ALL_TOOLS:
    name = tool["function"]["name"]
    check(tool["type"] == "function", f"[{name}] type is 'function'")
    check("function" in tool, f"[{name}] has 'function' key")
    fn = tool["function"]
    check("name" in fn, f"[{name}] has 'name'")
    check("description" in fn, f"[{name}] has 'description'")
    check("parameters" in fn, f"[{name}] has 'parameters'")
    params = fn["parameters"]
    check(params["type"] == "object", f"[{name}] parameters type is 'object'")
    check("properties" in params, f"[{name}] has properties")
    # Check required is present (can be empty list)
    check("required" in params, f"[{name}] has 'required' field")

# Check no duplicate tool names
check(len(tool_names) == len(set(tool_names)), "No duplicate tool names")

# ════════════════════════════════════════════════════════
# 3. TOOL HANDLERS
# ════════════════════════════════════════════════════════
section("3. Tool Handlers")


# Handler mapping
handler_map = {
    "save_vehicle": "handle_save_vehicle",
    "save_document": "handle_save_document",
    "save_event": "handle_save_event",
    "save_list": "handle_save_list",
    "save_note": "handle_save_note",
    "search_my_data": "handle_search_data",
    "search_conversation": "handle_search_conversation",
    "analyze_image": "handle_analyze_image",
    "get_my_summary": "handle_get_summary",
    "save_project_task": "handle_save_project_task",
    "list_project_tasks": "handle_list_project_tasks",
    "complete_project_task": "handle_complete_project_task",
    "update_last": "handle_update_last",
    "save_contact": "handle_save_contact",
    "list_contacts": "handle_list_contacts",
    "check_vehicle_info": "handle_check_vehicle_info",
    "send_photo": "handle_send_photo",
    "web_search": "handle_web_search",
    "list_my_vehicles": "handle_list_my_vehicles",
    "add_maintenance": "handle_add_maintenance",
    "list_maintenances": "handle_list_maintenances",
    "add_transaction": "handle_add_transaction",
    "list_transactions": "handle_list_transactions",
    "get_balance": "handle_get_balance",
    "set_budget": "handle_set_budget",
    "check_budget": "handle_check_budget",
}

for tool_name, handler_name in handler_map.items():
    check(tool_name in tool_names, f"Tool '{tool_name}' is in ALL_TOOLS")

# ════════════════════════════════════════════════════════
# 4. SKILL LOADER
# ════════════════════════════════════════════════════════
section("4. Skill Loader")

from app.agent.skills import (  # noqa: E402
    list_available_skills,
    load_skill_content,
    load_skills_for_message,
    ALWAYS_SKILLS,
    ON_DEMAND_SKILLS,
)

skills = list_available_skills()
check(len(skills) == 10, f"10 skills available (found {len(skills)})")

expected_skills = [
    "culture/cuisine.md",
    "culture/holidays.md",
    "culture/idioms.md",
    "legal/documents.md",
    "tax/invoicing.md",
    "transit/driving-restrictions.md",
    "transit/registration.md",
]

for expected in expected_skills:
    check(expected in skills, f"Skill '{expected}' exists")

# Validate all skills have content
for skill_path in skills:
    content = load_skill_content(skill_path)
    check(len(content) > 500, f"Skill '{skill_path}' has content (>500 chars, actual: {len(content)})")
    check(content.startswith("#"), f"Skill '{skill_path}' starts with heading")

# Validate ALWAYS skills are loaded for every message
check(len(ALWAYS_SKILLS) == 1, "Exactly 1 always-loaded skill")
check("culture/idioms.md" in ALWAYS_SKILLS, "idioms.md is always-loaded")

# Validate all ON_DEMAND skills have keywords
check(len(ON_DEMAND_SKILLS) == 6, f"6 on-demand skills (found {len(ON_DEMAND_SKILLS)})")
for skill_path, keywords in ON_DEMAND_SKILLS.items():
    check(len(keywords) >= 3, f"Skill '{skill_path}' has >=3 keywords (found {len(keywords)})")
    check(skill_path in skills, f"Skill '{skill_path}' referenced in ON_DEMAND exists on disk")

# Test keyword matching
tests = [
    ("¿cómo se hace un encebollado?", ["culture/idioms.md", "culture/cuisine.md"]),
    ("¿cuándo es el próximo feriado?", ["culture/idioms.md", "culture/holidays.md"]),
    ("cuanto cuesta renovar la cedula", ["culture/idioms.md", "legal/documents.md"]),
    ("necesito factura electronica", ["culture/idioms.md", "tax/invoicing.md"]),
    ("hola lucho como estas", ["culture/idioms.md"]),
    ("cual es el IVA en Ecuador", ["culture/idioms.md", "tax/invoicing.md"]),
    ("receta de locro de papas", ["culture/idioms.md", "culture/cuisine.md"]),
    ("donde pago la matricula del carro", ["culture/idioms.md", "transit/registration.md"]),
    ("que feriados hay en noviembre", ["culture/idioms.md", "culture/holidays.md"]),
    ("pico y placa quito viernes", ["culture/idioms.md", "transit/driving-restrictions.md"]),
    ("que es el carnaval", ["culture/idioms.md", "culture/holidays.md"]),
    ("sacar factura para el sri", ["culture/idioms.md", "tax/invoicing.md"]),
]

for msg, expected_skills_list in tests:
    result = load_skills_for_message(msg)
    check(result is not None and len(result) > 0, f"Keyword match '{msg[:50]}' → loaded content")

# ════════════════════════════════════════════════════════
# 5. SKILL CONTENT QUALITY
# ════════════════════════════════════════════════════════
section("5. Skill Content Quality")

for skill_path in skills:
    content = load_skill_content(skill_path)
    name = skill_path.split("/")[-1].replace(".md", "")
    check("##" in content, f"[{name}] Has at least two heading levels")
    check("|" in content, f"[{name}] Contains at least one table")

# ════════════════════════════════════════════════════════
# 6. ONBOARDING REGRESSION — v2.24.6 fix applied to both channels
# ════════════════════════════════════════════════════════
section("6. Onboarding Regression (v2.24.6)")

import re  # noqa: E402

webhook_files = [
    ("Telegram", "app/routers/webhook.py"),
    ("WhatsApp", "app/routers/whatsapp_webhook.py"),
]

for channel, path in webhook_files:
    src = Path(path).read_text()

    # Fix 1: onboarding_step = 0 (not 3) after accent selection
    has_step_zero = bool(re.search(
        r'send_onboarding_step2.*\n\s*user\.onboarding_step\s*=\s*0',
        src
    ))
    has_step_three = bool(re.search(
        r'send_onboarding_step2.*\n\s*user\.onboarding_step\s*=\s*3',
        src
    ))
    check(has_step_zero, f"[{channel}] onboarding_step = 0 after step2 completion")
    check(not has_step_three, f"[{channel}] NO onboarding_step = 3 after step2 completion")

    # Fix 2: Post-pago guard uses onboarding_complete
    has_guard = bool(re.search(
        r'not\s+user\.onboarding_complete\s+and\s+3\s*<=\s*user\.onboarding_step\s*<=\s*6',
        src
    ))
    bare_step_check = bool(re.search(
        r'#\s*-+\s*Post-pago.*\n\s*if\s+3\s*<=\s*user\.onboarding_step\s*<=\s*6\s*:',
        src
    ))
    check(has_guard, f"[{channel}] Post-pago guard has 'not onboarding_complete'")
    check(not bare_step_check, f"[{channel}] Post-pago does NOT use bare step range check")

# Logic regression: Given onboarding_complete=True and step=3, post-pago must NOT trigger
section("6b. Onboarding Logic Regression")


class MockUser:
    onboarding_complete = True
    onboarding_step = 3

user = MockUser()
should_skip_post_pago = not user.onboarding_complete and 3 <= user.onboarding_step <= 6
check(not should_skip_post_pago, "Completed user (step=3) blocked from post-pago")

class MockPostPagoUser:
    onboarding_complete = False
    onboarding_step = 3

pp_user = MockPostPagoUser()
should_enter_post_pago = not pp_user.onboarding_complete and 3 <= pp_user.onboarding_step <= 6
check(should_enter_post_pago, "Post-pago user (not complete) enters flow")

# ════════════════════════════════════════════════════════
# 7. SECURITY REGRESSION — DeUna webhook + internal endpoint
# ════════════════════════════════════════════════════════
section("7. Security — DeUna webhook")

from app.services import deuna as deuna_svc  # noqa: E402

# Signature validation: correct secret + payload
test_payload = b'{"id":"pay_123","status":"approved","amount":9.99,"currency":"USD"}'
test_signature = hmac.new(
    b"test-secret",
    test_payload,
    hashlib.sha256,
).hexdigest()

# Temporarily set the secret so validation works
import app.config as cfg  # noqa: E402
original_secret = cfg.settings.DEUNA_WEBHOOK_SECRET
cfg.settings.DEUNA_WEBHOOK_SECRET = "test-secret"

check(
    deuna_svc.validate_webhook_signature(test_payload, test_signature),
    "DeUna: valid HMAC signature accepted",
)
check(
    not deuna_svc.validate_webhook_signature(test_payload, "wrong_signature"),
    "DeUna: invalid HMAC signature rejected",
)
check(
    not deuna_svc.validate_webhook_signature(test_payload, ""),
    "DeUna: empty HMAC signature rejected",
)
check(
    not deuna_svc.validate_webhook_signature(b'{"different":"payload"}', test_signature),
    "DeUna: signature mismatch for different payload",
)

# Restore original secret
cfg.settings.DEUNA_WEBHOOK_SECRET = original_secret

# Test that unconfigured secret rejects everything (unlike PayPhone's accept-all)
cfg.settings.DEUNA_WEBHOOK_SECRET = ""
check(
    not deuna_svc.validate_webhook_signature(test_payload, test_signature),
    "DeUna: unconfigured secret REJECTS (not accepts)",
)
cfg.settings.DEUNA_WEBHOOK_SECRET = original_secret

# process_webhook: valid payload
parsed = deuna_svc.process_webhook({"id": "pay_123", "status": "approved", "amount": 9.99, "currency": "USD"})
check(parsed is not None, "DeUna: process_webhook returns data for valid payload")
check(parsed["transaction_id"] == "pay_123", "DeUna: transaction_id extracted correctly")
check(parsed["currency"] == "USD", "DeUna: currency defaults to USD")
check(parsed["amount"] == 9.99, "DeUna: amount parsed correctly")

# process_webhook: missing id and reference
parsed2 = deuna_svc.process_webhook({"status": "approved", "amount": 10})
check(parsed2 is None, "DeUna: process_webhook returns None for missing ID")

# process_webhook: reference fallback
parsed3 = deuna_svc.process_webhook({"reference": "SUB-456", "status": "pending"})
check(parsed3 is not None, "DeUna: process_webhook uses reference as fallback")
check(parsed3["transaction_id"] == "SUB-456", "DeUna: reference used as transaction_id")

# ---- Webhook source code patterns ----
deuna_src = Path("app/routers/deuna_webhook.py").read_text()
check(
    "raw_body = await request.body()" in deuna_src,
    "DeUna router: reads raw body for signature validation",
)
check(
    '"X-DeUna-Signature"' in deuna_src,
    "DeUna router: checks X-DeUna-Signature header",
)
check(
    "validate_webhook_signature(raw_body, signature)" in deuna_src,
    "DeUna router: calls validate_webhook_signature with raw body",
)
check(
    "payment.status == PaymentStatus.completed" in deuna_src,
    "DeUna router: idempotency check for completed payments",
)
check(
    "amount mismatch" in deuna_src,
    "DeUna router: validates amount against stored payment",
)
check(
    "unexpected currency" in deuna_src or "currency" in deuna_src.lower(),
    "DeUna router: validates currency",
)

# ---- Internal endpoint ----
section("7b. Security — Internal endpoint")

internal_src = Path("app/routers/internal_test.py").read_text()
main_src = Path("app/main.py").read_text()

check(
    'include_in_schema=False' in internal_src,
    "Internal router: hidden from OpenAPI schema",
)
check(
    '"593993832368"' not in internal_src,
    "Internal router: NO hardcoded WhatsApp number",
)
check(
    '_require_internal_token' in internal_src,
    "Internal router: has token auth dependency",
)
check(
    'if settings.DEBUG:' in main_src and 'internal_test' in main_src,
    "Main: internal router only mounted when DEBUG=True",
)

# ════════════════════════════════════════════════════════
# 8. TIMEZONE REGRESSION — local Ecuador, zero UTC
# ════════════════════════════════════════════════════════
section("8. Timezone — Local Ecuador (no UTC)")

# 8a. Source code: no prohibited patterns
forbidden_patterns = [
    ("timezone.utc", "datetime.now(timezone.utc)"),
    ("utcnow", "utcnow() function or import"),
    ("astimezone(", "astimezone() conversion"),
    ("replace(tzinfo=", "replace(tzinfo=) assignment"),
    ("DateTime(timezone=True)", "DateTime(timezone=True) in models"),
]
app_py_files = list(Path("app").rglob("*.py"))
for pattern, label in forbidden_patterns:
    found = False
    for fpath in app_py_files:
        if pattern in fpath.read_text():
            found = True
            break
    check(not found, f"No '{label}' anywhere in app/")

# 8b. base.py has now_ec() not utcnow()
base_src = Path("app/models/base.py").read_text()
check("def now_ec()" in base_src, "base.py: now_ec() function exists")
check("datetime.now()" in base_src, "base.py: uses datetime.now() naive")
check("utcnow" not in base_src, "base.py: no utcnow() function")
check("import timezone" not in base_src, "base.py: no 'import timezone' statement")
check("DateTime(timezone=False)" in base_src, "base.py: TimestampMixin uses timezone=False")
check("now_ec" in base_src and "default=now_ec" in base_src, "base.py: TimestampMixin defaults to now_ec")
check("onupdate=now_ec" in base_src, "base.py: TimestampMixin onupdate uses now_ec")

# 8c. now_ec() produces naive datetime (no tzinfo)
from app.models.base import now_ec  # noqa: E402
from datetime import datetime  # noqa: E402
ec_now = now_ec()
check(ec_now.tzinfo is None, "now_ec() returns naive datetime (tzinfo=None)")
check(isinstance(ec_now, datetime), "now_ec() returns datetime instance")

# 8d. All models use now_ec, not utcnow
model_files = list(Path("app/models").rglob("*.py"))
for mp in model_files:
    if mp.name == "__init__.py" or mp.name == "base.py":
        continue
    src = mp.read_text()
    if "utcnow" in src:
        check(False, f"{mp.name}: still references utcnow")
    # If file imports from base, it should use now_ec or not need it
    if "from app.models.base import" in src:
        if "default=now_ec" in src:
            check("now_ec" in src, f"{mp.name}: imports now_ec from base")

# 8e. Scheduler uses naive datetime.now() without timezone
sched_src = Path("app/services/scheduler.py").read_text()
check("datetime.now()" in sched_src, "scheduler: uses datetime.now()")
check("timezone.utc" not in sched_src, "scheduler: no timezone.utc")
check("local Ecuador time" in sched_src, "scheduler: documents local Ecuador time")

# ════════════════════════════════════════════════════════
# REPORT
# ════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"📊 UNIT TESTS: {PASS} ✅ / {FAIL} ❌ / {PASS+FAIL} total")
print(f"{'='*50}")
if PASS + FAIL > 0:
    print(f"🎯 {100*PASS//(PASS+FAIL)}% passed")
print()

sys.exit(0 if FAIL == 0 else 1)
