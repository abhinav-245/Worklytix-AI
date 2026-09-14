"""Phase 5 progression analytics tests (stdlib unittest; run from backend/).

    python -m unittest discover -s tests -v
"""

import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.progression import (
    compute_exercise_progression,
    compute_progression,
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


def history_of(name, workouts):
    for entry in compute_progression(workouts).exercises:
        if entry.exercise_name == name:
            return entry.history
    raise AssertionError(f"no progression entry for {name!r}")


class TestWeightProgression(unittest.TestCase):
    def test_weight_values(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00",
                         {"Bench": [make_set(60, 10)]}),
            make_workout("B", "2024-06-01T07:00:00",
                         {"Bench": [make_set(62.5, 10)]}),
            make_workout("C", "2024-06-08T07:00:00",
                         {"Bench": [make_set(65, 8)]}),
        ]
        self.assertEqual(
            [p.weight_kg for p in history_of("Bench", workouts)],
            [60, 62.5, 65],
        )

    def test_max_weight_within_workout(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Bench": [make_set(60, 10), make_set(65, 6), make_set(62.5, 8)],
            }),
        ]
        history = history_of("Bench", workouts)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].weight_kg, 65)


class TestRepProgression(unittest.TestCase):
    def test_rep_values(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00",
                         {"Bench": [make_set(60, 8)]}),
            make_workout("B", "2024-06-01T07:00:00",
                         {"Bench": [make_set(60, 10)]}),
            make_workout("C", "2024-06-08T07:00:00",
                         {"Bench": [make_set(60, 12)]}),
        ]
        self.assertEqual(
            [p.reps for p in history_of("Bench", workouts)], [8, 10, 12]
        )


class TestVolumeProgression(unittest.TestCase):
    def test_total_workout_volume_not_single_set_max(self):
        # Workout 1: 60x10 + 60x8 = 1080 ; Workout 2: 65x10 + 65x8 = 1170.
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Bench": [make_set(60, 10), make_set(60, 8)],
            }),
            make_workout("B", "2024-06-01T07:00:00", {
                "Bench": [make_set(65, 10), make_set(65, 8)],
            }),
        ]
        self.assertEqual(
            [p.volume_kg for p in history_of("Bench", workouts)],
            [1080, 1170],
        )


class TestEstimated1RMProgression(unittest.TestCase):
    def test_max_epley_per_workout(self):
        # 100x5 -> 116.67 beats 90x8 -> 114.0 within the same workout.
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Bench": [make_set(90, 8), make_set(100, 5)],
            }),
        ]
        history = history_of("Bench", workouts)
        self.assertEqual(history[0].estimated_1rm_kg, 116.67)


class TestInvalidSets(unittest.TestCase):
    def test_invalid_sets_excluded(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Bench": [
                    make_set(None, 10),
                    make_set(0, 10),
                    make_set(-10, 8),
                    make_set(60, None),
                    make_set(60, 0),
                    make_set(60, -5),
                    make_set(60, 8.5),
                    make_set(60, 8),
                ],
            }),
        ]
        history = history_of("Bench", workouts)
        self.assertEqual(len(history), 1)
        point = history[0]
        self.assertEqual(point.weight_kg, 60)
        self.assertEqual(point.reps, 8)
        self.assertEqual(point.volume_kg, 480)
        self.assertEqual(point.estimated_1rm_kg, 76.0)  # 60 x 38/30

    def test_all_set_types_eligible_when_valid(self):
        for set_type in ["normal", "warm_up", "drop_set", "failure",
                         "unknown", "unknown:custom"]:
            with self.subTest(set_type=set_type):
                workouts = [
                    make_workout("A", "2024-05-24T07:00:00", {
                        "Bench": [make_set(60, 8, set_type=set_type)],
                    }),
                ]
                history = history_of("Bench", workouts)
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0].weight_kg, 60)


class TestEmptyData(unittest.TestCase):
    def test_empty_dataset(self):
        self.assertEqual(compute_progression([]).exercises, [])

    def test_exercise_without_eligible_sets_has_empty_history(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Plank": [make_set(None, None)],
                "Bench": [make_set(60, 8)],
            }),
        ]
        entries = {e.exercise_name: e
                   for e in compute_progression(workouts).exercises}
        self.assertIn("Plank", entries)
        self.assertEqual(entries["Plank"].history, [])
        self.assertEqual(len(entries["Bench"].history), 1)


class TestOrderingAndIsolation(unittest.TestCase):
    def test_out_of_order_workouts_sorted_chronologically(self):
        workouts = [
            make_workout("C", "2024-06-08T07:00:00",
                         {"Bench": [make_set(70, 8)]}),
            make_workout("A", "2024-05-24T07:00:00",
                         {"Bench": [make_set(60, 8)]}),
            make_workout("B", "2024-06-01T07:00:00",
                         {"Bench": [make_set(65, 8)]}),
        ]
        history = history_of("Bench", workouts)
        self.assertEqual([p.date for p in history],
                         ["2024-05-24", "2024-06-01", "2024-06-08"])
        self.assertEqual([p.weight_kg for p in history], [60, 65, 70])

    def test_same_day_sessions_stay_separate(self):
        workouts = [
            make_workout("AM", "2024-06-01T07:00:00",
                         {"Bench": [make_set(60, 8)]}),
            make_workout("PM", "2024-06-01T18:00:00",
                         {"Bench": [make_set(62.5, 8)]}),
        ]
        history = history_of("Bench", workouts)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].workout_start, "2024-06-01T07:00:00")
        self.assertEqual(history[1].workout_start, "2024-06-01T18:00:00")
        self.assertEqual([p.weight_kg for p in history], [60, 62.5])

    def test_exercises_never_mix(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Bench": [make_set(60, 8)],
                "Squat": [make_set(100, 5)],
            }),
            make_workout("B", "2024-06-01T07:00:00", {
                "Bench": [make_set(65, 8)],
            }),
        ]
        bench = history_of("Bench", workouts)
        squat = history_of("Squat", workouts)
        self.assertEqual([p.weight_kg for p in bench], [60, 65])
        self.assertEqual([p.weight_kg for p in squat], [100])
        self.assertEqual(len(squat), 1)

    def test_exercises_sorted_deterministically(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Squat": [make_set(100, 5)],
                "Bench": [make_set(60, 8)],
                "Deadlift": [make_set(120, 5)],
            }),
        ]
        names = [e.exercise_name
                 for e in compute_progression(workouts).exercises]
        self.assertEqual(names, ["Bench", "Deadlift", "Squat"])
        again = [e.exercise_name
                 for e in compute_progression(workouts).exercises]
        self.assertEqual(names, again)


