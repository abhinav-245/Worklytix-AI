"""Phase 3 overview analytics tests (stdlib unittest; run from backend/ with the venv).

    python -m unittest discover -s tests -v
"""

import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.overview import compute_overview
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)


def make_set(set_type="normal", **kwargs):
    params = {"set_number": 0, "set_type": set_type}
    params.update(kwargs)
    return SetRecord(**params)


def make_workout(title, start, end=None, exercises=None):
    return WorkoutRecord(
        title=title,
        start_time=start,
        end_time=end,
        exercises=exercises or [],
    )


def make_exercise(name, set_types):
    return ExerciseRecord(
        exercise_name=name,
        sets=[make_set(set_type=t, set_number=i) for i, t in enumerate(set_types)],
    )


class TestEmptyDataset(unittest.TestCase):
    def test_empty(self):
        ov = compute_overview([])
        self.assertEqual(ov.total_workouts, 0)
        self.assertEqual(ov.total_exercises, 0)
        self.assertEqual(ov.total_sets, 0)
        self.assertEqual(ov.working_sets, 0)
        self.assertEqual(ov.warmup_sets, 0)
        self.assertEqual(ov.dropsets, 0)
        self.assertEqual(ov.failure_sets, 0)
        self.assertEqual(ov.total_volume_kg, 0.0)
        self.assertIsNone(ov.first_workout_date)
        self.assertIsNone(ov.last_workout_date)
        self.assertIsNone(ov.training_period_days)
        self.assertIsNone(ov.average_workout_duration_minutes)
        self.assertIsNone(ov.workouts_per_week)
        self.assertIsNone(ov.training_consistency)


class TestSingleWorkout(unittest.TestCase):
    def test_single_workout(self):
        workouts = [
            make_workout(
                "Push",
                "2026-09-07T07:00:00",
                "2026-09-07T08:00:00",
                [make_exercise("Bench Press", ["normal", "normal", "warm_up"])],
            )
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.total_workouts, 1)
        self.assertEqual(ov.first_workout_date, "2026-09-07T07:00:00")
        self.assertEqual(ov.last_workout_date, "2026-09-07T07:00:00")
        self.assertEqual(ov.training_period_days, 0)
        self.assertEqual(ov.total_exercises, 1)
        self.assertEqual(ov.total_sets, 3)
        self.assertEqual(ov.working_sets, 2)
        self.assertEqual(ov.warmup_sets, 1)
        self.assertEqual(ov.average_workout_duration_minutes, 60.0)
        self.assertIsNone(ov.workouts_per_week)  # zero-day period: no division
        self.assertEqual(ov.training_consistency, 100.0)


class TestTotalVolume(unittest.TestCase):
    def _workout_with_sets(self, title, start, set_specs):
        return WorkoutRecord(
            title=title,
            start_time=start,
            end_time=None,
            exercises=[
                ExerciseRecord(
                    exercise_name="Bench Press",
                    sets=[
                        SetRecord(
                            set_number=i,
                            set_type="normal",
                            weight_kg=w,
                            reps=r,
                        )
                        for i, (w, r) in enumerate(set_specs)
                    ],
                )
            ],
        )

    def test_sums_valid_set_volumes(self):
        workouts = [
            self._workout_with_sets("A", "2026-09-01T07:00:00",
                                    [(60, 10), (60, 8)]),
            self._workout_with_sets("B", "2026-09-08T07:00:00",
                                    [(65, 10), (65, 8)]),
        ]
        ov = compute_overview(workouts)
        # (60x10 + 60x8) + (65x10 + 65x8) = 1080 + 1170.
        self.assertEqual(ov.total_volume_kg, 2250.0)

    def test_invalid_sets_excluded_never_zero_filled(self):
        workouts = [
            self._workout_with_sets("A", "2026-09-01T07:00:00",
                                    [(None, 10), (0, 8), (60, None),
                                     (60, 0), (60, 8.5), (60, 8)]),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.total_volume_kg, 480.0)

    def test_matches_progression_volume_sum(self):
        from analytics.progression import compute_progression

        workouts = [
            self._workout_with_sets("A", "2026-09-01T07:00:00",
                                    [(80, 8), (90, 6)]),
            self._workout_with_sets("B", "2026-09-08T07:00:00",
                                    [(82.5, 5)]),
        ]
        ov = compute_overview(workouts)
        prog = compute_progression(workouts)
        expected = round(
            sum(p.volume_kg for e in prog.exercises for p in e.history), 2
        )
        self.assertEqual(ov.total_volume_kg, expected)
        self.assertEqual(ov.total_volume_kg, 80 * 8 + 90 * 6 + 82.5 * 5)


