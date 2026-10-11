#!/usr/bin/env python3
"""Physical simulator verification through the same TCP protocol as the GUI.

Close other GUI clients first. No respawn/teleport or ground-truth controller.
"""
import argparse
import json
import math
from pathlib import Path
import socket
import threading
import time


def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); p.add_argument('--realistic-return',action='store_true'); args=p.parse_args()
    sock=socket.create_connection(('localhost',9090),timeout=10); sock.settimeout(None)
    lock=threading.Lock(); stopped=threading.Event(); latest={}; command=[0.,0.,0.]; results={}; errors=[]
    def send(payload):
        with lock: sock.sendall((json.dumps(payload)+'\n').encode())
    def reader():
        buf=b''
        try:
            while not stopped.is_set():
                block=sock.recv(65536)
                if not block: return
                buf+=block
                while b'\n' in buf:
                    line,buf=buf.split(b'\n',1); packet=json.loads(line)
                    if 'state' in packet: latest.clear(); latest.update(packet['state'])
        except OSError: pass
    def heartbeat():
        try:
            while not stopped.wait(.1): send({'cmd':list(command)})
        except OSError: pass
    def wait(predicate,timeout=20):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate(): return
            time.sleep(.02)
        raise TimeoutError('Operator verification timed out')
    def run(values,duration):
        command[:]=values; end=time.monotonic()+duration
        while time.monotonic()<end: time.sleep(.05)
        command[:]=[0.,0.,0.]; send({'cmd':list(command)}); time.sleep(.7)
    threading.Thread(target=reader,daemon=True).start(); threading.Thread(target=heartbeat,daemon=True).start()
    try:
        wait(lambda:latest.get('telemetry',{}).get('ready'))
        results['ideal_start']=latest['telemetry']
        send({'realistic':True}); wait(lambda:latest.get('telemetry',{}).get('realistic'))
        time.sleep(2); results['realistic_stationary']=latest['telemetry']
        send({'realistic':False}); wait(lambda:not latest.get('telemetry',{}).get('realistic',True))
        run([.6,.6,0],4); run([.6,-.6,0],4); run([.6,.6,0],4)
        if args.realistic_return:
            send({'realistic':True}); wait(lambda:latest.get('telemetry',{}).get('realistic'))
            time.sleep(.3)
        results['return_start']=latest['telemetry']
        print('Starting physical return sequence',flush=True)
        send({'mission':'return'}); stages=[]; end=time.monotonic()+180
        while time.monotonic()<end:
            stage=latest.get('telemetry',{}).get('return',{}).get('state')
            if stage and (not stages or stages[-1]!=stage):
                stages.append(stage); print('Return stage: '+stage,flush=True)
            if stage=='complete': break
            if stage=='cancelled' and len(stages)>1: raise RuntimeError(latest['telemetry']['return'].get('reason','Return cancelled'))
            time.sleep(.05)
        else: raise TimeoutError('Physical return did not complete')
        results['return_stages']=stages; results['return_end']=latest['telemetry']
        xyz=latest['telemetry']['ground_truth']['position']; target=[-3.8,0,1.5]
        distance=math.sqrt(sum((a-b)**2 for a,b in zip(xyz,target)))
        results['actual_spawn_error_m']=distance
        yaw=abs(latest['telemetry']['ground_truth']['rpy_deg'][2]); results['actual_final_yaw_deg']=yaw
        if distance>.2 or yaw>5: errors.append('Return ground-truth error exceeds 0.2 m / 5 degrees')
        if not all(stage in stages for stage in ['orient_initial','translate','orient_final','complete']): errors.append('Return stages missing')
        # Manual override must cancel an armed return.
        send({'mission':'return'}); command[:]=[.2,.2,0]; send({'cmd':list(command)})
        wait(lambda:latest.get('telemetry',{}).get('return',{}).get('state')=='cancelled',timeout=3)
        results['manual_override']=True; command[:]=[0.,0.,0.]; send({'cmd':list(command)})
        send({'mission':'return'}); send({'mission':'cancel'})
        wait(lambda:latest.get('telemetry',{}).get('return',{}).get('state')=='cancelled',timeout=3)
        results['stop_cancel']=True
    except Exception as exc:
        errors.append(str(exc)); results['failure_state']=dict(latest)
    finally:
        stopped.set()
        try: send({'cmd':[0.,0.,0.],'mission':'cancel','realistic':False}); sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        sock.close()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(dict(passed=not errors,errors=errors,results=results),indent=2))
        print(json.dumps(dict(passed=not errors,errors=errors),indent=2))
    raise SystemExit(bool(errors))


if __name__=='__main__': main()
