"""Phase 8 exercise variety tests (stdlib unittest; run from backend/).

    python -m unittest discover -s tests -v
"""

import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.exercise_variety import compute_exercise_variety
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)

# Consecutive Mondays (ISO weeks, Jan/Feb 2026).
W1 = "2026-01-05T07:00:00"
W2 = "2026-01-12T07:00:00"
W3 = "2026-01-19T07:00:00"
W4 = "2026-01-26T07:00:00"


def make_set(set_number=0):
    return SetRecord(set_number=set_number, set_type="normal")


def make_workout(title, start, names):
    return WorkoutRecord(
        title=title,
        start_time=start,
        end_time=None,
        exercises=[
            ExerciseRecord(exercise_name=n, sets=[make_set()]) for n in names
        ],
    )


def frequency_of(name, workouts):
    for freq in compute_exercise_variety(workouts).frequencies:
        if freq.exercise_name == name:
            return freq
    raise AssertionError(f"no frequency for {name!r}")


def events_of(name, workouts):
    return [
        e for e in compute_exercise_variety(workouts).selection_events
        if e.exercise_name == name
    ]


class TestDistinctExercises(unittest.TestCase):
    def test_distinct_count_and_order(self):
        workouts = [
            make_workout("W1", W1, ["Bench Press", "Squat"]),
            make_workout("W2", W2, ["Bench Press", "Deadlift"]),
        ]
        result = compute_exercise_variety(workouts)
        self.assertEqual(result.total_workouts, 2)
        self.assertEqual(result.distinct_exercises, 3)
        self.assertEqual(
            result.exercises, ["Bench Press", "Deadlift", "Squat"]
        )


class TestExercisesPerMuscle(unittest.TestCase):
    def test_grouped_counts(self):
        # Phase 7 mapping: Bench/Chest, Cable Fly/Chest, Row/Back.
        workouts = [
            make_workout("W1", W1, [
                "Bench Press (Barbell)", "Cable Fly Crossovers"]),
            make_workout("W2", W2, [
                "Bench Press (Barbell)", "Dumbbell Row",
                "Bench Press (Dumbbell)"]),
        ]
        result = compute_exercise_variety(workouts)
        per_muscle = {m.muscle: m.exercise_count
                      for m in result.exercises_per_muscle}
        self.assertEqual(per_muscle["Chest"], 3)
        self.assertEqual(per_muscle["Back"], 1)
        self.assertEqual(
            [m.muscle for m in result.exercises_per_muscle],
            sorted(per_muscle),
        )


class TestFrequency(unittest.TestCase):
    def _ten_workouts(self):
        # Bench in 5, Squat in 2, Cable Fly in 1.
        specs = [
            ["Bench Press (Barbell)", "Squat (Barbell)"],
            ["Bench Press (Barbell)", "Squat (Barbell)"],
            ["Bench Press (Barbell)"],
            ["Bench Press (Barbell)"],
            ["Bench Press (Barbell)", "Cable Fly Crossovers"],
            ["Overhead Press (Barbell)"],
            ["Overhead Press (Dumbbell)"],
            ["Deadlift (Barbell)"],
            ["Pull Up"],
            ["Push Up"],
        ]
        return [
            make_workout(f"W{i}", f"2026-01-{5 + i * 7:02d}T07:00:00", names)
            for i, names in enumerate(specs)
        ]

    def test_percentages_use_total_workouts(self):
        workouts = self._ten_workouts()
        bench = frequency_of("Bench Press (Barbell)", workouts)
        squat = frequency_of("Squat (Barbell)", workouts)
        fly = frequency_of("Cable Fly Crossovers", workouts)
        self.assertEqual(bench.workout_occurrences, 5)
        self.assertEqual(bench.frequency_percent, 50.0)
        self.assertEqual(squat.frequency_percent, 20.0)
        self.assertEqual(fly.frequency_percent, 10.0)
        self.assertEqual(bench.muscle, "Chest")

    def test_duplicate_within_workout_counts_once(self):
        workouts = [
            make_workout("W1", W1, ["Bench Press (Barbell)"]),
        ]
        # Same exercise recorded twice in one workout (two records).
        workouts[0].exercises.append(
            ExerciseRecord(exercise_name="Bench Press (Barbell)",
                           sets=[make_set(), make_set()])
        )
        freq = frequency_of("Bench Press (Barbell)", workouts)
        self.assertEqual(freq.workout_occurrences, 1)
        self.assertEqual(freq.frequency_percent, 100.0)


