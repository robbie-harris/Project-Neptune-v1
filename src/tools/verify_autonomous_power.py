#!/usr/bin/env python3
"""Live power update/validation and full mission check via GUI protocol."""
import argparse,json,time,math
from pathlib import Path
from verify_inspection_mission import Link


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    link=Link();checks={};start=None
    def telemetry():return link.state.get('telemetry',{})
    def wait(predicate,timeout=5):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            link.send({'cmd':[0,0,0]})
            if predicate():return
            time.sleep(.05)
        raise RuntimeError('Condition timed out')
    try:
        wait(lambda:telemetry().get('ready') and telemetry().get('inspection',{}).get('can_start'),40)
        checks['default_100']=telemetry().get('autonomous_power_percent')==100
        link.send({'mission':'inspect'});start=time.monotonic()
        wait(lambda:telemetry().get('inspection',{}).get('state')=='travel')
        link.send({'autonomous_power_percent':60})
        wait(lambda:telemetry().get('autonomous_power_percent')==60)
        checks['live_60_without_cancel']=telemetry()['inspection']['active']
        for value in [True,19,101,'50',None]:link.send({'autonomous_power_percent':value})
        until=time.monotonic()+2
        while time.monotonic()<until:link.send({'cmd':[0,0,0]});time.sleep(.1)
        checks['invalid_ignored']=telemetry()['autonomous_power_percent']==60
        link.send({'autonomous_power_percent':100})
        wait(lambda:telemetry().get('autonomous_power_percent')==100)
        checks['restore_100_without_cancel']=telemetry()['inspection']['active']
        wait(lambda:not telemetry()['inspection']['active'],65)
        elapsed=time.monotonic()-start
        truth=telemetry().get('ground_truth',{})
        error=math.dist(truth['position'],[-3.8,0,1.5])
        checks['completed_full_cycle']=telemetry()['inspection']['state']=='complete' and elapsed<=60 and error<.25 and len(telemetry()['inspection']['visits'])==4
        report=dict(passed=all(checks.values()),checks=checks,wall_seconds=elapsed,true_spawn_error_m=error,final_state=link.state)
        args.output.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='final_state'}))
        if not report['passed']:raise SystemExit(1)
    finally:
        try:link.send({'mission':'cancel'});link.close()
        except OSError:pass

if __name__=='__main__':main()
