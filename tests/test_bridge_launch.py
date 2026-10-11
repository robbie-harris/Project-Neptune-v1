"""The command watchdog must work even without a running simulation clock."""
import json
import socket
import time
import threading
import unittest
import pytest
launch=pytest.importorskip('launch')
launch_testing=pytest.importorskip('launch_testing')
pytest.importorskip('rclpy')
from launch_testing import markers, actions
from launch_ros.actions import Node
import rclpy
from std_msgs.msg import Float64MultiArray, String
from sensor_msgs.msg import Image
from launch_testing import asserts


@pytest.mark.launch_test
@markers.keep_alive
def generate_test_description():
    bridge=Node(package='neptune_sim',executable='bridge',name='bridge_watchdog_test',
        parameters=[{'use_sim_time':True,'port':19090}],remappings=[
            ('/clock','/test/paused_clock'),('/neptune/thrusters','/test/thrusters'),
            ('/neptune/camera/left/image_color','/test/no_camera'),
            ('/neptune/perception/annotated','/test/no_annotated'),
            ('/neptune/overview/image_color','/test/overview'),
            ('/neptune/telemetry','/test/telemetry'),
            ('/neptune/control/return_command','/test/return_command')])
    return launch.LaunchDescription([bridge,actions.ReadyToTest()])


class TestWatchdog(unittest.TestCase):
    def test_return_controller_timeout_heartbeat_and_disconnect(self):
        rclpy.init(); node=rclpy.create_node('return_watchdog_observer'); commands=[]
        node.create_subscription(Float64MultiArray,'/test/thrusters',lambda m:commands.append(list(m.data)),10)
        telemetry=node.create_publisher(String,'/test/telemetry',10)
        auto=node.create_publisher(Float64MultiArray,'/test/return_command',10)
        conn=None
        def tick(heartbeat=True,controller=True):
            telemetry.publish(String(data=json.dumps({'ready':True,'return':{'active':True}})))
            if controller: auto.publish(Float64MultiArray(data=[.25,.25,0.]))
            if heartbeat: conn.sendall(b'{"cmd":[0,0,0]}\n')
            rclpy.spin_once(node,timeout_sec=.02)
        def wait(predicate,heartbeat=True,controller=True,timeout=3):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                tick(heartbeat,controller)
                if predicate(): return
            self.fail('Return watchdog condition did not arrive')
        try:
            conn=socket.create_connection(('localhost',19090),timeout=5)
            wait(lambda:auto.get_subscription_count()>0 and telemetry.get_subscription_count()>0)
            for heartbeat,controller in [(True,False),(False,True)]:
                # Prime both ROS callbacks after each intentional timeout before arming.
                for _ in range(10): tick()
                conn.sendall(b'{"mission":"return"}\n')
                wait(lambda:bool(commands) and commands[-1]==[.25,.25,0.])
                wait(lambda:commands[-1]==[0.,0.,0.],heartbeat,controller,timeout=2)
            for _ in range(10): tick()
            conn.sendall(b'{"mission":"return"}\n')
            wait(lambda:commands[-1]==[.25,.25,0.])
            conn.close(); conn=None
            end=time.monotonic()+.5
            while time.monotonic()<end and commands[-1]!=[0.,0.,0.]: rclpy.spin_once(node,timeout_sec=.02)
            self.assertEqual(commands[-1],[0.,0.,0.])
        finally:
            if conn is not None: conn.close()
            node.destroy_node(); rclpy.shutdown()

    def test_timeout_and_disconnect_while_clock_paused(self):
        rclpy.init(); node=rclpy.create_node('watchdog_observer'); commands=[]
        node.create_subscription(Float64MultiArray,'/test/thrusters',lambda m:commands.append(list(m.data)),10)
        conn=None
        def wait(predicate,timeout=5):
            start=time.monotonic()
            while time.monotonic()-start<timeout:
                rclpy.spin_once(node,timeout_sec=.05)
                if predicate(): return
            self.fail('Thruster watchdog condition did not arrive')
        try:
            start=time.monotonic()
            while conn is None and time.monotonic()-start<10:
                try: conn=socket.create_connection(('localhost',19090),timeout=.5)
                except OSError: time.sleep(.1)
            self.assertIsNotNone(conn)
            wait(lambda:bool(commands))
            conn.sendall((json.dumps({'cmd':[.2,.2,0]})+'\n').encode())
            wait(lambda:commands[-1]==[.2,.2,0])
            wait(lambda:commands[-1]==[0,0,0],timeout=2)
            conn.sendall((json.dumps({'cmd':[.3,.3,0]})+'\n').encode())
            wait(lambda:commands[-1]==[.3,.3,0])
            conn.close(); conn=None
            wait(lambda:commands[-1]==[0,0,0],timeout=.5)
        finally:
            if conn is not None: conn.close()
            node.destroy_node(); rclpy.shutdown()


