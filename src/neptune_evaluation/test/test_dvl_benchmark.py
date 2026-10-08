"""Validate benchmark conditions and honest result recording without simulation."""
import json

import pytest

from neptune_evaluation.dvl_benchmark import MATRIX, parameters, prepare, write_result
from neptune_evaluation.localization_metrics import LocalizationMetrics


def test_matrix_is_single_effect_and_dvl_only():
    assert len(MATRIX) == 7
    for case in MATRIX:
        p = parameters(case)
        assert p['seed'] == 42
        assert all(key == 'seed' or key.startswith('dvl_') for key in p)
        noise, bias, dropout = MATRIX[case]
        assert sum(value != 0 for value in (noise, bias, dropout)) <= 1
        assert p['dvl_noise_std_x'] == p['dvl_noise_std_y'] == p['dvl_noise_std_z']
    assert MATRIX['noise_low'][0] < MATRIX['noise_medium'][0] < MATRIX['noise_high'][0]
    assert 0 < MATRIX['dropout_mild'][2] < MATRIX['dropout_strong'][2] < 1


def test_prepare_records_conditions_and_remaps_only_dvl(tmp_path):
    directory = prepare('bias_small', tmp_path / 'run with spaces', 'sha dirty', 'launch scenario')
    config = json.loads((directory / 'degrader.json').read_text())
    assert config['sensor_degrader']['ros__parameters'] == parameters('bias_small')
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['mission_outcome'] == 'pending'
    assert manifest['revision'] == 'sha dirty'
    commands = (directory / 'commands.txt').read_text()
    assert '-r /sim/dvl:=/degraded/dvl' in commands
    assert '/sim/imu:=' not in commands
    assert '/sim/pressure:=' not in commands
    assert 'result_path:=' in commands
    assert not (directory / 'metrics.json').exists()
    with pytest.raises(FileExistsError):
        prepare('clean', directory, 'sha', 'launch')


def test_results_include_existing_metrics_and_counts(tmp_path):
    metrics = LocalizationMetrics()
    metrics.add_sample((0, 0, 0), (10, 10, 10), 0, 0)
    metrics.add_sample((3, 4, 2), (10, 10, 10), 0.1, 0)
    path = tmp_path / 'metrics.json'
    write_result(path, metrics.summary(), 7)
    result = json.loads(path.read_text())
    assert result['final_horizontal_error'] == 5
    assert result['final_3d_error'] == pytest.approx(29 ** 0.5)
    assert result['accepted_sample_count'] == 2
    assert result['rejected_sample_count'] == 7
    assert result['yaw_rmse'] == pytest.approx(0.1 / 2 ** 0.5)
    assert 'mission_outcome' not in result
    with pytest.raises(FileExistsError):
        write_result(path, metrics.summary(), 7)


def test_empty_results_are_explicit_not_fabricated(tmp_path):
    path = tmp_path / 'metrics.json'
    write_result(path, LocalizationMetrics().summary(), 0)
    result = json.loads(path.read_text())
    assert result['accepted_sample_count'] == 0
    assert result['horizontal_rmse'] is None
