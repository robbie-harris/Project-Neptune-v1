#!/usr/bin/env python3
"""Exercise real mission via GUI protocol. Ground truth is evaluation-only."""
import argparse,json,socket,threading,time,math
from pathlib import Path

class Link:
    def __init__(self):
        self.state={};self.socket=socket.create_connection(('localhost',9090),timeout=3)
        self.socket.settimeout(None);threading.Thread(target=self.read,daemon=True).start()
    def read(self):
        try:
            with self.socket.makefile('rb') as reader:
                for line in reader:
                    payload=json.loads(line)
                    if 'state' in payload:self.state=payload['state']
        except (OSError,ValueError):pass
    def send(self,p):self.socket.sendall((json.dumps(p)+'\n').encode())
    def close(self):self.socket.shutdown(socket.SHUT_RDWR);self.socket.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--camera-off',action='store_true');p.add_argument('--seconds',type=float,default=900);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    link=Link();started=time.monotonic();events=[];visits=[];seen=set();failure='';began=False;max_lateral_heading=0.;speeds=[]
    try:
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            link.send({'cmd':[0,0,0]});state=link.state
            if state.get('telemetry',{}).get('ready') and state.get('telemetry',{}).get('inspection',{}).get('can_start'):break
            time.sleep(.1)
        else:raise RuntimeError('Navigation or detector unavailable')
        if args.camera_off:
            link.send({'views':{'camera':False,'overview':True}})
            time.sleep(1)
        link.send({'mission':'inspect'});started=time.monotonic();last_phase=None
        while time.monotonic()-started<args.seconds:
            link.send({'cmd':[0,0,0]});state=link.state;telemetry=state.get('telemetry',{});mission=telemetry.get('inspection',{})
            phase=(mission.get('state'),mission.get('waypoint'))
            est=telemetry.get('estimated',{})
            if mission.get('state')=='travel':
                velocity=est.get('velocity_world',[])
                if velocity:speeds.append(math.sqrt(sum(x*x for x in velocity)))
                if mission.get('waypoint',0)>0 and est.get('rpy_deg'):max_lateral_heading=max(max_lateral_heading,abs(est['rpy_deg'][2]))
            if phase!=last_phase:
                event={'wall_seconds':time.monotonic()-started,'phase':phase,'target':mission.get('target'),'reason':mission.get('reason')}
                events.append(event);print(json.dumps(event),flush=True);last_phase=phase
            if mission.get('active'):began=True
            for i,v in enumerate(mission.get('visits',[])):
                if i not in seen:visits.append({**v,'ground_truth_at_report':telemetry.get('ground_truth')});seen.add(i)
            if began and not mission.get('active'):
                if mission.get('state')!='complete':failure=mission.get('reason') or 'Mission ended without completion'
                break
            time.sleep(.1)
        else:failure='Test wall timeout';link.send({'mission':'cancel'})
        truth=link.state.get('telemetry',{}).get('ground_truth',{})
        pos=truth.get('position');rpy=truth.get('rpy_deg');spawn_error=math.dist(pos,[-3.8,0,1.5]) if pos else None
        heading_error=abs((rpy[2]+180)%360-180) if rpy else None
        duration=time.monotonic()-started
        budget=link.state.get('telemetry',{}).get('inspection',{}).get('deadline_s')
        if budget and duration>budget and not failure:failure='Completed beyond configured wall-time budget'
        report={'passed':began and not failure and spawn_error is not None and spawn_error<.25 and heading_error is not None and heading_error<6,'failure':failure,'wall_seconds':duration,'camera_display_off':args.camera_off,
                'events':events,'visits':visits,'final_ground_truth':truth,'true_spawn_error_m':spawn_error,
                'true_final_heading_error_deg':heading_error,
                'max_lateral_body_heading_deg':max_lateral_heading,'max_travel_speed_m_s':max(speeds,default=0),
                'final_state':link.state,'ground_truth_used_for_control':False}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed'],'failure':failure,'spawn_error_m':spawn_error}),flush=True)
        if not report['passed']:raise SystemExit(1)
    finally:
        try:link.send({'mission':'cancel'});link.close()
        except OSError:pass
if __name__=='__main__':main()
