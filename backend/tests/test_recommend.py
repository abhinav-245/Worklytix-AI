"""Phase 13 recommendation tests (stdlib unittest).

Run from backend/ with the venv::

    python -m unittest discover -s tests -v

All Gemini calls are mocked -- no API key required, no network access.
Focused suite only: valid flow, context contents, grounding negatives,
safety boundaries, and controlled errors. Phase 12 /ai/ask behavior is
covered by tests/test_ai.py.
"""

import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

import main
from ai.config import GeminiConfig
from ai.models import RecommendationResponse
from ai.prompts import RECOMMENDATION_SYSTEM_PROMPT_V2
from ai.service import build_recommendation_contents, recommend_training
from ai.validation import validate_recommendation_response
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


ANALYSIS_TEXT = (
    "# Your Training Analysis\n\nBench Press progressed steadily."
)


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


def valid_recommendation_payload():
    return json.dumps({
        "recommendations": [{
            "recommendation": "Consider reviewing your current "
                              "progression strategy for Bench Press.",
            "reason": "Your Bench Press weight PR is 75 kg.",
            "fact_ids": ["pr:bench_press_barbell:weight_pr"],
        }],
        "observations": [{
            "statement": "Your Bench Press weight PR is 75 kg.",
            "fact_ids": ["pr:bench_press_barbell:weight_pr"],
        }],
        "assumptions": [],
        "limitations": ["The dataset contains no nutrition data."],
    })


class TestRecommendContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workouts = load_workouts()
        cls.profile = make_profile()

    def test_context_carries_goal_and_history(self):
        contents, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        text = contents[0]["parts"][0]["text"]
        self.assertIn("strength", text)
        self.assertIn("Intermediate", text)
        self.assertIn("pr:bench_press_barbell:weight_pr", text)
        self.assertIn("pr:bench_press_barbell:weight_pr", index.facts)

    def test_context_carries_knowledge_and_analysis(self):
        contents, _, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        text = contents[0]["parts"][0]["text"]
        self.assertIn("Bench Press progressed steadily", text)
        self.assertIn("General training principles", text)
        self.assertIn("[plateau-variation", text)

    def test_prompt_treats_input_as_data(self):
        self.assertIn("untrusted DATA", RECOMMENDATION_SYSTEM_PROMPT_V2)
        self.assertIn("never invent", RECOMMENDATION_SYSTEM_PROMPT_V2.lower())

    def test_valid_recommendation_passes_validation(self):
        _, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        resp = RecommendationResponse.model_validate(
            json.loads(valid_recommendation_payload())
        )
        self.assertEqual(validate_recommendation_response(resp, index), [])

    def test_invented_fact_id_rejected(self):
        _, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        resp = RecommendationResponse(
            recommendations=[{
                "recommendation": "Consider reviewing Bench Press.",
                "reason": "Bench Press is trained.",
                "fact_ids": ["prs"],
            }],
        )
        problems = validate_recommendation_response(resp, index)
        self.assertTrue(any("unknown fact ID" in p for p in problems))

    def test_unsupported_number_rejected(self):
        _, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        resp = RecommendationResponse(
            recommendations=[{
                "recommendation": "Lift 999999 kg next session.",
                "reason": "Bigger is better.",
                "fact_ids": ["pr:bench_press_barbell:weight_pr"],
            }],
        )
        problems = validate_recommendation_response(resp, index)
        self.assertTrue(any("999999" in p for p in problems))

    def test_invented_date_rejected(self):
        _, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        resp = RecommendationResponse(
            observations=[{
                "statement": "On 2031-01-01 you set a PR.",
                "fact_ids": ["pr:bench_press_barbell:weight_pr"],
            }],
        )
        problems = validate_recommendation_response(resp, index)
        self.assertTrue(any("2031-01-01" in p for p in problems))

    def test_nutrition_claim_rejected(self):
        _, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        resp = RecommendationResponse(
            recommendations=[{
                "recommendation": "Consume more protein every day.",
                "reason": "Protein supports muscle repair.",
                "fact_ids": ["pr:bench_press_barbell:weight_pr"],
            }],
        )
        problems = validate_recommendation_response(resp, index)
        self.assertTrue(any("nutrition" in p for p in problems))

    def test_medical_claim_rejected(self):
        _, index, _ = build_recommendation_contents(
            self.workouts, self.profile, ANALYSIS_TEXT
        )
        resp = RecommendationResponse(
            recommendations=[{
                "recommendation": "Your symptoms require treatment.",
                "reason": "This needs prescribed medication.",
                "fact_ids": ["pr:bench_press_barbell:weight_pr"],
            }],
        )
        problems = validate_recommendation_response(resp, index)
        self.assertTrue(any("medical" in p for p in problems))

    def test_service_uses_recommendation_schema(self):
        client = FakeClient([valid_recommendation_payload()])
        result = recommend_training(
            self.workouts,
            self.profile,
            ANALYSIS_TEXT,
            config=GeminiConfig(api_key="test-key", model="test-model"),
            client=client,
        )
        self.assertEqual(len(result.recommendations), 1)
        call = client.models.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertIs(call["config"].response_schema, RecommendationResponse)
        self.assertIn("goal", call["config"].system_instruction.lower())


