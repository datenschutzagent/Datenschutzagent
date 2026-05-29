"""Rule-based risk fallback when the LLM is unavailable or low-confidence.

Pure functions — no DB, no IO. The AVV/DSFA services call these when the
configured confidence-policy demands it.

Design goals:
  - Never raise. Heuristics must always produce a valid result so the API
    stays available even if the LLM provider is down for hours.
  - Match the LLM output shape closely so the rest of the pipeline
    (normalization, mitigation engine, persistence) can stay untouched.
  - Be conservative: when the input is ambiguous, lean toward higher risk
    so that the DPO is alerted rather than missed.

The heuristics are intentionally simple and deterministic — they are a
safety net, not a competitor to the LLM.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# AVV
# ---------------------------------------------------------------------------


# Keywords that indicate elevated risk per dimension. Matched
# case-insensitively against the contract fields.
_AVV_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "Datensensitivität": {
        "high": [
            "gesundheit", "patient", "diagnos",
            "biometrie", "kind", "schüler", "student",
            "personalakte", "lohnabrechnung", "religion",
            "sozial", "bonität", "kredit", "straf",
        ],
        "medium": ["kontakt", "kunde", "interessent", "vertrieb", "marketing"],
    },
    "Zugriffsumfang": {
        "high": ["administrator", "vollzugriff", "produktivdaten", "alle daten"],
        "medium": ["lese", "auswert", "monitor"],
    },
    "Drittlandrisiko": {
        "high": ["usa", "united states", "indien", "china", "drittland"],
        "medium": ["uk", "schweiz", "norweg"],
    },
    "Subauftragsverarbeiter-Risiko": {
        "high": ["sub-av", "subauftrag", "weitergabe", "subprozessor", "konzern"],
        "medium": ["dienstleister", "externer support"],
    },
    "Vertragliche Absicherung": {
        # Inverted — these keywords indicate WEAK contractual coverage (= higher risk)
        "high": ["entwurf", "draft", "noch nicht unterzeichnet", "ausstehend"],
        "medium": ["interne version", "alte version", "veraltet"],
    },
}


def _score_dimension(name: str, text: str) -> int:
    """Return 1..5 based on keyword hits for the given dimension.

    Defaults to 3 (medium) when no signals are found — a deliberately
    cautious midpoint that flags the assessment for review.
    """
    lc = text.lower()
    rules = _AVV_KEYWORDS.get(name, {})
    if any(kw in lc for kw in rules.get("high", [])):
        return 4
    if any(kw in lc for kw in rules.get("medium", [])):
        return 3
    return 3


def compute_avv_fallback(
    *,
    partner_name: str,
    partner_type: str,
    subject_matter: str | None,
    department: str | None,
    notes: str | None,
) -> dict[str, Any]:
    """Produce a structured AVV risk result without calling an LLM.

    Returns a dict shaped like ``_AVVRiskResult.model_dump()`` so the rest of
    ``avv_risk_service.assess_avv_risk`` can consume it transparently.
    """
    text = " ".join(
        x for x in (partner_name, subject_matter, department, notes) if x
    )

    dimensions: list[dict[str, Any]] = []
    for dim_name in (
        "Datensensitivität",
        "Zugriffsumfang",
        "Drittlandrisiko",
        "Subauftragsverarbeiter-Risiko",
        "Vertragliche Absicherung",
    ):
        score = _score_dimension(dim_name, text)
        # Sub-AVs carry inherently higher risk per Art. 28 IV.
        if dim_name == "Subauftragsverarbeiter-Risiko" and partner_type == "sub_processor":
            score = max(score, 4)
        dimensions.append({
            "name": dim_name,
            "score": score,
            "rationale": "Regelbasierte Heuristik (LLM nicht verfügbar oder niedrige Konfidenz).",
        })

    avg = sum(d["score"] for d in dimensions) / len(dimensions)
    # Match avv_cfg.level_for_score default thresholds: 1.5 / 2.5 / 3.5 / 5.
    if avg <= 1.5:
        overall = "low"
    elif avg <= 2.5:
        overall = "medium"
    elif avg <= 3.5:
        overall = "high"
    else:
        overall = "critical"

    main_risks: list[str] = []
    if any(d["name"] == "Datensensitivität" and d["score"] >= 4 for d in dimensions):
        main_risks.append("Verarbeitung sensibler personenbezogener Daten")
    if any(d["name"] == "Drittlandrisiko" and d["score"] >= 4 for d in dimensions):
        main_risks.append("Mögliche Datenübermittlung in Drittland ohne Angemessenheitsbeschluss")
    if any(d["name"] == "Vertragliche Absicherung" and d["score"] >= 4 for d in dimensions):
        main_risks.append("AVV-Klauseln unvollständig oder noch nicht unterzeichnet")
    if not main_risks:
        main_risks.append("Keine spezifischen Risikoindikatoren in den Vertragsdaten erkannt.")

    recommended_measures = [
        "Manuelle Prüfung durch DSB empfohlen (Regelbasierter Fallback).",
        "Vertragsgegenstand und Datenkategorien präzisieren.",
        "AVV-Klauseln auf Vollständigkeit prüfen (Art. 28 III DSGVO).",
    ]

    return {
        "dimensions": dimensions,
        "overall_risk_level": overall,
        "main_risks": main_risks[:3],
        "recommended_measures": recommended_measures[:5],
        "summary": (
            f"Regelbasierte Bewertung. Durchschnittlicher Risikoscore {avg:.1f}/5. "
            "Eine manuelle Prüfung durch den Datenschutzbeauftragten wird empfohlen."
        ),
        # Mark explicitly as low-confidence by definition.
        "confidence": 0.3,
    }


# ---------------------------------------------------------------------------
# DSFA
# ---------------------------------------------------------------------------


# Map of (keyword, likelihood, severity) tuples → risk template. Used to
# generate DSFA risks based on case context.
_DSFA_TEMPLATES: list[dict[str, Any]] = [
    {
        "trigger": "special_category_data",
        "description": (
            "Verarbeitung besonderer Kategorien personenbezogener Daten "
            "(Art. 9 DSGVO) — erhöhtes Schutzbedürfnis."
        ),
        "likelihood": 3,
        "severity": 5,
        "mitigation": "Zugriffskontrollen, Pseudonymisierung, Schulung.",
    },
    {
        "trigger": "international_transfer",
        "description": (
            "Übermittlung in Drittländer — Schutzniveau muss "
            "über SCC oder Angemessenheitsbeschluss sichergestellt werden."
        ),
        "likelihood": 3,
        "severity": 4,
        "mitigation": "EU-Standardvertragsklauseln; TIA (Transfer Impact Assessment).",
    },
    {
        "keywords": ["profil", "scoring", "automat", "entscheid"],
        "description": (
            "Profiling oder automatisierte Entscheidungsfindung — "
            "betroffene Personen müssen informiert werden, Widerspruchsrecht beachten."
        ),
        "likelihood": 3,
        "severity": 4,
        "mitigation": "Transparenz, menschliche Letztentscheidung, Widerspruchsrecht.",
    },
    {
        "keywords": ["überwach", "kamera", "tracking", "monitor"],
        "description": "Systematische Überwachung — Verhältnismäßigkeit prüfen.",
        "likelihood": 3,
        "severity": 4,
        "mitigation": "Beschränkung des Erfassungsbereichs, Löschkonzept, Beschilderung.",
    },
    {
        "keywords": ["kind", "schüler", "student", "minderjähr"],
        "description": "Verarbeitung von Daten Minderjähriger oder vulnerabler Gruppen.",
        "likelihood": 3,
        "severity": 4,
        "mitigation": "Einwilligungserfordernisse beachten (Art. 8), Datenminimierung.",
    },
    {
        "keywords": ["ki ", "künstliche intel", "biometrie", "iot", "blockchain"],
        "description": "Einsatz innovativer Technologie mit unbekanntem Risikoprofil.",
        "likelihood": 3,
        "severity": 3,
        "mitigation": "Externe Evaluation, Pilotphase mit DSB-Begleitung.",
    },
    {
        "keywords": ["massendaten", "großmaßst", "umfangreich"],
        "description": "Umfangreiche Verarbeitung — erhöhtes kumulatives Risiko.",
        "likelihood": 3,
        "severity": 3,
        "mitigation": "Strikte Zweckbindung, kurze Aufbewahrungsfristen.",
    },
]


def compute_dsfa_fallback(
    *,
    case_title: str,
    case_type: str,
    processing_context: str | None,
    special_category_data: bool,
    international_transfer: bool,
    open_critical_findings: int,
) -> dict[str, Any]:
    """Produce a structured DSFA result without calling an LLM.

    Returns a dict shaped like ``_DSFAResult.model_dump()``.
    """
    haystack = " ".join(
        x for x in (case_title, case_type, processing_context or "") if x
    ).lower()

    risks: list[dict[str, Any]] = []
    for tpl in _DSFA_TEMPLATES:
        match = False
        trigger = tpl.get("trigger")
        if trigger == "special_category_data" and special_category_data:
            match = True
        elif trigger == "international_transfer" and international_transfer:
            match = True
        else:
            kws = tpl.get("keywords", [])
            if kws and any(kw in haystack for kw in kws):
                match = True
        if match:
            risks.append({
                "description": tpl["description"],
                "likelihood": tpl["likelihood"],
                "severity": tpl["severity"],
                "mitigation": tpl["mitigation"],
            })

    # Critical findings escalate at least one generic risk.
    if open_critical_findings > 0:
        risks.append({
            "description": (
                f"{open_critical_findings} offene kritische/hohe Compliance-Befunde "
                "aus Playbook-Prüfungen."
            ),
            "likelihood": 4,
            "severity": 4,
            "mitigation": "Findings priorisiert abarbeiten; Re-Run nach Behebung.",
        })

    # Conservative baseline if nothing matched — surface that a review is needed.
    if not risks:
        risks.append({
            "description": (
                "Allgemeines Datenschutzrisiko – manuelle Bewertung durch DSB erforderlich, "
                "da der automatische Heuristik-Fallback keine spezifischen Auslöser erkannt hat."
            ),
            "likelihood": 2,
            "severity": 3,
            "mitigation": "DSB-Review anstoßen, Verarbeitungskontext präzisieren.",
        })

    return {
        "necessity_assessment": (
            "Regelbasierter Fallback (LLM nicht verfügbar oder niedrige Konfidenz). "
            "Notwendigkeit der Verarbeitung bitte manuell prüfen."
        ),
        "proportionality_assessment": (
            "Regelbasierter Fallback. Verhältnismäßigkeitsprüfung durch DSB erforderlich."
        ),
        "risks": risks,
        "measures": [
            "Manuelle Validierung durch Datenschutzbeauftragten.",
            "Verarbeitungskontext im Vorgang vervollständigen.",
            "Bei Verfügbarkeit des LLM: Re-Generierung der DSFA.",
        ],
        "confidence": 0.3,
    }