class TestPreviewRate(unittest.TestCase):
    def test_ten_hz_preview_without_duplicate_frames(self):
        rclpy.init(); node=rclpy.create_node('preview_rate_observer'); frames=[]; overview_frames=[]; errors=[]
        publisher=node.create_publisher(Image,'/test/no_camera',10)
        overview=node.create_publisher(Image,'/test/overview',10)
        conn=None
        def drain(sock):
            buffer=b''
            try:
                while True:
                    chunk=sock.recv(65536)
                    if not chunk: return
                    buffer+=chunk
                    while b'\n' in buffer:
                        line,buffer=buffer.split(b'\n',1); payload=json.loads(line)
                        if 'img' in payload: frames.append((time.monotonic(),payload['img']))
                        if 'overview' in payload: overview_frames.append(payload['overview'])
            except OSError: pass
            except Exception as exc: errors.append(str(exc))
        try:
            end=time.monotonic()+10
            while conn is None and time.monotonic()<end:
                try: conn=socket.create_connection(('localhost',19090),timeout=.5)
                except OSError: rclpy.spin_once(node,timeout_sec=.1)
            self.assertIsNotNone(conn); conn.settimeout(None)
            threading.Thread(target=drain,args=(conn,),daemon=True).start()
            end=time.monotonic()+5
            while not publisher.get_subscription_count() and time.monotonic()<end: rclpy.spin_once(node,timeout_sec=.05)
            self.assertGreater(publisher.get_subscription_count(),0)
            next_frame=0; sequence=0; end=time.monotonic()+4
            while time.monotonic()<end:
                now=time.monotonic()
                if now>=next_frame:
                    msg=Image(); msg.width=640; msg.height=480; msg.step=1920; msg.encoding='bgr8'
                    pixels=bytearray(640*480*3); pixels[0]=sequence; msg.data=bytes(pixels)
                    publisher.publish(msg); sequence+=1; next_frame=now+.1
                    if sequence%2==0:
                        image=Image(); image.width=640; image.height=240; image.step=1920; image.encoding='bgr8'
                        pixels=bytearray(640*240*3); pixels[0]=sequence; image.data=bytes(pixels); overview.publish(image)
                rclpy.spin_once(node,timeout_sec=.01)
            self.assertFalse(errors,errors)
            self.assertGreaterEqual(len(frames),32,'Preview still capped below 8 FPS')
            self.assertEqual(len(frames),len({data for _,data in frames}),'Repeated stale frames sent')
            self.assertLessEqual(len(frames),sequence)
            self.assertGreaterEqual(len(overview_frames),16,'Overview not streamed independently')
            self.assertEqual(len(overview_frames),len(set(overview_frames)),'Repeated stale overview frames')
        finally:
            if conn is not None: conn.shutdown(socket.SHUT_RDWR); conn.close()
            node.destroy_node(); rclpy.shutdown()


@launch_testing.post_shutdown_test()
class TestCleanExit(unittest.TestCase):
    def test_exit_codes(self,proc_info):
        asserts.assertExitCodes(proc_info)
