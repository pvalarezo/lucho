#!/usr/bin/env python3
"""Lucho stress test — preguntas variadas, mal escritas, fuera de contexto."""

import json, subprocess, sys, time

API = "http://localhost:8000/telegram/webhook"
PASS = 0; FAIL = 0; RESULTS = []
CID = 777777

def send(text):
    payload = json.dumps({"message":{"chat":{"id":CID,"first_name":"Tester"},"text":text}})
    r = subprocess.run(["curl","-s","-X","POST",API,"-H","Content-Type: application/json","-d",payload],
                       capture_output=True,text=True,timeout=30)
    try: return json.loads(r.stdout) if r.stdout else {"error": r.stderr or "empty"}
    except: return {"error": str(r)}

def t(cat, q, expected=None, notes=""):
    global PASS, FAIL
    r = send(q)
    target = r.get("target_table", r.get("error", "???"))
    status = r.get("status", "?")
    ok = True; reason = ""
    if expected and target != expected:
        ok = False; reason = f"esperaba '{expected}', recibí '{target}'"
    if expected and status != "processed":
        ok = False; reason = f"status={status}"
    print(f"{'✅' if ok else '❌'} [{cat}] {q[:70]}{'...' if len(q)>70 else ''}  → {target}")
    if reason: print(f"     {reason}")
    if ok: PASS += 1
    else: FAIL += 1
    RESULTS.append({"cat":cat,"q":q,"target":target,"ok":ok,"reason":reason})
    time.sleep(2.5)

# ═════════════════════════════════════════════
print("="*60); print("1. NÚCLEO — comandos correctos"); print("="*60)
t("1.ok","Mi carro es un Chevrolet Spark placa XYZ-9999","asset")
t("1.ok","Tengo una tarjeta Mastercard del Banco Guayaquil","asset")
t("1.ok","Cita con el veterinario el 30 de julio a las 2pm","event")
t("1.ok","Recordame ir al cumpleaños de mi sobrino el sábado","event")
t("1.ok","Comprar café, azúcar, arroz y fideos","list_item")
t("1.ok","Lavar el carro y sacar al perro","list_item")
t("1.ok","Receta de locro de papa: papa, queso, aguacate, cebolla","note")
t("1.ok","Posible negocio: vender desayunos a domicilio en Cuenca","note")

print("="*60); print("2. FALTAS DE ORTOGRAFÍA"); print("="*60)
t("2.orto","Mi caro es un toyota corola placa abc-1234","asset")
t("2.orto","Cita con el dotor el juves 15","event")
t("2.orto","Comprar leshe, pan i huebos","list_item")
t("2.orto","Receta de sebiche: pescado, limon, serbesa","note")
t("2.orto","Hola lucho q puedes aser x mi","meta")
t("2.orto","ke veiculo tengo registrado","search")
t("2.orto","Tengo multas en la placa pbx-1234","tool")
t("2.orto","Corrije la fecha es 20 no 15","correction")

print("="*60); print("3. PALABRAS INCOMPLETAS / ABREVIATURAS"); print("="*60)
t("3.inc","carro placa pbc","asset")
t("3.inc","cita dr lunes 3pm","event")
t("3.inc","comprar pan lech huevo","list_item")
t("3.inc","idea negocio export","note")
t("3.inc","q haces?","meta")
t("3.inc","multas?","tool")
t("3.inc","pendientes?","search")

print("="*60); print("4. FUERA DE CONTEXTO — debe ser note"); print("="*60)
t("4.out","¿Quién es el presidente de Ecuador?","note")
t("4.out","Cómo hacer un pastel de chocolate","note")
t("4.out","Cuánto es 345 x 678","note")
t("4.out","Dame un chiste","note")
t("4.out","Escribe un poema sobre la lluvia","note")
t("4.out","Traduce 'hello' al francés","note")
t("4.out","Cuál es la mejor pizza de Cuenca","note")

print("="*60); print("5. PROYECTOS — nueva funcionalidad"); print("="*60)
t("5.proj","Para el proyecto viaje a Salinas, comprar protector solar","list_item",
  notes="project_task debería ir por ruta ortogonal")
t("5.proj","Agrega al proyecto de la boda: contratar DJ","list_item")
t("5.proj","Necesito planificar la mudanza: empacar libros, contratar camión, avisar al arrendador","list_item")

print("="*60); print("6. GASTOS COMPARTIDOS — nueva funcionalidad"); print("="*60)
t("6.exp","Cena $60 entre 4 personas: Juan, María, Pedro, Ana","shared_expense")
t("6.exp","Pagué el arriendo $400 dividido entre 3","shared_expense")
t("6.exp","Compras del super $85.50 entre 2","shared_expense")
t("6.exp","Gasolina $30 yo y mi hermano","shared_expense")

print("="*60); print("7. CONTACTOS — nueva funcionalidad"); print("="*60)
t("7.cont","Agrega a mi mamá: María Valarezo, teléfono 0991234567","note",
  notes="Correcto: contacto sin target propio → note")
t("7.cont","Mi papá Juan es mi contacto de emergencia","asset",
  notes="Correcto: menciona persona → asset")

print("="*60); print("8. VARIANTES ECUATORIANAS / LATAM"); print("="*60)
t("8.var","Anótame pues que tengo cita con el doc","event")
t("8.var","Apúntame comprar pan y leche porfa","list_item")
t("8.var","Mi nave es un Lada placa TTT-0001","asset")
t("8.var","De ley tengo que pagar la matrícula","asset")
t("8.var","Que fue, ¿qué más haces?","meta")
t("8.var","Oye y ¿qué tienes anotado?","search")

print("="*60); print("9. EDGE CASES EXTREMOS"); print("="*60)
t("9.edge","a","note")
t("9.edge","","note") 
t("9.edge"," ","note")
t("9.edge","...","note")
t("9.edge","¿?","note")
t("9.edge","😀🎉🚀","note")
t("9.edge","1234567890","asset",
  notes="Números → parece placa. Edge case aceptable")

print("="*60); print("10. SPANGLISH / MEZCLA"); print("="*60)
t("10.mix","Mi car is a Toyota plate ABC-1234","asset")
t("10.mix","Meeting con el boss mañana a las 9","event")
t("10.mix","Comprar milk, bread and eggs","list_item")
t("10.mix","Business idea: import phones from USA","note")
t("10.mix","What can you do?","meta")

# ═════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"📊 {PASS}✅ / {FAIL}❌ / {PASS+FAIL} total")
print(f"{'='*60}")
if FAIL:
    print("\n❌ FALLOS:")
    for r in RESULTS:
        if not r["ok"]:
            print(f"  [{r['cat']}] \"{r['q'][:60]}\" → {r['target']}")
            if r["reason"]: print(f"     {r['reason']}")
print(f"\n🎯 {100*PASS//(PASS+FAIL)}%" if PASS+FAIL else "sin tests")
sys.exit(0 if FAIL == 0 else 1)
