#!/usr/bin/env python3
"""Comprehensive test suite for Lucho - validates all response types.

Tests valid commands, edge cases, guardrail violations, Spanish variants,
and multiple instructions. Runs via webhook API.
"""

import json
import subprocess
import sys
import time

API = "http://localhost:8000/telegram/webhook"
CHAT_ID = 999999

HEADERS = ["-H", "Content-Type: application/json"]
PASS = 0
FAIL = 0
RESULTS = []


def send(text: str, chat_id: int = CHAT_ID) -> dict:
    """Send a message to the webhook and return parsed response."""
    payload = json.dumps({
        "message": {
            "chat": {"id": chat_id, "first_name": "Tester"},
            "text": text,
        }
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", API] + HEADERS + ["-d", payload],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(result.stdout) if result.stdout else {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def test(category: str, question: str, expected_target: str | None = None,
         should_respond: bool = True, notes: str = ""):
    """Run one test and record result."""
    global PASS, FAIL
    print(f"\n{'='*60}")
    print(f"[{category}] {question[:80]}")
    
    resp = send(question)
    target = resp.get("target_table", resp.get("error", "unknown"))
    status = resp.get("status", "?")
    
    ok = True
    reason = ""
    
    if expected_target and target != expected_target:
        ok = False
        reason = f"Expected target='{expected_target}', got '{target}'"
    
    if should_respond and status != "processed":
        ok = False
        reason = f"Expected status='processed', got '{status}'"
    
    if ok:
        PASS += 1
        print(f"  ✅ {target}")
    else:
        FAIL += 1
        print(f"  ❌ {target} — {reason}")
    
    RESULTS.append({
        "category": category,
        "question": question,
        "target": target,
        "expected": expected_target,
        "ok": ok,
        "reason": reason,
        "notes": notes,
    })
    time.sleep(2)  # avoid rate limiting


# ═════════════════════════════════════════════════════
# 1. NÚCLEO: Comandos válidos
# ═════════════════════════════════════════════════════
test("1.asset", "Mi carro es un Kia Sportage placa GHI-7890", "asset")
test("1.asset", "Tengo una tarjeta de crédito Visa del Banco Pichincha", "asset")
test("1.event", "Cita con el abogado el 25 de julio a las 4pm", "event")
test("1.event", "Recordame llamar a mamá mañana", "event")
test("1.list", "Comprar arroz, atún, cebolla y tomate en el mercado", "list_item")
test("1.list", "Tengo que lavar el carro, sacar la basura y planchar", "list_item")
test("1.note", "Receta de encebollado: pescado, yuca, cebolla, tomate, cilantro", "note")
test("1.note", "Idea: poner un food truck de sanduches en la U", "note")

# ═════════════════════════════════════════════════════
# 2. META: Preguntas sobre Lucho mismo
# ═════════════════════════════════════════════════════
test("2.meta", "¿Qué puedes hacer por mí?", "meta")
test("2.meta", "Hola Lucho, ¿cómo funcionas?", "meta")
test("2.meta", "¿Para qué servís?", "meta")
test("2.meta", "Ayuda por favor", "meta")
test("2.meta", "¿Qué eres exactamente?", "meta")
test("2.meta", "Explícame qué servicios tienes", "meta")
test("2.meta", "¿Cuáles son tus capacidades?", "meta")
test("2.meta", "¿Qué podés hacer vos?", "meta")  # voseo

# ═════════════════════════════════════════════════════
# 3. SEARCH: Búsquedas de datos del usuario
# ═════════════════════════════════════════════════════
test("3.search", "¿Qué vehículo tengo registrado?", "search")
test("3.search", "¿Cuál es la placa de mi carro?", "search")
test("3.search", "¿Qué tengo pendiente?", "search")
test("3.search", "Muéstrame la lista de compras", "search")
test("3.search", "¿Cuándo vence la matriculación?", "asset",
     notes="Correcto: matriculación está ligada al vehículo (asset)")

# ═════════════════════════════════════════════════════
# 4. CORRECCIÓN
# ═════════════════════════════════════════════════════
test("4.correction", "No, la cita es el 20 de julio, no el 25", "correction")
test("4.correction", "Corrige, la placa es ABC-1234 no ABC-1235", "correction")

# ═════════════════════════════════════════════════════
# 5. TOOLS: Consultas externas
# ═════════════════════════════════════════════════════
test("5.tool", "¿Tengo multas en la placa ABC-1234?", "tool")
test("5.tool", "Consultame si debo algo de tránsito de mi carro", "tool")

# ═════════════════════════════════════════════════════
# 6. GUARDRAILS: Lo que NO debe responder
# ═════════════════════════════════════════════════════
# These should be classified as 'note' (the default fallback),
# which is acceptable — Lucho shouldn't answer as a general assistant
test("6.guardrail", "¿Cuál es la capital de Francia?", "note", 
     notes="Guardrail: cultura general → debe ser note, no responder como asistente")
test("6.guardrail", "¿Qué hora es?", "note",
     notes="Guardrail: información externa → note")
test("6.guardrail", "¿Cómo está el clima en Quito?", "note",
     notes="Guardrail: clima → note")
test("6.guardrail", "Hacé mi tarea de matemáticas: 2+2", "note",
     notes="Guardrail: tareas escolares → note")
test("6.guardrail", "¿Quién ganó el mundial de fútbol 2022?", "note",
     notes="Guardrail: cultura general → note")
test("6.guardrail", "Pagá la matrícula del carro por mí", "note",
     notes="Guardrail: acción autónoma → debe ser note, nunca ejecutar")

# ═════════════════════════════════════════════════════
# 7. VARIANTES DE ESPAÑOL
# ═════════════════════════════════════════════════════
test("7.variante", "Anótame que tengo cita con el doctor", "event",
     notes="Voseo: 'anótame' + evento implícito")
test("7.variante", "Apúntame comprar pan y leche", "list_item",
     notes="Tuteo/voseo")
test("7.variante", "Mi carro es placa AAA-0001, recuérdame la revisión", "asset",
     notes="Instrucción compuesta, debe priorizar asset")

# ═════════════════════════════════════════════════════
# 8. EDGE CASES
# ═════════════════════════════════════════════════════
test("8.edge", "ok", "note", notes="Mensaje muy corto")
test("8.edge", "sí", "note", notes="Afirmación simple")
test("8.edge", "no", "note", notes="Negación simple")
test("8.edge", "🚀", "note", notes="Solo emoji")
test("8.edge", "a" * 500, "note", notes="Mensaje muy largo")

# ═════════════════════════════════════════════════════
# 9. MÚLTIPLES INSTRUCCIONES
# ═════════════════════════════════════════════════════
test("9.multi", "Comprar leche y además recordame la cita del viernes", 
     None, notes="Dos instrucciones: lista + evento. La primera domina.")
test("9.multi", "Mi carro PBC-1234 necesita SOAT y también comprar pan", 
     None, notes="Asset + lista. Asset debe dominar.")

# ═════════════════════════════════════════════════════
# REPORTE
# ═════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"📊 RESULTADOS: {PASS} ✅ / {FAIL} ❌ / {PASS+FAIL} total")
print(f"{'='*60}")

if FAIL > 0:
    print("\n❌ FALLOS:")
    for r in RESULTS:
        if not r["ok"]:
            print(f"  [{r['category']}] \"{r['question'][:60]}...\"")
            print(f"       → {r['reason']}")

print(f"\n✅ ACIERTOS: {PASS}/{PASS+FAIL} ({100*PASS//(PASS+FAIL)}%)")

sys.exit(0 if FAIL == 0 else 1)
