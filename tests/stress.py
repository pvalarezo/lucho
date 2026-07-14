#!/usr/bin/env python3
"""
Lucho Stress Test — Agent Architecture (v2.4.0)

Tests: spelling errors, incomplete words, out-of-scope questions,
projects, expenses, contacts, Ecuadorian variants, edge cases, Spanglish.

REQUIRES: server running + LLM provider configured.
"""

import json
import subprocess
import sys
import time

API = "http://localhost:8000/telegram/webhook"
PASS = 0
FAIL = 0
RESULTS: list[dict] = []
CID = 777777


def send(text: str, chat_id: int = CID) -> dict:
    payload = json.dumps({
        "message": {
            "chat": {"id": chat_id, "first_name": "Tester"},
            "text": text,
        }
    })
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", API,
             "-H", "Content-Type: application/json", "-d", payload],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(r.stdout) if r.stdout else {"error": r.stderr or "empty"}
    except Exception as e:
        return {"error": str(e)}


def t(cat: str, q: str, must_process: bool = True, notes: str = ""):
    global PASS, FAIL
    r = send(q)
    status = r.get("status", "error")
    ok = True
    reason = ""

    if must_process and status != "processed":
        ok = False
        reason = f"status={status}"

    print(f"{'✅' if ok else '❌'} [{cat}] {q[:70]}{'...' if len(q)>70 else ''}  → {status}")
    if reason:
        print(f"     {reason}")

    PASS += 1 if ok else 0
    FAIL += 0 if ok else 1
    RESULTS.append({"cat": cat, "q": q, "status": status, "ok": ok, "reason": reason})
    time.sleep(2.5)


# ══════════════════════════════════════════
print("="*60)
print("1. NÚCLEO — entity saving")
print("="*60)
t("1.core", "Mi carro es un Chevrolet Spark placa XYZ-9999")
t("1.core", "Tengo una tarjeta Mastercard del Banco Guayaquil")
t("1.core", "Cita con el veterinario el 30 de julio a las 2pm")
t("1.core", "Recordame ir al cumpleaños de mi sobrino el sábado")
t("1.core", "Comprar café, azúcar, arroz y fideos")
t("1.core", "Lavar el carro y sacar al perro")
t("1.core", "Receta de locro de papa: papa, queso, aguacate, cebolla")
t("1.core", "Posible negocio: vender desayunos a domicilio en Cuenca")

print("="*60)
print("2. FALTAS DE ORTOGRAFÍA")
print("="*60)
t("2.spell", "Mi caro es un toyota corola placa abc-1234")
t("2.spell", "Cita con el dotor el juves 15")
t("2.spell", "Comprar leshe, pan i huebos")
t("2.spell", "Receta de sebiche: pescado, limon, serbesa")
t("2.spell", "Hola lucho q puedes aser x mi")
t("2.spell", "ke veiculo tengo registrado")
t("2.spell", "Corrije la fecha es 20 no 15")

print("="*60)
print("3. PALABRAS INCOMPLETAS / ABREVIATURAS")
print("="*60)
t("3.abbr", "carro placa pbc")
t("3.abbr", "cita dr lunes 3pm")
t("3.abbr", "comprar pan lech huevo")
t("3.abbr", "idea negocio export")
t("3.abbr", "q haces?")
t("3.abbr", "pendientes?")

print("="*60)
print("4. FUERA DE CONTEXTO — guardrails")
print("="*60)
t("4.out", "¿Quién es el presidente de Ecuador?")
t("4.out", "Cómo hacer un pastel de chocolate")
t("4.out", "Cuánto es 345 x 678")
t("4.out", "Dame un chiste")
t("4.out", "Escribe un poema sobre la lluvia")
t("4.out", "Traduce 'hello' al francés")
t("4.out", "Cuál es la mejor pizza de Cuenca")

print("="*60)
print("5. PROYECTOS Y TAREAS")
print("="*60)
t("5.proj", "Para el proyecto viaje a Salinas, comprar protector solar")
t("5.proj", "Agrega al proyecto de la boda: contratar DJ")
t("5.proj", "Necesito planificar la mudanza: empacar libros, contratar camión")

print("="*60)
print("6. GASTOS COMPARTIDOS")
print("="*60)
t("6.exp", "Cena $60 entre 4 personas: Juan, María, Pedro, Ana")
t("6.exp", "Pagué el arriendo $400 dividido entre 3")
t("6.exp", "Compras del super $85.50 entre 2")
t("6.exp", "Gasolina $30 yo y mi hermano")

print("="*60)
print("7. CONTACTOS")
print("="*60)
t("7.cont", "Agrega a mi mamá: María Valarezo, teléfono 0991234567")
t("7.cont", "Mi papá Juan es mi contacto de emergencia")
t("7.cont", "El teléfono de Carlos es 0987654321")

print("="*60)
print("8. VARIANTES ECUATORIANAS")
print("="*60)
t("8.var", "Anótame pues que tengo cita con el doc")
t("8.var", "Apúntame comprar pan y leche porfa")
t("8.var", "Mi nave es un Lada placa TTT-0001")
t("8.var", "De ley tengo que pagar la matrícula")
t("8.var", "Que fue, ¿qué más haces?")
t("8.var", "Oye y ¿qué tienes anotado?")

print("="*60)
print("9. EDGE CASES EXTREMOS")
print("="*60)
t("9.edge", "a")
t("9.edge", " ")
t("9.edge", "...")
t("9.edge", "😀🎉🚀")
t("9.edge", "1234567890")

print("="*60)
print("10. SPANGLISH / MEZCLA")
print("="*60)
t("10.mix", "Mi car is a Toyota plate ABC-1234")
t("10.mix", "Meeting con el boss mañana a las 9")
t("10.mix", "Comprar milk, bread and eggs")
t("10.mix", "Business idea: import phones from USA")
t("10.mix", "What can you do?")

# ══════════════════════════════════════════
print(f"\n{'='*60}")
print(f"📊 {PASS}✅ / {FAIL}❌ / {PASS+FAIL} total")
print(f"{'='*60}")
if FAIL:
    print("\n❌ FALLOS:")
    for r in RESULTS:
        if not r["ok"]:
            print(f"  [{r['cat']}] \"{r['q'][:60]}\" → {r['status']}")
            if r["reason"]:
                print(f"     {r['reason']}")
if PASS + FAIL > 0:
    print(f"\n🎯 {100*PASS//(PASS+FAIL)}%")
sys.exit(0 if FAIL == 0 else 1)
