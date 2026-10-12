#!/usr/bin/env python3
"""Live start/stop/override/heartbeat checks through the GUI bridge protocol."""
import argparse,json,time
from pathlib import Path
from verify_inspection_mission import Link

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();link=Link();results={}
    def wait(predicate,timeout=5,heartbeat=True):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if heartbeat:link.send({'cmd':[0,0,0]})
            if predicate():return
            time.sleep(.05)
        raise RuntimeError('Live control condition timed out: '+json.dumps(link.state.get('telemetry',{}).get('inspection',{})))
    def active():return link.state.get('telemetry',{}).get('inspection',{}).get('active',False)
    def start():
        link.send({'mission':'inspect'});wait(active)
    def stopped():return not active() and link.state.get('thrusters')==[0,0,0] and link.state.get('sway',0)==0
    try:
        wait(lambda:link.state.get('telemetry',{}).get('ready') and link.state.get('telemetry',{}).get('inspection',{}).get('can_start'),40)
        start();link.send({'mission':'cancel'});wait(stopped);results['start_and_operator_stop']=True
        start();link.send({'cmd':[.1,.1,0]});wait(lambda:not active(),heartbeat=False)
        results['manual_override']=link.state.get('telemetry',{}).get('inspection',{}).get('reason')=='Manual override'
        link.send({'cmd':[0,0,0]});wait(stopped)
        start();wait(stopped,3,heartbeat=False)
        results['heartbeat_stop']=link.state.get('telemetry',{}).get('inspection',{}).get('reason')=='GUI heartbeat timed out'
        start();link.close();time.sleep(1.2);link=Link()
        wait(stopped)
        results['disconnect_stop_all_axes']=link.state.get('telemetry',{}).get('inspection',{}).get('reason')=='GUI disconnected'
        report={'passed':all(results.values()),'results':results,'final_state':link.state}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed'],'results':results}))
        if not report['passed']:raise SystemExit(1)
    finally:
        try:link.send({'mission':'cancel'});link.close()
        except OSError:pass
if __name__=='__main__':main()
