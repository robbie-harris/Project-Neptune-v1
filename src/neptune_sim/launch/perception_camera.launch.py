"""Launch the optional perception scene and inspection-camera extrinsics."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('neptune_sim'))
    simulator = dict(
        package='stonefish_ros2', executable='stonefish_simulator',
        arguments=[LaunchConfiguration('simulation_data'),
                   LaunchConfiguration('scenario'), '100',
                   LaunchConfiguration('window_width'),
                   LaunchConfiguration('window_height'), 'low'],
        output='screen',
    )
    return LaunchDescription([
        # Existing Girona resources are owned by the supplied Stonefish data root.
        DeclareLaunchArgument('simulation_data'),
        DeclareLaunchArgument('software_rendering', default_value='false',
                             choices=['true', 'false']),
        DeclareLaunchArgument('window_width', default_value='800'),
        DeclareLaunchArgument('window_height', default_value='600'),
        DeclareLaunchArgument(
            'scenario', default_value=str(
                share / 'scenarios/benchmarks/03_port_pipe_perception.scn'),
        ),
        Node(**simulator,
             condition=UnlessCondition(LaunchConfiguration('software_rendering'))),
        Node(**simulator,
             condition=IfCondition(LaunchConfiguration('software_rendering')),
             additional_env={'GALLIUM_DRIVER': 'llvmpipe',
                             'LIBGL_ALWAYS_SOFTWARE': '1', 'LP_NUM_THREADS': '8'}),
        Node(
            package='tf2_ros', executable='static_transform_publisher',
            name='inspection_camera_mount_tf',
            arguments=['--x', '0.82', '--y', '0', '--z', '0.20',
                       '--roll', '0', '--pitch', '0', '--yaw', '0',
                       '--frame-id', 'base_link',
                       '--child-frame-id', 'inspection_camera_link'],
        ),
        Node(
            package='tf2_ros', executable='static_transform_publisher',
            name='inspection_camera_optical_tf',
            arguments=['--roll', '1.5707963267948966',
                       '--pitch', '0', '--yaw', '1.5707963267948966',
                       '--frame-id', 'inspection_camera_link',
                       '--child-frame-id', 'GIRONA500/inspection_camera_optical_frame'],
        ),
    ])
