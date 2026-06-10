"""Pure unit tests for VVT normalization: map-reduce merge + value grounding (no DB, no LLM)."""

from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from app.config import settings
from app.services import vvt_service as vs
from app.services.vvt_service import (
    UNVERIFIED_VALUE_NOTE,
    _VVTExtractionField,
    _VVTExtractionResult,
)


def _field(
    name="Zwecke der Verarbeitung",
    status="filled",
    value=None,
    evidence=None,
    finding=None,
):
    return _VVTExtractionField(
        field_name=name,
        status=status,
        canonical_value=value,
        evidence=evidence,
        finding=finding,
    )


_SOURCE = (
    "Verzeichnis der Verarbeitungstätigkeiten. "
    "Zwecke der Verarbeitung: Durchführung von Online-Prüfungen im Fachbereich Informatik. "
    "Speicherdauer: 10 Jahre gemäß HGB. "
    "Rechtsgrundlage: Art. 6 Abs. 1 lit. e DSGVO in Verbindung mit dem HessHG."
)


# ---------------------------------------------------------------------------
# _value_grounded
# ---------------------------------------------------------------------------


class TestValueGrounded:
    def test_verbatim_value_is_grounded(self):
        assert vs._value_grounded("Durchführung von Online-Prüfungen", _SOURCE, 0.85)

    def test_fabricated_value_is_not_grounded(self):
        assert not vs._value_grounded(
            "Videoüberwachung sämtlicher Mitarbeiter am Arbeitsplatz", _SOURCE, 0.85
        )

    def test_short_value_auto_passes(self):
        # Too short to verify reliably (see grounding module) — never penalized.
        assert vs._value_grounded("10 Jahre", _SOURCE, 0.85)

    def test_empty_value_or_source_passes(self):
        assert vs._value_grounded(None, _SOURCE, 0.85)
        assert vs._value_grounded("   ", _SOURCE, 0.85)
        assert vs._value_grounded("irgendein Wert", "", 0.85)

    def test_list_value_with_half_grounded_parts_passes(self):
        value = "Durchführung von Online-Prüfungen im Fachbereich Informatik, frei erfundener Verarbeitungszweck XYZ"
        assert vs._value_grounded(value, _SOURCE, 0.85)


# ---------------------------------------------------------------------------
# _merge_two / _merge_extractions
# ---------------------------------------------------------------------------


class TestMerge:
    def test_filled_beats_missing_in_both_orders(self):
        filled = _field(value="Online-Prüfungen", evidence="Sheet 1, Zeile 2")
        missing = _field(status="missing")
        for a, b in ((filled, missing), (missing, filled)):
            merged = vs._merge_two(a, b)
            assert merged.status == "filled"
            assert merged.canonical_value == "Online-Prüfungen"
            assert merged.evidence == "Sheet 1, Zeile 2"

    def test_equivalent_filled_values_keep_richer_value(self):
        a = _field(value="Online-Prüfungen", evidence="Sheet 1")
        b = _field(value="Durchführung von Online-Prüfungen", evidence="Sheet 2")
        merged = vs._merge_two(a, b)
        assert merged.status == "filled"
        assert merged.canonical_value == "Durchführung von Online-Prüfungen"
        assert "Sheet 1" in merged.evidence and "Sheet 2" in merged.evidence

    def test_conflicting_filled_values_become_inconsistent(self):
        a = _field(name="Speicherdauer", value="10 Jahre")
        b = _field(name="Speicherdauer", value="6 Monate")
        merged = vs._merge_two(a, b)
        assert merged.status == "inconsistent"
        assert "10 Jahre" in merged.finding and "6 Monate" in merged.finding

    def test_inconsistent_always_wins(self):
        bad = _field(status="inconsistent", value="A", finding="Widerspruch")
        good = _field(value="B")
        merged = vs._merge_two(good, bad)
        assert merged.status == "inconsistent"
        assert "Widerspruch" in merged.finding

    def test_both_missing_stays_missing(self):
        merged = vs._merge_two(_field(status="missing"), _field(status="missing"))
        assert merged.status == "missing"
        assert merged.canonical_value is None

    def test_merge_extractions_prefers_concrete_template(self):
        r1 = _VVTExtractionResult(
            source_template="Unbekannt", fields=[_field(status="missing")]
        )
        r2 = _VVTExtractionResult(
            source_template="Variante A", fields=[_field(value="X")]
        )
        merged = vs._merge_extractions([r1, r2])
        assert merged.source_template == "Variante A"
        assert merged.fields[0].status == "filled"


# ---------------------------------------------------------------------------
# _apply_vvt_grounding
# ---------------------------------------------------------------------------


