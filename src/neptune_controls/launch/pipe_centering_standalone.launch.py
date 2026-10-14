"""Explicit P5a command ownership; starts no mission or other controller."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('neptune_controls'))/'config/pipe_centering.yaml'
    return LaunchDescription([
        Node(package='neptune_controls', executable='pipe_centering',
             parameters=[str(config)], remappings=[
                 ('/neptune/control/alignment_cmd_body', '/neptune/cmd_body')]),
        Node(package='neptune_vehicle', executable='stonefish_adapter',
             parameters=[{'motor_count': 7}]),
    ])
