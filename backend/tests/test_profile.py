"""Phase 9 profile tests (stdlib unittest; run from backend/ with the venv).

    python -m unittest discover -s tests -v
"""

import os
import unittest
from datetime import date

from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from analytics.profile import (
    UserProfile,
    attach_bodyweight_ratios,
    calculate_bodyweight_ratio,
    classify_training_history_level,
    compute_training_history,
)
from analytics.prs import generate_exercise_prs
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def make_workout(title, start, names=("Bench Press (Barbell)",)):
    return WorkoutRecord(
        title=title,
        start_time=start,
        end_time=None,
        exercises=[
            ExerciseRecord(
                exercise_name=name,
                sets=[SetRecord(set_number=0, set_type="normal",
                                weight_kg=60, reps=8)],
            )
            for name in names
        ],
    )


def history_of(workouts):
    result = compute_training_history(workouts)
    assert result is not None
    return result


class TestProfileValidation(unittest.TestCase):
    def test_valid_profile(self):
        profile = UserProfile(age=25, body_weight_kg=63.0, goal="muscle_gain")
        self.assertEqual(profile.age, 25)
        self.assertEqual(profile.body_weight_kg, 63.0)
        self.assertEqual(profile.goal, "muscle_gain")

    def test_valid_integer_body_weight(self):
        profile = UserProfile(age=30, body_weight_kg=63, goal="strength")
        self.assertEqual(profile.body_weight_kg, 63.0)

    def test_valid_goals(self):
        for goal in ["muscle_gain", "strength", "fat_loss", "general_fitness"]:
            with self.subTest(goal=goal):
                UserProfile(age=25, body_weight_kg=63.0, goal=goal)

    def test_integer_compatible_float_age_accepted(self):
        # 25.0 arrives as an integer-compatible value.
        self.assertEqual(
            UserProfile(age=25.0, body_weight_kg=63.0,  # type: ignore[arg-type]
                        goal="strength").age, 25
        )

    def test_zero_age_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=0, body_weight_kg=63.0, goal="strength")

    def test_negative_age_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=-5, body_weight_kg=63.0, goal="strength")

    def test_fractional_age_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=25.5, body_weight_kg=63.0,  # type: ignore[arg-type]
                        goal="strength")

    def test_zero_body_weight_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=25, body_weight_kg=0, goal="strength")

    def test_negative_body_weight_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=25, body_weight_kg=-10, goal="strength")

    def test_invalid_goal_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=25, body_weight_kg=63.0, goal="marathon")  # type: ignore[arg-type]

    def test_missing_fields_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(age=25, goal="strength")  # type: ignore[call-arg]
        with self.assertRaises(ValidationError):
            UserProfile(body_weight_kg=63.0, goal="strength")  # type: ignore[call-arg]
        with self.assertRaises(ValidationError):
            UserProfile(age=25, body_weight_kg=63.0)  # type: ignore[call-arg]


class TestTrainingHistory(unittest.TestCase):
    def test_empty_dataset_returns_none(self):
        self.assertIsNone(compute_training_history([]))

    def test_single_workout(self):
        history = history_of([make_workout("W1", "2026-01-01T07:00:00")])
        self.assertEqual(history.start_date, "2026-01-01")
        self.assertEqual(history.end_date, "2026-01-01")
        self.assertEqual(history.duration_days, 0)
        self.assertEqual(history.duration_text, "0 days")
        self.assertEqual(history.level, "Beginner")

    def test_multiple_workouts(self):
        history = history_of([
            make_workout("W1", "2024-05-24T07:00:00"),
            make_workout("W2", "2026-09-12T18:00:00"),
        ])
        self.assertEqual(history.start_date, "2024-05-24")
        self.assertEqual(history.end_date, "2026-09-12")
        self.assertEqual(history.duration_days, 841)
        self.assertEqual(history.duration_text, "2 years, 3 months, 19 days")
        self.assertEqual(history.level, "Intermediate")

    def test_time_of_day_ignored(self):
        history = history_of([
            make_workout("W1", "2026-01-01T00:00:00"),
            make_workout("W2", "2026-01-01T23:59:00"),
        ])
        self.assertEqual(history.duration_days, 0)
        self.assertEqual(history.duration_text, "0 days")

    def test_exactly_one_year_is_intermediate(self):
        history = history_of([
            make_workout("W1", "2024-01-15T07:00:00"),
            make_workout("W2", "2025-01-15T07:00:00"),
        ])
        self.assertEqual(history.duration_days, 366)  # leap year span
        self.assertEqual(history.duration_text, "1 year")
        self.assertEqual(history.level, "Intermediate")

    def test_just_under_one_year_is_beginner(self):
        history = history_of([
            make_workout("W1", "2024-01-15T07:00:00"),
            make_workout("W2", "2025-01-14T07:00:00"),
        ])
        self.assertEqual(history.level, "Beginner")

    def test_exactly_three_years_is_advanced(self):
        history = history_of([
            make_workout("W1", "2023-03-10T07:00:00"),
            make_workout("W2", "2026-03-10T07:00:00"),
        ])
        self.assertEqual(history.duration_text, "3 years")
        self.assertEqual(history.level, "Advanced")

    def test_just_under_three_years_is_intermediate(self):
        history = history_of([
            make_workout("W1", "2023-03-10T07:00:00"),
            make_workout("W2", "2026-03-09T07:00:00"),
        ])
        self.assertEqual(history.level, "Intermediate")

    def test_year_boundary(self):
        history = history_of([
            make_workout("W1", "2024-12-30T07:00:00"),
            make_workout("W2", "2025-01-06T07:00:00"),
        ])
        self.assertEqual(history.start_date, "2024-12-30")
        self.assertEqual(history.end_date, "2025-01-06")
        self.assertEqual(history.duration_days, 7)
        self.assertEqual(history.duration_text, "7 days")
        self.assertEqual(history.level, "Beginner")

    def test_classify_directly(self):
        self.assertEqual(
            classify_training_history_level(date(2024, 1, 1), date(2024, 6, 1)),
            "Beginner",
        )
        self.assertEqual(
            classify_training_history_level(date(2024, 1, 1), date(2026, 1, 1)),
            "Intermediate",
        )
        self.assertEqual(
            classify_training_history_level(date(2020, 1, 1), date(2026, 1, 1)),
            "Advanced",
        )