class TestApplyGrounding:
    def test_ungrounded_filled_value_gets_review_note(self, monkeypatch):
        monkeypatch.setattr(settings, "evidence_grounding_enabled", True, raising=False)
        result = _VVTExtractionResult(
            fields=[
                _field(
                    value="Videoüberwachung sämtlicher Mitarbeiter am Arbeitsplatz",
                    finding="bestehend",
                ),
            ]
        )
        out = vs._apply_vvt_grounding(result, _SOURCE)
        assert UNVERIFIED_VALUE_NOTE in out.fields[0].finding
        assert "bestehend" in out.fields[0].finding  # existing finding preserved

    def test_grounded_value_is_untouched(self, monkeypatch):
        monkeypatch.setattr(settings, "evidence_grounding_enabled", True, raising=False)
        result = _VVTExtractionResult(
            fields=[
                _field(
                    value="Durchführung von Online-Prüfungen im Fachbereich Informatik"
                ),
            ]
        )
        out = vs._apply_vvt_grounding(result, _SOURCE)
        assert out.fields[0].finding is None

    def test_disabled_grounding_is_noop(self, monkeypatch):
        monkeypatch.setattr(
            settings, "evidence_grounding_enabled", False, raising=False
        )
        result = _VVTExtractionResult(
            fields=[
                _field(value="Videoüberwachung sämtlicher Mitarbeiter am Arbeitsplatz"),
            ]
        )
        out = vs._apply_vvt_grounding(result, _SOURCE)
        assert out.fields[0].finding is None


# ---------------------------------------------------------------------------
# _make_vvt_grounding_validator
# ---------------------------------------------------------------------------


class TestGroundingValidator:
    def _ctx(self, retry=0):
        return SimpleNamespace(retry=retry)

    def test_all_filled_values_fabricated_triggers_retry(self, monkeypatch):
        monkeypatch.setattr(settings, "evidence_grounding_enabled", True, raising=False)
        monkeypatch.setattr(settings, "llm_output_retries", 2, raising=False)
        validate = vs._make_vvt_grounding_validator(_SOURCE)
        output = _VVTExtractionResult(
            fields=[
                _field(
                    name="Zwecke der Verarbeitung",
                    value="Videoüberwachung sämtlicher Mitarbeiter am Arbeitsplatz",
                ),
                _field(
                    name="Speicherdauer",
                    value="vollständig erfundene Aufbewahrungsregelung 99",
                ),
            ]
        )
        with pytest.raises(ModelRetry):
            validate(self._ctx(retry=0), output)

    def test_one_grounded_value_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "evidence_grounding_enabled", True, raising=False)
        monkeypatch.setattr(settings, "llm_output_retries", 2, raising=False)
        validate = vs._make_vvt_grounding_validator(_SOURCE)
        output = _VVTExtractionResult(
            fields=[
                _field(
                    name="Zwecke der Verarbeitung",
                    value="Durchführung von Online-Prüfungen im Fachbereich Informatik",
                ),
                _field(
                    name="Speicherdauer",
                    value="vollständig erfundene Aufbewahrungsregelung 99",
                ),
            ]
        )
        assert validate(self._ctx(retry=0), output) is output

    def test_final_attempt_never_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "evidence_grounding_enabled", True, raising=False)
        monkeypatch.setattr(settings, "llm_output_retries", 2, raising=False)
        validate = vs._make_vvt_grounding_validator(_SOURCE)
        output = _VVTExtractionResult(
            fields=[
                _field(
                    name="Zwecke der Verarbeitung",
                    value="Videoüberwachung sämtlicher Mitarbeiter am Arbeitsplatz",
                ),
                _field(
                    name="Speicherdauer",
                    value="vollständig erfundene Aufbewahrungsregelung 99",
                ),
            ]
        )
        assert validate(self._ctx(retry=2), output) is output


# ---------------------------------------------------------------------------
# normalize_vvt — map-reduce over long documents
# ---------------------------------------------------------------------------


class _FakeRunResult:
    def __init__(self, output):
        self.output = output


@pytest.fixture
def _no_db_templates(monkeypatch):
    async def _none(_key):
        return None

    monkeypatch.setattr(vs, "get_active_template", _none)
    monkeypatch.setattr(vs, "create_agent", lambda **kwargs: object())


