"""Verify exact ideal bypass, upstream pixel/timestamp errors, and restoration."""
import time
import unittest
from pathlib import Path
import pytest
launch=pytest.importorskip('launch')
launch_testing=pytest.importorskip('launch_testing')
rclpy=pytest.importorskip('rclpy')
from launch_testing import actions, markers, asserts
from launch_ros.actions import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from rclpy.qos import QoSProfile, DurabilityPolicy
from ament_index_python.packages import get_package_share_directory


@pytest.mark.launch_test
@markers.keep_alive
def generate_test_description():
    profile=str(Path(get_package_share_directory('neptune_sim'))/'config/errors.json')
    node=Node(package='neptune_sim',executable='error_adapter',parameters=[{'profile':profile}])
    return launch.LaunchDescription([node,actions.ReadyToTest()])


class TestAdapter(unittest.TestCase):
    def test_ideal_realistic_ideal(self):
        rclpy.init(); node=rclpy.create_node('error_adapter_observer'); frames=[]
        pub=node.create_publisher(Image,'/neptune/ideal/camera/left/image_color',10)
        mode=node.create_publisher(Bool,'/neptune/simulation/realistic',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        node.create_subscription(Image,'/neptune/camera/left/image_color',lambda m:frames.append(m),10)
        def wait(predicate,timeout=10):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                rclpy.spin_once(node,timeout_sec=.02)
                if predicate(): return
            self.fail('Error adapter did not respond')
        def settle():
            end=time.monotonic()+.15
            while time.monotonic()<end: rclpy.spin_once(node,timeout_sec=.01)
        try:
            wait(lambda:pub.get_subscription_count()>0 and mode.get_subscription_count()>0)
            msg=Image(); msg.width=640; msg.height=480; msg.encoding='bgr8'; msg.step=1920
            msg.header.frame_id='Neptune/CameraLeft'; msg.header.stamp.sec=10; msg.data=bytes([100])*(640*480*3)
            mode.publish(Bool(data=False)); settle(); pub.publish(msg); wait(lambda:len(frames)>0)
            self.assertEqual(bytes(frames[-1].data),bytes(msg.data)); self.assertEqual(frames[-1].header,msg.header)
            mode.publish(Bool(data=True)); settle(); before=len(frames); pub.publish(msg); wait(lambda:len(frames)>before)
            self.assertNotEqual(bytes(frames[-1].data),bytes(msg.data)); self.assertNotEqual(frames[-1].header.stamp,msg.header.stamp)
            self.assertEqual(frames[-1].header.frame_id,msg.header.frame_id)
            mode.publish(Bool(data=False)); settle(); before=len(frames); pub.publish(msg); wait(lambda:len(frames)>before)
            self.assertEqual(bytes(frames[-1].data),bytes(msg.data)); self.assertEqual(frames[-1].header,msg.header)
        finally: node.destroy_node(); rclpy.shutdown()


@launch_testing.post_shutdown_test()
class TestExit(unittest.TestCase):
    def test_exit(self,proc_info): asserts.assertExitCodes(proc_info)
