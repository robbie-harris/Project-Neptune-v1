#!/usr/bin/env python3
"""Fault-inject local inference pauses; heartbeat and sensor navigation stay live."""
import argparse,json,subprocess,time
from pathlib import Path
from verify_inspection_mission import Link

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    link=Link();paused=False;results={};snapshots={}
    def mission():return link.state.get('telemetry',{}).get('inspection',{})
    def wait(predicate,timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            link.send({'cmd':[0,0,0]})
            if predicate():return
            time.sleep(.05)
        raise RuntimeError('Recovery condition timed out: '+json.dumps(mission()))
    def pause():
        nonlocal paused
        subprocess.run(['docker','pause','neptune-inference'],check=True,stdout=subprocess.DEVNULL);paused=True
    def unpause():
        nonlocal paused
        subprocess.run(['docker','unpause','neptune-inference'],check=True,stdout=subprocess.DEVNULL);paused=False
    def start():
        wait(lambda:link.state.get('telemetry',{}).get('ready') and mission().get('can_start'),40)
        link.send({'mission':'inspect'});wait(lambda:mission().get('state')=='travel',30)
    try:
        start();index=mission()['waypoint'];pause()
        wait(lambda:mission().get('perception_hold',{}).get('active') and link.state.get('thrusters')==[0,0,0],8)
        snapshots['brief_hold']=json.loads(json.dumps(link.state))
        results['holds_with_zero_thrust']=link.state.get('thrusters')==[0,0,0] and mission().get('active')
        results['raw_camera_remains_fresh']=mission().get('camera_age_s',100)<3
        unpause();wait(lambda:mission().get('active') and not mission().get('perception_hold',{}).get('active'),20)
        results['resumes_same_waypoint']=mission()['waypoint']==index and mission()['state']=='travel'
        snapshots['resumed']=json.loads(json.dumps(link.state))
        link.send({'mission':'cancel'});wait(lambda:not mission().get('active'))
        start();pause();wait(lambda:not mission().get('active') and link.state.get('thrusters')==[0,0,0],40)
        snapshots['persistent_failure']=json.loads(json.dumps(link.state))
        results['persistent_failure_cancels']=mission().get('reason','').startswith('Perception recovery timed out') and link.state.get('thrusters')==[0,0,0]
        unpause();wait(lambda:mission().get('can_start'),30)
        results['no_restart_after_cancel']=not mission().get('active')
        report={'passed':all(results.values()),'results':results,'snapshots':snapshots}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed'],'results':results}),flush=True)
        if not report['passed']:raise SystemExit(1)
    finally:
        if paused:unpause()
        try:link.send({'mission':'cancel'});link.close()
        except OSError:pass
if __name__=='__main__':main()
