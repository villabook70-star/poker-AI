"""Optional natural-language explanations via the Claude API.

The model never computes poker maths. It receives the deterministic engine's
numbers (equity, pot odds, EV, ranges, provenance tags) and is instructed to
explain them in Spanish without inventing figures. If no API key is
configured the module returns a deterministic template explanation.
"""
from __future__ import annotations

import json
import os
from typing import Optional

MODEL = os.environ.get("POKERMIND_CLAUDE_MODEL", "claude-opus-5-5")

SYSTEM_PROMPT = (
    "Eres un entrenador de póker (Twister / Spin & Go 3-max). Recibirás un JSON producido por un motor "
    "determinista con la situación, la recomendación, las alternativas con su EV y la procedencia de cada "
    "número (exact, monte_carlo, nash, heuristic). Explica la decisión en español, en 4-7 frases claras para un "
    "jugador que aprende. REGLAS ESTRICTAS: no inventes ni recalcules porcentajes, EV ni rangos; usa solo los "
    "números del JSON; distingue explícitamente lo exacto, lo estimado por Monte Carlo, lo que viene del "
    "equilibrio Nash push/fold y lo heurístico; nunca presentes una heurística como jugada óptima; menciona la "
    "incertidumbre cuando el nivel de confianza sea bajo o la muestra del rival sea pequeña."
)


def claude_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def template_explanation(payload: dict) -> str:
    rec = payload.get("recommendation", {})
    lines = [f"Acción recomendada: {rec.get('action', '?').upper()}" + (f" por {rec['amount']}" if rec.get("amount") else "") +
             f" (confianza {rec.get('confidence', '?')})."]
    lines += rec.get("explanation", [])
    srcs = rec.get("sources", [])
    if srcs:
        legend = {"exact": "cálculo exacto", "monte_carlo": "estimación Monte Carlo", "nash": "equilibrio Nash push/fold (juego restringido)", "heuristic": "heurística"}
        lines.append("Procedencia de los números: " + ", ".join(legend.get(s, s) for s in srcs) + ".")
    if rec.get("warnings"):
        lines.append("Avisos: " + " ".join(rec["warnings"]))
    return "\n".join(lines)


def explain(payload: dict, use_claude: Optional[bool] = None) -> dict:
    """Return {"text": ..., "provider": "claude"|"template", "model": ...}."""
    if use_claude is None:
        use_claude = claude_available()
    if not use_claude:
        return {"text": template_explanation(payload), "provider": "template", "model": None}
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Explica esta decisión:\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"}],
        )
        if response.stop_reason == "refusal":
            return {"text": template_explanation(payload), "provider": "template", "model": None,
                    "note": "El modelo rechazó la petición; se muestra la explicación determinista."}
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return {"text": text or template_explanation(payload), "provider": "claude", "model": response.model}
    except Exception as exc:  # noqa: BLE001 - never let the optional layer break the app
        return {"text": template_explanation(payload), "provider": "template", "model": None, "note": f"Claude no disponible: {type(exc).__name__}"}
