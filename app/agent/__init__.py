"""
Lucho Agent — reactive AI agent with tools.

The agent uses a single LLM with a unified system prompt ("soul")
and tool-calling to understand, persist, search, and respond.

Architecture:
- system_prompt.py → Lucho's identity, boundaries, personality
- tools.py         → Tool schemas + deterministic handlers
- loop.py          → Agent loop: message → LLM → (tools) → response

Usage:
    from app.agent import process_message

    response = await process_message(session, user_id, "Mi carro es PBC-1234")
    # → "¡Listo! Guardé tu carro PBC-1234. Tu matriculación es en octubre..."
"""

from app.agent.loop import process_message

__all__ = ["process_message"]
