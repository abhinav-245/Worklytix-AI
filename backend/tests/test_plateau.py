"""Phase 6 plateau detection tests (stdlib unittest; run from backend/).

    python -m unittest discover -s tests -v
"""

import os
import unittest
from datetime import date

import pandas as pd
from fastapi.testclient import TestClient

import main
from analytics.plateau import compute_exercise_plateaus, compute_plateaus
from data.models import ExerciseRecord, SetRecord, WorkoutRecord
from data.pipeline import process_csv_bytes

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "workout_data.csv"
)

# Consecutive Mondays in Jan/Feb 2026 (ISO weeks W02..W07).
MONDAYS = [
    "2026-01-05T07:00:00",
    "2026-01-12T07:00:00",
    "2026-01-19T07:00:00",
    "2026-01-26T07:00:00",
    "2026-02-02T07:00:00",
    "2026-02-09T07:00:00",
]


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


def weekly_workouts(name, specs):
    """One Monday workout per (start, sets) spec for a single exercise."""
    return [
        make_workout(f"W{i}", start, {name: sets})
        for i, (start, sets) in enumerate(specs)
    ]


def plateaus_of(name, workouts):
    return [p for p in compute_plateaus(workouts).plateaus
            if p.exercise_name == name]


class TestHeaviestWeight(unittest.TestCase):
    def test_heaviest_weight_and_reps_at_heaviest(self):
        workouts = weekly_workouts("Bench", [
            (MONDAYS[0], [make_set(60, 10), make_set(70, 8), make_set(75, 5)]),
            (MONDAYS[1], [make_set(60, 10), make_set(70, 8), make_set(75, 5)]),
            (MONDAYS[2], [make_set(60, 10), make_set(70, 8), make_set(75, 5)]),
            (MONDAYS[3], [make_set(60, 10), make_set(70, 8), make_set(75, 5)]),
        ])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].heaviest_weight_kg, 75)
        self.assertEqual(found[0].reps_at_heaviest_weight, 5)

    def test_max_reps_at_heaviest_weight_wins(self):
        sets = [make_set(75, 5), make_set(75, 8), make_set(75, 6),
                make_set(60, 12)]
        workouts = weekly_workouts("Bench", [(m, list(sets)) for m in MONDAYS[:4]])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        # 8 comes from the 75 kg sets, never the 60 kg x 12 set.
        self.assertEqual(found[0].heaviest_weight_kg, 75)
        self.assertEqual(found[0].reps_at_heaviest_weight, 8)


class TestFourWeekRule(unittest.TestCase):
    def _four_identical_weeks(self):
        return weekly_workouts("Bench", [
            (m, [make_set(80, 8)]) for m in MONDAYS[:4]
        ])

    def test_four_identical_weeks_is_plateau(self):
        found = plateaus_of("Bench", self._four_identical_weeks())
        self.assertEqual(len(found), 1)
        plateau = found[0]
        self.assertEqual(plateau.label, "Possible Plateau")
        self.assertEqual(plateau.consecutive_weeks, 4)
        self.assertEqual(plateau.heaviest_weight_kg, 80)
        self.assertEqual(plateau.reps_at_heaviest_weight, 8)
        self.assertEqual(len(plateau.evidence), 4)
        self.assertEqual(
            [e.week for e in plateau.evidence],
            ["2026-W02", "2026-W03", "2026-W04", "2026-W05"],
        )
        self.assertEqual(plateau.plateau_start, "2026-01-05")
        self.assertEqual(plateau.plateau_end, "2026-01-26")
        self.assertEqual(plateau.duration_days, 21)

    def test_three_weeks_is_not_plateau(self):
        workouts = weekly_workouts("Bench", [
            (m, [make_set(80, 8)]) for m in MONDAYS[:3]
        ])
        self.assertEqual(plateaus_of("Bench", workouts), [])

    def test_rep_improvement_breaks_plateau(self):
        workouts = weekly_workouts("Bench", [
            (MONDAYS[0], [make_set(80, 8)]),
            (MONDAYS[1], [make_set(80, 8)]),
            (MONDAYS[2], [make_set(80, 8)]),
            (MONDAYS[3], [make_set(80, 9)]),
        ])
        self.assertEqual(plateaus_of("Bench", workouts), [])

    def test_weight_improvement_breaks_plateau(self):
        workouts = weekly_workouts("Bench", [
            (MONDAYS[0], [make_set(80, 8)]),
            (MONDAYS[1], [make_set(80, 8)]),
            (MONDAYS[2], [make_set(80, 8)]),
            (MONDAYS[3], [make_set(82.5, 8)]),
        ])
        self.assertEqual(plateaus_of("Bench", workouts), [])

    def test_missing_week_breaks_sequence(self):
        workouts = weekly_workouts("Bench", [
            (MONDAYS[0], [make_set(80, 8)]),
            (MONDAYS[1], [make_set(80, 8)]),
            # Week 3 (MONDAYS[2]) skipped entirely.
            (MONDAYS[3], [make_set(80, 8)]),
            (MONDAYS[4], [make_set(80, 8)]),
        ])
        self.assertEqual(plateaus_of("Bench", workouts), [])

    def test_six_weeks_is_one_continuous_plateau(self):
        workouts = weekly_workouts("Bench", [
            (m, [make_set(80, 8)]) for m in MONDAYS[:6]
        ])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].consecutive_weeks, 6)
        self.assertEqual(len(found[0].evidence), 6)

    def test_multiple_plateau_periods(self):
        workouts = weekly_workouts("Bench", [
            (MONDAYS[0], [make_set(80, 8)]),
            (MONDAYS[1], [make_set(80, 8)]),
            (MONDAYS[2], [make_set(80, 8)]),
            (MONDAYS[3], [make_set(80, 8)]),
            (MONDAYS[4], [make_set(82.5, 8)]),
            ("2026-02-09T07:00:00", [make_set(82.5, 8)]),
            ("2026-02-16T07:00:00", [make_set(82.5, 8)]),
            ("2026-02-23T07:00:00", [make_set(82.5, 8)]),
            ("2026-03-02T07:00:00", [make_set(82.5, 8)]),
            ("2026-03-09T07:00:00", [make_set(82.5, 8)]),
        ])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].heaviest_weight_kg, 80)
        self.assertEqual(found[0].consecutive_weeks, 4)
        self.assertEqual(found[1].heaviest_weight_kg, 82.5)
        # Feb 2 + Feb 9/16/23 + Mar 2/9 = 6 consecutive weeks at 82.5x8.
        self.assertEqual(found[1].consecutive_weeks, 6)


