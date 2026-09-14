"""Phase 10 standardized analytics API tests (stdlib unittest).

Run from backend/ with the venv::

    python -m unittest discover -s tests -v

Covers the ``{"success", "data", "meta"}`` envelope on every analytics
endpoint, the new volume and profile endpoints, and Hevy regression
values proving Phase 2-9 calculations are unchanged.
"""

import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.progression import compute_progression
from analytics.volume import compute_exercise_volume, compute_volume
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)

ANALYTICS_PATHS = [
    "/analysis/overview",
    "/analysis/prs",
    "/analysis/progression",
    "/analysis/volume",
    "/analysis/plateaus",
    "/analysis/muscles",
    "/analysis/exercise-variety",
]


def make_set(weight=None, reps=None, set_number=0):
    return SetRecord(
        set_number=set_number, set_type="normal",
        weight_kg=weight, reps=reps,
    )


def make_workout(title, start, sets_by_exercise):
    return WorkoutRecord(
        title=title,
        start_time=start,
        end_time=None,
        exercises=[
            ExerciseRecord(exercise_name=name, sets=sets)
            for name, sets in sets_by_exercise.items()
        ],
    )


def upload_fixture(client):
    with open(FIXTURE_PATH, "rb") as f:
        raw = f.read()
    res = client.post(
        "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
    )
    assert res.status_code == 200
    return raw


class TestEnvelopeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def test_missing_dataset_is_404_for_all_analytics(self):
        for path in ANALYTICS_PATHS:
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 404)
                self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_envelope_shape_on_every_endpoint(self):
        upload_fixture(self.client)
        expected_data_keys = {
            "/analysis/overview": {
                "total_workouts", "training_period_days",
                "first_workout_date", "last_workout_date",
                "total_exercises", "total_sets", "working_sets",
                "warmup_sets", "dropsets", "failure_sets", "other_sets",
                "average_workout_duration_minutes", "workouts_per_week",
                "training_consistency", "total_volume_kg",
            },
            "/analysis/prs": {"exercises"},
            "/analysis/progression": {"exercises"},
            "/analysis/volume": {"exercises"},
            "/analysis/plateaus": {"plateaus"},
            "/analysis/muscles": {"muscles", "mapping", "unmapped_exercises"},
            "/analysis/exercise-variety": {
                "total_workouts", "distinct_exercises", "exercises",
                "frequencies", "exercises_per_muscle", "selection_events",
                "selection_summary",
            },
        }
        for path in ANALYTICS_PATHS:
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 200)
                body = res.json()
                self.assertEqual(set(body), {"success", "data", "meta"})
                self.assertTrue(body["success"])
                self.assertEqual(
                    body["meta"], {"analysis_version": "v1"}
                )
                self.assertEqual(set(body["data"]), expected_data_keys[path])

    def test_profile_endpoint_contract(self):
        # No profile submitted yet.
        res = self.client.get("/analysis/profile")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_profile")

        # Profile without a dataset: valid profile, null history.
        self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        res = self.client.get("/analysis/profile")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["meta"], {"analysis_version": "v1"})
        self.assertEqual(
            body["data"]["profile"],
            {"age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain"},
        )
        self.assertIsNone(body["data"]["training_history"])

        # After upload the same endpoint gains training history.
        upload_fixture(self.client)
        res = self.client.get("/analysis/profile")
        self.assertEqual(res.status_code, 200)
        history = res.json()["data"]["training_history"]
        self.assertEqual(history["duration_days"], 841)
        self.assertEqual(history["level"], "Intermediate")

    def test_openapi_documents_all_endpoints(self):
        res = self.client.get("/openapi.json")
        self.assertEqual(res.status_code, 200)
        paths = res.json()["paths"]
        for path in ANALYTICS_PATHS + [
            "/health", "/upload", "/profile", "/analysis/profile",
        ]:
            with self.subTest(path=path):
                self.assertIn(path, paths)
        schemas = res.json()["components"]["schemas"]
        self.assertIn("APIResponse", str(sorted(schemas.keys())))


