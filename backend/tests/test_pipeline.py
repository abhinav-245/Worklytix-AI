"""Phase 2 pipeline tests (stdlib unittest; run from backend/ with the venv).

    python -m unittest discover -s tests -v
"""

import csv
import os
import unittest

from fastapi.testclient import TestClient

from data.cleaner import normalize_set_type
from data.pipeline import process_csv_bytes
from data.parser import MissingColumnsError
from main import app

HEADER = (
    "title,start_time,end_time,description,exercise_title,superset_id,"
    "exercise_notes,set_index,set_type,weight_kg,reps,distance_km,"
    "duration_seconds,rpe"
)

VALID_CSV = "\n".join(
    [
        HEADER,
        '"Morning Push","12 Sep 2026, 07:00","12 Sep 2026, 08:00","",'
        '"Bench Press (Barbell)",,"",1,"normal",80,8,,,',
        '"Morning Push","12 Sep 2026, 07:00","12 Sep 2026, 08:00","",'
        '"Bench Press (Barbell)",,"",0,"warmup",60,10,,,',
        '"Morning Push","12 Sep 2026, 07:00","12 Sep 2026, 08:00","",'
        '"Overhead Press (Dumbbell)",,"",0,"normal",20,10,,,7.5',
        '"Evening Pull","13 Sep 2026, 18:00","13 Sep 2026, 19:00","",'
        '"Deadlift (Barbell)",,"",0,"dropset",100,5,,,',
        '"Evening Pull","13 Sep 2026, 18:00","13 Sep 2026, 19:00","",'
        '"Deadlift (Barbell)",,"",1,"Warm-Up",60,8,,,',
        '"Evening Pull","13 Sep 2026, 18:00","13 Sep 2026, 19:00","",'
        '"Pull Up",,,0,"my_custom_type",,10,,,',
    ]
) + "\n"

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def run(csv_text: str):
    return process_csv_bytes(csv_text.encode("utf-8"))


class TestValidCsv(unittest.TestCase):
    def test_parses_and_normalizes(self):
        res = run(VALID_CSV)
        stats = res.statistics
        self.assertEqual(stats.total_rows, 6)
        self.assertEqual(stats.valid_rows, 6)
        self.assertEqual(stats.invalid_rows, 0)
        self.assertEqual(stats.total_workouts, 2)
        self.assertEqual(stats.total_sets, 6)
        self.assertEqual(stats.total_exercises, 4)
        self.assertEqual(stats.first_workout_date, "2026-09-12T07:00:00")
        self.assertEqual(stats.last_workout_date, "2026-09-13T18:00:00")


class TestMissingColumns(unittest.TestCase):
    def test_missing_required_column_raises(self):
        bad = HEADER.replace("weight_kg,", "") + "\n"
        with self.assertRaises(MissingColumnsError) as ctx:
            run(bad)
        self.assertIn("weight_kg", ctx.exception.missing)

    def test_unexpected_columns_allowed(self):
        lines = VALID_CSV.split("\n")
        lines[0] = lines[0] + ",my_future_column"
        lines[1] = lines[1] + ",extra-value"
        res = run("\n".join(lines))
        self.assertEqual(res.statistics.valid_rows, 6)
        self.assertIn("my_future_column", res.statistics.extra_columns)
        extras = [
            s.extra.get("my_future_column")
            for w in res.workouts
            for e in w.exercises
            for s in e.sets
        ]
        self.assertIn("extra-value", extras)


class TestInvalidData(unittest.TestCase):
    def test_invalid_numeric_becomes_null_and_reported(self):
        csv_text = VALID_CSV.replace(",80,8,,,", ",abc,8,,,", 1)
        res = run(csv_text)
        bench = res.workouts[0].exercises[0]
        weights = {s.weight_kg for s in bench.sets}
        self.assertIn(None, weights)
        self.assertNotIn(0, weights)
        self.assertEqual(res.statistics.invalid_values["weight_kg"], 1)
        self.assertEqual(res.statistics.valid_rows, 6)  # row kept, value nulled

    def test_missing_numeric_becomes_null(self):
        csv_text = VALID_CSV.replace(",80,8,,,", ",,8,,,", 1)
        res = run(csv_text)
        bench = res.workouts[0].exercises[0]
        self.assertIn(None, {s.weight_kg for s in bench.sets})
        # Base fixture already has 1 empty weight (bodyweight Pull Up row).
        self.assertEqual(res.statistics.missing_values["weight_kg"], 2)

    def test_invalid_date_drops_row_without_crashing(self):
        csv_text = VALID_CSV.replace("12 Sep 2026, 07:00", "not-a-date", 1)
        res = run(csv_text)
        self.assertEqual(res.statistics.valid_rows, 5)
        self.assertEqual(res.statistics.invalid_rows, 1)
        self.assertEqual(res.statistics.invalid_values["start_time"], 1)
        reasons = res.statistics.dropped_rows[0].reasons
        self.assertTrue(any("start_time" in r for r in reasons))

    def test_missing_exercise_title_drops_row(self):
        csv_text = VALID_CSV.replace('"Bench Press (Barbell)",,"",1,', '"",,,1,', 1)
        res = run(csv_text)
        self.assertEqual(res.statistics.invalid_rows, 1)
        self.assertEqual(
            res.statistics.dropped_rows[0].reasons, ["missing exercise_title"]
        )


