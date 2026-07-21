#!/usr/bin/env python3
"""
Test WhatsApp templates — send all 5 approved templates to a test phone number.

Usage:
    python3 scripts/test_whatsapp_templates.py 593993832368
    python3 scripts/test_whatsapp_templates.py 593993832368 --template document_reminder
    python3 scripts/test_whatsapp_templates.py 593993832368 --template pico_y_placa
    python3 scripts/test_whatsapp_templates.py 593993832368 --template project_reminder
    python3 scripts/test_whatsapp_templates.py 593993832368 --template daily_digest
    python3 scripts/test_whatsapp_templates.py 593993832368 --template event_reminder
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import whatsapp as whatsapp_svc


async def test_document_reminder(phone: str):
    """Test the document_reminder template (6 body params)."""
    print("\n📄 Testing: document_reminder")
    result = await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="document_reminder",
        language_code="es",
        body_params=[
            "🔴",                       # {{1}} emoji
            "SOAT PBC1234",            # {{2}} doc_name
            "soat",                    # {{3}} doc_type
            "en 7 días",               # {{4}} days_text
            "2026-07-28",              # {{5}} expiry_date
            "SOAT PBC1234",            # {{6}} doc_name (repeat, Meta requirement)
        ],
    )
    status = "✅ SENT" if result else "❌ FAILED"
    print(f"  Result: {status}")
    if result:
        print(f"  Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
    return result


async def test_project_reminder(phone: str):
    """Test the project_reminder template (6 body params)."""
    print("\n📋 Testing: project_reminder")
    result = await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="project_reminder",
        language_code="es",
        body_params=[
            "🟡",                                  # {{1}} emoji
            "Tienda Online",                       # {{2}} project_name
            "Configurar pasarela de pago",         # {{3}} task_content
            "en 3 días",                           # {{4}} days_text
            "2026-07-24",                          # {{5}} due_date
            "Configurar pasarela de pago",         # {{6}} task_content (repeat)
        ],
    )
    status = "✅ SENT" if result else "❌ FAILED"
    print(f"  Result: {status}")
    if result:
        print(f"  Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
    return result


async def test_pico_y_placa(phone: str):
    """Test the pico_y_placa template (2 body params)."""
    print("\n🚗 Testing: pico_y_placa")
    result = await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="pico_y_placa",
        language_code="es",
        body_params=[
            "PBC1234",              # {{1}} plate
            "hoy lunes",            # {{2}} restriction day
        ],
    )
    status = "✅ SENT" if result else "❌ FAILED"
    print(f"  Result: {status}")
    if result:
        print(f"  Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
    return result


async def test_event_reminder(phone: str):
    """Test the event_reminder template (5 body params)."""
    print("\n📌 Testing: event_reminder")
    result = await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="event_reminder",
        language_code="es",
        body_params=[
            "🔴",                       # {{1}} emoji
            "Cita con el dentista",     # {{2}} event_title
            "HOY",                      # {{3}} days_text
            "2026-07-22",               # {{4}} target_date
            "Cita con el dentista",     # {{5}} event_title (repeat, Meta requirement)
        ],
    )
    status = "✅ SENT" if result else "❌ FAILED"
    print(f"  Result: {status}")
    if result:
        print(f"  Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
    return result


async def test_daily_digest(phone: str):
    """Test the daily_digest template (1 body param)."""
    print("\n☀️ Testing: daily_digest")
    digest_text = (
        "Buenos días Patricio. ☀️\n\n"
        "Hoy es lunes 21 de julio. Tenés:\n"
        "📅 1 cita hoy: Reunión equipo AURACORE a las 10am\n"
        "📝 3 tareas pendientes del proyecto Tienda Online\n"
        "📄 SOAT del carro vence en 7 días\n\n"
        "¡Que tengas un excelente día!"
    )
    result = await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="daily_digest",
        language_code="es",
        body_params=[digest_text],  # {{1}} full digest
    )
    status = "✅ SENT" if result else "❌ FAILED"
    print(f"  Result: {status}")
    if result:
        print(f"  Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
    return result


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_whatsapp_templates.py <phone_number> [--template <name>]")
        print("  Templates: document_reminder, project_reminder, pico_y_placa, daily_digest, event_reminder")
        print("  Without --template, sends ALL 5 templates.")
        sys.exit(1)

    phone = sys.argv[1]

    # Check which template(s) to send
    specific_template = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--template":
        specific_template = sys.argv[3]

    print(f"\n{'='*60}")
    print(f"  WhatsApp Template Test")
    print(f"  Phone: {phone}")
    print(f"  Template(s): {specific_template or 'ALL (5)'}")
    print(f"{'='*60}")

    results = {}

    if not specific_template or specific_template == "document_reminder":
        results["document_reminder"] = await test_document_reminder(phone)

    if not specific_template or specific_template == "project_reminder":
        results["project_reminder"] = await test_project_reminder(phone)

    if not specific_template or specific_template == "pico_y_placa":
        results["pico_y_placa"] = await test_pico_y_placa(phone)

    if not specific_template or specific_template == "event_reminder":
        results["event_reminder"] = await test_event_reminder(phone)

    if not specific_template or specific_template == "daily_digest":
        results["daily_digest"] = await test_daily_digest(phone)

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
