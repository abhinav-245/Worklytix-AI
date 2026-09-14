"""AI-first analysis tests (stdlib unittest).

Run from backend/ with the venv::

    python -m unittest discover -s tests -v

All Gemini calls are mocked -- no API key required, no network access.
Focused suite only: /ai/analyze flow, analysis prompt contract, and
the curated knowledge selector. Follow-up questions stay covered by
tests/test_ai.py; recommendations by tests/test_recommend.py.
"""

import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

import main
from ai.config import GeminiConfig
from ai.knowledge import (
    UserSignals,
    format_knowledge,
    select_knowledge,
)
from ai.models import AIResponse
from ai.prompts import ANALYSIS_SYSTEM_PROMPT
from ai.service import (
    MAX_ANALYSIS_PLATEAUS,
    _fact_id_suggestions,
    analyze_training,
    build_analysis_contents,
    trim_context_for_model,
)
from ai.validation import (
    _numbers_requiring_grounding,
    validate_ai_response,
)
from analytics.profile import UserProfile
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def load_workouts():
    with open(FIXTURE_PATH, "rb") as f:
        raw = f.read()
    return process_csv_bytes(raw).workouts


def make_profile():
    return UserProfile(age=30, body_weight_kg=80.0, goal="strength")


class FakeModels:
    """Mimics google-genai's ``client.models`` namespace."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append(
            {"model": model, "contents": contents, "config": config}
        )
        if len(self.payloads) > 1:
            text = self.payloads.pop(0)
        else:
            text = self.payloads[0]
        return SimpleNamespace(text=text)


class FakeClient:
    """Mimics ``google.genai.Client`` (only what the service uses)."""

    def __init__(self, payloads):
        self.models = FakeModels(payloads)


def valid_analysis_payload():
    return json.dumps({
        "answer": (
            "# Your Training Analysis\n\n"
            "Your Bench Press weight PR is 75 kg, achieved on 2025-08-11.\n"
            "\n## Overall Training\n\nSteady training observed."
        ),
        "observations": [{
            "statement": "Your Bench Press weight PR is 75 kg.",
            "fact_ids": ["pr:bench_press_barbell:weight_pr"],
        }],
        "assumptions": [],
        "limitations": ["The dataset contains no nutrition data."],
    })


class TestAnalysisPrompt(unittest.TestCase):
    def test_reasoning_contract(self):
        prompt = ANALYSIS_SYSTEM_PROMPT
        self.assertIn("Is this actually meaningful?", prompt)
        self.assertIn("FACT VS INTERPRETATION", prompt)
        self.assertIn("Possible Plateau", prompt)
        self.assertIn("NO GENERIC FITNESS LECTURE", prompt)
        self.assertIn("untrusted DATA", prompt)
        self.assertIn("## Goal Alignment", prompt)

    def test_context_carries_goal_and_history(self):
        workouts = load_workouts()
        contents, index, _ = build_analysis_contents(
            workouts, make_profile()
        )
        text = contents[0]["parts"][0]["text"]
        self.assertIn("strength", text)
        self.assertIn("Intermediate", text)
        self.assertIn("pr:bench_press_barbell:weight_pr", text)
        self.assertIn("pr:bench_press_barbell:weight_pr", index.facts)

    def test_valid_analysis_passes_validation(self):
        workouts = load_workouts()
        _, index, _ = build_analysis_contents(workouts, make_profile())
        resp = AIResponse.model_validate(
            json.loads(valid_analysis_payload())
        )
        self.assertEqual(validate_ai_response(resp, index), [])

    def test_plateau_trim_is_capped_deterministic_and_lossless(self):
        from ai.context import build_ai_context

        workouts = load_workouts()
        context, index = build_ai_context(
            workouts, make_profile(), []
        )
        total = len(context.plateaus)
        self.assertGreater(total, MAX_ANALYSIS_PLATEAUS)
        trimmed = trim_context_for_model(context)
        self.assertEqual(len(trimmed.plateaus), MAX_ANALYSIS_PLATEAUS)
        # Original untouched; index still registers every plateau fact.
        self.assertEqual(len(context.plateaus), total)
        ends = [
            p["plateau_end"]["value"]
            if isinstance(p["plateau_end"], dict)
            else p["plateau_end"]
            for p in trimmed.plateaus
        ]
        self.assertEqual(ends, sorted(ends, reverse=True))
        self.assertEqual(trim_context_for_model(context).plateaus,
                         trimmed.plateaus)
        plateau_facts = [
            fid for fid in index.facts if fid.startswith("plateau:")
        ]
        self.assertGreater(len(plateau_facts), 0)

    def test_service_uses_analysis_schema(self):
        workouts = load_workouts()
        client = FakeClient([valid_analysis_payload()])
        result = analyze_training(
            workouts,
            make_profile(),
            config=GeminiConfig(api_key="test-key", model="test-model"),
            client=client,
        )
        self.assertIn("Bench Press", result.answer)
        call = client.models.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertIs(call["config"].response_schema, AIResponse)
        self.assertEqual(
            call["config"].system_instruction, ANALYSIS_SYSTEM_PROMPT
        )
        self.assertEqual(call["config"].max_output_tokens, 4096)


class TestGroundingCompatibility(unittest.TestCase):
    """Regression tests for the live /ai/analyze grounding failure.

    The real model response was rejected for: (a) thousands-formatted
    numbers fragmented by the extractor, (b) unregistered duration_text
    and potentially_neglected fact IDs, (c) invented 'prs'-style IDs.
    """

    @classmethod
    def setUpClass(cls):
        cls.workouts = load_workouts()
        cls.profile = make_profile()
        _, cls.index, _ = build_analysis_contents(
            cls.workouts, cls.profile
        )

    def test_thousands_formatted_grounded_number_accepted(self):
        resp = AIResponse(
            answer="Total volume is 3,274,475.1 kg.",
            observations=[{
                "statement": "Total volume is 3,274,475.1 kg.",
                "fact_ids": ["overview:dataset:total_volume_kg"],
            }],
        )
        self.assertEqual(validate_ai_response(resp, self.index), [])

    def test_thousands_formatted_invented_number_rejected(self):
        resp = AIResponse(
            answer="You completed 12,000 sets.",
            observations=[{
                "statement": "You completed 12,000 sets.",
                "fact_ids": ["overview:dataset:total_sets"],
            }],
        )
        problems = validate_ai_response(resp, self.index)
        self.assertTrue(any("12000" in p for p in problems))

    def test_duration_text_fact_accepted(self):
        self.assertIn("profile:duration_text", self.index.facts)
        resp = AIResponse(
            answer="Training spans 2 years, 3 months, 19 days.",
            observations=[{
                "statement": "Training history spans the full period.",
                "fact_ids": ["profile:duration_text"],
            }],
        )
        self.assertEqual(validate_ai_response(resp, self.index), [])

    def test_potentially_neglected_fact_accepted(self):
        fid = "muscle:abductors:potentially_neglected"
        self.assertIn(fid, self.index.facts)
        resp = AIResponse(
            answer="Abductors are potentially neglected with 0 sets.",
            observations=[{
                "statement": "Abductors are potentially neglected.",
                "fact_ids": [fid],
            }],
        )
        self.assertEqual(validate_ai_response(resp, self.index), [])

    def test_shortened_fact_id_rejected(self):
        resp = AIResponse(
            answer="Your Bench Press weight PR is 75 kg.",
            observations=[{
                "statement": "Your Bench Press weight PR is 75 kg.",
                "fact_ids": ["pr:bench_press_barbell"],
            }],
        )
        problems = validate_ai_response(resp, self.index)
        self.assertTrue(any("unknown fact ID" in p for p in problems))

    def test_suggestions_name_close_match(self):
        hints = _fact_id_suggestions(
            ["Observation 1 cites unknown fact ID "
             "'pr:bench_press_barbell'; only supplied fact IDs may be "
             "used."],
            self.index,
        )
        self.assertEqual(len(hints), 1)
        self.assertIn("pr:bench_press_barbell:weight_pr", hints[0])

    def test_suggestions_guide_without_close_match(self):
        hints = _fact_id_suggestions(
            ["Observation 1 cites unknown fact ID 'prs'; only supplied "
             "fact IDs may be used."],
            self.index,
        )
        self.assertEqual(len(hints), 1)
        self.assertIn("category:subject:metric", hints[0])

    def test_corrective_retry_carries_suggestions_and_recovers(self):
        bad = json.dumps({
            "answer": "Your Bench Press weight PR is 75 kg.",
            "observations": [{
                "statement": "Your Bench Press weight PR is 75 kg.",
                "fact_ids": ["prs"],
            }],
            "assumptions": [],
            "limitations": [],
        })
        client = FakeClient([bad, valid_analysis_payload()])
        result = analyze_training(
            self.workouts,
            self.profile,
            config=GeminiConfig(api_key="test-key", model="test-model"),
            client=client,
        )
        self.assertIn("Your Training Analysis", result.answer)
        self.assertEqual(len(client.models.calls), 2)
        retry_text = client.models.calls[1]["contents"][-1]["parts"][0][
            "text"
        ]
        self.assertIn("prs", retry_text)
        self.assertIn("category:subject:metric", retry_text)


class TestKnowledgeSelector(unittest.TestCase):
    def test_strength_plateau_signals(self):
        items = select_knowledge(UserSignals(
            goal="strength", level="Intermediate", has_plateau=True,
        ))
        ids = [item.id for item in items]
        self.assertIn("plateau-variation", ids)
        self.assertIn("volume-landmarks-strength", ids)
        self.assertNotIn("volume-landmarks-hypertrophy", ids)

    def test_fat_loss_selects_consistency(self):
        items = select_knowledge(UserSignals(
            goal="fat_loss", level="Beginner", low_frequency=True,
        ))
        ids = [item.id for item in items]
        self.assertIn("consistency-first-fat-loss", ids)
        self.assertIn("beginner-foundations", ids)

    def test_limit_and_determinism(self):
        signals = UserSignals(goal="strength", level="Intermediate")
        first = [item.id for item in select_knowledge(signals, limit=3)]
        second = [item.id for item in select_knowledge(signals, limit=3)]
        self.assertEqual(len(first), 3)
        self.assertEqual(first, second)

    def test_format_labels_non_facts(self):
        items = select_knowledge(UserSignals(goal="strength"))
        text = format_knowledge(items)
        self.assertIn("background knowledge only", text)
        self.assertIn("never cite", text.lower())


class TestAnalyzeEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def _upload_and_profile(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        res = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        assert res.status_code == 200
        res = self.client.post("/profile", json={
            "age": 30, "body_weight_kg": 80.0, "goal": "strength",
        })
        assert res.status_code == 200

    def _analyze(self):
        return self.client.post("/ai/analyze")

    def _mocked(self, payloads):
        return (
            mock.patch("ai.service._get_client",
                       return_value=FakeClient(payloads)),
            mock.patch("main.load_gemini_config",
                       return_value=GeminiConfig(
                           api_key="test-key", model="test-model")),
        )

    def test_no_dataset_404(self):
        res = self._analyze()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_no_profile_404(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        res = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        assert res.status_code == 200
        res = self._analyze()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_profile")

    def test_missing_key_503(self):
        self._upload_and_profile()
        with mock.patch("main.load_gemini_config",
                        return_value=GeminiConfig(api_key="",
                                                  model="test-model")):
            res = self._analyze()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["detail"]["error"], "ai_not_configured")

    def test_valid_analysis_envelope(self):
        self._upload_and_profile()
        get_client, load_config = self._mocked(
            [valid_analysis_payload()]
        )
        with get_client, load_config:
            res = self._analyze()
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["meta"]["analysis_version"], "v1")
        self.assertEqual(body["meta"]["model"], "test-model")
        data = body["data"]
        self.assertIn("# Your Training Analysis", data["answer"])
        self.assertEqual(
            data["observations"][0]["fact_ids"],
            ["pr:bench_press_barbell:weight_pr"],
        )

    def test_invented_fact_id_becomes_502(self):
        self._upload_and_profile()
        bad = json.dumps({
            "answer": "Your Bench Press weight PR is 75 kg.",
            "observations": [{
                "statement": "Your Bench Press weight PR is 75 kg.",
                "fact_ids": ["prs"],
            }],
            "assumptions": [],
            "limitations": [],
        })
        get_client, load_config = self._mocked([bad, bad])
        with get_client, load_config:
            res = self._analyze()
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.json()["detail"]["error"], "ai_provider_error")

    def test_raw_provider_exception_becomes_controlled_502(self):
        self._upload_and_profile()

        class ExplodingModels:
            def generate_content(self, **kwargs):
                raise RuntimeError("simulated transport failure")

        class ExplodingClient:
            models = ExplodingModels()

        with mock.patch("ai.service._get_client",
                        return_value=ExplodingClient()):
            _, load_config = self._mocked([])
            with load_config:
                res = self._analyze()
        self.assertEqual(res.status_code, 502)
        body = res.json()["detail"]
        self.assertEqual(body["error"], "ai_provider_error")
        self.assertNotIn("simulated transport failure",
                         json.dumps(body))


if __name__ == "__main__":
    unittest.main()
