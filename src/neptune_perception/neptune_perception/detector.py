"""Latest-frame YOLO worker. Geometry/ground truth are never inputs."""
import copy
import hashlib
import json
import threading
import time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock
from rclpy.clock_type import ClockType
from rclpy.qos import qos_profile_sensor_data
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from .backends import RoboflowBackend, annotate, CLASSES, validate_model_names


class PipeDetector(Node):
    def __init__(self):
        super().__init__('pipe_detector')
        for name,value in [('backend','ultralytics'),('inference_url','http://neptune-inference:9001'),('model_id','projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t2'),('api_key_file','/run/secrets/roboflow_api_key'),('request_timeout',10.),('weights','/workspace/models/pipe/best.pt'),('image_topic','/neptune/camera/left/image_color'),('confidence',0.25),('imgsz',640),('device','cpu'),('cpu_threads',2)]:
            self.declare_parameter(name,value)
        self.cv=CvBridge(); self.lock=threading.Lock(); self.pending=None
        self.stop=threading.Event(); self.ready=threading.Event()
        self.model=None; self.status={'state':'loading','latency_ms':None,'detections':[]}
        self.boxes=self.create_publisher(Detection2DArray,'/neptune/perception/pipe_detections',10)
        self.objects=self.create_publisher(Detection2DArray,'/neptune/perception/object_detections',10)
        self.image=self.create_publisher(Image,'/neptune/perception/annotated',10)
        self.health=self.create_publisher(String,'/neptune/perception/status',10)
        self.create_subscription(Image,self.get_parameter('image_topic').value,self.receive,10)
        self.wall_clock=Clock(clock_type=ClockType.STEADY_TIME); self.create_timer(0.2,self.publish_status,clock=self.wall_clock)
        self.worker=threading.Thread(target=self.process,daemon=True); self.worker.start()

    def receive(self,msg):
        with self.lock: self.pending=msg
        self.ready.set()

    def publish_status(self):
        with self.lock: status=dict(self.status)
        self.health.publish(String(data=json.dumps(status)))

    def process(self):
        weights=Path(self.get_parameter('weights').value)
        backend=self.get_parameter('backend').value
        self.weights_sha256=None
        rf_loaded=False; next_retry=0.
        try:
            if backend=='roboflow':
                self.model=RoboflowBackend(self.get_parameter('inference_url').value,self.get_parameter('model_id').value,self.get_parameter('api_key_file').value,self.get_parameter('request_timeout').value)
                self.inference_device='roboflow-local'
                self.model.load()
                rf_loaded=True
            elif backend=='ultralytics':
                if not weights.is_file(): raise FileNotFoundError(f'Train/download pipe weights: {weights}')
                import torch
                from ultralytics import YOLO
                self.inference_device=torch.device(self.get_parameter('device').value)
                if self.inference_device.type=='cpu':
                    torch.set_num_threads(max(1,self.get_parameter('cpu_threads').value))
                self.model=YOLO(str(weights))
                validate_model_names(self.model.names)
                self.weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest()
            else:
                raise ValueError('Unknown detector backend')
            with self.lock: self.status={'state':'ready','latency_ms':None,'detections':[]}
        except Exception as exc:
            if backend!='roboflow': self.model=None
            next_retry=time.monotonic()+5
            with self.lock: self.status={'state':'unavailable','reason':str(exc),'latency_ms':None,'detections':[]}
            self.get_logger().error(str(exc))
        while not self.stop.is_set():
            self.ready.wait(0.2)
            with self.lock: msg,self.pending=self.pending,None; self.ready.clear()
            if msg is None or self.model is None: continue
            try:
                if backend=='roboflow' and not rf_loaded:
                    if time.monotonic()<next_retry: continue
                    self.model.load(); rf_loaded=True
                frame=self.cv.imgmsg_to_cv2(msg,desired_encoding='bgr8')
                start=time.perf_counter()
                if backend=='roboflow':
                    items=self.model.infer(frame,self.get_parameter('confidence').value)
                    latency=(time.perf_counter()-start)*1000
                    rendered=annotate(frame,items)
                else:
                    result=self.model.predict(frame,conf=self.get_parameter('confidence').value,
                        imgsz=self.get_parameter('imgsz').value,device=self.inference_device,verbose=False)[0]
                    latency=(time.perf_counter()-start)*1000
                    items=[{'class':self.model.names[int(box.cls[0])],'confidence':float(box.conf[0]),'bbox':list(map(float,box.xyxy[0].cpu().tolist()))} for box in result.boxes]
                    rendered=result.plot()
                arr=Detection2DArray(); arr.header=copy.deepcopy(msg.header)
                for item in items:
                    x1,y1,x2,y2=item['bbox']; score=item['confidence']
                    d=Detection2D(); d.header=copy.deepcopy(msg.header)
                    d.bbox.center.position.x=(x1+x2)/2; d.bbox.center.position.y=(y1+y2)/2
                    d.bbox.size_x=x2-x1; d.bbox.size_y=y2-y1
                    h=ObjectHypothesisWithPose(); h.hypothesis.class_id=item['class']; h.hypothesis.score=score
                    d.results.append(h); arr.detections.append(d)
                out=self.cv.cv2_to_imgmsg(rendered,encoding='bgr8'); out.header=copy.deepcopy(msg.header)
                self.objects.publish(arr)
                pipes=Detection2DArray(); pipes.header=copy.deepcopy(msg.header)
                pipes.detections=[d for d in arr.detections if d.results[0].hypothesis.class_id=='pipe']
                self.boxes.publish(pipes); self.image.publish(out)
                with self.lock: self.status={'state':'ready','latency_ms':latency,'detections':items,
                    'stamp':{'sec':msg.header.stamp.sec,'nanosec':msg.header.stamp.nanosec},
                    'backend':backend,'model_id':self.get_parameter('model_id').value if backend=='roboflow' else None,
                    'device':str(self.inference_device),'cpu_threads':torch.get_num_threads() if backend=='ultralytics' else None,'weights_sha256':self.weights_sha256,'confidence_threshold':self.get_parameter('confidence').value}
            except Exception as exc:
                if backend=='roboflow': rf_loaded=False; next_retry=time.monotonic()+5
                with self.lock: self.status={'state':'error','reason':str(exc),'latency_ms':None,'detections':[]}
                self.get_logger().error(str(exc))

    def destroy_node(self):
        self.stop.set(); self.ready.set(); self.worker.join(timeout=5)
        return super().destroy_node()


def main():
    rclpy.init(); node=PipeDetector()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.try_shutdown()
