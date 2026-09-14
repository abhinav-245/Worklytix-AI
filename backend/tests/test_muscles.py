"""Phase 7 muscle mapping/analytics tests (stdlib unittest; run from backend/).

    python -m unittest discover -s tests -v
"""

import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.muscles import compute_muscles
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes
from mappings.exercise_muscles import (
    PRIMARY_MUSCLES,
    get_primary_muscle,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def make_set(set_type="normal", set_number=0):
    return SetRecord(set_number=set_number, set_type=set_type)


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


def sets(n, set_type="normal"):
    return [make_set(set_type=set_type, set_number=i) for i in range(n)]


def summary_of(muscle, workouts):
    for summary in compute_muscles(workouts).muscles:
        if summary.muscle == muscle:
            return summary
    raise AssertionError(f"no summary for {muscle!r}")


class TestMapping(unittest.TestCase):
    def test_known_exercise(self):
        self.assertEqual(
            get_primary_muscle("Bench Press (Barbell)"), "Chest"
        )

    def test_unknown_exercise_returns_none(self):
        self.assertIsNone(
            get_primary_muscle("Some Completely Unknown Exercise")
        )

    def test_exact_matching(self):
        self.assertIsNone(get_primary_muscle("bench press (barbell)"))
        self.assertIsNone(get_primary_muscle("Bench Press"))
        self.assertIsNone(get_primary_muscle(""))
        self.assertIsNone(get_primary_muscle(None))  # type: ignore[arg-type]

    def test_canonical_values_only(self):
        from mappings.exercise_muscles import EXERCISE_PRIMARY_MUSCLE

        for name, muscle in EXERCISE_PRIMARY_MUSCLE.items():
            with self.subTest(exercise=name):
                self.assertIn(muscle, PRIMARY_MUSCLES)


class TestMappingCoverage(unittest.TestCase):
    def test_controlled_coverage(self):
        workouts = [
            make_workout("A", "2026-01-05T07:00:00", {
                "Bench Press (Barbell)": sets(1),
                "Squat (Barbell)": sets(1),
                "Deadlift (Barbell)": sets(1),
                "Mystery Move": sets(1),
            }),
        ]
        mapping = compute_muscles(workouts).mapping
        self.assertEqual(mapping.total_exercises, 4)
        self.assertEqual(mapping.mapped_exercises, 3)
        self.assertEqual(mapping.unmapped_exercises, 1)
        self.assertEqual(mapping.coverage_percent, 75.0)


class TestSetsPerMuscle(unittest.TestCase):
    def test_controlled_sets(self):
        # W1: Bench 3 + Cable Fly 2 (Chest); W2: Bench 4 (Chest), Squat 3 (Quads).
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench Press (Barbell)": sets(3),
                "Cable Fly Crossovers": sets(2),
            }),
            make_workout("W2", "2026-01-12T07:00:00", {
                "Bench Press (Barbell)": sets(4),
                "Squat (Barbell)": sets(3),
            }),
        ]
        self.assertEqual(summary_of("Chest", workouts).total_sets, 9)
        self.assertEqual(summary_of("Quadriceps", workouts).total_sets, 3)


class TestTrainingFrequency(unittest.TestCase):
    def test_sessions_count_distinct_workouts(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench Press (Barbell)": sets(2),
            }),
            make_workout("W2", "2026-01-12T07:00:00", {
                # Several chest exercises still count as ONE chest session.
                "Bench Press (Barbell)": sets(2),
                "Cable Fly Crossovers": sets(2),
                "Squat (Barbell)": sets(2),
            }),
            make_workout("W3", "2026-01-19T07:00:00", {
                "Bench Press (Barbell)": sets(2),
            }),
        ]
        self.assertEqual(summary_of("Chest", workouts).training_sessions, 3)
        self.assertEqual(
            summary_of("Quadriceps", workouts).training_sessions, 1
        )

    def test_multiple_sessions(self):
        workouts = [
            make_workout("A", "2026-01-05T07:00:00",
                         {"Bench Press (Barbell)": sets(5)}),
            make_workout("B", "2026-01-12T07:00:00",
                         {"Bench Press (Barbell)": sets(3)}),
        ]
        chest = summary_of("Chest", workouts)
        self.assertEqual(chest.training_sessions, 2)
        self.assertEqual(chest.total_sets, 8)


class TestExerciseVariety(unittest.TestCase):
    def test_distinct_exercises(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench Press (Barbell)": sets(2),
                "Cable Fly Crossovers": sets(2),
            }),
            make_workout("W2", "2026-01-12T07:00:00", {
                "Bench Press (Barbell)": sets(2),
                "Chest Press (Machine)": sets(2),
            }),
        ]
        self.assertEqual(summary_of("Chest", workouts).exercise_variety, 3)

    def test_repeated_exercise_in_one_workout(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench Press (Barbell)": sets(5) + sets(3),
            }),
        ]
        chest = summary_of("Chest", workouts)
        self.assertEqual(chest.total_sets, 8)
        self.assertEqual(chest.exercise_variety, 1)
        self.assertEqual(chest.training_sessions, 1)


