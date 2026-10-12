#!/usr/bin/env python3
"""Check native applied view profiles and enabled-only GUI transport."""
import argparse,json,socket,threading,time
from pathlib import Path
from collections import defaultdict

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    s=socket.create_connection(('localhost',9090));s.settimeout(None);state={};samples=defaultdict(list);reports=[]
    def read():
        try:
            with s.makefile('rb') as reader:
                for line in reader:
                    msg=json.loads(line)
                    if 'state' in msg:state.update(msg['state'])
                    for key in ('img','overview'):
                        if key in msg:samples[key].append(time.monotonic())
        except OSError:pass
    threading.Thread(target=read,daemon=True).start()
    def send(p):s.sendall((json.dumps(p)+'\n').encode())
    def wait(predicate,seconds=30):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            send({'cmd':[0,0,0]})
            if predicate():return
            time.sleep(.05)
        raise RuntimeError('View confirmation timed out: '+json.dumps(state.get('views',{})))
    try:
        wait(lambda:state.get('detector',{}).get('state')=='ready')
        for camera,overview in ((True,True),(True,False),(False,True),(False,False),(True,True)):
            profile={'camera':camera,'overview':overview};send({'views':profile})
            wait(lambda:state.get('views',{}).get('state')=='applied' and state['views'].get('applied')==profile)
            # Exclude in-flight frames sent before acknowledgement.
            until=time.monotonic()+1
            while time.monotonic()<until:send({'cmd':[0,0,0]});time.sleep(.05)
            start=time.monotonic();end=start+12
            while time.monotonic()<end:send({'cmd':[0,0,0]});time.sleep(.05)
            counts={k:sum(t>=start for t in samples[k]) for k in ('img','overview')}
            valid=(counts['img']>0 if camera else counts['img']==0) and (counts['overview']>0 if overview else counts['overview']==0)
            valid=valid and state.get('detector',{}).get('state')=='ready' and state.get('telemetry',{}).get('inspection',{}).get('can_start')
            r={'profile':profile,'passed':bool(valid),'counts':counts,'wall_feed_fps':{k:v/12 for k,v in counts.items()},'native':state['views']}
            reports.append(r);print(json.dumps(r),flush=True)
        args.output.write_text(json.dumps({'passed':all(r['passed'] for r in reports),'runs':reports},indent=2))
        if not all(r['passed'] for r in reports):raise SystemExit(1)
    finally:s.shutdown(socket.SHUT_RDWR);s.close()
if __name__=='__main__':main()
