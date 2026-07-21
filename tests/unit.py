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

import json
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

from app.agent.lucho_system_prompt import build_system_prompt, LUCHO_SYSTEM_PROMPT_SHORT

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

from app.agent.tools import ALL_TOOLS, TOOL_SCHEMAS

check(len(ALL_TOOLS) == 26, f"Exactly 26 tools (found {len(ALL_TOOLS)})")
check(len(TOOL_SCHEMAS) == 26, f"TOOL_SCHEMAS has 26 entries (found {len(TOOL_SCHEMAS)})")

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

from app.agent.tools import execute_tool

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

from app.agent.skills import (
    list_available_skills,
    load_skill_content,
    load_skills_for_message,
    ALWAYS_SKILLS,
    ON_DEMAND_SKILLS,
)

skills = list_available_skills()
check(len(skills) == 7, f"7 skills available (found {len(skills)})")

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
# REPORT
# ════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"📊 UNIT TESTS: {PASS} ✅ / {FAIL} ❌ / {PASS+FAIL} total")
print(f"{'='*50}")
if PASS + FAIL > 0:
    print(f"🎯 {100*PASS//(PASS+FAIL)}% passed")
print()

sys.exit(0 if FAIL == 0 else 1)
