"""Sensor dead reckoning, telemetry comparison and bounded return guidance."""
import math
import numpy as np


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))

def thrust_commands(surge_effort,yaw_effort,heave):
    """Allocate signed thrust before applying the propeller square-root law."""
    def rotor(force):return math.copysign(math.sqrt(abs(force)),force)
    port=rotor(surge_effort+yaw_effort);starboard=rotor(surge_effort-yaw_effort)
    scale=max(1,abs(port),abs(starboard))
    return [port/scale,starboard/scale,float(heave)]


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
        target=initial; surge=0.;surge_effort=0.
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
                desired=sign*min(self.settings.get('cruise_speed_m_s',.18),self.settings.get('distance_speed_gain',.7)*distance)*max(0,math.cos(error)) if abs(error)<self.settings.get('travel_alignment_rad',.55) else 0
                along=float(np.dot(estimate.velocity[:2],[math.cos(yaw),math.sin(yaw)]))
                effort=self.settings.get('speed_gain',.8)*(desired-along)
                surge_effort=effort/self.settings.get('speed_scale',.35)+self.settings.get('drag_feedforward',0)*desired*abs(desired)
                surge=np.clip(math.copysign(math.sqrt(abs(surge_effort)),surge_effort),-self.settings['max_surge'],self.settings['max_surge'])
        elif self.state=='orient_final':
            if distance>self.settings['position_tolerance_m']*1.5:
                self.state='translate'
            elif abs(wrap(initial-yaw))<self.settings['heading_tolerance_rad'] and tilt_settled and abs(offset[2])<self.settings['depth_tolerance_m'] and np.linalg.norm(estimate.velocity)<.04 and abs(estimate.gyro[2])<.025:
                self.state='complete'; return [0.,0.,0.]
            else:
                along=float(np.dot(estimate.velocity[:2],[math.cos(yaw),math.sin(yaw)]))
                surge=np.clip(-2*along,-.2,.2)
        effort=self.settings.get('yaw_gain',1.3)*wrap(target-yaw)-self.settings.get('yaw_damping',1.7)*estimate.gyro[2]
        yaw_scale=self.settings.get('yaw_scale',2)
        yaw_cmd=float(np.clip(math.copysign(math.sqrt(abs(effort)/yaw_scale),effort),-self.settings['max_yaw'],self.settings['max_yaw']))
        if self.settings.get('thrust_allocation',False):
            if self.state=='translate':s=float(np.clip(surge_effort,-self.settings['max_surge']**2,self.settings['max_surge']**2))
            else:
                along=float(np.dot(estimate.velocity[:2],[math.cos(yaw),math.sin(yaw)]))
                s=-self.settings.get('speed_gain',.25)*along/self.settings.get('speed_scale',.35)
            y=float(np.clip(effort/yaw_scale,-self.settings['max_yaw']**2,self.settings['max_yaw']**2))
            return thrust_commands(s,y,heave)
        port,starboard=surge+yaw_cmd,surge-yaw_cmd; scale=max(1,abs(port),abs(starboard))
        return [float(port/scale),float(starboard/scale),float(heave)]


def holonomic_commands(estimate, goal, settings, heading=0., translate=True):
    """Four DOF command from estimated pose and DVL velocity, never ground truth."""
    delta=np.asarray(goal)-estimate.position
    distance=float(np.linalg.norm(delta[:2]))
    desired=delta[:2]*min(settings.get('cruise_speed_m_s',1.),settings.get('distance_speed_gain',1.2)*distance)/max(distance,1e-9) if translate else np.zeros(2)
    yaw=estimate.attitude[2]
    basis=np.array([[math.cos(yaw),math.sin(yaw)],[-math.sin(yaw),math.cos(yaw)]])
    wanted=basis@desired;actual=basis@estimate.velocity[:2]
    wanted[1]=np.clip(wanted[1],-settings.get('sway_cruise_speed_m_s',.55),settings.get('sway_cruise_speed_m_s',.55))
    surge=settings.get('speed_gain',.16)*(wanted[0]-actual[0])+settings.get('drag_feedforward',.075)*wanted[0]*abs(wanted[0])
    sway=settings.get('sway_gain',.35)*(wanted[1]-actual[1])+settings.get('sway_feedforward',.4)*wanted[1]*abs(wanted[1])
    turn=(settings.get('yaw_gain',2.)*wrap(heading-yaw)-settings.get('yaw_damping',2.)*estimate.gyro[2])/settings.get('yaw_scale',16.)
    heave_effort=-settings.get('heave_gain',.8)*delta[2]+settings.get('heave_damping',1.2)*estimate.velocity[2]
    heave=float(np.clip(math.copysign(math.sqrt(abs(heave_effort)),heave_effort),-settings['max_heave'],settings['max_heave']))
    commands=thrust_commands(float(np.clip(surge,-settings['max_surge']**2,settings['max_surge']**2)),float(np.clip(turn,-settings['max_yaw']**2,settings['max_yaw']**2)),heave)
    commands.append(float(np.clip(math.copysign(math.sqrt(abs(sway)),sway),-settings.get('max_sway',.95),settings.get('max_sway',.95))))
    return commands,distance,abs(delta[2])


class HolonomicReturnGuidance(ReturnGuidance):
    def step(self,estimate,now,fresh=True):
        zero=[0.]*4
        if not self.active:return zero
        if not fresh:self.cancel('Sensor data stale');return zero
        if now-self.started>self.settings['timeout_s']:self.cancel('Return timed out');return zero
        p=estimate.position
        if not(-4.4<p[0]<4.1 and abs(p[1])<2.5 and .2<p[2]<2.8):
            self.cancel('Estimated pose outside return operating envelope');return zero
        heading=self.spawn['rpy'][2]
        cmd,distance,depth=holonomic_commands(estimate,self.spawn['xyz'],self.settings,heading,self.state!='orient_initial')
        aligned=abs(wrap(heading-estimate.attitude[2]))<self.settings['heading_tolerance_rad'] and abs(estimate.gyro[2])<.03
        tilt_settled=max(abs(estimate.attitude[:2]-np.asarray(self.spawn['rpy'][:2])))<.09
        if self.state=='orient_initial' and aligned and tilt_settled:self.state='translate'
        elif self.state=='translate' and distance<self.settings['position_tolerance_m'] and depth<self.settings['depth_tolerance_m']:self.state='orient_final'
        elif self.state=='orient_final':
            if distance>self.settings['position_tolerance_m']*1.5:self.state='translate'
            elif aligned and depth<self.settings['depth_tolerance_m'] and np.linalg.norm(estimate.velocity)<.04 and max(abs(estimate.attitude[:2]-np.asarray(self.spawn['rpy'][:2])))<.09:
                self.state='complete';return zero
        return cmd


def return_guidance(spawn,settings):
    return (HolonomicReturnGuidance if settings.get('holonomic',False) else ReturnGuidance)(spawn,settings)
