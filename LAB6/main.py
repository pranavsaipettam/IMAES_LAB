"""Experiment 6: Fuzzy Logic and Constraint Satisfaction.

This program uses Mamdani-style fuzzy inference for student performance and
backtracking search to create a conflict-free class timetable.
"""

from collections.abc import Mapping, Sequence


FUZZY_SETS = ("low", "medium", "high")
OUTPUT_VALUES = tuple(range(101))

# A rule maps (attendance category, marks category) to a performance category.
PERFORMANCE_RULES = {
    ("low", "low"): "low",
    ("low", "medium"): "low",
    ("low", "high"): "average",
    ("medium", "low"): "low",
    ("medium", "medium"): "average",
    ("medium", "high"): "high",
    ("high", "low"): "average",
    ("high", "medium"): "high",
    ("high", "high"): "high",
}

TIME_SLOTS = (
    "09:00-10:00",
    "10:00-11:00",
    "11:00-12:00",
    "13:00-14:00",
)

COURSES = {
    "Mathematics": {"teacher": "Dr. Rao", "room": "R1"},
    "Artificial Intelligence": {"teacher": "Dr. Sen", "room": "R2"},
    "Databases": {"teacher": "Dr. Rao", "room": "R2"},
    "Computer Networks": {"teacher": "Dr. Kim", "room": "R1"},
}


def left_shoulder(value: float, full_until: float, zero_at: float) -> float:
    """Membership for a category that is strongest at low values."""
    if value <= full_until:
        return 1.0
    if value >= zero_at:
        return 0.0
    return (zero_at - value) / (zero_at - full_until)


def triangle(value: float, start: float, peak: float, end: float) -> float:
    """Triangular membership function."""
    if value <= start or value >= end:
        return 0.0
    if value == peak:
        return 1.0
    if value < peak:
        return (value - start) / (peak - start)
    return (end - value) / (end - peak)


def right_shoulder(value: float, zero_at: float, full_from: float) -> float:
    """Membership for a category that is strongest at high values."""
    if value <= zero_at:
        return 0.0
    if value >= full_from:
        return 1.0
    return (value - zero_at) / (full_from - zero_at)


def input_memberships(value: float) -> dict[str, float]:
    """Return low, medium, and high membership for a percentage value."""
    if not 0 <= value <= 100:
        raise ValueError("Attendance and marks must be between 0 and 100.")
    return {
        "low": left_shoulder(value, 40, 65),
        "medium": triangle(value, 30, 60, 85),
        "high": right_shoulder(value, 70, 90),
    }


def output_membership(category: str, value: int) -> float:
    """Performance output membership on a 0-100 scale."""
    if category == "low":
        return left_shoulder(value, 30, 55)
    if category == "average":
        return triangle(value, 25, 50, 75)
    if category == "high":
        return right_shoulder(value, 60, 85)
    raise ValueError(f"Unknown performance category: {category}")


def student_performance(
    attendance: float,
    marks: float,
    rules: Mapping[tuple[str, str], str] = PERFORMANCE_RULES,
) -> float:
    """Evaluate fuzzy rules and defuzzify the combined output using a centroid."""
    attendance_degrees = input_memberships(attendance)
    marks_degrees = input_memberships(marks)
    aggregated_output = [0.0] * len(OUTPUT_VALUES)

    for (attendance_set, marks_set), performance_set in rules.items():
        firing_strength = min(
            attendance_degrees[attendance_set],
            marks_degrees[marks_set],
        )
        for index, output_value in enumerate(OUTPUT_VALUES):
            clipped = min(
                firing_strength,
                output_membership(performance_set, output_value),
            )
            aggregated_output[index] = max(aggregated_output[index], clipped)

    total_membership = sum(aggregated_output)
    if total_membership == 0:
        raise ValueError("The rules produced no output for these input values.")
    return sum(
        value * degree
        for value, degree in zip(OUTPUT_VALUES, aggregated_output)
    ) / total_membership


def solve_timetable(
    courses: Mapping[str, Mapping[str, str]],
    time_slots: Sequence[str],
    unavailable: Mapping[str, set[str]] | None = None,
) -> dict[str, str] | None:
    """Find a schedule with no simultaneous teacher or room conflicts."""
    unavailable = unavailable or {}
    domains = {
        course: [
            slot
            for slot in time_slots
            if slot not in unavailable.get(course, set())
        ]
        for course in courses
    }
    if any(not domain for domain in domains.values()):
        return None

    schedule: dict[str, str] = {}

    def can_assign(course: str, slot: str) -> bool:
        for assigned_course, assigned_slot in schedule.items():
            if assigned_slot != slot:
                continue
            same_teacher = (
                courses[course]["teacher"] == courses[assigned_course]["teacher"]
            )
            same_room = courses[course]["room"] == courses[assigned_course]["room"]
            if same_teacher or same_room:
                return False
        return True

    def backtrack() -> bool:
        if len(schedule) == len(courses):
            return True

        # Choose the remaining course with the fewest available slots first.
        remaining = [course for course in courses if course not in schedule]
        course = min(
            remaining,
            key=lambda item: sum(can_assign(item, slot) for slot in domains[item]),
        )
        for slot in domains[course]:
            if can_assign(course, slot):
                schedule[course] = slot
                if backtrack():
                    return True
                del schedule[course]
        return False

    return schedule.copy() if backtrack() else None


def show_timetable(schedule: Mapping[str, str] | None) -> None:
    if schedule is None:
        print("No timetable satisfies the constraints.")
        return
    for course, slot in schedule.items():
        teacher = COURSES[course]["teacher"]
        room = COURSES[course]["room"]
        print(f"  {slot}: {course} | {teacher} | Room {room}")


def main() -> None:
    print("EXERCISE 1: Student performance")
    test_students = ((35, 40), (60, 65), (90, 88))
    for attendance, marks in test_students:
        result = student_performance(attendance, marks)
        print(
            f"  Attendance {attendance:>3}% and marks {marks:>3}% "
            f"-> performance {result:.1f}/100"
        )

    print("\nEXERCISE 2: Timetable without conflicts")
    schedule = solve_timetable(COURSES, TIME_SLOTS)
    show_timetable(schedule)

    print("\nEXERCISE 3: Change a rule and add a constraint")
    changed_rules = PERFORMANCE_RULES.copy()
    # Changed rule: low attendance with high marks now gives high performance.
    changed_rules[("low", "high")] = "high"
    attendance, marks = 35, 90
    print(
        f"  Original rule output ({attendance}% attendance, {marks}% marks): "
        f"{student_performance(attendance, marks):.1f}/100"
    )
    print(
        f"  Changed rule output ({attendance}% attendance, {marks}% marks): "
        f"{student_performance(attendance, marks, changed_rules):.1f}/100"
    )

    # Additional constraint: Artificial Intelligence cannot use the first slot.
    changed_schedule = solve_timetable(
        COURSES,
        TIME_SLOTS,
        unavailable={"Artificial Intelligence": {TIME_SLOTS[0]}},
    )
    print("  Timetable after adding the AI time-slot restriction:")
    show_timetable(changed_schedule)


if __name__ == "__main__":
    main()