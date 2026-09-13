"""Phase 4 PR engine tests (stdlib unittest; run from backend/ with the venv).

    python -m unittest discover -s tests -v
"""

import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.prs import (
    calculate_estimated_1rm,
    calculate_estimated_1rm_pr,
    calculate_rep_pr,
    calculate_volume_pr,
    calculate_weight_pr,
    generate_exercise_prs,
)
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def make_set(weight=None, reps=None, set_type="normal", set_number=0):
    return SetRecord(
        set_number=set_number,
        set_type=set_type,
        weight_kg=weight,
        reps=reps,
    )


def make_workout(title, start, sets_by_exercise, end=None):
    return WorkoutRecord(
        title=title,
        start_time=start,
        end_time=end,
        exercises=[
            ExerciseRecord(exercise_name=name, sets=sets)
            for name, sets in sets_by_exercise.items()
        ],
    )


def pr_of(name, workouts):
    for pr in generate_exercise_prs(workouts):
        if pr.exercise_name == name:
            return pr
    raise AssertionError(f"no PR entry for {name!r}")


class TestKnownExamples(unittest.TestCase):
    def test_weight_pr(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(80, 8), make_set(90, 8), make_set(100, 5)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.weight_pr is not None
        self.assertEqual(pr.weight_pr.value, 100)
        self.assertEqual(pr.weight_pr.unit, "kg")
        self.assertEqual(pr.weight_pr.date, "2026-08-01")

    def test_rep_pr(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(80, 5), make_set(80, 8), make_set(80, 12)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.rep_pr is not None
        self.assertEqual(pr.rep_pr.value, 12)
        self.assertEqual(pr.rep_pr.unit, "reps")

    def test_volume_pr(self):
        # 80x8=640, 90x6=540, 75x10=750 -> 750 wins (not the heaviest set).
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(80, 8), make_set(90, 6), make_set(75, 10)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.volume_pr is not None
        self.assertEqual(pr.volume_pr.value, 750)
        self.assertEqual(pr.volume_pr.weight, 75)
        self.assertEqual(pr.volume_pr.reps, 10)

    def test_epley_1rm(self):
        self.assertEqual(calculate_estimated_1rm(100, 5), 116.67)

    def test_estimated_1rm_pr_selects_formula_maximum(self):
        # 100x5 -> 116.67, 95x6 -> 114.0, 90x8 -> 114.0
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(100, 5), make_set(95, 6), make_set(90, 8)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.estimated_1rm_pr is not None
        self.assertEqual(pr.estimated_1rm_pr.value, 116.67)
        self.assertEqual(pr.estimated_1rm_pr.weight, 100)
        self.assertEqual(pr.estimated_1rm_pr.reps, 5)

    def test_heaviest_weight_is_not_always_best_1rm(self):
        # 100x1 -> 103.33 but 95x5 -> 110.83 wins.
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(100, 1), make_set(95, 5)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.estimated_1rm_pr is not None
        assert pr.weight_pr is not None
        self.assertEqual(pr.weight_pr.value, 100)
        self.assertEqual(pr.estimated_1rm_pr.value, 110.83)
        self.assertEqual(pr.estimated_1rm_pr.weight, 95)


class TestMultipleExercises(unittest.TestCase):
    def test_independent_per_exercise(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(100, 5)],
            "Squat": [make_set(140, 8)],
        })
        prs = {p.exercise_name: p for p in generate_exercise_prs([w])}
        self.assertEqual(set(prs), {"Bench Press", "Squat"})
        assert prs["Bench Press"].weight_pr is not None
        assert prs["Squat"].weight_pr is not None
        self.assertEqual(prs["Bench Press"].weight_pr.value, 100)
        self.assertEqual(prs["Squat"].weight_pr.value, 140)
        self.assertEqual(prs["Squat"].volume_pr.value, 1120)  # type: ignore[union-attr]