class TestBodyweightRatios(unittest.TestCase):
    def _workouts(self):
        return [
            WorkoutRecord(
                title="W1",
                start_time="2026-01-05T07:00:00",
                end_time=None,
                exercises=[
                    ExerciseRecord(
                        exercise_name="Bench Press (Barbell)",
                        sets=[
                            SetRecord(set_number=0, set_type="normal",
                                      weight_kg=75, reps=8),
                            SetRecord(set_number=1, set_type="normal",
                                      weight_kg=95, reps=5),
                        ],
                    ),
                    ExerciseRecord(
                        exercise_name="Plank",
                        sets=[SetRecord(set_number=0, set_type="normal")],
                    ),
                ],
            )
        ]

    def test_ratio_calculation(self):
        self.assertEqual(calculate_bodyweight_ratio(100, 63), 1.59)
        self.assertEqual(calculate_bodyweight_ratio(75, 63), 1.19)
        self.assertEqual(calculate_bodyweight_ratio(95, 63), 1.51)

    def test_weight_and_1rm_ratios(self):
        prs = attach_bodyweight_ratios(
            generate_exercise_prs(self._workouts()), 63.0
        )
        bench = next(p for p in prs if p.exercise_name == "Bench Press (Barbell)")
        assert bench.weight_pr is not None
        assert bench.estimated_1rm_pr is not None
        # 95 kg max; epley max is 95x5 -> 110.83.
        self.assertEqual(bench.weight_pr.value, 95)
        self.assertEqual(bench.weight_pr_ratio, 1.51)
        self.assertEqual(bench.estimated_1rm_pr.value, 110.83)
        self.assertEqual(bench.estimated_1rm_pr_ratio, 1.76)

    def test_decimal_body_weight(self):
        prs = attach_bodyweight_ratios(
            generate_exercise_prs(self._workouts()), 63.5
        )
        bench = next(p for p in prs if p.exercise_name == "Bench Press (Barbell)")
        self.assertEqual(bench.weight_pr_ratio, round(95 / 63.5, 2))

    def test_missing_pr_keeps_null_ratio(self):
        prs = attach_bodyweight_ratios(
            generate_exercise_prs(self._workouts()), 63.0
        )
        plank = next(p for p in prs if p.exercise_name == "Plank")
        self.assertIsNone(plank.weight_pr)
        self.assertIsNone(plank.weight_pr_ratio)
        self.assertIsNone(plank.estimated_1rm_pr_ratio)

    def test_original_values_unchanged(self):
        workouts = self._workouts()
        before = [p.model_dump() for p in generate_exercise_prs(workouts)]
        attach_bodyweight_ratios(generate_exercise_prs(workouts), 63.0)
        after = [p.model_dump() for p in generate_exercise_prs(workouts)]
        self.assertEqual(before, after)
        enriched = attach_bodyweight_ratios(generate_exercise_prs(workouts), 63.0)
        bench = next(p for p in enriched
                     if p.exercise_name == "Bench Press (Barbell)")
        assert bench.weight_pr is not None
        self.assertEqual(bench.weight_pr.value, 95)  # load untouched

    def test_independent_per_exercise(self):
        prs = attach_bodyweight_ratios(
            generate_exercise_prs(self._workouts()), 100.0
        )
        by_name = {p.exercise_name: p for p in prs}
        assert by_name["Bench Press (Barbell)"].weight_pr_ratio is not None
        self.assertEqual(
            by_name["Bench Press (Barbell)"].weight_pr_ratio, 0.95
        )
        self.assertIsNone(by_name["Plank"].weight_pr_ratio)


class TestProfileApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def test_submit_profile_before_upload(self):
        res = self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["profile"], {
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        self.assertIsNone(body["training_history"])

    def test_submit_profile_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        self.assertEqual(res.status_code, 200)
        history = res.json()["training_history"]
        self.assertEqual(history["start_date"], "2024-05-24")
        self.assertEqual(history["end_date"], "2026-09-12")
        self.assertEqual(history["duration_days"], 841)
        self.assertEqual(history["duration_text"], "2 years, 3 months, 19 days")
        self.assertEqual(history["level"], "Intermediate")

    def test_invalid_profile_returns_422(self):
        for payload in [
            {"age": 0, "body_weight_kg": 63.0, "goal": "strength"},
            {"age": -5, "body_weight_kg": 63.0, "goal": "strength"},
            {"age": 25.5, "body_weight_kg": 63.0, "goal": "strength"},
            {"age": 25, "body_weight_kg": 0, "goal": "strength"},
            {"age": 25, "body_weight_kg": -10, "goal": "strength"},
            {"age": 25, "body_weight_kg": 63.0, "goal": "marathon"},
            {"age": 25, "goal": "strength"},
        ]:
            with self.subTest(payload=payload):
                res = self.client.post("/profile", json=payload)
                self.assertEqual(res.status_code, 422)

    def test_pr_ratios_appear_after_profile(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        before = self.client.get("/analysis/prs").json()
        bench_before = next(
            p for p in before if p["exercise_name"] == "Bench Press (Barbell)"
        )
        self.assertIsNone(bench_before["weight_pr_ratio"])
        self.assertIsNone(bench_before["estimated_1rm_pr_ratio"])

        self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        after = self.client.get("/analysis/prs").json()
        bench_after = next(
            p for p in after if p["exercise_name"] == "Bench Press (Barbell)"
        )
        # Existing values untouched; ratios added.
        self.assertEqual(bench_after["weight_pr"], bench_before["weight_pr"])
        self.assertEqual(
            bench_after["estimated_1rm_pr"], bench_before["estimated_1rm_pr"]
        )
        self.assertEqual(bench_after["weight_pr_ratio"], 1.19)
        self.assertEqual(bench_after["estimated_1rm_pr_ratio"], 1.51)

    def test_existing_endpoints_intact(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        for path in ["/health", "/analysis/overview", "/analysis/prs",
                     "/analysis/progression", "/analysis/plateaus",
                     "/analysis/muscles", "/analysis/exercise-variety"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


class TestRealHevyProfile(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_history_and_ratios(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        workouts = process_csv_bytes(raw).workouts
        history = compute_training_history(workouts)
        assert history is not None
        self.assertEqual(history.start_date, "2024-05-24")
        self.assertEqual(history.end_date, "2026-09-12")
        self.assertEqual(history.duration_days, 841)
        self.assertEqual(history.level, "Intermediate")

        prs = attach_bodyweight_ratios(generate_exercise_prs(workouts), 63.0)
        by_name = {p.exercise_name: p for p in prs}
        # Cross-check several PRs against the raw CSV, then verify ratios.
        import pandas as pd

        df = pd.read_csv(FIXTURE_PATH)
        valid = df[df["weight_kg"].notna() & df["reps"].notna()]
        valid = valid[(valid["weight_kg"] > 0) & (valid["reps"] > 0)]
        for name in ["Bench Press (Barbell)", "Squat (Barbell)",
                     "Deadlift (Barbell)", "Overhead Press (Barbell)"]:
            with self.subTest(exercise=name):
                sub = valid[valid["exercise_title"] == name]
                pr = by_name[name]
                assert pr.weight_pr is not None
                assert pr.estimated_1rm_pr is not None
                expected_w = round(float(sub["weight_kg"].max()), 2)
                self.assertAlmostEqual(pr.weight_pr.value, expected_w, places=2)
                self.assertAlmostEqual(
                    pr.weight_pr_ratio or 0, round(expected_w / 63.0, 2),
                    places=2,
                )
                epley = (sub["weight_kg"] * (1 + sub["reps"] / 30)).max()
                self.assertAlmostEqual(
                    pr.estimated_1rm_pr_ratio or 0,
                    round(float(epley) / 63.0, 2),
                    places=2,
                )


if __name__ == "__main__":
    unittest.main()
