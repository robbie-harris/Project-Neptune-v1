# S2.2 sensor degradation infrastructure

`sensor_degrader` copies Stonefish sensors to separate output topics. It never
subscribes to simulator odometry. Existing estimators opt in with ROS remapping.

| Input | Output | ROS message | Changed measurements |
| --- | --- | --- | --- |
| `/sim/dvl` | `/degraded/dvl` | `stonefish_ros2/msg/DVL` | `velocity.x/y/z` |
| `/sim/imu` | `/degraded/imu` | `sensor_msgs/msg/Imu` | angular velocity, acceleration, orientation |
| `/sim/pressure` | `/degraded/pressure` | `sensor_msgs/msg/FluidPressure` | `fluid_pressure` |

Headers, timestamps, frames, covariance fields, DVL altitude and beams are copied
unchanged. Zero configuration performs an exact value pass-through, including
leaving the input quaternion untouched. The input message is never mutated.

## Complete parameter list

All parameters are read-only after startup. Restart the node to change settings.
`seed` is an integer, default **0**. Every parameter below is a floating-point
value, default **0.0**:

| Parameters | Units / meaning |
| --- | --- |
| `dvl_noise_std_x`, `dvl_noise_std_y`, `dvl_noise_std_z` | m/s, independent Gaussian standard deviation |
| `dvl_bias_x`, `dvl_bias_y`, `dvl_bias_z` | m/s, constant additive bias in original DVL sensor frame |
| `dvl_dropout_probability` | probability in [0, 1] per incoming message |
| `imu_gyro_noise_std_x`, `imu_gyro_noise_std_y`, `imu_gyro_noise_std_z` | rad/s |
| `imu_gyro_bias_x`, `imu_gyro_bias_y`, `imu_gyro_bias_z` | rad/s |
| `imu_accel_noise_std_x`, `imu_accel_noise_std_y`, `imu_accel_noise_std_z` | m/s² |
| `imu_accel_bias_x`, `imu_accel_bias_y`, `imu_accel_bias_z` | m/s² |
| `imu_orientation_noise_std_x`, `imu_orientation_noise_std_y`, `imu_orientation_noise_std_z` | rad, rotation-vector components |
| `imu_orientation_bias_x`, `imu_orientation_bias_y`, `imu_orientation_bias_z` | rad, rotation-vector components |
| `pressure_noise_std` | Pa |
| `pressure_bias` | Pa |
| `pressure_dropout_probability` | probability in [0, 1] per incoming message |

Noise standard deviations must be finite and nonnegative; biases must be finite.
For vectors, each axis receives its own zero-mean Gaussian draw plus its bias.
Gyro and acceleration use the original message's sensor coordinates.

Orientation uses a body-frame rotation vector `r = bias + noise` in radians:
`delta_q = (r * sin(|r|/2)/|r|, cos(|r|/2))` in x/y/z/w order, with the
continuous zero-angle limit. The output is the normalized Hamilton product
`q_input * delta_q`. This is an exact axis-angle perturbation, approximating
small roll/pitch/yaw errors near zero; it is not an Euler-angle addition.
The unavailable-orientation sentinel (`orientation_covariance[0] == -1`) is
preserved and orientation perturbation is skipped. Enabled orientation
perturbation requires a finite nonzero input quaternion; invalid input raises
an error. The current estimator consumes orientation directly, so orientation
degradation matters even though it does not propagate gyro/acceleration.

## Running

First source Jazzy, the workspace providing **generated Stonefish ROS messages**,
and the Neptune installation. For a normal workspace install:

```bash
source /opt/ros/jazzy/setup.bash
# Source your Stonefish workspace's install/setup.bash here.
source /home/swarmx/project-neptune/install/setup.bash
```

If building with temporary writable directories instead:

```bash
source /opt/ros/jazzy/setup.bash
colcon --log-base /tmp/neptune-s22-log build \
  --build-base /tmp/neptune-s22-build \
  --install-base /tmp/neptune-s22-install --packages-select neptune_sim
source /tmp/neptune-s22-install/setup.bash
```

In the S2.2 validation environment, generated `stonefish_ros2` messages were
unavailable. The command above therefore failed on the missing dependency's
`package.sh`. Package installation was checked successfully by adding
`--packages-ignore stonefish_ros2` to that build command. This does not install
the dependency: running the executable still requires a real Stonefish overlay.

Clean pass-through (all defaults):

```bash
ros2 run neptune_sim sensor_degrader
```

Example configuration for future use: DVL sensor-x bias 0.01 m/s and
independent 0.005 m/s noise on all DVL velocity axes:

```bash
ros2 run neptune_sim sensor_degrader --ros-args \
  -p seed:=42 -p dvl_bias_x:=0.01 \
  -p dvl_noise_std_x:=0.005 -p dvl_noise_std_y:=0.005 \
  -p dvl_noise_std_z:=0.005
```

In separate sourced terminals, run the existing nodes with these exact remaps
instead of running additional unremapped copies of those nodes:

```bash
ros2 run neptune_state_estimation dead_reckoning_state --ros-args \
  -r /sim/dvl:=/degraded/dvl -r /sim/imu:=/degraded/imu

ros2 run neptune_state_estimation pressure_depth --ros-args \
  -r /sim/pressure:=/degraded/pressure
```

`/estimate/depth` and `/state/odometry` retain their existing interfaces.
These are usage examples, not S2.3–S2.5 experiments.

## Diagnostics and limitations

Cumulative received/published/dropped counts for all three sensors are logged
every five seconds of steady wall time, including when simulation time pauses.
IMU dropout is not implemented; its dropped counter remains zero. DVL and
pressure dropout probabilities 0 and 1 never and always drop respectively.
Dropped samples produce no output, and original timestamps are never shifted.

Each sensor has an independent standard-library PRNG derived from `seed` and
its sensor name, so cross-sensor callback interleaving does not affect results.
Reproducibility assumes the same ordered input sequence **received by the node**,
parameters, and Python runtime. Transport loss or changed within-sensor ordering
can change that sequence. Inputs use sensor-data best-effort QoS; outputs use
reliable depth-10 QoS to match the existing estimators. Counters describe this
node's actions, not downstream DDS delivery.

No latency, jitter, drift, burst dropout, bottom-lock model, covariance inflation,
or performance benchmarking is implemented. Covariances remain those of the raw
sensor and do not represent injected noise. No extra math dependency is needed.

## Validation in this workspace

`python3 -m compileall -q src/neptune_sim` passed. With Jazzy sourced and
`PYTHONPATH=src/neptune_sim:$PYTHONPATH`, `python3 -m pytest -q
src/neptune_sim/test` passed all 23 tests. Tests cover pass-through and copied
metadata, all required biases, dropout endpoints, seed reproducibility and
variation, sensor-stream independence, quaternion normalization/convention,
parameter validation, callback counters, and diagnostics. Callback tests prefer
generated DVL messages when installed; this environment uses a schema-shaped
DVL substitute and real ROS Imu/FluidPressure messages.

The normal selected-package build failed because the existing `log/` directory
is not writable. The requested temporary-directory build then failed because
`stonefish_ros2` is not built. The packaging-only fallback succeeded:

```bash
colcon --log-base /tmp/neptune-s22-log build \
  --build-base /tmp/neptune-s22-build \
  --install-base /tmp/neptune-s22-install \
  --packages-select neptune_sim --packages-ignore stonefish_ros2
source /tmp/neptune-s22-install/setup.bash
ros2 pkg executables neptune_sim
# neptune_sim sensor_degrader
```

No live Stonefish graph or S2.3 benchmark was run. Generated Stonefish messages
must be available before executing the node; executable registration alone does
not validate runtime transport.