class TestMultipleWorkouts(unittest.TestCase):
    def test_counts_and_period(self):
        workouts = [
            make_workout("A", "2026-09-01T07:00:00", "2026-09-01T08:00:00",
                         [make_exercise("Squat", ["normal"])]),
            make_workout("B", "2026-09-08T07:00:00", "2026-09-08T07:30:00",
                         [make_exercise("Squat", ["normal"]),
                          make_exercise("Deadlift", ["normal"])]),
            make_workout("C", "2026-09-15T07:00:00", "2026-09-15T08:30:00",
                         [make_exercise("Bench Press", ["normal"])]),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.total_workouts, 3)
        self.assertEqual(ov.training_period_days, 14)
        self.assertEqual(ov.total_sets, 4)
        # 3 workouts / (14 days / 7) = 1.5 per week.
        self.assertEqual(ov.workouts_per_week, 1.5)
        # Weeks of Sep 1, Sep 8, Sep 15 all active -> 3/3.
        self.assertEqual(ov.training_consistency, 100.0)


class TestDistinctExercises(unittest.TestCase):
    def test_repeated_exercises_counted_once(self):
        ex = lambda n: make_exercise(n, ["normal"])  # noqa: E731
        workouts = [
            make_workout("A", "2026-09-01T07:00:00", None, [ex("Bench"), ex("Squat")]),
            make_workout("B", "2026-09-02T07:00:00", None,
                         [ex("Bench"), ex("Squat"), ex("Deadlift")]),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.total_exercises, 3)
        self.assertEqual(ov.total_sets, 5)


class TestSetTypes(unittest.TestCase):
    def test_all_types_accounted(self):
        workouts = [
            make_workout(
                "A",
                "2026-09-01T07:00:00",
                None,
                [make_exercise("Mix", [
                    "normal", "normal", "warm_up", "drop_set",
                    "failure", "unknown", "unknown:super_set",
                ])],
            )
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.total_sets, 7)
        self.assertEqual(ov.working_sets, 2)
        self.assertEqual(ov.warmup_sets, 1)
        self.assertEqual(ov.dropsets, 1)
        self.assertEqual(ov.failure_sets, 1)
        self.assertEqual(ov.other_sets, 2)
        self.assertEqual(
            ov.working_sets + ov.warmup_sets + ov.dropsets
            + ov.failure_sets + ov.other_sets,
            ov.total_sets,
        )


class TestDurations(unittest.TestCase):
    def test_average_of_valid_durations(self):
        workouts = [
            make_workout("A", "2026-09-01T07:00:00", "2026-09-01T08:00:00"),
            make_workout("B", "2026-09-02T07:00:00", "2026-09-02T08:30:00"),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.average_workout_duration_minutes, 75.0)

    def test_missing_end_time_excluded_not_zero(self):
        workouts = [
            make_workout("A", "2026-09-01T07:00:00", "2026-09-01T08:00:00"),
            make_workout("B", "2026-09-02T07:00:00", None),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.average_workout_duration_minutes, 60.0)

    def test_end_before_start_excluded(self):
        workouts = [
            make_workout("A", "2026-09-01T07:00:00", "2026-09-01T08:00:00"),
            make_workout("B", "2026-09-02T09:00:00", "2026-09-02T08:00:00"),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.average_workout_duration_minutes, 60.0)

    def test_no_valid_durations_is_null(self):
        workouts = [make_workout("A", "2026-09-01T07:00:00", None)]
        ov = compute_overview(workouts)
        self.assertIsNone(ov.average_workout_duration_minutes)


