"""Sensor dead reckoning, telemetry comparison and bounded return guidance."""
import math
import numpy as np


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def sensors_fresh(now, seen, sim_now, last_dvl_stamp, settings):
    # Stream watchdog stays in wall time; a configured lock-loss interval is in sim time.
    return (last_dvl_stamp is not None
            and all(0<=now-seen.get(k,float('-inf'))<settings['stream_timeout_s'] for k in ['imu','pressure','dvl_stream'])
            and -.02<=sim_now-last_dvl_stamp<settings['dvl_hold_sim_s'])


def rpy(q):
    x,y,z,w=q
    return np.array([math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),
                     math.asin(np.clip(2*(w*y-z*x),-1,1)),
                     math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))])


def quat(angles):
    r,p,y=np.asarray(angles)/2
    return [math.sin(r)*math.cos(p)*math.cos(y)-math.cos(r)*math.sin(p)*math.sin(y),
            math.cos(r)*math.sin(p)*math.cos(y)+math.sin(r)*math.cos(p)*math.sin(y),
            math.cos(r)*math.cos(p)*math.sin(y)-math.sin(r)*math.sin(p)*math.cos(y),
            math.cos(r)*math.cos(p)*math.cos(y)+math.sin(r)*math.sin(p)*math.sin(y)]


def rotation(angles):
    r,p,y=angles; cr,sr=math.cos(r),math.sin(r); cp,sp=math.cos(p),math.sin(p); cy,sy=math.cos(y),math.sin(y)
    return np.array([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],
                     [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])


def agreement(position, attitude, truth_position, truth_attitude, settings):
    pe=float(np.linalg.norm(np.asarray(position)-truth_position))
    # Quaternion geodesic angle avoids Euler wrap and singularities.
    dot=abs(float(np.dot(quat(attitude),quat(truth_attitude))))
    ae=math.degrees(2*math.acos(np.clip(dot,0,1)))
    score=100*(1-min(1,max(pe/settings['position_limit_m'],ae/settings['angle_limit_deg'])))
    return dict(position_error_m=pe,attitude_error_deg=ae,pose_accuracy_percent=score)


class DeadReckoning:
    def __init__(self, spawn):
        self.position=np.array(spawn['xyz'],dtype=float)
        self.attitude=np.array(spawn['rpy'],dtype=float)
        self.gyro=np.zeros(3); self.velocity=np.zeros(3); self.last_stamp=None

    def dvl(self, body_velocity, stamp):
        # DVL sits 18 cm below the body origin; remove rotational lever-arm velocity.
        velocity=rotation(self.attitude) @ (np.asarray(body_velocity)-np.cross(self.gyro,[0,0,.18]))
        if self.last_stamp is not None:
            dt=stamp-self.last_stamp
            if 0<dt<.75: self.position[:2]+=(self.velocity[:2]+velocity[:2])*.5*dt
        self.last_stamp=stamp; self.velocity=velocity


class ReturnGuidance:
    def __init__(self, spawn, settings):
        self.spawn=spawn; self.settings=settings; self.state='idle'; self.reason=''; self.started=0.; self.reverse=False

    def cancel(self, reason='Cancelled'):
        self.state='cancelled'; self.reason=reason

    def start(self, now):
        self.state='orient_initial'; self.started=now; self.reason=''; self.reverse=False

    @property
    def active(self):
        return self.state in ('orient_initial','translate','orient_final')

    def step(self, estimate, now, fresh=True):
        if not self.active: return [0.,0.,0.]
        if not fresh: self.cancel('Sensor data stale'); return [0.,0.,0.]
        if now-self.started>self.settings['timeout_s']: self.cancel('Return timed out'); return [0.,0.,0.]
        position=estimate.position; yaw=estimate.attitude[2]; initial=self.spawn['rpy'][2]
        tilt_settled=max(abs(estimate.attitude[:2]-np.asarray(self.spawn['rpy'][:2])))<.09
        offset=np.asarray(self.spawn['xyz'])-position; distance=float(np.linalg.norm(offset[:2]))
        if not (-4.4<position[0]<4.1 and abs(position[1])<2.5 and .2<position[2]<2.8):
            self.cancel('Estimated pose outside return operating envelope'); return [0.,0.,0.]
        heave=np.clip(-1.8*offset[2]+1.3*estimate.velocity[2],-self.settings['max_heave'],self.settings['max_heave'])
        target=initial; surge=0.
        if self.state=='orient_initial':
            heave=0.
            if abs(wrap(initial-yaw))<self.settings['heading_tolerance_rad'] and abs(estimate.gyro[2])<.03 and tilt_settled:
                self.state='translate'
                self.reverse=abs(wrap(math.atan2(offset[1],offset[0])-initial))>math.pi/2
        elif self.state=='translate':
            if distance<self.settings['position_tolerance_m'] and abs(offset[2])<self.settings['depth_tolerance_m']:
                self.state='orient_final'
            else:
                target=wrap(math.atan2(offset[1],offset[0])+(math.pi if self.reverse else 0))
                error=wrap(target-yaw)
                sign=-1 if self.reverse else 1
                desired=sign*min(.18,.7*distance)*max(0,math.cos(error)) if abs(error)<.55 else 0
                along=float(np.dot(estimate.velocity[:2],[math.cos(yaw),math.sin(yaw)]))
                effort=.8*(desired-along)
                surge=np.clip(math.copysign(math.sqrt(abs(effort)/.35),effort),-self.settings['max_surge'],self.settings['max_surge'])
        elif self.state=='orient_final':
            if distance>self.settings['position_tolerance_m']*1.5:
                self.state='translate'
            elif abs(wrap(initial-yaw))<self.settings['heading_tolerance_rad'] and tilt_settled and abs(offset[2])<self.settings['depth_tolerance_m'] and np.linalg.norm(estimate.velocity)<.04 and abs(estimate.gyro[2])<.025:
                self.state='complete'; return [0.,0.,0.]
            else:
                along=float(np.dot(estimate.velocity[:2],[math.cos(yaw),math.sin(yaw)]))
                surge=np.clip(-2*along,-.2,.2)
        effort=1.3*wrap(target-yaw)-1.7*estimate.gyro[2]
        yaw_cmd=float(np.clip(math.copysign(math.sqrt(abs(effort)/2),effort),-self.settings['max_yaw'],self.settings['max_yaw']))
        port,starboard=surge+yaw_cmd,surge-yaw_cmd; scale=max(1,abs(port),abs(starboard))
        return [float(port/scale),float(starboard/scale),float(heave)]
