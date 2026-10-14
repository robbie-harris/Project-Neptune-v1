"""Evaluation-only displacement recorder; never supplies a control input."""

import math
import time

from nav_msgs.msg import Odometry


class LateralMotionEvaluation:
    """Store truth privately; expose only a post-experiment displacement report."""

    def __init__(self, node):
        self.latest = self.origin = None
        self.samples = 0
        self.receipts = []
        self.history = []
        self.awaiting_origin = False
        self.subscription = node.create_subscription(Odometry, '/sim/odometry', self.receive, 10)

    def receive(self, message):
        """Retain the latest evaluation sample."""
        self.latest = message
        now = time.monotonic()
        self.receipts.append(now)
        pose, twist = message.pose.pose, message.twist.twist
        q = pose.orientation
        self.history.append({
            'receipt': now, 'stamp': message.header.stamp.sec+message.header.stamp.nanosec/1e9,
            'depth': pose.position.z,
            'yaw': math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)),
            'linear_velocity': [twist.linear.x, twist.linear.y, twist.linear.z],
            'angular_velocity': [twist.angular.x, twist.angular.y, twist.angular.z]})
        if self.awaiting_origin:
            self.origin = message
            self.awaiting_origin = False
        self.samples += 1

    def arm(self):
        """Start evaluation at the next sample, including startup drift."""
        self.origin = None
        self.awaiting_origin = True
        self.samples = 0

    def begin(self):
        """Mark the evaluation origin without returning truth to the caller."""
        self.origin = self.latest
        self.samples = 0

    def summary(self):
        """Report displacement projected onto the initial body lateral axis."""
        if self.origin is None or self.latest is None or not self.samples:
            return {'available': False}
        a, b = self.origin.pose.pose, self.latest.pose.pose
        q = a.orientation
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        dx, dy = b.position.x-a.position.x, b.position.y-a.position.y
        dz = b.position.z-a.position.z
        lateral = -math.sin(yaw)*dx+math.cos(yaw)*dy
        return {'available': True, 'body_lateral_displacement_m': lateral,
                'world_displacement_m': [dx, dy, dz], 'samples': self.samples,
                'initial_position_m': [a.position.x, a.position.y, a.position.z],
                'final_position_m': [b.position.x, b.position.y, b.position.z]}