class TestConsistency(unittest.TestCase):
    def test_gap_week_lowers_consistency(self):
        # Active in weeks of Sep 7 and Sep 21, idle in week of Sep 14.
        workouts = [
            make_workout("A", "2026-09-07T07:00:00", None),
            make_workout("B", "2026-09-21T07:00:00", None),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.training_consistency, 66.7)

    def test_year_boundary_weeks(self):
        # 2025-12-29 (Mon) is ISO 2026-W01; 2026-01-12 (Mon) is ISO 2026-W03.
        # Span covers W01..W03, active in W01 and W03.
        workouts = [
            make_workout("A", "2025-12-29T07:00:00", None),
            make_workout("B", "2026-01-12T07:00:00", None),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.training_period_days, 14)
        self.assertEqual(ov.training_consistency, 66.7)

    def test_same_iso_week_across_new_year(self):
        # 2024-12-30 (Mon) and 2025-01-05 (Sun) share ISO week 2025-W01.
        workouts = [
            make_workout("A", "2024-12-30T07:00:00", None),
            make_workout("B", "2025-01-05T07:00:00", None),
        ]
        ov = compute_overview(workouts)
        self.assertEqual(ov.training_period_days, 6)
        self.assertEqual(ov.training_consistency, 100.0)


class TestDeterminism(unittest.TestCase):
    def test_repeated_runs_agree(self):
        with open(FIXTURE_PATH, "rb") as f:
            workouts = process_csv_bytes(f.read()).workouts
        first = compute_overview(workouts).model_dump()
        second = compute_overview(workouts).model_dump()
        self.assertEqual(first, second)


class TestOverviewApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None

    def tearDown(self):
        main._LAST_WORKOUTS = None

    def test_overview_before_upload_is_404(self):
        res = self.client.get("/analysis/overview")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_upload_returns_overview_and_endpoint_matches(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)
        self.assertIn("overview", upload.json())
        self.assertEqual(upload.json()["overview"]["total_workouts"], 538)

        res = self.client.get("/analysis/overview")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"], upload.json()["overview"])


class TestRealHevyOverview(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_dataset(self):
        with open(FIXTURE_PATH, "rb") as f:
            result = process_csv_bytes(f.read())
        ov = compute_overview(result.workouts)
        stats = result.statistics

        # Reconcile against the Phase 2 normalized dataset (not hard-coded).
        self.assertEqual(ov.total_workouts, stats.total_workouts)
        self.assertEqual(ov.total_sets, stats.total_sets)
        self.assertEqual(ov.total_exercises, stats.total_exercises)
        self.assertEqual(ov.first_workout_date, stats.first_workout_date)
        self.assertEqual(ov.last_workout_date, stats.last_workout_date)
        self.assertEqual(
            ov.working_sets + ov.warmup_sets + ov.dropsets
            + ov.failure_sets + ov.other_sets,
            ov.total_sets,
        )

        # Independent pandas cross-check (raw CSV, not the normalized model).
        df = pd.read_csv(FIXTURE_PATH)
        self.assertEqual(ov.working_sets, int((df["set_type"] == "normal").sum()))
        self.assertEqual(ov.warmup_sets, int((df["set_type"] == "warmup").sum()))
        self.assertEqual(ov.dropsets, int((df["set_type"] == "dropset").sum()))
        self.assertEqual(ov.failure_sets, int((df["set_type"] == "failure").sum()))
        sessions = df.groupby(["title", "start_time"])["end_time"].first().reset_index()
        starts = pd.to_datetime(sessions["start_time"], format="%d %b %Y, %H:%M")
        ends = pd.to_datetime(sessions["end_time"], format="%d %b %Y, %H:%M")
        expected_avg = ((ends - starts).dt.total_seconds() / 60).mean()
        assert ov.average_workout_duration_minutes is not None
        self.assertAlmostEqual(
            ov.average_workout_duration_minutes, expected_avg, places=1
        )

        # Sane ranges for the derived metrics.
        assert ov.workouts_per_week is not None
        assert ov.training_consistency is not None
        self.assertGreater(ov.training_period_days or 0, 100)
        self.assertGreater(ov.workouts_per_week, 0)
        self.assertLessEqual(ov.workouts_per_week, 14)
        self.assertGreaterEqual(ov.training_consistency, 0)
        self.assertLessEqual(ov.training_consistency, 100)
        self.assertGreater(ov.average_workout_duration_minutes, 0)
        self.assertLess(ov.average_workout_duration_minutes, 24 * 60)


if __name__ == "__main__":
    unittest.main()