class TestVolumeAnalytics(unittest.TestCase):
    def test_per_workout_sums(self):
        # W1: 60x10 + 60x8 = 1080 ; W2: 65x10 + 65x8 = 1170.
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench": [make_set(60, 10), make_set(60, 8)],
            }),
            make_workout("W2", "2026-01-12T07:00:00", {
                "Bench": [make_set(65, 10), make_set(65, 8)],
            }),
        ]
        history = compute_volume(workouts).exercises[0].history
        self.assertEqual(
            [(p.date, p.volume_kg) for p in history],
            [("2026-01-05", 1080), ("2026-01-12", 1170)],
        )

    def test_matches_progression_volume(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench": [make_set(80, 8), make_set(90, 6), make_set(None, 5)],
                "Squat": [make_set(100, 5)],
            }),
        ]
        volumes = {
            e.exercise_name: [p.volume_kg for p in e.history]
            for e in compute_volume(workouts).exercises
        }
        progression = {
            e.exercise_name: [p.volume_kg for p in e.history]
            for e in compute_progression(workouts).exercises
        }
        self.assertEqual(volumes, progression)
        self.assertEqual(volumes["Bench"], [80 * 8 + 90 * 6])
        self.assertEqual(volumes["Squat"], [500])

    def test_invalid_sets_excluded_and_empty_history(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench": [make_set(0, 8), make_set(80, 0)],
                "Plank": [make_set(None, None)],
            }),
        ]
        by_name = {
            e.exercise_name: e for e in compute_volume(workouts).exercises
        }
        self.assertEqual(by_name["Bench"].history, [])
        self.assertEqual(by_name["Plank"].history, [])

    def test_chronological_and_sorted(self):
        workouts = [
            make_workout("W2", "2026-01-12T07:00:00",
                         {"Squat": [make_set(100, 5)]}),
            make_workout("W1", "2026-01-05T07:00:00",
                         {"Bench": [make_set(60, 8)]}),
        ]
        response = compute_volume(workouts)
        self.assertEqual(
            [e.exercise_name for e in response.exercises],
            ["Bench", "Squat"],
        )

    def test_single_exercise_filter(self):
        workouts = [
            make_workout("W1", "2026-01-05T07:00:00", {
                "Bench": [make_set(60, 8)],
            }),
        ]
        single = compute_exercise_volume(workouts, "Bench")
        assert single is not None
        self.assertEqual(single.exercise_name, "Bench")
        self.assertIsNone(compute_exercise_volume(workouts, "Nope"))

    def test_empty_dataset(self):
        self.assertEqual(compute_volume([]).exercises, [])


class TestVolumeApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def test_volume_before_upload_is_404(self):
        res = self.client.get("/analysis/volume")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_volume_after_upload(self):
        upload_fixture(self.client)
        res = self.client.get("/analysis/volume")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        names = [e["exercise_name"] for e in body["data"]["exercises"]]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(names), 117)
        bench = next(
            e for e in body["data"]["exercises"]
            if e["exercise_name"] == "Bench Press (Barbell)"
        )
        self.assertGreater(len(bench["history"]), 10)
        self.assertEqual(
            set(bench["history"][0]), {"date", "workout_start", "volume_kg"}
        )
        starts = [p["workout_start"] for p in bench["history"]]
        self.assertEqual(starts, sorted(starts))

    def test_volume_filter_and_unknown(self):
        upload_fixture(self.client)
        res = self.client.get(
            "/analysis/volume", params={"exercise_name": "Squat (Barbell)"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["data"]["exercises"]), 1)
        unknown = self.client.get(
            "/analysis/volume", params={"exercise_name": "Nope"}
        )
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(
            unknown.json()["detail"]["error"], "unknown_exercise"
        )


