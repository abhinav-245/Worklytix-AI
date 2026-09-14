"""Deterministic exercise -> primary-muscle mapping (Phase 7).

Rules:
- Keys are exact normalized ``exercise_name`` values (no fuzzy matching,
  no substring similarity, no embeddings, no AI). Lookup is exact.
- Each mapped exercise has exactly ONE primary muscle (no secondary
  muscles in this phase).
- Unknown exercises return None -- never forced into a category, never
  "Other"/"Misc". Unmapped never implies a neglected muscle.
- Canonical muscle names are fixed by PRIMARY_MUSCLES; only these names
  may appear as mapping values.

Coverage of the bundled Hevy fixture (backend/tests/fixtures/
workout_data.csv): 113/117 exercises mapped. The 4 unmapped entries are
cardio activities (Elliptical Trainer, Spinning, Treadmill, Walking) with
no single primary lifting muscle.
"""

from __future__ import annotations

#: Canonical primary-muscle taxonomy. Only these values may be used.
#: Muscles with zero mapped sets are reported as "Potentially Neglected".
PRIMARY_MUSCLES = [
    "Abdominals",
    "Abductors",
    "Adductors",
    "Back",
    "Biceps",
    "Calves",
    "Chest",
    "Forearms",
    "Glutes",
    "Hamstrings",
    "Lower Back",
    "Quadriceps",
    "Shoulders",
    "Traps",
    "Triceps",
]