class TestEligibility(unittest.TestCase):
    def test_missing_weight_excluded(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(None, 10), make_set(80, 8)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.weight_pr is not None
        assert pr.volume_pr is not None
        assert pr.estimated_1rm_pr is not None
        self.assertEqual(pr.weight_pr.value, 80)
        # Per spec, rep PR also requires valid weight: the None-weight set
        # is fully ineligible, so the max comes from the 80x8 set.
        assert pr.rep_pr is not None
        self.assertEqual(pr.rep_pr.value, 8)

    def test_missing_reps_excluded(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(80, None), make_set(90, 6)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.weight_pr is not None
        # The None-reps set is fully ineligible, so the max is 90, not 80.
        self.assertEqual(pr.weight_pr.value, 90)
        assert pr.rep_pr is not None
        self.assertEqual(pr.rep_pr.value, 6)

    def test_zero_and_negative_values_ineligible(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [
                make_set(0, 10),
                make_set(80, 0),
                make_set(-50, 5),
                make_set(60, -3),
                make_set(70, 6),
            ],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.weight_pr is not None
        assert pr.rep_pr is not None
        assert pr.volume_pr is not None
        assert pr.estimated_1rm_pr is not None
        self.assertEqual(pr.weight_pr.value, 70)
        self.assertEqual(pr.rep_pr.value, 6)
        self.assertEqual(pr.volume_pr.value, 420)
        self.assertEqual(pr.estimated_1rm_pr.value, 84.0)  # 70 x (1 + 6/30)

    def test_non_integer_reps_ineligible(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(80, 8.5), make_set(70, 6)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.rep_pr is not None
        self.assertEqual(pr.rep_pr.value, 6)

    def test_all_set_types_eligible_when_valid(self):
        for set_type in ["normal", "warm_up", "drop_set", "failure", "unknown",
                         "unknown:super_set"]:
            with self.subTest(set_type=set_type):
                w = make_workout("A", "2026-08-01T07:00:00", {
                    "Bench Press": [make_set(100, 5, set_type=set_type)],
                })
                pr = pr_of("Bench Press", [w])
                assert pr.weight_pr is not None
                self.assertEqual(pr.weight_pr.value, 100)
                assert pr.estimated_1rm_pr is not None
                self.assertEqual(pr.estimated_1rm_pr.value, 116.67)


class TestEmptyAndNoEligible(unittest.TestCase):
    def test_empty_dataset_returns_empty_list(self):
        self.assertEqual(generate_exercise_prs([]), [])

    def test_exercise_without_eligible_sets_has_null_prs(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Plank": [make_set(None, None)],
            "Bench Press": [make_set(80, 8)],
        })
        prs = {p.exercise_name: p for p in generate_exercise_prs([w])}
        self.assertIn("Plank", prs)  # listed, not omitted
        self.assertIsNone(prs["Plank"].weight_pr)
        self.assertIsNone(prs["Plank"].rep_pr)
        self.assertIsNone(prs["Plank"].volume_pr)
        self.assertIsNone(prs["Plank"].estimated_1rm_pr)
        assert prs["Bench Press"].weight_pr is not None


class TestTies(unittest.TestCase):
    def test_earliest_occurrence_wins(self):
        w1 = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(100, 5)],
        })
        w2 = make_workout("B", "2026-08-20T07:00:00", {
            "Bench Press": [make_set(100, 5)],
        })
        # Pass out of order: result must still pick the earliest workout.
        pr = pr_of("Bench Press", [w2, w1])
        assert pr.weight_pr is not None
        assert pr.volume_pr is not None
        assert pr.estimated_1rm_pr is not None
        self.assertEqual(pr.weight_pr.value, 100)
        self.assertEqual(pr.weight_pr.date, "2026-08-01")
        self.assertEqual(pr.volume_pr.date, "2026-08-01")
        self.assertEqual(pr.estimated_1rm_pr.date, "2026-08-01")
        # Deterministic across repeated runs.
        again = pr_of("Bench Press", [w1, w2])
        self.assertEqual(pr.model_dump(), again.model_dump())


