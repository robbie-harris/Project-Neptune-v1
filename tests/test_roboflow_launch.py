"""ROS contract against a local fake Inference server; no model/secret required."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
import pytest
launch=pytest.importorskip('launch')
launch_testing=pytest.importorskip('launch_testing')
pytest.importorskip('rclpy')
import rclpy
from launch_ros.actions import Node
from launch_testing import actions, asserts
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.headers.get('Authorization')!='Bearer local-test-key' or 'api_key' in payload:
            self.send_error(403); return
        if self.path=='/model/add':
            self.server.load_requests+=1
            if self.server.load_requests==1:
                self.send_error(503); return
        result={'models':[]} if self.path=='/model/add' else {'image':{'width':640,'height':480},'predictions':[{'class':'pipe','x':320,'y':240,'width':80,'height':40,'confidence':.95}]}
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(json.dumps(result).encode())


@pytest.mark.launch_test
def generate_test_description():
    temporary=tempfile.TemporaryDirectory(); key=Path(temporary.name)/'key'; key.write_text('local-test-key')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.load_requests=0
    threading.Thread(target=server.serve_forever,daemon=True).start()
    detector=Node(package='neptune_perception',executable='pipe_detector',parameters=[{
        'backend':'roboflow','model_id':'test/model','api_key_file':str(key),
        'inference_url':f'http://127.0.0.1:{server.server_port}','use_sim_time':False,
        'image_topic':'/test_rf/input'}], remappings=[('/neptune/perception/annotated','/test_rf/output'),('/neptune/perception/pipe_detections','/test_rf/boxes')])
    return launch.LaunchDescription([detector,actions.ReadyToTest()]), {'server':server,'temporary':temporary}


class TestROSContract(unittest.TestCase):
    def test_recovers_and_preserves_timestamp_and_box_coordinates(self,server,temporary):
        rclpy.init(); node=rclpy.create_node('roboflow_contract_test'); images=[]; boxes=[]
        publisher=node.create_publisher(Image,'/test_rf/input',10)
        node.create_subscription(Image,'/test_rf/output',images.append,10)
        node.create_subscription(Detection2DArray,'/test_rf/boxes',boxes.append,10)
        frame=Image(); frame.header.stamp.sec=123; frame.header.stamp.nanosec=456; frame.header.frame_id='left_optical'
        frame.width=640; frame.height=480; frame.encoding='bgr8'; frame.step=640*3; frame.data=bytes(640*480*3)
        try:
            end=time.monotonic()+15
            while time.monotonic()<end and not (images and boxes):
                publisher.publish(frame); rclpy.spin_once(node,timeout_sec=.1)
            self.assertTrue(images); self.assertTrue(boxes)
            self.assertGreaterEqual(server.load_requests,2)
            self.assertEqual(images[-1].header,frame.header); self.assertEqual(boxes[-1].header,frame.header)
            detection=boxes[-1].detections[0]
            self.assertEqual(detection.header,frame.header)
            self.assertEqual(detection.bbox.center.position.x,320.)
            self.assertEqual(detection.bbox.size_x,80.)
            self.assertEqual(detection.results[0].hypothesis.class_id,'pipe')
        finally:
            node.destroy_node(); rclpy.shutdown(); server.shutdown(); temporary.cleanup()


@launch_testing.post_shutdown_test()
class TestCleanExit(unittest.TestCase):
    def test_exit_codes(self,proc_info): asserts.assertExitCodes(proc_info)
