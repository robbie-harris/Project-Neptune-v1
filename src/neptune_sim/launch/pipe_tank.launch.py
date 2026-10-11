from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = Path(get_package_share_directory('neptune_sim'))
    stonefish = Path(get_package_share_directory('stonefish_ros2'))
    detector = Path(get_package_share_directory('neptune_perception'))
    return LaunchDescription([
        DeclareLaunchArgument('scenario', default_value=str(share/'scenarios/pipe_tank.scn')),
        DeclareLaunchArgument('weights', default_value='/workspace/models/pipe/best.pt'),
        DeclareLaunchArgument('backend', default_value='ultralytics'),
        DeclareLaunchArgument('inference_url', default_value='http://neptune-inference:9001'),
        DeclareLaunchArgument('model_id', default_value='projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t2'),
        DeclareLaunchArgument('api_key_file', default_value='/run/secrets/roboflow_api_key'),
        DeclareLaunchArgument('confidence', default_value=str(yaml.safe_load((detector/'config/detector.yaml').read_text())['pipe_detector']['ros__parameters']['confidence'])),
        DeclareLaunchArgument('quality', default_value='low'),
        DeclareLaunchArgument('realistic', default_value='false'),
        DeclareLaunchArgument('window_width', default_value='640'),
        DeclareLaunchArgument('window_height', default_value='480'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(stonefish/'launch/stonefish_simulator.launch.py')),
            launch_arguments={'simulation_data': str(share/'scenarios'),
                'scenario_desc': LaunchConfiguration('scenario'), 'simulation_rate': '100.0',
                'window_res_x': LaunchConfiguration('window_width'), 'window_res_y': LaunchConfiguration('window_height'),
                'rendering_quality': LaunchConfiguration('quality')}.items()),
        Node(package='neptune_sim', executable='rig_adapter', parameters=[{'use_sim_time': True, 'rig': str(share/'config/rig.json')}], output='screen'),
        Node(package='neptune_sim', executable='error_adapter', parameters=[{'use_sim_time':True,'profile':str(share/'config/errors.json')}], output='screen'),
        Node(package='neptune_sim', executable='operator_state', parameters=[{'use_sim_time':True,'rig':str(share/'config/rig.json'),'profile':str(share/'config/errors.json')}], output='screen'),
        Node(package='neptune_perception', executable='pipe_detector', name='pipe_detector',
             parameters=[str(detector/'config/detector.yaml'), {'weights': LaunchConfiguration('weights'),'backend':LaunchConfiguration('backend'),'inference_url':LaunchConfiguration('inference_url'),'model_id':LaunchConfiguration('model_id'),'api_key_file':LaunchConfiguration('api_key_file'),'confidence':ParameterValue(LaunchConfiguration('confidence'),value_type=float)}], output='screen'),
        Node(package='neptune_sim', executable='bridge', parameters=[{'use_sim_time': True,'realistic':ParameterValue(LaunchConfiguration('realistic'),value_type=bool)}], output='screen'),
    ])
