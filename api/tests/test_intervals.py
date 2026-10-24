import pytest

from app.scheduler.intervals import Interval, align_up, merge, subtract, total


def test_merge_joins_overlapping_and_touching() -> None:
    merged = merge([Interval(60, 120), Interval(0, 30), Interval(30, 45), Interval(100, 200)])
    assert merged == [Interval(0, 45), Interval(60, 200)]


def test_subtract_cuts_holes() -> None:
    result = subtract([Interval(540, 780)], [Interval(600, 630), Interval(700, 800)])
    assert result == [Interval(540, 600), Interval(630, 700)]


def test_subtract_with_nothing_to_remove_returns_base() -> None:
    assert subtract([Interval(0, 60)], []) == [Interval(0, 60)]


def test_total_ignores_overlap() -> None:
    assert total([Interval(0, 60), Interval(30, 90)]) == 90


def test_align_up() -> None:
    assert align_up(541, 15) == 555
    assert align_up(540, 15) == 540


def test_invalid_interval_rejected() -> None:
    with pytest.raises(ValueError):
        Interval(100, 50)
