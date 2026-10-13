"""Launch the P3 software performance profile; ordinary visual launch is separate."""

from pathlib import Path
from tempfile import TemporaryDirectory

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler,
)
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from neptune_sim.perception_profile import write_performance_scenario


def _launch_profile(context):
    share = Path(get_package_share_directory('neptune_sim'))
    temporary = TemporaryDirectory(prefix='neptune-perception-performance-')
    try:
        scenario = write_performance_scenario(share, temporary.name)
    except Exception:
        temporary.cleanup()
        raise

    def cleanup(_context):
        temporary.cleanup()
        return []

    return [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(share / 'launch/perception_camera.launch.py')),
            launch_arguments={
                'simulation_data': LaunchConfiguration('simulation_data').perform(context),
                'scenario': str(scenario),
                'software_rendering': 'true',
                'window_width': '160',
                'window_height': '120',
            }.items(),
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('simulation_data'),
        OpaqueFunction(function=_launch_profile),
    ])
