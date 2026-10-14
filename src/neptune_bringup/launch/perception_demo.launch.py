"""One-command Demo V0: frozen graphics, onboard autonomy and read-only GUI."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, EmitEvent, OpaqueFunction, RegisterEventHandler,
    SetEnvironmentVariable, UnsetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit, OnShutdown
from launch.events import Shutdown
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from neptune_sim.perception_profile import write_performance_scenario


def _start(context):
    data = Path(LaunchConfiguration('simulation_data').perform(context))
    if not data.is_dir():
        raise RuntimeError('simulation_data must point to the existing Stonefish Tests/Data directory')
    # Read-only diagnostic; refuse a silent software fallback before movement.
    check = subprocess.run(['glxinfo', '-B'], capture_output=True, text=True, timeout=10,
                           env=dict(context.environment))
    if (check.returncode != 0 or 'D3D12 (NVIDIA' not in check.stdout
            or 'Accelerated: yes' not in check.stdout):
        raise RuntimeError('Demo V0 requires the validated accelerated NVIDIA D3D12 renderer')
    temporary = TemporaryDirectory(prefix='neptune-demo-v0-')
    try:
        scenario = write_performance_scenario(get_package_share_directory('neptune_sim'), temporary.name)
    except Exception:
        temporary.cleanup()
        raise

    def cleanup(_context):
        temporary.cleanup()
        return []

    nodes = [
        Node(package='stonefish_ros2', executable='stonefish_simulator',
             arguments=[str(data), str(scenario), '100', '1280', '720', 'low'], output='screen'),
        Node(package='neptune_vehicle', executable='stonefish_adapter',
             parameters=[{'motor_count': 7}], output='screen'),
        Node(package='neptune_state_estimation', executable='pressure_depth', output='screen'),
        Node(package='neptune_state_estimation', executable='dead_reckoning_state', output='screen'),
        Node(package='neptune_bringup', executable='demo_readiness', output='screen'),
        Node(package='neptune_autonomy', executable='mission_executive',
             parameters=[{'demo_mode': True,
                          'auto_start': ParameterValue(LaunchConfiguration('auto_start'), value_type=bool)}],
             output='screen'),
    ]
    gui = Node(package='neptune_bringup', executable='demo_gui', output='screen',
               condition=IfCondition(LaunchConfiguration('gui')),
               parameters=[{'evidence_directory': ParameterValue(
                   LaunchConfiguration('evidence_directory'), value_type=str)}])
    nodes.append(gui)
    actions = [RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)]))]
    for node in nodes:
        actions.append(RegisterEventHandler(OnProcessExit(
            target_action=node,
            on_exit=[EmitEvent(event=Shutdown(reason='A Demo V0 component exited'))],
        )))
    actions.extend(nodes)
    actions.extend([
        Node(package='tf2_ros', executable='static_transform_publisher',
             name='inspection_camera_mount_tf',
             arguments=['--x', '0.82', '--y', '0', '--z', '0.20',
                        '--frame-id', 'base_link', '--child-frame-id', 'inspection_camera_link']),
        Node(package='tf2_ros', executable='static_transform_publisher',
             name='inspection_camera_optical_tf',
             arguments=['--roll', '1.5707963267948966', '--yaw', '1.5707963267948966',
                        '--frame-id', 'inspection_camera_link',
                        '--child-frame-id', 'GIRONA500/inspection_camera_optical_frame']),
    ])
    return actions


def generate_launch_description():
    """Preserve legacy launches; Demo V0 never includes inference or P5."""
    actions = [
        DeclareLaunchArgument('simulation_data'),
        DeclareLaunchArgument('auto_start', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('gui', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('evidence_directory', default_value=''),
        SetEnvironmentVariable('GALLIUM_DRIVER', 'd3d12'),
        SetEnvironmentVariable('MESA_D3D12_DEFAULT_ADAPTER_NAME', 'NVIDIA'),
        SetEnvironmentVariable('LD_LIBRARY_PATH', [
            '/usr/lib/wsl/lib:', EnvironmentVariable('LD_LIBRARY_PATH', default_value=''),
        ]),
    ]
    for name in ('LIBGL_ALWAYS_SOFTWARE', 'MESA_LOADER_DRIVER_OVERRIDE',
                 'MESA_GL_VERSION_OVERRIDE', 'MESA_GLSL_VERSION_OVERRIDE'):
        actions.append(UnsetEnvironmentVariable(name))
    actions.append(OpaqueFunction(function=_start))
    return LaunchDescription(actions)
