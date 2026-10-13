"""Start only the A1 robust pipe observer; physical orientation is unavailable."""

from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('neptune_perception')) / 'config'
    return LaunchDescription([Node(
        package='neptune_perception', executable='orientation_a',
        name='orientation_a', output='screen',
        parameters=[str(config / 'orientation_a.yaml')],
    )])
