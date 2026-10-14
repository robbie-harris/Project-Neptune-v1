"""Lifecycle measurement must expose blackout tails and allow health recovery."""
from perception_p5a_lifecycle import advancing, max_gap
import pytest


def test_empty_and_stopped_stream_gaps():
    assert max_gap([], 10, 22) == 12
    assert max_gap([10.1, 10.3, 10.5], 10, 22) == 11.5
    assert max_gap([9, 10.2, 10.4, 11.5, 23], 10, 12) == pytest.approx(1.1)


def test_current_consecutive_stamps():
    assert not advancing([1, 2, 3, 4, 5])
    assert not advancing([1, 2, 3, 4, 4, 5])
    assert advancing([9, 8, 10, 11, 12, 13, 14, 15])
