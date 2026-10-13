"""Start only the observation node; no simulator, autonomy or commands."""

from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('neptune_perception')) / 'config'
    return LaunchDescription([Node(
        package='neptune_perception', executable='inspection_objects',
        name='inspection_objects', output='screen',
        parameters=[str(config / 'inspection_objects.yaml')],
    )])
