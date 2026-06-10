"""Pure unit tests for evidence grounding (no DB, no LLM)."""

from app.core.grounding import (
    _normalize,
    grounding_ratio,
    is_grounded,
    partition_grounded,
)

SOURCE = (
    "Die Speicherdauer der Lohndaten betraegt 10 Jahre gemaess HGB. "
    "Rechtsgrundlage der Verarbeitung ist Art. 6 Abs. 1 lit. c DSGVO. "
    "Eine Uebermittlung in Drittlaender findet nicht statt."
)


class TestIsGrounded:
    def test_exact_quote_is_grounded(self):
        assert is_grounded(
            "die Speicherdauer der Lohndaten betraegt 10 Jahre", _normalize(SOURCE)
        )

    def test_quote_with_different_whitespace_and_case(self):
        assert is_grounded("RECHTSGRUNDLAGE   der    Verarbeitung", _normalize(SOURCE))

    def test_hallucinated_quote_not_grounded(self):
        assert not is_grounded(
            "Daten werden an einen US-Dienstleister ohne Garantien uebermittelt",
            _normalize(SOURCE),
        )

    def test_short_quote_skipped(self):
        # Too short to verify reliably → treated as grounded (no false alarm).
        assert is_grounded("Art. 6", _normalize(SOURCE))

    def test_empty_source_does_not_penalize(self):
        assert is_grounded("irgendein langer satz hier", "")


class TestPartitionAndRatio:
    def test_partition_drops_empty_and_classifies(self):
        grounded, ungrounded = partition_grounded(
            [
                "",
                "  ",
                "Eine Uebermittlung in Drittlaender findet nicht statt",
                "voellig erfundener inhalt xyz abc",
            ],
            SOURCE,
        )
        assert grounded == ["Eine Uebermittlung in Drittlaender findet nicht statt"]
        assert ungrounded == ["voellig erfundener inhalt xyz abc"]

    def test_ratio_all_grounded_when_no_quotes(self):
        assert grounding_ratio([], SOURCE) == 1.0

    def test_ratio_half(self):
        ratio = grounding_ratio(
            [
                "Die Speicherdauer der Lohndaten betraegt 10 Jahre",
                "frei erfundene aussage ohne bezug",
            ],
            SOURCE,
        )
        assert ratio == 0.5