class TestWeeklyGrouping(unittest.TestCase):
    def test_multiple_sessions_use_best_reps_at_heaviest(self):
        workouts = [
            make_workout("AM", "2026-01-05T07:00:00",
                         {"Bench": [make_set(75, 5)]}),
            make_workout("PM", "2026-01-08T18:00:00",
                         {"Bench": [make_set(75, 7)]}),
            make_workout("W2", "2026-01-12T07:00:00",
                         {"Bench": [make_set(75, 7)]}),
            make_workout("W3", "2026-01-19T07:00:00",
                         {"Bench": [make_set(75, 7)]}),
            make_workout("W4", "2026-01-26T07:00:00",
                         {"Bench": [make_set(75, 7)]}),
        ]
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        # Week 1 signature is 75x7 (best reps at 75), matching weeks 2-4.
        self.assertEqual(found[0].reps_at_heaviest_weight, 7)
        self.assertEqual(found[0].consecutive_weeks, 4)

    def test_heaviest_weight_beats_high_rep_lighter_sets(self):
        workouts = weekly_workouts("Bench", [
            (m, [make_set(70, 12), make_set(75, 5)]) for m in MONDAYS[:4]
        ])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].heaviest_weight_kg, 75)
        self.assertEqual(found[0].reps_at_heaviest_weight, 5)

    def test_same_day_sessions_stay_separate_but_share_week(self):
        workouts = [
            make_workout("AM", "2026-01-05T07:00:00",
                         {"Bench": [make_set(80, 8)]}),
            make_workout("PM", "2026-01-05T18:00:00",
                         {"Bench": [make_set(80, 8)]}),
            make_workout("W2", "2026-01-12T07:00:00",
                         {"Bench": [make_set(80, 8)]}),
            make_workout("W3", "2026-01-19T07:00:00",
                         {"Bench": [make_set(80, 8)]}),
            make_workout("W4", "2026-01-26T07:00:00",
                         {"Bench": [make_set(80, 8)]}),
        ]
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].consecutive_weeks, 4)