class TestThresholds(unittest.TestCase):
    def test_rare_boundary(self):
        # Build 100 workouts manually (dates roll weekly into 2027; fine).
        workouts = [
            make_workout(f"W{i}", f"2026-01-05T07:00:00", ["Squat (Barbell)"])
            for i in range(100)
        ]
        for i in range(10):
            workouts[i].exercises.append(
                ExerciseRecord(exercise_name="Bench Press (Barbell)",
                               sets=[make_set()])
            )
        freq = frequency_of("Bench Press (Barbell)", workouts)
        self.assertEqual(freq.frequency_percent, 10.0)
        self.assertTrue(freq.rarely_performed)
        self.assertFalse(freq.frequently_performed)

        workouts[10].exercises.append(
            ExerciseRecord(exercise_name="Bench Press (Barbell)",
                           sets=[make_set()])
        )
        freq = frequency_of("Bench Press (Barbell)", workouts)
        self.assertEqual(freq.frequency_percent, 11.0)
        self.assertFalse(freq.rarely_performed)

    def test_frequent_boundary(self):
        workouts = [
            make_workout(f"W{i}", "2026-01-05T07:00:00", ["Squat (Barbell)"])
            for i in range(100)
        ]
        for i in range(50):
            workouts[i].exercises.append(
                ExerciseRecord(exercise_name="Bench Press (Barbell)",
                               sets=[make_set()])
            )
        freq = frequency_of("Bench Press (Barbell)", workouts)
        self.assertEqual(freq.frequency_percent, 50.0)
        self.assertTrue(freq.frequently_performed)
        self.assertFalse(freq.rarely_performed)

        workouts2 = [
            make_workout(f"W{i}", "2026-01-05T07:00:00", ["Squat (Barbell)"])
            for i in range(100)
        ]
        for i in range(49):
            workouts2[i].exercises.append(
                ExerciseRecord(exercise_name="Bench Press (Barbell)",
                               sets=[make_set()])
            )
        freq = frequency_of("Bench Press (Barbell)", workouts2)
        self.assertEqual(freq.frequency_percent, 49.0)
        self.assertFalse(freq.frequently_performed)

    def test_neither_category(self):
        workouts = [
            make_workout(f"W{i}", "2026-01-05T07:00:00", ["Squat (Barbell)"])
            for i in range(100)
        ]
        for i in range(30):
            workouts[i].exercises.append(
                ExerciseRecord(exercise_name="Bench Press (Barbell)",
                               sets=[make_set()])
            )
        freq = frequency_of("Bench Press (Barbell)", workouts)
        self.assertEqual(freq.frequency_percent, 30.0)
        self.assertFalse(freq.rarely_performed)
        self.assertFalse(freq.frequently_performed)


class TestUnmappedExercise(unittest.TestCase):
    def test_unmapped_still_counted(self):
        workouts = [
            make_workout("W1", W1, ["Mystery Move"]),
            make_workout("W2", W2, ["Bench Press (Barbell)"]),
        ]
        result = compute_exercise_variety(workouts)
        self.assertEqual(result.distinct_exercises, 2)
        self.assertIn("Mystery Move", result.exercises)
        freq = frequency_of("Mystery Move", workouts)
        self.assertIsNone(freq.muscle)
        self.assertEqual(freq.workout_occurrences, 1)
        self.assertEqual(freq.frequency_percent, 50.0)
        self.assertEqual(result.exercises_per_muscle[0].muscle, "Chest")