class TestPrecision(unittest.TestCase):
    def test_decimal_weights(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(82.5, 5)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.weight_pr is not None
        assert pr.volume_pr is not None
        assert pr.estimated_1rm_pr is not None
        self.assertEqual(pr.weight_pr.value, 82.5)
        self.assertEqual(pr.volume_pr.value, 412.5)
        self.assertEqual(pr.estimated_1rm_pr.value, 96.25)  # 82.5 x 35/30

    def test_no_float_artifacts(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Bench Press": [make_set(100, 5), make_set(33.3, 3)],
        })
        pr = pr_of("Bench Press", [w])
        assert pr.estimated_1rm_pr is not None
        assert pr.volume_pr is not None
        self.assertEqual(pr.estimated_1rm_pr.value, 116.67)
        for value in (pr.estimated_1rm_pr.value, pr.volume_pr.value):
            self.assertEqual(value, round(value, 2))

    def test_large_values(self):
        w = make_workout("A", "2026-08-01T07:00:00", {
            "Deadlift": [make_set(500, 10)],
        })
        pr = pr_of("Deadlift", [w])
        assert pr.volume_pr is not None
        assert pr.estimated_1rm_pr is not None
        self.assertEqual(pr.volume_pr.value, 5000)
        self.assertEqual(pr.estimated_1rm_pr.value, 666.67)  # 500 x 40/30


class TestPrApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None

    def tearDown(self):
        main._LAST_WORKOUTS = None

    def test_prs_before_upload_is_404(self):
        res = self.client.get("/analysis/prs")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_prs_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)
        res = self.client.get("/analysis/prs")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 117)
        names = [p["exercise_name"] for p in body]
        self.assertEqual(names, sorted(names))
        self.assertIn("Bench Press (Barbell)", names)


class TestRealHevyPrs(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_dataset(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        workouts = process_csv_bytes(raw).workouts
        prs = {p.exercise_name: p for p in generate_exercise_prs(workouts)}

        df = pd.read_csv(FIXTURE_PATH)
        valid = df[df["weight_kg"].notna() & df["reps"].notna()]
        valid = valid[(valid["weight_kg"] > 0) & (valid["reps"] > 0)]
        self.assertEqual(len(prs), df["exercise_title"].nunique())

        # Independently verify several exercises against the raw CSV.
        for name in ["Deadlift (Barbell)", "Bench Press (Barbell)", "Squat (Barbell)"]:
            with self.subTest(exercise=name):
                sub = valid[valid["exercise_title"] == name]
                self.assertGreater(len(sub), 0)
                pr = prs[name]
                assert pr.weight_pr is not None
                assert pr.rep_pr is not None
                assert pr.volume_pr is not None
                assert pr.estimated_1rm_pr is not None
                self.assertAlmostEqual(
                    pr.weight_pr.value, float(sub["weight_kg"].max()), places=2
                )
                self.assertEqual(pr.rep_pr.value, int(sub["reps"].max()))
                volume = (sub["weight_kg"] * sub["reps"]).max()
                self.assertAlmostEqual(pr.volume_pr.value, float(volume), places=2)
                epley = (sub["weight_kg"] * (1 + sub["reps"] / 30)).max()
                self.assertAlmostEqual(
                    pr.estimated_1rm_pr.value, round(float(epley), 2), places=2
                )

        # Bodyweight-only exercises must not produce false PRs.
        for name, pr in prs.items():
            sub = valid[valid["exercise_title"] == name]
            if len(sub) == 0:
                self.assertIsNone(pr.weight_pr)
                self.assertIsNone(pr.volume_pr)
                self.assertIsNone(pr.estimated_1rm_pr)


if __name__ == "__main__":
    unittest.main()
