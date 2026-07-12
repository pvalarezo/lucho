"""Vehicle rules engine — deterministic calculations for Ecuadorian vehicle obligations.

Rules are pure functions: no IO, no database access. The scheduler calls these
and compares results against stored assets/events. This is the "determinism in
the center" principle in action.

Sources:
- Matriculación: ANT Ecuador, último dígito de placa → mes
- Pico y placa: Quito/Cuenca, último dígito → días restringidos
- SOAT/RTV: annual, tied to matriculación month
"""

import logging
from datetime import date, timedelta
from enum import IntEnum

logger = logging.getLogger(__name__)


# ---- Matriculación: último dígito de placa → mes de matriculación ----

MATRICULATION_MONTH: dict[int, int] = {
    1: 1,   # enero
    2: 2,   # febrero
    3: 3,   # marzo
    4: 4,   # abril
    5: 5,   # mayo
    6: 6,   # junio
    7: 7,   # julio
    8: 8,   # agosto
    9: 9,   # septiembre
    0: 10,  # octubre
}


def matriculation_month(last_digit: int) -> int:
    """
    Return the month (1-12) when a vehicle must renew its matriculación.
    Based on ANT Ecuador rules: last digit of plate → month.
    """
    return MATRICULATION_MONTH.get(last_digit, 1)


def matriculation_deadline(last_digit: int, year: int | None = None) -> date:
    """
    Return the exact deadline date for matriculación renewal.
    Deadline is the last day of the corresponding month.
    Example: plate ending in 3 → March 31.
    """
    if year is None:
        year = date.today().year

    month = matriculation_month(last_digit)
    # Last day of month
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return next_month - timedelta(days=1)


def next_matriculation_date(last_digit: int, reference_date: date | None = None) -> date:
    """
    Return the next upcoming matriculación deadline from a reference date.
    If this year's deadline has passed, returns next year's deadline.
    """
    if reference_date is None:
        reference_date = date.today()

    deadline = matriculation_deadline(last_digit, reference_date.year)
    if deadline < reference_date:
        deadline = matriculation_deadline(last_digit, reference_date.year + 1)
    return deadline


# ---- Pico y placa: último dígito → días restringidos (Quito/Cuenca) ----

# Standard Ecuador pico y placa: 2 digits per day, Mon-Fri
PICO_Y_PLACA_SCHEDULE: dict[int, list[int]] = {
    # digit → [restricted weekdays (0=Mon, 6=Sun)]
    1: [0],          # Lunes
    2: [0],          # Lunes
    3: [1],          # Martes
    4: [1],          # Martes
    5: [2],          # Miércoles
    6: [2],          # Miércoles
    7: [3],          # Jueves
    8: [3],          # Jueves
    9: [4],          # Viernes
    0: [4],          # Viernes
}


def pico_y_placa_restricted_days(last_digit: int) -> list[int]:
    """
    Return the restricted weekdays (0=Monday, 6=Sunday) for a plate's last digit.
    """
    return PICO_Y_PLACA_SCHEDULE.get(last_digit, [])


def is_pico_y_placa_today(last_digit: int, reference_date: date | None = None) -> bool:
    """
    Check if the vehicle has pico y placa restriction today.
    Returns False on weekends (no restriction).
    """
    if reference_date is None:
        reference_date = date.today()

    weekday = reference_date.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:  # Weekend
        return False

    restricted = pico_y_placa_restricted_days(last_digit)
    return weekday in restricted


def pico_y_placa_description(last_digit: int) -> str:
    """
    Human-readable description of pico y placa restriction.
    Example: "Lunes" or "Lunes y Martes (placa terminada en 1 o 2)".
    """
    days = pico_y_placa_restricted_days(last_digit)
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    day_labels = [day_names[d] for d in days if d < 5]
    if not day_labels:
        return "Sin restricción"
    return " y ".join(day_labels)


# ---- SOAT: annual, tied to vehicle purchase/ matriculación month ----

def soat_expiry(acquisition_month: int, year: int | None = None) -> date:
    """
    SOAT expires one year after purchase, on the last day of the acquisition month.
    """
    if year is None:
        year = date.today().year

    if acquisition_month == 12:
        return date(year, 12, 31)
    return date(year, acquisition_month + 1, 1) - timedelta(days=1)


# ---- RTV (Revisión Técnica Vehicular): same month as matriculación ----

def rtv_deadline(last_digit: int, year: int | None = None) -> date:
    """
    RTV deadline follows the same schedule as matriculación.
    """
    return matriculation_deadline(last_digit, year)


# ---- Utility: evaluate all rules for a vehicle asset ----

def evaluate_vehicle_rules(
    plate: str,
    last_digit: int | None = None,
    reference_date: date | None = None,
) -> dict:
    """
    Evaluate all vehicle rules for a given plate.
    Returns a dict with upcoming deadlines and restrictions.
    This is the entry point called by the daily cron.
    """
    if reference_date is None:
        reference_date = date.today()

    # Auto-detect last digit from plate if not provided
    if last_digit is None and plate:
        # Extract last numeric digit from plate (e.g., "PBC-1234" → 4)
        digits = [c for c in plate if c.isdigit()]
        last_digit = int(digits[-1]) if digits else 0

    if last_digit is None:
        last_digit = 0

    today_pyp = is_pico_y_placa_today(last_digit, reference_date)
    matriculation = next_matriculation_date(last_digit, reference_date)
    pyp_days = pico_y_placa_description(last_digit)

    return {
        "plate": plate,
        "last_digit": last_digit,
        "pico_y_placa_today": today_pyp,
        "pico_y_placa_days": pyp_days,
        "matriculation_month": matriculation_month(last_digit),
        "next_matriculation": matriculation.isoformat(),
        "days_until_matriculation": (matriculation - reference_date).days,
    }