#: Exact normalized exercise name -> primary muscle.
EXERCISE_PRIMARY_MUSCLE: dict[str, str] = {
    "Ab Wheel": "Abdominals",
    "Back Extension (Hyperextension)": "Lower Back",
    "Back Extension (Weighted Hyperextension)": "Lower Back",
    "Bench Press (Barbell)": "Chest",
    "Bench Press (Dumbbell)": "Chest",
    "Bench Press - Close Grip (Barbell)": "Triceps",
    "Bent Over Row (Barbell)": "Back",
    "Bicep Curl (Barbell)": "Biceps",
    "Bicep Curl (Cable)": "Biceps",
    "Bicep Curl (Dumbbell)": "Biceps",
    "Cable Fly Crossovers": "Chest",
    "Chest Dip": "Chest",
    "Chest Dip (Weighted)": "Chest",
    "Chest Fly (Dumbbell)": "Chest",
    "Chest Fly (Machine)": "Chest",
    "Chest Press (Band)": "Chest",
    "Chest Press (Machine)": "Chest",
    "Chest Supported Incline Row (Dumbbell)": "Back",
    "Cross Body Hammer Curl": "Biceps",
    "Crunch": "Abdominals",
    "Deadlift (Barbell)": "Back",
    "Decline Bench Press (Barbell)": "Chest",
    "Decline Bench Press (Dumbbell)": "Chest",
    "Decline Crunch": "Abdominals",
    "Decline Crunch (Weighted)": "Abdominals",
    "Dumbbell Row": "Back",
    "EZ Bar Biceps Curl": "Biceps",
    "Ez Bar Preacher Curl": "Biceps",
    "Face Pull": "Shoulders",
    "Front Raise (Cable)": "Shoulders",
    "Front Raise (Dumbbell)": "Shoulders",
    "Goblet Squat": "Quadriceps",
    "Hammer Curl (Cable)": "Biceps",
    "Hammer Curl (Dumbbell)": "Biceps",
    "Hanging Leg Raise": "Abdominals",
    "Incline Bench Press (Barbell)": "Chest",
    "Incline Bench Press (Dumbbell)": "Chest",
    "Incline Chest Press (Machine)": "Chest",
    "Iso-Lateral Row (Machine)": "Back",
    "Jumping Squats": "Quadriceps",
    "Kettlebell Goblet Squat": "Quadriceps",
    "Kettlebell Shoulder Press": "Shoulders",
    "Knee Raise Parallel Bars": "Abdominals",
    "Lat Pull Down New Grip": "Back",
    "Lat Pulldown (Cable)": "Back",
    "Lat Pulldown - Close Grip (Cable)": "Back",
    "Lateral Raise (Dumbbell)": "Shoulders",
    "Leg Extension (Machine)": "Quadriceps",
    "Leg Press (Machine)": "Quadriceps",
    "Leg Press Horizontal (Machine)": "Quadriceps",
    "Leg Raise Parallel Bars": "Abdominals",
    "Low Cable Fly Crossovers": "Chest",
    "Lunge (Dumbbell)": "Quadriceps",
    "Lying Leg Curl (Machine)": "Hamstrings",
    "Mid Back Machine Row": "Back",
    "Overhead Press (Barbell)": "Shoulders",
    "Overhead Press (Dumbbell)": "Shoulders",
    "Overhead Triceps Extension (Cable)": "Triceps",
    "Pendulum Squat (Machine)": "Quadriceps",
    "Plank": "Abdominals",
    "Plate Front Raise": "Shoulders",
    "Preacher Curl (Barbell)": "Biceps",
    "Preacher Curl (Dumbbell)": "Biceps",
    "Preacher Curl (Machine)": "Biceps",
    "Pull Up": "Back",
    "Pull Up (Assisted)": "Back",
    "Push Up": "Chest",
    "Rear Delt Reverse Fly (Cable)": "Shoulders",
    "Rear Delt Reverse Fly (Machine)": "Shoulders",
    "Reverse Fly Single Arm (Cable)": "Shoulders",
    "Reverse Grip Lat Pulldown (Cable)": "Back",
    "Romanian Deadlift (Barbell)": "Hamstrings",
    "Romanian Deadlift (Dumbbell)": "Hamstrings",
    "Rope Cable Curl": "Biceps",
    "Rope Straight Arm Pulldown": "Back",
    "Russian Twist (Bodyweight)": "Abdominals",
    "Russian Twist (Weighted)": "Abdominals",
    "Seated Cable Row - Bar Grip": "Back",
    "Seated Cable Row - V Grip (Cable)": "Back",
    "Seated Calf Raise": "Calves",
    "Seated Incline Curl (Dumbbell)": "Biceps",
    "Seated Overhead Press (Barbell)": "Shoulders",
    "Seated Palms Up Wrist Curl": "Forearms",
    "Seated Shoulder Press (Machine)": "Shoulders",
    "Seated Wrist Extension (Barbell)": "Forearms",
    "Shoulder Press (Dumbbell)": "Shoulders",
    "Shoulder Press (Machine Plates)": "Shoulders",
    "Shrug (Barbell)": "Traps",
    "Shrug (Dumbbell)": "Traps",
    "Single Arm Cable Row": "Back",
    "Single Arm Iso Lateral Row": "Back",
    "Single Arm Lateral Raise (Cable)": "Shoulders",
    "Single Arm Tricep Extension (Dumbbell)": "Triceps",
    "Single Arm Triceps Pushdown (Cable)": "Triceps",
    "Single Hand Rear Delt Machine": "Shoulders",
    "Single Leg Extensions": "Quadriceps",
    "Skullcrusher (Barbell)": "Triceps",
    "Skullcrusher (Dumbbell)": "Triceps",
    "Squat (Barbell)": "Quadriceps",
    "Squat (Bodyweight)": "Quadriceps",
    "Squat (Machine)": "Quadriceps",
    "Squat (Smith Machine)": "Quadriceps",
    "Standing Calf Raise": "Calves",
    "Straight Arm Lat Pulldown (Cable)": "Back",
    "T Bar Row": "Back",
    "Triceps Dip": "Triceps",
    "Triceps Dip (Assisted)": "Triceps",
    "Triceps Extension (Cable)": "Triceps",
    "Triceps Extension (Dumbbell)": "Triceps",
    "Triceps Pushdown": "Triceps",
    "Triceps Rope Pushdown": "Triceps",
    "Wide Pull Up": "Back",
    "Zercher Squat": "Quadriceps",
}

# Deliberately unmapped cardio activities with no single primary
# lifting muscle: "Elliptical Trainer", "Spinning", "Treadmill", "Walking".


def get_primary_muscle(exercise_name: str) -> str | None:
    """Return the canonical primary muscle, or None when unmapped.

    Matching is exact against the normalized exercise name.
    """
    if not exercise_name or not isinstance(exercise_name, str):
        return None
    return EXERCISE_PRIMARY_MUSCLE.get(exercise_name)


__all__ = [
    "PRIMARY_MUSCLES",
    "EXERCISE_PRIMARY_MUSCLE",
    "get_primary_muscle",
]
