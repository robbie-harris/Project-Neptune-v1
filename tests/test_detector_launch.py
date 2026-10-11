"""ROS integration: absent weights remain explicit and never emit fake boxes."""
import json
import time
import unittest
import pytest
launch=pytest.importorskip('launch')
launch_testing=pytest.importorskip('launch_testing')
pytest.importorskip('rclpy')
from launch_ros.actions import Node
from launch_testing import markers, actions
import rclpy
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray
from launch_testing import asserts

@pytest.mark.launch_test
@markers.keep_alive

def generate_test_description():
    detector=Node(package='neptune_perception',executable='pipe_detector',name='pipe_detector',
                  remappings=[('/neptune/perception/status','/test_pipe/status'),('/neptune/perception/pipe_detections','/test_pipe/detections')], parameters=[{'weights':'/nonexistent/neptune-pipe.pt','use_sim_time':False}])
    return launch.LaunchDescription([detector,actions.ReadyToTest()]), {'detector':detector}


class TestUnavailable(unittest.TestCase):
    def test_missing_model(self):
        rclpy.init(); node=rclpy.create_node('missing_model_test'); status=[]; boxes=[]
        node.create_subscription(String,'/test_pipe/status',lambda m:status.append(json.loads(m.data)),10)
        node.create_subscription(Detection2DArray,'/test_pipe/detections',lambda m:boxes.append(m),10)
        try:
            start=time.monotonic()
            while time.monotonic()-start<10 and not status: rclpy.spin_once(node,timeout_sec=.1)
            self.assertTrue(status)
            self.assertEqual(status[-1]['state'],'unavailable')
            self.assertIn('weights',status[-1]['reason'])
            self.assertEqual(boxes,[])
        finally: node.destroy_node(); rclpy.shutdown()


@launch_testing.post_shutdown_test()
class TestCleanExit(unittest.TestCase):
    def test_exit_codes(self,proc_info):
        asserts.assertExitCodes(proc_info)
