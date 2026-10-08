"""Prepare explicit S2.3 live-run artifacts; never launch or score a mission."""

import argparse
import json
from pathlib import Path
import shlex

MATRIX = {
    'clean': (0.0, 0.0, 0.0),
    'noise_low': (0.005, 0.0, 0.0),
    'noise_medium': (0.02, 0.0, 0.0),
    'noise_high': (0.05, 0.0, 0.0),
    'bias_small': (0.0, 0.01, 0.0),
    'dropout_mild': (0.0, 0.0, 0.10),
    'dropout_strong': (0.0, 0.0, 0.40),
}


def parameters(case):
    """Only DVL perturbations; other S2.2 parameters retain zero defaults."""
    noise, bias, dropout = MATRIX[case]
    return dict(seed=42, dvl_noise_std_x=noise, dvl_noise_std_y=noise,
                dvl_noise_std_z=noise, dvl_bias_x=bias, dvl_bias_y=0.0,
                dvl_bias_z=0.0, dvl_dropout_probability=dropout)


def write_result(path, metrics, rejected):
    """Save unrounded S2.1 metrics without inventing mission outcome."""
    with Path(path).open('x') as output:
        json.dump(dict(metrics, accepted_sample_count=metrics['sample_count'],
                       rejected_sample_count=rejected,
                       rejected_count_semantics='invalid/repeated messages or skew discards; '
                       'not DVL dropout count'), output, indent=2, allow_nan=False)
        output.write('\n')


def prepare(case, directory, revision, simulator_command):
    """Create a fresh directory to prevent accidentally overwriting a run."""
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    config = parameters(case)
    (directory / 'degrader.json').write_text(json.dumps(
        {'sensor_degrader': {'ros__parameters': config}}, indent=2) + '\n')
    manifest = dict(case=case, parameters=config, revision=revision,
                    simulator_command=simulator_command,
                    scenario='src/neptune_sim/scenarios/benchmarks/02_port_pipe_mission.scn',
                    max_pair_skew_seconds=0.1, mission_timeout_seconds=420,
                    mission_outcome='pending', outcome_reason='',
                    environment_notes='', start_stamp=None, end_stamp=None)
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    q = lambda name: shlex.quote(str(directory / name))
    commands = [
        '# Run each line in a separate sourced terminal; simulator first, mission last.',
        f'# Simulator invocation recorded by operator: {simulator_command}',
        f'ros2 run neptune_sim sensor_degrader --ros-args --params-file {q("degrader.json")} 2>&1 | tee {q("degrader.log")}',
        f'ros2 run neptune_evaluation localization_evaluator --ros-args -p max_pair_skew:=0.1 -p result_path:={q("metrics.json")} 2>&1 | tee {q("evaluator.log")}',
        f'ros2 run neptune_state_estimation pressure_depth 2>&1 | tee {q("pressure.log")}',
        f'ros2 run neptune_state_estimation dead_reckoning_state --ros-args -r /sim/dvl:=/degraded/dvl 2>&1 | tee {q("estimator.log")}',
        f'ros2 run neptune_vehicle stonefish_adapter 2>&1 | tee {q("adapter.log")}',
        f'ros2 bag record -o {q("bag")} /sim/dvl /degraded/dvl /sim/imu /sim/pressure /estimate/depth /state/odometry /sim/odometry /neptune/cmd_body /rosout /clock',
        f'ros2 run neptune_autonomy mission_executive 2>&1 | tee {q("mission.log")}',
    ]
    (directory / 'commands.txt').write_text('\n'.join(commands) + '\n')
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=MATRIX)
    parser.add_argument('directory')
    parser.add_argument('--revision', required=True,
                        help='Git SHA plus dirty-tree description or patch reference')
    parser.add_argument('--simulator-command', required=True,
                        help='Exact working Stonefish launch command including scenario')
    args = parser.parse_args()
    directory = prepare(args.case, args.directory, args.revision, args.simulator_command)
    print((directory / 'commands.txt').read_text())