class TestSelectionEvents(unittest.TestCase):
    def test_introduction(self):
        workouts = [
            make_workout("W1", W1, ["Squat (Barbell)"]),
            make_workout("W2", W2, ["Bench Press (Barbell)"]),
            make_workout("W3", W3, ["Bench Press (Barbell)"]),
        ]
        events = events_of("Bench Press (Barbell)", workouts)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "introduced")
        self.assertEqual(events[0].week, "2026-W03")
        self.assertEqual(events[0].date, "2026-01-12")

    def test_disappearance(self):
        workouts = [
            make_workout("W1", W1, ["Bench Press (Barbell)"]),
            make_workout("W2", W2, ["Bench Press (Barbell)"]),
            make_workout("W3", W3, ["Squat (Barbell)"]),
        ]
        events = events_of("Bench Press (Barbell)", workouts)
        self.assertEqual(
            [(e.event_type, e.week) for e in events],
            [("introduced", "2026-W02"), ("disappeared", "2026-W04")],
        )
        self.assertEqual(events[1].date, "2026-01-19")

    def test_reappearance(self):
        workouts = [
            make_workout("W1", W1, ["Bench Press (Barbell)"]),
            make_workout("W2", W2, ["Bench Press (Barbell)"]),
            make_workout("W3", W3, ["Squat (Barbell)"]),
            make_workout("W4", W4, ["Bench Press (Barbell)"]),
        ]
        events = events_of("Bench Press (Barbell)", workouts)
        self.assertEqual(
            [(e.event_type, e.week) for e in events],
            [("introduced", "2026-W02"), ("disappeared", "2026-W04"),
             ("reappeared", "2026-W05")],
        )

    def test_training_gap_creates_no_events(self):
        workouts = [
            make_workout("W1", W1, ["Bench Press (Barbell)"]),
            # Week 2 (2026-01-12): no workouts at all.
            make_workout("W3", W3, ["Bench Press (Barbell)"]),
        ]
        events = events_of("Bench Press (Barbell)", workouts)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "introduced")

    def test_multiple_exercises_independent(self):
        workouts = [
            make_workout("W1", W1, ["Bench Press (Barbell)", "Squat (Barbell)"]),
            make_workout("W2", W2, ["Bench Press (Barbell)", "Deadlift (Barbell)"]),
            make_workout("W3", W3, ["Squat (Barbell)", "Deadlift (Barbell)"]),
        ]
        bench = [(e.event_type, e.week)
                 for e in events_of("Bench Press (Barbell)", workouts)]
        squat = [(e.event_type, e.week)
                 for e in events_of("Squat (Barbell)", workouts)]
        deadlift = [(e.event_type, e.week)
                    for e in events_of("Deadlift (Barbell)", workouts)]
        self.assertEqual(bench, [("introduced", "2026-W02"),
                                 ("disappeared", "2026-W04")])
        self.assertEqual(squat, [("introduced", "2026-W02"),
                                 ("disappeared", "2026-W03"),
                                 ("reappeared", "2026-W04")])
        self.assertEqual(deadlift, [("introduced", "2026-W03")])

    def test_multiple_sessions_one_week(self):
        workouts = [
            make_workout("Mon", "2026-01-05T07:00:00",
                         ["Bench Press (Barbell)"]),
            make_workout("Thu", "2026-01-08T18:00:00",
                         ["Bench Press (Barbell)"]),
            make_workout("W2", W2, ["Squat (Barbell)"]),
        ]
        events = events_of("Bench Press (Barbell)", workouts)
        self.assertEqual(
            [(e.event_type, e.week) for e in events],
            [("introduced", "2026-W02"), ("disappeared", "2026-W03")],
        )

    def test_year_boundary(self):
        workouts = [
            make_workout("W1", "2024-12-30T07:00:00",
                         ["Bench Press (Barbell)"]),
            make_workout("W2", "2025-01-06T07:00:00",
                         ["Squat (Barbell)"]),
            make_workout("W3", "2025-01-13T07:00:00",
                         ["Bench Press (Barbell)"]),
        ]
        events = events_of("Bench Press (Barbell)", workouts)
        # 2024-12-30 is ISO 2025-W01; 2025-01-06 is 2025-W02.
        self.assertEqual(
            [(e.event_type, e.week) for e in events],
            [("introduced", "2025-W01"), ("disappeared", "2025-W02"),
             ("reappeared", "2025-W03")],
        )


class TestEmptyDataset(unittest.TestCase):
    def test_empty(self):
        result = compute_exercise_variety([])
        self.assertEqual(result.total_workouts, 0)
        self.assertEqual(result.distinct_exercises, 0)
        self.assertEqual(result.exercises, [])
        self.assertEqual(result.frequencies, [])
        self.assertEqual(result.exercises_per_muscle, [])
        self.assertEqual(result.selection_events, [])
        summary = result.selection_summary
        self.assertEqual(summary.total_selection_events, 0)
        self.assertEqual(summary.introductions, 0)
        self.assertEqual(summary.disappearances, 0)
        self.assertEqual(summary.reappearances, 0)


class TestVarietyApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None

    def tearDown(self):
        main._LAST_WORKOUTS = None

    def test_variety_before_upload_is_404(self):
        res = self.client.get("/analysis/exercise-variety")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_variety_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)
        res = self.client.get("/analysis/exercise-variety")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(
            set(body),
            {"total_workouts", "distinct_exercises", "exercises",
             "frequencies", "exercises_per_muscle", "selection_events",
             "selection_summary"},
        )
        self.assertEqual(body["total_workouts"], 538)
        self.assertEqual(body["distinct_exercises"], 117)
        names = [f["exercise_name"] for f in body["frequencies"]]
        self.assertEqual(names, sorted(names))
        muscles = [m["muscle"] for m in body["exercises_per_muscle"]]
        self.assertEqual(muscles, sorted(muscles))

    def test_exercise_filter(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.get(
            "/analysis/exercise-variety",
            params={"exercise_name": "Bench Press (Barbell)"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["distinct_exercises"], 1)
        self.assertEqual(len(body["frequencies"]), 1)
        self.assertEqual(
            body["frequencies"][0]["exercise_name"], "Bench Press (Barbell)"
        )
        # Global denominator retained for the filtered exercise.
        self.assertEqual(body["total_workouts"], 538)

    def test_unknown_exercise_filter_is_404(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.get(
            "/analysis/exercise-variety", params={"exercise_name": "Nope"}
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "unknown_exercise")

    def test_existing_endpoints_intact(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        for path in ["/health", "/analysis/overview", "/analysis/prs",
                     "/analysis/progression", "/analysis/plateaus",
                     "/analysis/muscles"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


class TestRealHevyVariety(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_dataset(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        workouts = process_csv_bytes(raw).workouts
        from analytics.exercise_variety import compute_exercise_variety

        result = compute_exercise_variety(workouts)
        self.assertEqual(result.total_workouts, 538)
        self.assertEqual(result.distinct_exercises, 117)

        df = pd.read_csv(FIXTURE_PATH)
        df["workout_key"] = df["title"] + "|" + df["start_time"]

        # Distinct names match the raw CSV exactly.
        self.assertEqual(set(result.exercises),
                         set(df["exercise_title"].unique()))

        # Frequency cross-check for several exercises.
        freqs = {f.exercise_name: f for f in result.frequencies}
        for name in ["Lat Pulldown (Cable)", "Bench Press (Barbell)",
                     "Squat (Barbell)", "Treadmill", "Deadlift (Barbell)"]:
            with self.subTest(exercise=name):
                expected_occ = df[df["exercise_title"] == name][
                    "workout_key"].nunique()
                freq = freqs[name]
                self.assertEqual(freq.workout_occurrences, expected_occ)
                self.assertAlmostEqual(
                    freq.frequency_percent,
                    round(expected_occ / 538 * 100, 2),
                    places=2,
                )

        # Exercises per muscle cross-check for several muscles.
        from mappings.exercise_muscles import EXERCISE_PRIMARY_MUSCLE

        mapped_names = {n for n in result.exercises
                        if n in EXERCISE_PRIMARY_MUSCLE}
        for muscle in ["Chest", "Back", "Quadriceps", "Shoulders", "Biceps"]:
            with self.subTest(muscle=muscle):
                expected = sum(
                    1 for n in mapped_names
                    if EXERCISE_PRIMARY_MUSCLE[n] == muscle
                )
                actual = next(
                    m.exercise_count for m in result.exercises_per_muscle
                    if m.muscle == muscle
                )
                self.assertEqual(actual, expected)

        # Selection events: validate one exercise end-to-end from raw CSV.
        # Presence per training week, derived independently via pandas.
        df["start_dt"] = pd.to_datetime(
            df["start_time"], format="%d %b %Y, %H:%M")
        df["iso"] = list(zip(
            df["start_dt"].dt.isocalendar().year.astype(int),
            df["start_dt"].dt.isocalendar().week.astype(int),
        ))
        name = "Cable Fly Crossovers"
        present = set(df[df["exercise_title"] == name]["iso"])
        actual_events = [
            e for e in result.selection_events
            if e.exercise_name == name
        ]
        self.assertGreater(len(actual_events), 2)
        # Alternation invariant: introduced once, then strict
        # disappeared/reappeared alternation.
        self.assertEqual(actual_events[0].event_type, "introduced")
        self.assertEqual(
            sum(1 for e in actual_events if e.event_type == "introduced"), 1
        )
        rest = [e.event_type for e in actual_events[1:]]
        for i, event_type in enumerate(rest):
            expected_type = ("disappeared" if i % 2 == 0 else "reappeared")
            self.assertEqual(event_type, expected_type)
        # First event week matches the raw earliest presence week.
        first_week = min(present)
        self.assertEqual(
            actual_events[0].week, f"{first_week[0]}-W{first_week[1]:02d}"
        )

        # Threshold behavior on the real dataset.
        rare = [f for f in result.frequencies if f.rarely_performed]
        frequent = [f for f in result.frequencies if f.frequently_performed]
        neither = [f for f in result.frequencies
                   if not f.rarely_performed and not f.frequently_performed]
        self.assertEqual(len(rare) + len(neither) + len(frequent),
                         len(result.frequencies))
        for freq in rare:
            self.assertLessEqual(freq.frequency_percent, 10.0)
        for freq in frequent:
            self.assertGreaterEqual(freq.frequency_percent, 50.0)


if __name__ == "__main__":
    unittest.main()
