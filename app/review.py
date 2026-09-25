"""Spaced-repetition scheduling (SM-2) for the wrong-answer review module.

A *review plan* is created from one finished session's wrong answers (the
``score = 0`` frozen into ``responses`` at answer time); stem, options and
the correct answer are frozen into the plan at creation, so later bank
edits never change what is reviewed.  Every plan item carries the classic
SM-2 scheduling state:

* ``ease_factor``   -- starts at 2.5 and is updated after **every** recorded
  review (failures included) by::

      EF' = max(1.3, EF + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))

* ``success_count`` -- consecutive reviews graded >= 3; a grade below 3
  resets it to 0 and retrains the item the next day (interval 1);
* ``interval_days`` -- the 1st / 2nd consecutive success schedule 1 / 6
  days; from the 3rd success on the interval is the *old* interval times
  the ease factor, rounded half up (四舍五入).

The interval uses the **pre-update** ease factor: scheduling is computed
first and the factor update is applied afterwards, matching the "每次结果后
更新因子" ordering of the specification (and the original SM-2 algorithm).

All dates are UTC calendar dates (``YYYY-MM-DD``): items of a freshly
created plan are due on the creation day, and a review graded ``grade``
reschedules the item to ``review_date + interval_days``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Every plan item starts with this ease factor (熟练因子).
INITIAL_EASE_FACTOR = 2.5

# The ease factor never drops below this floor.
MIN_EASE_FACTOR = 1.3

# Grades below this threshold are failures: retrain next day, reset streak.
PASS_GRADE = 3

MIN_GRADE = 0
MAX_GRADE = 5


@dataclass(frozen=True)
class ScheduleUpdate:
    """The scheduling state of one item after one recorded review."""

    ease_factor: float
    interval_days: int
    success_count: int


def updated_ease_factor(ease_factor: float, grade: int) -> float:
    """SM-2 ease-factor update, floored at :data:`MIN_EASE_FACTOR`.

    ``EF' = max(1.3, EF + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))``
    """
    miss = MAX_GRADE - grade
    return max(
        MIN_EASE_FACTOR,
        ease_factor + 0.1 - miss * (0.08 + miss * 0.02),
    )


def round_half_up(value: float) -> int:
    """四舍五入 for non-negative values (0.5 rounds up).

    Python's built-in ``round`` uses banker's rounding (``round(2.5) == 2``),
    which is *not* 四舍五入; ``floor(x + 0.5)`` is.
    """
    return int(math.floor(value + 0.5))


def advance_schedule(
    *,
    ease_factor: float,
    interval_days: int,
    success_count: int,
    grade: int,
) -> ScheduleUpdate:
    """Advance one item's SM-2 schedule for a review grade (0..5).

    * ``grade < 3`` -- retrain the next day (interval 1) and reset the
      consecutive-success count to 0;
    * otherwise the 1st / 2nd consecutive success schedules 1 / 6 days;
    * from the 3rd consecutive success on, the new interval is the *old*
      interval times the (pre-update) ease factor, rounded half up.

    The ease factor is updated on every review, including failures.
    """
    if not MIN_GRADE <= grade <= MAX_GRADE:  # defensive: validated upstream
        raise ValueError(f"grade must be in {MIN_GRADE}..{MAX_GRADE}")
    if grade < PASS_GRADE:
        new_success = 0
        new_interval = 1
    else:
        new_success = success_count + 1
        if new_success == 1:
            new_interval = 1
        elif new_success == 2:
            new_interval = 6
        else:
            new_interval = round_half_up(interval_days * ease_factor)
    return ScheduleUpdate(
        ease_factor=updated_ease_factor(ease_factor, grade),
        interval_days=new_interval,
        success_count=new_success,
    )