class TestPotentiallyNeglected(unittest.TestCase):
    def test_zero_sets_means_potentially_neglected(self):
        from mappings.exercise_muscles import PRIMARY_MUSCLES as canonical

        self.assertIn("Calves", canonical)
        self.assertIn("Quadriceps", canonical)
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench Press (Barbell)": sets(2),
                "Bent Over Row (Barbell)": sets(2),
            }),
        ]
        chest = summary_of("Chest", workouts)
        back = summary_of("Back", workouts)
        quads = summary_of("Quadriceps", workouts)
        calves = summary_of("Calves", workouts)
        self.assertFalse(chest.potentially_neglected)
        self.assertFalse(back.potentially_neglected)
        self.assertTrue(quads.potentially_neglected)
        self.assertTrue(calves.potentially_neglected)

    def test_unmapped_is_not_neglected(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Mystery Move": sets(10),
            }),
        ]
        response = compute_muscles(workouts)
        self.assertIn("Mystery Move", response.unmapped_exercises)
        # Every muscle still has zero sets here (Mystery Move maps nowhere),
        # but no *inferred* muscle may be blamed on the unknown exercise:
        # the mapping table simply has no entry for it.
        self.assertIsNone(get_primary_muscle("Mystery Move"))
        for summary in response.muscles:
            if summary.total_sets == 0:
                self.assertTrue(summary.potentially_neglected)


class TestSetTypes(unittest.TestCase):
    def test_all_set_types_count(self):
        workout = make_workout("W1", "2026-01-05T07:00:00", {
            "Bench Press (Barbell)": [
                make_set("normal"),
                make_set("warm_up"),
                make_set("drop_set"),
                make_set("failure"),
                make_set("unknown"),
            ],
        })
        self.assertEqual(summary_of("Chest", [workout]).total_sets, 5)


class TestEmptyDataset(unittest.TestCase):
    def test_empty(self):
        response = compute_muscles([])
        self.assertEqual(len(response.muscles), len(PRIMARY_MUSCLES))
        for summary in response.muscles:
            self.assertEqual(summary.total_sets, 0)
            self.assertEqual(summary.training_sessions, 0)
            self.assertEqual(summary.exercise_variety, 0)
            self.assertIsNone(summary.average_sessions_per_week)
            self.assertTrue(summary.potentially_neglected)
        self.assertEqual(response.mapping.total_exercises, 0)
        self.assertEqual(response.unmapped_exercises, [])


class TestMuscleApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None

    def tearDown(self):
        main._LAST_WORKOUTS = None

    def test_muscles_before_upload_is_404(self):
        res = self.client.get("/analysis/muscles")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_muscles_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)
        res = self.client.get("/analysis/muscles")
        self.assertEqual(res.status_code, 200)
        body = res.json()["data"]
        self.assertEqual(
            set(body),
            {"muscles", "mapping", "unmapped_exercises"},
        )
        muscles = {m["muscle"]: m for m in body["muscles"]}
        self.assertEqual(set(muscles), set(PRIMARY_MUSCLES))
        chest = muscles["Chest"]
        self.assertEqual(
            set(chest),
            {"muscle", "total_sets", "training_sessions",
             "exercise_variety", "average_sessions_per_week",
             "potentially_neglected"},
        )
        self.assertGreater(chest["total_sets"], 0)
        self.assertFalse(chest["potentially_neglected"])
        self.assertEqual(
            body["mapping"]["total_exercises"], 117
        )

    def test_existing_endpoints_intact(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        for path in ["/health", "/analysis/overview", "/analysis/prs",
                     "/analysis/progression", "/analysis/plateaus"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


class TestRealHevyMuscles(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_dataset(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        workouts = process_csv_bytes(raw).workouts
        response = compute_muscles(workouts)

        self.assertEqual(response.mapping.total_exercises, 117)
        self.assertEqual(response.mapping.mapped_exercises, 113)
        self.assertEqual(response.mapping.unmapped_exercises, 4)
        self.assertAlmostEqual(response.mapping.coverage_percent, 96.58,
                               places=2)
        self.assertEqual(
            response.unmapped_exercises,
            ["Elliptical Trainer", "Spinning", "Treadmill", "Walking"],
        )

        df = pd.read_csv(FIXTURE_PATH)
        from mappings.exercise_muscles import EXERCISE_PRIMARY_MUSCLE

        df["muscle"] = df["exercise_title"].map(EXERCISE_PRIMARY_MUSCLE)
        df["start_key"] = df["title"] + "|" + df["start_time"]

        for muscle in ["Chest", "Back", "Quadriceps", "Hamstrings",
                       "Shoulders"]:
            with self.subTest(muscle=muscle):
                sub = df[df["muscle"] == muscle]
                summary = summary_of(muscle, workouts)
                # Total sets: every normalized row of a mapped exercise.
                self.assertEqual(summary.total_sets, len(sub))
                # Sessions: distinct workout occurrences with the muscle.
                self.assertEqual(summary.training_sessions,
                                 sub["start_key"].nunique())
                # Variety: distinct mapped exercise names present.
                self.assertEqual(summary.exercise_variety,
                                 sub["exercise_title"].nunique())

        # Mapped-set accounting: every non-cardio row lands in exactly
        # one muscle total.
        mapped_rows = df[df["muscle"].notna()]
        self.assertEqual(
            sum(m.total_sets for m in response.muscles), len(mapped_rows)
        )
        # Neglected rule: zero mapped sets <-> potentially neglected.
        for summary in response.muscles:
            self.assertEqual(summary.potentially_neglected,
                             summary.total_sets == 0)


if __name__ == "__main__":
    unittest.main()
