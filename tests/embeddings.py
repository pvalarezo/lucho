#!/usr/bin/env python3
"""Test suite for local embeddings — semantic search by meaning, not words."""

import json
import subprocess
import sys
import time

API = "http://localhost:8000"
CID = 999888

def send(text):
    payload = json.dumps({"message":{"chat":{"id":CID,"first_name":"Tester"},"text":text}})
    r = subprocess.run(["curl","-s","-X","POST",f"{API}/telegram/webhook",
        "-H","Content-Type: application/json","-d",payload],
        capture_output=True,text=True,timeout=30)
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except Exception:
        return {}

def search(q, uid):
    r = subprocess.run(["curl","-s",f"{API}/search/semantic?q={q}&user_id={uid}"],
        capture_output=True,text=True,timeout=30)
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except Exception:
        return {}

# ═══════════════════════════════════════════
# 1. Sembrar datos variados
# ═══════════════════════════════════════════
print("🌱 Sembrando datos...")
data = [
    "Mi carro es un Kia Sportage placa ABC-1234 color azul",
    "Compré un refrigerador Samsung de 2 puertas en La Ganga",
    "Mi perro se llama Max, es un golden retriever de 3 años",
    "Receta de ceviche de camarón: camarón, limón, cebolla, tomate, cilantro",
    "El SOAT de mi carro vence en diciembre, tengo que renovarlo",
    "Cita con el veterinario para las vacunas de Max el próximo viernes",
    "Pagué el arriendo de julio $350, somos 3 roommates",
    "Idea de negocio: importar repuestos de motos desde Colombia",
    "Mi papá toma medicamento para la presión, recordarle cada 8 horas",
    "Ahorros: meta de $5000 para el enganche de la casa",
]
for d in data:
    r = send(d)
    print(f"  {r.get('target_table','?'):12s} ← {d[:60]}...")
    time.sleep(2.5)

# Obtener user_id
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
import asyncio  # noqa: E402
async def get_uid():
    e = create_async_engine('postgresql+asyncpg://lucho:lucho@localhost:5434/lucho')
    async with e.connect() as c:
        r = await c.execute(text("SELECT id FROM users WHERE telegram_id='999888'"))
        return str(r.fetchone()[0])
uid = asyncio.run(get_uid())
print(f"\n👤 User: {uid[:8]}...")

# ═══════════════════════════════════════════
# 2. Pruebas semánticas
# ═══════════════════════════════════════════
tests = [
    # (query, expected_word, description)
    ("nevera", "refrigerador", "sinónimo español"),
    ("auto", "Kia/Sportage/carro", "sinónimo auto→carro"),
    ("mascota", "perro/Max", "contexto mascota→perro"),
    ("comida", "ceviche/receta", "contexto comida→receta"),
    ("salud", "medicamento/presión/veterinario", "contexto salud→medico"),
    ("finanzas", "ahorros/enganche/arriendo", "contexto finanzas→dinero"),
    ("vehicle", "carro/SOAT/Kia", "inglés→español"),
    ("recipe", "receta/ceviche", "inglés→español receta"),
    ("dog", "perro/Max/golden", "inglés→español mascota"),
    ("casa", "arriendo/enganche", "contexto vivienda"),
    ("renovar", "SOAT/diciembre/vencimiento", "contexto trámite"),
    ("transporte", "carro/placas/motos", "contexto general"),
]

print(f"\n{'='*60}")
print("🔍 PRUEBAS DE BÚSQUEDA SEMÁNTICA")
print(f"{'='*60}")

passed = 0
failed = 0

for query, expected, desc in tests:
    r = search(query, uid)
    results = r.get("results", [])
    method = r.get("method", "?")
    
    # Check if any result contains expected words
    found = False
    top_matches = []
    for res in results[:3]:
        ttext = res.get("text", "")
        sim = res.get("similarity", 0)
        src = res.get("source", "?")
        top_matches.append(f"{src}:{sim:.2f}")
        if any(w.lower() in text.lower() for w in expected.split("/")):
            found = True
    
    status = "✅" if found else "❌"
    if found:
        passed += 1
    else:
        failed += 1
    
    print(f"{status} \"{query}\" → busca '{expected}' | top: {', '.join(top_matches)} | {desc}")

print(f"\n{'='*60}")
print(f"📊 Semántica: {passed}✅ / {failed}❌ / {passed+failed} total")
print(f"🎯 {100*passed//(passed+failed)}% | método: {method}")
print(f"{'='*60}")

# ═══════════════════════════════════════════
# 3. Mostrar resultados detallados de un par
# ═══════════════════════════════════════════
print("\n📋 DETALLE: 'salud' (debería encontrar medicamento y veterinario):")
r = search("salud", uid)
for res in r.get("results", [])[:5]:
    print(f"  {res['similarity']:.4f} [{res['source']}] {res['text'][:80]}")

print("\n📋 DETALLE: 'vehicle' (inglés, debería encontrar carro/SOAT):")
r = search("vehicle", uid)
for res in r.get("results", [])[:3]:
    print(f"  {res['similarity']:.4f} [{res['source']}] {res['text'][:80]}")

sys.exit(0 if failed == 0 else 1)