class TestNormalizeVvtMapReduce:
    @pytest.mark.anyio
    async def test_long_document_is_extracted_per_fragment_and_merged(
        self, monkeypatch, _no_db_templates
    ):
        monkeypatch.setattr(
            settings, "evidence_grounding_enabled", False, raising=False
        )
        monkeypatch.setattr(settings, "vvt_map_reduce_enabled", True, raising=False)
        monkeypatch.setattr(settings, "max_context_chars_vvt", 300, raising=False)
        monkeypatch.setattr(settings, "vvt_max_chunks", 8, raising=False)

        # Two fragments: the first knows the Zwecke, the second the Speicherdauer.
        per_call = [
            _VVTExtractionResult(
                source_template="Unbekannt",
                fields=[
                    _field(name="Zwecke der Verarbeitung", value="Online-Prüfungen"),
                    _field(name="Speicherdauer", status="missing"),
                ],
            ),
            _VVTExtractionResult(
                source_template="Variante A",
                fields=[
                    _field(name="Zwecke der Verarbeitung", status="missing"),
                    _field(name="Speicherdauer", value="10 Jahre gemäß HGB"),
                ],
            ),
        ]
        calls = {"n": 0}

        async def _fake_llm(agent, user_content, output_type):
            out = per_call[min(calls["n"], len(per_call) - 1)]
            calls["n"] += 1
            return _FakeRunResult(out.model_copy(deep=True))

        monkeypatch.setattr(vs, "llm_retry_call", _fake_llm)

        raw = " ".join(
            f"Satz Nummer {i} über die Verarbeitung personenbezogener Daten."
            for i in range(40)
        )
        assert len(raw) > 300
        result = await vs.normalize_vvt(
            raw, language="de", field_names=["Zwecke der Verarbeitung", "Speicherdauer"]
        )

        assert calls["n"] >= 2  # one LLM call per fragment
        by_name = {f.field_name: f for f in result.fields}
        assert by_name["Zwecke der Verarbeitung"].status == "filled"
        assert by_name["Zwecke der Verarbeitung"].canonical_value == "Online-Prüfungen"
        assert by_name["Speicherdauer"].status == "filled"
        assert by_name["Speicherdauer"].canonical_value == "10 Jahre gemäß HGB"
        assert result.source_template == "Variante A"
        # Canonical order is preserved.
        assert [f.field_name for f in result.fields] == [
            "Zwecke der Verarbeitung",
            "Speicherdauer",
        ]

    @pytest.mark.anyio
    async def test_conflicting_fragments_yield_inconsistent_field(
        self, monkeypatch, _no_db_templates
    ):
        monkeypatch.setattr(
            settings, "evidence_grounding_enabled", False, raising=False
        )
        monkeypatch.setattr(settings, "vvt_map_reduce_enabled", True, raising=False)
        monkeypatch.setattr(settings, "max_context_chars_vvt", 300, raising=False)

        per_call = [
            _VVTExtractionResult(
                fields=[_field(name="Speicherdauer", value="10 Jahre")]
            ),
            _VVTExtractionResult(
                fields=[_field(name="Speicherdauer", value="6 Monate")]
            ),
        ]
        calls = {"n": 0}

        async def _fake_llm(agent, user_content, output_type):
            out = per_call[min(calls["n"], len(per_call) - 1)]
            calls["n"] += 1
            return _FakeRunResult(out.model_copy(deep=True))

        monkeypatch.setattr(vs, "llm_retry_call", _fake_llm)

        raw = " ".join(
            f"Satz Nummer {i} über Aufbewahrungsfristen und Löschkonzepte."
            for i in range(40)
        )
        result = await vs.normalize_vvt(
            raw, language="de", field_names=["Speicherdauer"]
        )
        field = result.fields[0]
        assert field.status == "inconsistent"
        assert "10 Jahre" in field.finding and "6 Monate" in field.finding

    @pytest.mark.anyio
    async def test_short_document_uses_single_call(self, monkeypatch, _no_db_templates):
        monkeypatch.setattr(
            settings, "evidence_grounding_enabled", False, raising=False
        )
        monkeypatch.setattr(settings, "vvt_map_reduce_enabled", True, raising=False)
        monkeypatch.setattr(settings, "max_context_chars_vvt", 25000, raising=False)
        calls = {"n": 0}

        async def _fake_llm(agent, user_content, output_type):
            calls["n"] += 1
            return _FakeRunResult(_VVTExtractionResult(fields=[]))

        monkeypatch.setattr(vs, "llm_retry_call", _fake_llm)
        result = await vs.normalize_vvt(
            "Kurzer VVT-Text.", language="de", field_names=["Speicherdauer"]
        )
        assert calls["n"] == 1
        assert result.fields[0].status == "missing"  # canonical fields are completed

    @pytest.mark.anyio
    async def test_disabled_map_reduce_falls_back_to_truncation(
        self, monkeypatch, _no_db_templates
    ):
        monkeypatch.setattr(
            settings, "evidence_grounding_enabled", False, raising=False
        )
        monkeypatch.setattr(settings, "vvt_map_reduce_enabled", False, raising=False)
        monkeypatch.setattr(settings, "max_context_chars_vvt", 300, raising=False)
        captured = {}

        async def _fake_llm(agent, user_content, output_type):
            captured["user_content"] = user_content
            return _FakeRunResult(_VVTExtractionResult(fields=[]))

        monkeypatch.setattr(vs, "llm_retry_call", _fake_llm)
        raw = " ".join(f"Satz Nummer {i} über die Verarbeitung." for i in range(40))
        await vs.normalize_vvt(raw, language="de", field_names=["Speicherdauer"])
        assert "[... truncated" in captured["user_content"]