class TestHevyRegression(unittest.TestCase):
    """Phase 10 changed the API contract, not the calculations."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def tearDown(self):
        main._LAST_WORKOUTS = None
        main._LAST_PROFILE = None

    def test_representative_values_unchanged(self):
        raw = upload_fixture(self.client)
        workouts = process_csv_bytes(raw).workouts
        get = self.client.get

        overview = get("/analysis/overview").json()["data"]
        self.assertEqual(overview["total_workouts"], 538)
        self.assertEqual(overview["total_sets"], 9151)
        self.assertEqual(overview["training_period_days"], 841)
        # Total weighted volume cross-checked against the raw CSV below.
        df = pd.read_csv(FIXTURE_PATH)
        valid = df[df["weight_kg"].notna() & df["reps"].notna()]
        valid = valid[(valid["weight_kg"] > 0) & (valid["reps"] > 0)]
        valid = valid[valid["reps"].apply(lambda r: float(r).is_integer())]
        expected_volume = round(
            float((valid["weight_kg"] * valid["reps"]).sum()), 2
        )
        self.assertEqual(overview["total_volume_kg"], expected_volume)

        prs = {
            p["exercise_name"]: p
            for p in get("/analysis/prs").json()["data"]["exercises"]
        }
        self.assertEqual(prs["Bench Press (Barbell)"]["weight_pr"]["value"], 75)
        self.assertEqual(prs["Deadlift (Barbell)"]["weight_pr"]["value"], 150)
        self.assertEqual(prs["Squat (Barbell)"]["weight_pr"]["value"], 80)

        progression = get("/analysis/progression").json()["data"]
        bench_prog = next(
            e for e in progression["exercises"]
            if e["exercise_name"] == "Bench Press (Barbell)"
        )
        self.assertEqual(bench_prog["history"][0]["volume_kg"], 1800.0)

        volume = get("/analysis/volume").json()["data"]
        bench_vol = next(
            e for e in volume["exercises"]
            if e["exercise_name"] == "Bench Press (Barbell)"
        )
        self.assertEqual(
            [(p["date"], p["volume_kg"]) for p in bench_vol["history"]],
            [(p["date"], p["volume_kg"]) for p in bench_prog["history"]],
        )

        plateaus = get("/analysis/plateaus").json()["data"]["plateaus"]
        self.assertGreater(len(plateaus), 0)
        self.assertEqual(plateaus[0]["label"], "Possible Plateau")

        muscles = {
            m["muscle"]: m
            for m in get("/analysis/muscles").json()["data"]["muscles"]
        }
        self.assertEqual(muscles["Chest"]["total_sets"], 1949)
        self.assertEqual(muscles["Back"]["total_sets"], 1781)
        self.assertEqual(muscles["Quadriceps"]["total_sets"], 1105)
        self.assertEqual(muscles["Hamstrings"]["total_sets"], 454)

        variety = get("/analysis/exercise-variety").json()["data"]
        self.assertEqual(variety["distinct_exercises"], 117)

        # Profile flow with the established Hevy expectations.
        self.client.post("/profile", json={
            "age": 25, "body_weight_kg": 63.0, "goal": "muscle_gain",
        })
        profile = get("/analysis/profile").json()["data"]
        self.assertEqual(profile["training_history"]["duration_days"], 841)
        self.assertEqual(profile["training_history"]["level"], "Intermediate")
        prs_with_ratios = {
            p["exercise_name"]: p
            for p in get("/analysis/prs").json()["data"]["exercises"]
        }
        bench = prs_with_ratios["Bench Press (Barbell)"]
        self.assertEqual(bench["weight_pr_ratio"], 1.19)
        self.assertEqual(bench["estimated_1rm_pr_ratio"], 1.51)

    def test_volume_independently_verified(self):
        upload_fixture(self.client)
        df = pd.read_csv(FIXTURE_PATH)
        valid = df[df["weight_kg"].notna() & df["reps"].notna()]
        valid = valid[(valid["weight_kg"] > 0) & (valid["reps"] > 0)]
        valid = valid[valid["reps"].apply(lambda r: float(r).is_integer())]

        volume = {
            e["exercise_name"]: e
            for e in self.client.get("/analysis/volume").json()["data"][
                "exercises"
            ]
        }
        for name in ["Bench Press (Barbell)", "Squat (Barbell)",
                     "Deadlift (Barbell)"]:
            with self.subTest(exercise=name):
                sub = valid[valid["exercise_title"] == name].copy()
                sub["start_iso"] = pd.to_datetime(
                    sub["start_time"], format="%d %b %Y, %H:%M"
                ).dt.strftime("%Y-%m-%dT%H:%M:%S")
                expected = sorted(
                    (iso, round(float(g["volume_kg"].sum()), 2))
                    for iso, g in sub.assign(
                        volume_kg=sub["weight_kg"] * sub["reps"]
                    ).groupby("start_iso")
                )
                actual = [
                    (p["workout_start"], p["volume_kg"])
                    for p in volume[name]["history"]
                ]
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
