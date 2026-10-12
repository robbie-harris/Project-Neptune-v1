"""Mapped inspection state machine. No simulator ground-truth inputs."""
import math
import time
import numpy as np
from .navigation import wrap, ReturnGuidance,thrust_commands,holonomic_commands,return_guidance


def inspection_route(position, settings):
    ends=[np.array(p,dtype=float) for p in settings['pipe_endpoints']]
    first=min(range(2),key=lambda i:np.linalg.norm(ends[i]-position))
    start,end=ends[first],ends[1-first]
    direction=(end-start)/np.linalg.norm(end-start)
    # Current rig's pipe axis is world Y; body faces +X at observation stops.
    def viewpoint(p):
        p=np.array(p,dtype=float);p[0]-=settings['body_standoff_m'];return p
    ordered=sorted(settings['components'],key=lambda c:np.linalg.norm(np.array(c['position'])-start))
    targets=[('closest pipe end',start+direction*settings['endpoint_inset_m'],'pipe')]
    targets += [(c['class'],np.array(c['position']),c['class']) for c in ordered]
    targets += [('far pipe end',end-direction*settings['endpoint_inset_m'],'pipe')]
    route=[];previous=None
    for label,p,required in targets:
        goal=viewpoint(p)
        if previous is not None:
            count=max(1,math.ceil(np.linalg.norm(goal-previous)/settings['scan_step_m']))
            for i in range(1,count):
                route.append({'label':'pipe scan','position':(previous+(goal-previous)*i/count).tolist(),'class':'pipe'})
        route.append({'label':label,'position':goal.tolist(),'class':required});previous=goal
    return route


def lateral_transit(position,goal,heading_deg):
    """Two shallow passes instead of a 90-degree lateral heading.

    First advance towards the pipe, then reverse away from it. Both body
    headings stay within the configured angle of the pipe-facing heading.
    """
    start=np.asarray(position);goal=np.asarray(goal);delta=goal-start
    tangent=math.tan(math.radians(heading_deg))
    advance=(abs(delta[1])/tangent+delta[0])/2
    retreat=advance-delta[0]
    if advance<=0 or retreat<=0 or abs(delta[1])<.15:return [goal.tolist()]
    middle=start.copy();middle[0]+=advance;middle[1]+=math.copysign(advance*tangent,delta[1]);middle[2]=goal[2]
    if middle[0]>=3.1:raise ValueError('Lateral transit would enter pipe clearance envelope')
    return [middle.tolist(),goal.tolist()]


