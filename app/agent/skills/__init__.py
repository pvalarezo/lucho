"""
Skill Loader — loads Ecuadorian domain knowledge as context.

Skills are flat Markdown files organized by domain under skills/.
They are loaded and injected as user-message context (not system prompt)
so the base system prompt stays short and cacheable.

Loading strategy:
- "always" skills: loaded for every message (modismos, cultura general)
- "on-demand" skills: loaded only when the message contains trigger keywords
"""

from pathlib import Path

# Skill files directory
SKILLS_DIR = Path(__file__).parent

# ---- Skill loading configuration ----

# Skills loaded for every message (always relevant)
ALWAYS_SKILLS = [
    "cultura/modismos.md",
]

# Skills loaded on-demand based on keyword triggers
ON_DEMAND_SKILLS = {
    "transito/matriculacion.md": [
        "matriculación", "matricula", "matricular", "soat", "rtv",
        "revisión técnica", "revision tecnica", "placa", "ant",
        "renovar", "renovación",
    ],
    "transito/pico-y-placa.md": [
        "pico y placa", "pico placa", "restricción", "restriccion",
        "no circula", "circulación", "quito", "cuenca", "multa",
    ],
    "legal/documentos.md": [
        "cédula", "cedula", "pasaporte", "licencia", "registro civil",
        "renovar documento", "vencimiento documento",
    ],
    "sri/facturacion.md": [
        "factura", "sri", "iva", "ruc", "impuesto", "declaración",
        "declaracion", "retención", "retencion",
    ],
}


def load_skill_content(relative_path: str) -> str:
    """Load a single skill file as text."""
    full_path = SKILLS_DIR / relative_path
    if not full_path.exists():
        return ""
    return full_path.read_text(encoding="utf-8").strip()


def load_skills_for_message(user_message: str) -> str:
    """
    Load relevant skills for a user message.

    Returns a combined context string (or empty if no skills match).
    This is injected into the agent as user-message context.
    """
    message_lower = user_message.lower()
    loaded_paths: list[str] = []
    loaded_contents: list[str] = []

    # 1. Always-loaded skills
    for skill_path in ALWAYS_SKILLS:
        content = load_skill_content(skill_path)
        if content:
            loaded_paths.append(skill_path)
            loaded_contents.append(content)

    # 2. On-demand skills (keyword match)
    for skill_path, keywords in ON_DEMAND_SKILLS.items():
        if any(kw in message_lower for kw in keywords):
            content = load_skill_content(skill_path)
            if content:
                loaded_paths.append(skill_path)
                loaded_contents.append(content)

    if not loaded_contents:
        return ""

    # Format as context block
    header = "## Contexto de dominio ecuatoriano relevante\n"
    return header + "\n\n---\n\n".join(loaded_contents)


def list_available_skills() -> list[str]:
    """List all available skill file paths."""
    skills = []
    for md_file in SKILLS_DIR.rglob("*.md"):
        relative = md_file.relative_to(SKILLS_DIR)
        skills.append(str(relative))
    return sorted(skills)