class TestSingleExerciseFilter(unittest.TestCase):
    def test_known_exercise(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00", {
                "Bench": [make_set(60, 8)],
                "Squat": [make_set(100, 5)],
            }),
        ]
        single = compute_exercise_progression(workouts, "Squat")
        assert single is not None
        self.assertEqual(single.exercise_name, "Squat")
        self.assertEqual(len(single.history), 1)

    def test_unknown_exercise_returns_none(self):
        workouts = [
            make_workout("A", "2024-05-24T07:00:00",
                         {"Bench": [make_set(60, 8)]}),
        ]
        self.assertIsNone(compute_exercise_progression(workouts, "Nope"))


class TestProgressionApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None

    def tearDown(self):
        main._LAST_WORKOUTS = None

    def test_progression_before_upload_is_404(self):
        res = self.client.get("/analysis/progression")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_progression_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)

        res = self.client.get("/analysis/progression")
        self.assertEqual(res.status_code, 200)
        body = res.json()["data"]
        self.assertIn("exercises", body)
        names = [e["exercise_name"] for e in body["exercises"]]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(names), 117)
        bench = next(e for e in body["exercises"]
                     if e["exercise_name"] == "Bench Press (Barbell)")
        self.assertGreater(len(bench["history"]), 10)
        point = bench["history"][0]
        self.assertEqual(
            set(point),
            {"date", "workout_start", "weight_kg", "reps", "volume_kg",
             "estimated_1rm_kg"},
        )
        starts = [p["workout_start"] for p in bench["history"]]
        self.assertEqual(starts, sorted(starts))

    def test_exercise_filter(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.get(
            "/analysis/progression",
            params={"exercise_name": "Squat (Barbell)"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["data"]["exercises"]), 1)
        self.assertEqual(
            res.json()["data"]["exercises"][0]["exercise_name"], "Squat (Barbell)"
        )

    def test_unknown_exercise_filter_is_404(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.get(
            "/analysis/progression", params={"exercise_name": "Nope"}
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "unknown_exercise")

    def test_existing_endpoints_intact(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(
            self.client.get("/analysis/overview").status_code, 200
        )
        prs = self.client.get("/analysis/prs")
        self.assertEqual(prs.status_code, 200)
        self.assertEqual(len(prs.json()["data"]["exercises"]), 117)


class TestRealHevyProgression(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_dataset(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        workouts = process_csv_bytes(raw).workouts
        entries = {e.exercise_name: e
                   for e in compute_progression(workouts).exercises}

        df = pd.read_csv(FIXTURE_PATH)
        valid = df[df["weight_kg"].notna() & df["reps"].notna()]
        valid = valid[(valid["weight_kg"] > 0) & (valid["reps"] > 0)]
        valid = valid[valid["reps"].apply(
            lambda r: float(r).is_integer())].copy()
        valid["start_dt"] = pd.to_datetime(
            valid["start_time"], format="%d %b %Y, %H:%M")

        self.assertEqual(len(entries), df["exercise_title"].nunique())

        for name in ["Deadlift (Barbell)", "Bench Press (Barbell)",
                     "Squat (Barbell)"]:
            with self.subTest(exercise=name):
                sub = valid[valid["exercise_title"] == name]
                self.assertGreater(len(sub), 0)
                history = entries[name].history
                self.assertGreater(len(history), 5)

                # Independent per-workout aggregation from the raw CSV.
                grouped = sub.groupby("start_dt")
                expected = sorted(
                    (
                        ts.date().isoformat(),
                        ts.isoformat(),
                        round(float(g["weight_kg"].max()), 2),
                        int(g["reps"].max()),
                        round(float((g["weight_kg"] * g["reps"]).sum()), 2),
                        round(float(
                            (g["weight_kg"] * (1 + g["reps"] / 30)).max()), 2),
                    )
                    for ts, g in grouped
                )
                actual = [
                    (p.date, p.workout_start, p.weight_kg, p.reps,
                     p.volume_kg, p.estimated_1rm_kg)
                    for p in history
                ]
                # Compare the first 3 and last 3 observations exactly.
                self.assertEqual(actual[:3], expected[:3])
                self.assertEqual(actual[-3:], expected[-3:])
                # Full-length chronological check.
                self.assertEqual(
                    [p.workout_start for p in history],
                    sorted(p.workout_start for p in history),
                )

        # Bodyweight-only exercises get no fabricated weighted metrics.
        exercised_with_data = set(valid["exercise_title"].unique())
        for name, entry in entries.items():
            if name not in exercised_with_data:
                self.assertEqual(entry.history, [])


if __name__ == "__main__":
    unittest.main()