class TestSetTypesAndInvalid(unittest.TestCase):
    def test_all_set_types_eligible(self):
        for set_type in ["normal", "warm_up", "drop_set", "failure",
                         "unknown", "unknown:custom"]:
            with self.subTest(set_type=set_type):
                workouts = weekly_workouts("Bench", [
                    (m, [make_set(80, 8, set_type=set_type)])
                    for m in MONDAYS[:4]
                ])
                found = plateaus_of("Bench", workouts)
                self.assertEqual(len(found), 1)

    def test_invalid_values_ignored(self):
        good = [make_set(80, 8)]
        bad_variants = [
            [make_set(None, 8)], [make_set(0, 8)], [make_set(-10, 8)],
            [make_set(80, None)], [make_set(80, 0)], [make_set(80, -5)],
            [make_set(80, 8.5)],
        ]
        for i, bad in enumerate(bad_variants):
            with self.subTest(i=i):
                workouts = weekly_workouts("Bench", [
                    (MONDAYS[0], good + bad),
                    (MONDAYS[1], good),
                    (MONDAYS[2], good),
                    (MONDAYS[3], good),
                ])
                found = plateaus_of("Bench", workouts)
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0].heaviest_weight_kg, 80)

    def test_occurrence_without_valid_sets_is_skipped(self):
        workouts = weekly_workouts("Bench", [
            (MONDAYS[0], [make_set(80, 8)]),
            # Week 2 has the exercise but only invalid sets -> missing week.
            (MONDAYS[1], [make_set(None, None)]),
            (MONDAYS[2], [make_set(80, 8)]),
            (MONDAYS[3], [make_set(80, 8)]),
            (MONDAYS[4], [make_set(80, 8)]),
        ])
        # Weeks 1,3,4,5 share the signature but week 2 is missing -> no run.
        self.assertEqual(plateaus_of("Bench", workouts), [])


class TestWeekBoundaries(unittest.TestCase):
    def test_year_boundary_consecutive_weeks(self):
        # 2024-12-23 (Mon, 2024-W52), 2024-12-30 (Mon, 2025-W01),
        # 2025-01-06 (Mon, 2025-W02), 2025-01-13 (Mon, 2025-W03).
        starts = [
            "2024-12-23T07:00:00",
            "2024-12-30T07:00:00",
            "2025-01-06T07:00:00",
            "2025-01-13T07:00:00",
        ]
        workouts = weekly_workouts("Bench", [
            (s, [make_set(80, 8)]) for s in starts
        ])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].consecutive_weeks, 4)
        self.assertEqual(
            [e.week for e in found[0].evidence],
            ["2024-W52", "2025-W01", "2025-W02", "2025-W03"],
        )

    def test_same_iso_week_number_different_years_not_consecutive(self):
        # 2025-01-06 (2025-W02) and 2026-01-05 (2026-W02): same week number,
        # different ISO years -> must NOT count as consecutive.
        workouts = weekly_workouts("Bench", [
            ("2025-01-06T07:00:00", [make_set(80, 8)]),
            ("2025-01-13T07:00:00", [make_set(80, 8)]),
            ("2026-01-05T07:00:00", [make_set(80, 8)]),
            ("2026-01-12T07:00:00", [make_set(80, 8)]),
        ])
        self.assertEqual(plateaus_of("Bench", workouts), [])

    def test_month_boundary(self):
        workouts = weekly_workouts("Bench", [
            ("2026-01-26T07:00:00", [make_set(80, 8)]),
            ("2026-02-02T07:00:00", [make_set(80, 8)]),
            ("2026-02-09T07:00:00", [make_set(80, 8)]),
            ("2026-02-16T07:00:00", [make_set(80, 8)]),
        ])
        found = plateaus_of("Bench", workouts)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].consecutive_weeks, 4)


class TestExerciseIsolation(unittest.TestCase):
    def test_histories_never_mix(self):
        bench_specs = [(m, [make_set(80, 8)]) for m in MONDAYS[:4]]
        squat_specs = [
            (MONDAYS[0], [make_set(100, 5)]),
            (MONDAYS[1], [make_set(105, 5)]),
            (MONDAYS[2], [make_set(110, 5)]),
            (MONDAYS[3], [make_set(115, 5)]),
        ]
        deadlift_specs = [(m, [make_set(120, 5)]) for m in MONDAYS[:4]]
        workouts = [
            make_workout(f"W{i}", MONDAYS[i], {
                "Bench Press": bench_specs[i][1],
                "Squat": squat_specs[i][1],
                "Deadlift": deadlift_specs[i][1],
            })
            for i in range(4)
        ]
        response = compute_plateaus(workouts)
        by_name = {p.exercise_name: p for p in response.plateaus}
        self.assertEqual(set(by_name), {"Bench Press", "Deadlift"})
        self.assertNotIn("Squat", by_name)
        # Deterministic sort: exercise name, then start.
        names = [(p.exercise_name, p.plateau_start) for p in response.plateaus]
        self.assertEqual(names, sorted(names))

    def test_empty_dataset(self):
        self.assertEqual(compute_plateaus([]).plateaus, [])

    def test_exercise_filter_helper(self):
        workouts = weekly_workouts("Bench", [
            (m, [make_set(80, 8)]) for m in MONDAYS[:4]
        ])
        self.assertEqual(
            len(compute_exercise_plateaus(workouts, "Bench")), 1
        )
        self.assertEqual(
            compute_exercise_plateaus(workouts, "Unknown"), []
        )


class TestPlateauApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._LAST_WORKOUTS = None

    def tearDown(self):
        main._LAST_WORKOUTS = None

    def test_plateaus_before_upload_is_404(self):
        res = self.client.get("/analysis/plateaus")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error"], "no_dataset")

    def test_plateaus_after_upload(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        upload = self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        self.assertEqual(upload.status_code, 200)
        res = self.client.get("/analysis/plateaus")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("plateaus", body)
        self.assertGreater(len(body["plateaus"]), 0)
        first = body["plateaus"][0]
        self.assertEqual(
            set(first),
            {"exercise_name", "label", "plateau_start", "plateau_end",
             "duration_days", "consecutive_weeks", "heaviest_weight_kg",
             "reps_at_heaviest_weight", "evidence"},
        )
        self.assertEqual(first["label"], "Possible Plateau")
        names = [(p["exercise_name"], p["plateau_start"])
                 for p in body["plateaus"]]
        self.assertEqual(names, sorted(names))

    def test_exercise_filter(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.get(
            "/analysis/plateaus",
            params={"exercise_name": "Bench Press (Barbell)"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.json()["plateaus"]), 0)
        for plateau in res.json()["plateaus"]:
            self.assertEqual(
                plateau["exercise_name"], "Bench Press (Barbell)"
            )

    def test_unknown_exercise_filter_is_404(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        self.client.post(
            "/upload", files={"file": ("workouts.csv", raw, "text/csv")}
        )
        res = self.client.get(
            "/analysis/plateaus", params={"exercise_name": "Nope"}
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
        self.assertEqual(self.client.get("/analysis/prs").status_code, 200)
        progression = self.client.get("/analysis/progression")
        self.assertEqual(progression.status_code, 200)
        self.assertEqual(len(progression.json()["exercises"]), 117)


class TestRealHevyPlateaus(unittest.TestCase):
    @unittest.skipUnless(
        os.path.exists(FIXTURE_PATH), "real Hevy CSV fixture not available"
    )
    def test_real_hevy_dataset(self):
        with open(FIXTURE_PATH, "rb") as f:
            raw = f.read()
        workouts = process_csv_bytes(raw).workouts
        response = compute_plateaus(workouts)
        plateaus = response.plateaus
        self.assertGreater(len(plateaus), 0)

        df = pd.read_csv(FIXTURE_PATH)
        valid = df[df["weight_kg"].notna() & df["reps"].notna()]
        valid = valid[(valid["weight_kg"] > 0) & (valid["reps"] > 0)]
        valid = valid[valid["reps"].apply(
            lambda r: float(r).is_integer())].copy()
        valid["start_dt"] = pd.to_datetime(
            valid["start_time"], format="%d %b %Y, %H:%M")
        valid["iso_year"] = valid["start_dt"].dt.isocalendar().year.astype(int)
        valid["iso_week"] = valid["start_dt"].dt.isocalendar().week.astype(int)

        # Independently validate several reported plateaus from the raw CSV.
        for plateau in plateaus[:6]:
            with self.subTest(exercise=plateau.exercise_name,
                              start=plateau.plateau_start):
                sub = valid[valid["exercise_title"] == plateau.exercise_name]
                evidence_weeks = []
                for ev in plateau.evidence:
                    year, week = int(ev.week[:4]), int(ev.week[6:])
                    week_rows = sub[(sub["iso_year"] == year)
                                    & (sub["iso_week"] == week)]
                    self.assertGreater(len(week_rows), 0,
                                       f"no raw rows for {ev.week}")
                    top_weight = float(week_rows["weight_kg"].max())
                    top_reps = int(week_rows[week_rows["weight_kg"]
                                             == top_weight]["reps"].max())
                    self.assertAlmostEqual(
                        top_weight, plateau.heaviest_weight_kg, places=2)
                    self.assertEqual(top_reps,
                                     plateau.reps_at_heaviest_weight)
                    evidence_weeks.append((year, week))
                # Consecutive ISO weeks with no gaps.
                for (y1, w1), (y2, w2) in zip(evidence_weeks,
                                              evidence_weeks[1:]):
                    monday1 = date.fromisocalendar(y1, w1, 1)
                    monday2 = date.fromisocalendar(y2, w2, 1)
                    self.assertEqual((monday2 - monday1).days, 7)
                self.assertGreaterEqual(plateau.consecutive_weeks, 4)
                self.assertEqual(plateau.label, "Possible Plateau")

        # Determinism across repeated runs.
        again = compute_plateaus(workouts)
        self.assertEqual(response.model_dump(), again.model_dump())


if __name__ == "__main__":
    unittest.main()