class TestSetTypeNormalization(unittest.TestCase):
    def test_known_mappings(self):
        cases = {
            "normal": "normal",
            "warmup": "warm_up",
            "Warm-Up": "warm_up",
            "warm up": "warm_up",
            "dropset": "drop_set",
            "drop set": "drop_set",
            "failure": "failure",
            "": "unknown",
            "my_custom_type": "unknown:my_custom_type",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_set_type(raw), expected)

    def test_pipeline_set_types(self):
        res = run(VALID_CSV)
        types = [
            s.set_type
            for w in res.workouts
            for e in w.exercises
            for s in e.sets
        ]
        self.assertIn("normal", types)
        self.assertIn("warm_up", types)
        self.assertIn("drop_set", types)
        self.assertIn("unknown:my_custom_type", types)
        self.assertNotIn("Warm-Up", types)


class TestGrouping(unittest.TestCase):
    def test_workout_exercise_grouping_and_set_order(self):
        res = run(VALID_CSV)
        self.assertEqual(len(res.workouts), 2)
        morning = res.workouts[0]
        self.assertEqual(morning.title, "Morning Push")
        self.assertEqual(
            [e.exercise_name for e in morning.exercises],
            ["Bench Press (Barbell)", "Overhead Press (Dumbbell)"],
        )
        # set_index 1 uploaded before set_index 0 -> normalized order is 0, 1.
        bench_sets = morning.exercises[0].sets
        self.assertEqual([s.set_number for s in bench_sets], [0, 1])
        self.assertEqual([s.set_type for s in bench_sets], ["warm_up", "normal"])

    def test_rpe_and_bodyweight_row(self):
        res = run(VALID_CSV)
        pullup = res.workouts[1].exercises[1]
        self.assertEqual(pullup.sets[0].reps, 10)
        self.assertIsNone(pullup.sets[0].weight_kg)


class TestUploadEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_still_works(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

    def test_upload_valid_csv(self):
        res = self.client.post(
            "/upload",
            files={"file": ("workouts.csv", VALID_CSV, "text/csv")},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["statistics"]["total_workouts"], 2)
        self.assertEqual(len(body["workouts"]), 2)

    def test_upload_missing_columns(self):
        bad = HEADER.replace("weight_kg,", "") + "\n"
        res = self.client.post(
            "/upload", files={"file": ("w.csv", bad, "text/csv")}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("weight_kg", res.json()["detail"]["message"])

    def test_upload_non_csv_rejected(self):
        res = self.client.post(
            "/upload", files={"file": ("w.txt", VALID_CSV, "text/plain")}
        )
        self.assertEqual(res.status_code, 400)

    def test_upload_malformed_csv(self):
        res = self.client.post(
            "/upload",
            files={"file": ("w.csv", 'a,b\n"unterminated', "text/csv")},
        )
        self.assertIn(res.status_code, (400, 500))
        self.assertIn("detail", res.json())


class TestRealHevyCsv(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_csv(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        res = process_csv_bytes(raw)

        with open(FIXTURE_PATH, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        sessions = {(r["title"], r["start_time"]) for r in rows}
        exercises = {r["exercise_title"] for r in rows}

        stats = res.statistics
        self.assertEqual(stats.total_rows, len(rows))
        self.assertEqual(stats.valid_rows + stats.invalid_rows, len(rows))
        self.assertEqual(stats.total_workouts, len(sessions))
        self.assertEqual(stats.total_exercises, len(exercises))
        self.assertGreater(stats.total_workouts, 100)
        self.assertLessEqual(
            stats.first_workout_date or "", stats.last_workout_date or ""
        )
        # Hierarchy spot check: sets ordered, grouped under exercises.
        for workout in res.workouts[:5]:
            self.assertTrue(workout.exercises)
            for exercise in workout.exercises:
                self.assertTrue(exercise.sets)


if __name__ == "__main__":
    unittest.main()
