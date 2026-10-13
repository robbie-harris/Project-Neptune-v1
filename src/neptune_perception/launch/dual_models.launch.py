"""Both independent full-frame observers and pipe fusion only; no motion nodes."""

from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('neptune_perception')) / 'config'
    return LaunchDescription([Node(
        package='neptune_perception', executable=executable, name=executable,
        output='screen', parameters=[str(config / filename)])
        for executable, filename in [('inspection_objects', 'inspection_objects.yaml'),
                                     ('orientation_a', 'orientation_a.yaml'),
                                     ('pipe_fusion', 'pipe_fusion.yaml')]])