class TestRecommendEndpoint(unittest.TestCase):
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

    def _recommend(self, body=None):
        return self.client.post(
            "/ai/recommend",
            json={"analysis": ANALYSIS_TEXT} if body is None else body,
        )

    def _mocked(self, payloads):
        return (
            mock.patch("ai.service._get_client",
                       return_value=FakeClient(payloads)),
            mock.patch("main.load_gemini_config",
                       return_value=GeminiConfig(
                           api_key="test-key", model="test-model")),
        )

    def test_no_dataset_404(self):
        res = self._recommend()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_no_profile_404(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        res = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        assert res.status_code == 200
        res = self._recommend()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_profile")

    def test_missing_key_503(self):
        self._upload_and_profile()
        with mock.patch("main.load_gemini_config",
                        return_value=GeminiConfig(api_key="",
                                                  model="test-model")):
            res = self._recommend()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["detail"]["error"], "ai_not_configured")

    def test_empty_analysis_422(self):
        self._upload_and_profile()
        res = self._recommend(body={"analysis": "   "})
        self.assertEqual(res.status_code, 422)
        res = self._recommend(body={})
        self.assertEqual(res.status_code, 422)

    def test_valid_recommendation_envelope(self):
        self._upload_and_profile()
        get_client, load_config = self._mocked(
            [valid_recommendation_payload()]
        )
        with get_client, load_config:
            res = self._recommend()
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["meta"]["analysis_version"], "v1")
        self.assertEqual(body["meta"]["model"], "test-model")
        data = body["data"]
        self.assertEqual(len(data["recommendations"]), 1)
        self.assertEqual(
            data["recommendations"][0]["fact_ids"],
            ["pr:bench_press_barbell:weight_pr"],
        )
        self.assertTrue(data["observations"])
        self.assertIn("recommendation", data["recommendations"][0])
        self.assertIn("reason", data["recommendations"][0])

    def test_invented_fact_id_becomes_502(self):
        self._upload_and_profile()
        bad = json.dumps({
            "recommendations": [{
                "recommendation": "Consider reviewing Bench Press.",
                "reason": "Bench Press is trained.",
                "fact_ids": ["prs"],
            }],
            "observations": [],
            "assumptions": [],
            "limitations": [],
        })
        get_client, load_config = self._mocked([bad, bad])
        with get_client, load_config:
            res = self._recommend()
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.json()["detail"]["error"], "ai_provider_error")

    def test_unsupported_claim_becomes_502(self):
        self._upload_and_profile()
        bad = json.dumps({
            "recommendations": [{
                "recommendation": "Lift 999999 kg next session.",
                "reason": "Bigger is better.",
                "fact_ids": ["pr:bench_press_barbell:weight_pr"],
            }],
            "observations": [],
            "assumptions": [],
            "limitations": [],
        })
        get_client, load_config = self._mocked([bad, bad])
        with get_client, load_config:
            res = self._recommend()
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.json()["detail"]["error"], "ai_provider_error")

    def test_unsafe_claim_becomes_502(self):
        self._upload_and_profile()
        bad = json.dumps({
            "recommendations": [{
                "recommendation": "Consume more protein every day.",
                "reason": "Protein supports muscle repair.",
                "fact_ids": ["pr:bench_press_barbell:weight_pr"],
            }],
            "observations": [],
            "assumptions": [],
            "limitations": [],
        })
        get_client, load_config = self._mocked([bad, bad])
        with get_client, load_config:
            res = self._recommend()
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
                res = self._recommend()
        self.assertEqual(res.status_code, 502)
        body = res.json()["detail"]
        self.assertEqual(body["error"], "ai_provider_error")
        self.assertNotIn("simulated transport failure",
                         json.dumps(body))


if __name__ == "__main__":
    unittest.main()
