"""A1 robust pipe detector across viewpoints; no physical orientation output."""

from .core import A1_CLASSES, A1_MODEL_ID
from .detector import InspectionObjects, run


class OrientationA(InspectionObjects):
    node_name = 'orientation_a'
    model_id = A1_MODEL_ID
    expected_classes = A1_CLASSES
    inference_route = '/infer/orientation_a'
    detection_topic = '/neptune/perception/orientation_a_detections'
    annotated_topic = '/neptune/perception/orientation_a_annotated'
    status_topic = '/neptune/perception/orientation_a_status'
    reject_stale_completions = True


def main(args=None):
    run(OrientationA, args)
