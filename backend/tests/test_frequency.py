"""Phase 11 dashboard-support API tests (stdlib unittest).

Run from backend/ with the venv::

    python -m unittest discover -s tests -v

Covers the training-frequency time series (new in Phase 11) and the
profile read endpoint. All values are deterministic derivations of the
normalized workout model; no analytics logic is duplicated here.
"""

import os
import unittest

from fastapi.testclient import TestClient

import main
from analytics.frequency import compute_training_frequency
from data.models import ExerciseRecord, SetRecord, WorkoutRecord

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def make_workout(title, start):
    return WorkoutRecord(
        title=title,
        start_time=start,
        end_time=None,
        exercises=[
            ExerciseRecord(
                exercise_name="Bench Press (Barbell)",
                sets=[SetRecord(set_number=0, set_type="normal")],
            )
        ],
    )


class TestTrainingFrequency(unittest.TestCase):
    def test_empty_dataset(self):
        self.assertEqual(compute_training_frequency([]).weeks, [])

    def test_single_workout_single_bucket(self):
        weeks = compute_training_frequency(
            [make_workout("W1", "2026-01-05T07:00:00")]
        ).weeks
        self.assertEqual(len(weeks), 1)
        self.assertEqual(weeks[0].week, "2026-W02")
        self.assertEqual(weeks[0].week_start, "2026-01-05")
        self.assertEqual(weeks[0].workouts, 1)

    def test_gaps_become_zero_buckets(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00"),
            make_workout("W2", "2026-01-05T18:00:00"),
            make_workout("W3", "2026-01-19T07:00:00"),
        ]
        weeks = compute_training_frequency(workouts).weeks
        self.assertEqual(
            [(w.week, w.workouts) for w in weeks],
            [("2026-W02", 2), ("2026-W03", 0), ("2026-W04", 1)],
        )

    def test_iso_year_boundary(self):
        workouts = [
            make_workout("W1", "2024-12-30T07:00:00"),  # Monday, ISO 2025-W01
            make_workout("W2", "2025-01-06T07:00:00"),  # Monday, ISO 2025-W02
        ]
        weeks = compute_training_frequency(workouts).weeks
        self.assertEqual(
            [(w.week, w.week_start, w.workouts) for w in weeks],
            [
                ("2025-W01", "2024-12-30", 1),
                ("2025-W02", "2025-01-06", 1),
            ],
        )

    def test_continuous_and_chronological(self):
        workouts = [
            make_workout("W2", "2026-02-09T07:00:00"),
            make_workout("W1", "2026-01-05T07:00:00"),
        ]
        weeks = compute_training_frequency(workouts).weeks
        starts = [w.week_start for w in weeks]
        self.assertEqual(starts, sorted(starts))
        # 2026-01-05 .. 2026-02-09 spans 6 ISO weeks.
        self.assertEqual(len(weeks), 6)
        self.assertEqual(sum(w.workouts for w in weeks), 2)


class TestFrequencyApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def test_frequency_before_upload_is_404(self):
        res = self.client.get("/analysis/frequency")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_frequency_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)
        res = self.client.get("/analysis/frequency")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(set(body), {"success", "data", "meta"})
        self.assertTrue(body["success"])
        self.assertEqual(body["meta"], {"analysis_version": "v1"})
        weeks = body["data"]["weeks"]
        self.assertGreater(len(weeks), 100)
        self.assertEqual(
            sum(w["workouts"] for w in weeks), 538
        )
        starts = [w["week_start"] for w in weeks]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(set(weeks[0]), {"week", "week_start", "workouts"})


class TestProfileReadApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def test_profile_before_submit_is_404(self):
        res = self.client.get("/analysis/profile")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_profile")

    def test_profile_without_dataset_has_null_history(self):
        submit = self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        self.assertEqual(submit.status_code, 200)
        res = self.client.get("/analysis/profile")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["meta"], {"analysis_version": "v1"})
        self.assertEqual(body["data"]["profile"]["age"], 25)
        self.assertIsNone(body["data"]["training_history"])

    def test_profile_with_dataset_has_history(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        res = self.client.get("/analysis/profile")
        self.assertEqual(res.status_code, 200)
        history = res.json()["data"]["training_history"]
        self.assertEqual(history["duration_days"], 841)
        self.assertEqual(history["level"], "Intermediate")


if __name__ == "__main__":
    unittest.main()
