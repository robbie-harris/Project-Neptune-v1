"""Regression checks for sticky steering, auto-repeat saturation and stop rearming."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('controls', Path(__file__).parents[1] / 'src/neptune_gui/controls.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_held_forward_repeat_release_and_previous_turn():
    c = module.ManualControls()
    c.press('a'); c.release('a')
    for _ in range(100): c.press('w')
    assert c.command() == [.6, .6, 0]
    c.release('w')
    assert c.command() == [0, 0, 0]


def test_stop_does_not_rearm_held_keys_and_opposites_cancel():
    c = module.ManualControls()
    c.press('w'); c.stop(); c.press('w')
    assert c.command() == [0, 0, 0]
    c.release('w'); c.press('w'); c.press('s')
    assert c.command() == [0, 0, 0]
    c.release('s'); c.press('up')
    assert c.command() == [.6, .6, 0]  # aliases do not double the command


def test_all_directions_and_combined_mixing():
    for key, expected in [('w',[.6,.6,0]),('s',[-.6,-.6,0]),('a',[-.6,.6,0]),
                          ('d',[.6,-.6,0]),('r',[0,0,.6]),('f',[0,0,-.6])]:
        c=module.ManualControls(); c.press(key)
        assert c.command() == expected
    assert module.mix(.8,.6,.3) == pytest.approx([1,1/7,.3])