class InspectionMission:
    def __init__(self, settings, spawn, return_settings):
        self.settings=settings;self.returner=return_guidance(spawn,{**return_settings,**settings.get('return',{})})
        self.state='idle';self.reason='';self.route=[];self.index=0;self.visits=[]
        self.started=0.;self.phase_started=0.;self.observations=[];self.last_stamp=None
        self.capture_seen=float('-inf');self.detector_ready=False;self.last_classes=set()
        self.observe_started=None
        self.camera_seen=float('-inf');self.camera_stamp=None
        self.hold_since=None;self.hold_reason='';self.detector_reason=''
        self.transit=[];self.transit_index=0
        self.observe_heading=0.

    @property
    def active(self):return self.state in ('acquire_pipe','travel','observe','returning')

    def health_reason(self,now):
        if now-self.camera_seen>=self.settings['camera_timeout_s']:return 'Forward camera frames stale'
        if not self.detector_ready:return self.detector_reason or 'Detector unavailable'
        if now-self.capture_seen>=self.settings['inference_timeout_s']:return 'Inference results stale'
        if self.hold_since is not None and (self.capture_seen<=self.hold_since or self.camera_seen<=self.hold_since):
            return 'Waiting for fresh camera and inference data'
        return ''

    def ready(self,now):return not self.health_reason(now)

    def camera(self,stamp,now,sim_now):
        if stamp==self.camera_stamp or not -.1<=sim_now-stamp<=self.settings['camera_timeout_s']:return
        self.camera_stamp=stamp;self.camera_seen=now

    def cancel(self, reason='Operator stop'):
        if self.state=='complete':return
        self.state='cancelled';self.reason=reason;self.returner.cancel(reason)
        self.hold_since=None;self.hold_reason=''

    def transition(self,state,now):
        self.state=state;self.phase_started=now;self.observations=[];self.observe_started=None
        if state=='travel':self.transit=[];self.transit_index=0
        if state=='observe':self.observe_heading=0.

    def start(self,estimate,now):
        self.route=inspection_route(estimate.position,self.settings);self.index=0;self.visits=[]
        self.started=now;self.reason='';self.transition('acquire_pipe',now)
        self.hold_since=None;self.hold_reason=''

    def detection(self,status,now,sim_now,position=None):
        self.detector_ready=status.get('state')=='ready'
        self.detector_reason=status.get('reason','') if not self.detector_ready else ''
        if not self.detector_ready:return
        stamp=status.get('stamp');key=(stamp.get('sec'),stamp.get('nanosec')) if isinstance(stamp,dict) else None
        if key is None or key==self.last_stamp:return
        self.last_stamp=key
        capture=key[0]+key[1]*1e-9
        if not -.1<=sim_now-capture<=self.settings['inference_timeout_s']:return
        self.capture_seen=now
        classes={d['class'] for d in status.get('detections',[]) if d.get('confidence',0)>=self.settings['confidence']}
        self.last_classes=classes
        moving=(self.settings.get('moving_confirmations',False) and self.state=='travel' and position is not None
                and self.transit_index==len(self.transit)-1 and np.linalg.norm(np.asarray(position)-self.route[self.index]['position'])<self.settings['confirmation_radius_m'])
        if self.hold_since is None and (self.state in ('acquire_pipe','observe') or moving):
            required='pipe' if self.state=='acquire_pipe' else self.route[self.index]['class']
            self.observations.append((now,required in classes))
            self.observations=self.observations[-self.settings['confirmation_frames']:]

    def visit(self,estimate,now):
        self.visits.append({'label':self.route[self.index]['label'],'class':self.route[self.index]['class'],'position':estimate.position.tolist()})
        self.index+=1
        if self.index==len(self.route):self.transition('returning',now);self.returner.start(now)
        else:self.transition('travel',now)

    def confirmed(self,now):
        return (len(self.observations)>=self.settings['confirmation_frames']
                and all(hit and now-t<self.settings['camera_timeout_s'] for t,hit in self.observations))

    def motion(self,estimate,goal,face_pipe=False):
        if self.settings.get('holonomic',False):
            return holonomic_commands(estimate,goal,self.settings,translate=not face_pipe)
        delta=np.asarray(goal)-estimate.position;distance=float(np.linalg.norm(delta[:2]))
        yaw=estimate.attitude[2]
        target=(self.observe_heading if self.state=='observe' else 0.) if face_pipe else math.atan2(delta[1],delta[0])
        reverse=False
        if not face_pipe and abs(wrap(target-yaw))>math.pi/2:
            target=wrap(target+math.pi);reverse=True
        if not face_pipe and self.index>0 and len(self.transit)==2:
            # Select thrust direction from the remaining X error, including
            # recovery after overshoot. A permanently reverse leg runs away
            # once the vehicle crosses its endpoint.
            reverse=delta[0]<0
            target=wrap(math.atan2(delta[1],delta[0])+(math.pi if reverse else 0))
            limit=math.radians(self.settings.get('travel_heading_limit_deg',self.settings['lateral_heading_deg']))
            target=float(np.clip(target,-limit,limit))
        error=wrap(target-yaw)
        along=float(np.dot(estimate.velocity[:2],[math.cos(yaw),math.sin(yaw)]))
        speed=0. if face_pipe else (-1 if reverse else 1)*min(self.settings['cruise_speed_m_s'],self.settings.get('distance_speed_gain',.65)*distance)*max(0,math.cos(error))
        if self.settings.get('smooth_alignment',False):speed*=max(0.,1-(abs(error)/self.settings['travel_alignment_rad'])**2)
        elif abs(error)>self.settings['travel_alignment_rad']:speed=0.
        effort=self.settings.get('speed_gain',.8)*(speed-along)
        surge_effort=effort/self.settings.get('speed_scale',.35)+self.settings.get('drag_feedforward',0)*speed*abs(speed)
        surge=float(np.clip(math.copysign(math.sqrt(abs(surge_effort)),surge_effort),-self.settings['max_surge'],self.settings['max_surge']))
        turn_effort=self.settings.get('yaw_gain',1.3)*error-self.settings.get('yaw_damping',1.7)*estimate.gyro[2]
        yaw_scale=self.settings.get('yaw_scale',2)
        turn=float(np.clip(math.copysign(math.sqrt(abs(turn_effort)/yaw_scale),turn_effort),-self.settings['max_yaw'],self.settings['max_yaw']))
        heave=float(np.clip(-1.8*delta[2]+1.3*estimate.velocity[2],-self.settings['max_heave'],self.settings['max_heave']))
        if self.settings.get('thrust_allocation',False):
            s=float(np.clip(surge_effort,-self.settings['max_surge']**2,self.settings['max_surge']**2))
            y=float(np.clip(turn_effort/yaw_scale,-self.settings['max_yaw']**2,self.settings['max_yaw']**2))
            return thrust_commands(s,y,heave),distance,abs(delta[2])
        port,starboard=surge+turn,surge-turn;scale=max(1,abs(port),abs(starboard))
        return [port/scale,starboard/scale,heave],distance,abs(delta[2])

    def step(self,estimate,now,fresh):
        zero=[0.]*(4 if self.settings.get('holonomic',False) else 3)
        if not self.active:return zero
        if not fresh:self.cancel('Navigation sensors stale');return zero
        if now-self.started>self.settings['timeout_s']:self.cancel('Mission timed out');return zero
        p=estimate.position
        if not (-4.4<p[0]<3.6 and abs(p[1])<2.5 and .25<p[2]<2.75):
            self.cancel('Estimated pose outside mission operating envelope');return zero
        if self.state=='returning':
            cmd=self.returner.step(estimate,now,fresh)
            if self.returner.state=='complete':self.state='complete'
            elif not self.returner.active:self.cancel(self.returner.reason)
            return cmd
        health=self.health_reason(now)
        if health:
            if self.hold_since is None:
                self.hold_since=now;self.observations=[]
            self.hold_reason=health
            if now-self.hold_since>=self.settings['perception_recovery_s']:
                self.cancel('Perception recovery timed out: '+health)
            return zero
        if self.hold_since is not None:
            elapsed=now-self.hold_since
            self.phase_started+=elapsed
            if self.observe_started is not None:self.observe_started+=elapsed
            self.hold_since=None;self.hold_reason='';self.observations=[]
        goal=self.route[self.index]['position']
        if self.state=='acquire_pipe':
            cmd,_,_=self.motion(estimate,[p[0],p[1],goal[2]],True)
            aligned=abs(wrap(estimate.attitude[2]))<self.settings['heading_tolerance_rad'] and abs(estimate.gyro[2])<self.settings.get('observation_rate_rad_s',.04)
            if aligned and self.confirmed(now):self.transition('travel',now)
            elif now-self.phase_started>self.settings['observation_timeout_s']:self.cancel('Pipe not visually confirmed')
            return cmd if self.active else zero
        if now-self.phase_started>self.settings['leg_timeout_s']:
            self.cancel('Inspection leg timed out');return zero
        if self.state=='travel':
            if not self.transit:
                try:self.transit=lateral_transit(p,goal,self.settings['lateral_heading_deg']) if self.index>0 and not self.settings.get('holonomic',False) else [goal]
                except ValueError as exc:self.cancel(str(exc));return zero
            destination=self.transit[self.transit_index]
            cmd,distance,depth=self.motion(estimate,destination)
            if (self.settings.get('moving_confirmations',False) and self.transit_index==len(self.transit)-1
                    and distance<self.settings['moving_visit_tolerance_m'] and depth<.08 and self.confirmed(now)
                    and (self.index<len(self.route)-1 or np.linalg.norm(estimate.velocity)<self.settings.get('final_visit_speed_max',float('inf')))):
                self.visit(estimate,now);return zero
            tolerance=self.settings['transit_tolerance_m'] if self.transit_index<len(self.transit)-1 else self.settings['position_tolerance_m']
            stop_speed=self.settings.get('corner_speed_max',.05) if self.transit_index<len(self.transit)-1 else .05
            if distance<tolerance and depth<.08 and np.linalg.norm(estimate.velocity)<stop_speed:
                self.transit_index+=1
                if self.transit_index==len(self.transit):
                    self.transition('observe',now)
                    if self.settings.get('keep_scan_heading',False):self.observe_heading=float(estimate.attitude[2])
                return zero
            return cmd
        cmd,distance,depth=self.motion(estimate,goal,True)
        if distance>self.settings['position_tolerance_m']*1.7:self.transition('travel',now);return zero
        aligned=abs(wrap(self.observe_heading-estimate.attitude[2]))<self.settings['heading_tolerance_rad'] and abs(estimate.gyro[2])<self.settings.get('observation_rate_rad_s',.04) and depth<.08
        if not aligned:
            self.observations=[];self.observe_started=None
        elif self.observe_started is None:self.observe_started=now
        if aligned and self.confirmed(now):
            self.visit(estimate,now)
        elif self.observe_started is not None and now-self.observe_started>self.settings['observation_timeout_s']:
            self.cancel('Target not confirmed: '+self.route[self.index]['class'])
        elif self.observe_started is not None and now-self.observe_started>3 and abs(self.observe_heading)>.1:
            self.observe_heading=0.;self.observe_started=None;self.observations=[]
        return cmd if self.active else zero

    def status(self):
        now=time.monotonic()
        age=lambda t:now-t if math.isfinite(t) else None
        return {'state':self.state,'active':self.active,'can_start':self.ready(time.monotonic()) and not self.active,'reason':self.reason,'waypoint':self.index,'total_waypoints':len(self.route),
                'profile':self.settings['name'],'deadline_s':self.settings['timeout_s'],'return_state':self.returner.state,
                'perception_hold':{'active':self.hold_since is not None,'reason':self.hold_reason,'elapsed_s':0 if self.hold_since is None else now-self.hold_since},
                'camera_age_s':age(self.camera_seen),'inference_age_s':age(self.capture_seen),
                'transit_leg':self.transit_index,'transit_legs':len(self.transit),
                'target':self.route[self.index] if self.index<len(self.route) else None,'visits':self.visits,
                'navigation':'mapped scene + IMU/DVL/pressure; visual confirmation'}
