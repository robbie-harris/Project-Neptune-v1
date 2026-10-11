#!/usr/bin/env python3
"""Test manual command wiring against actual simulated vehicle motion.

Close the GUI before running. A stop zeros thrust; it does not remove momentum.
"""
import argparse
import json
import math
from pathlib import Path
import socket
import threading
import time
import rclpy
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64MultiArray
from stonefish_ros2.srv import Respawn


def pose(msg):
    p=msg.pose.pose.position; q=msg.pose.pose.orientation
    return [p.x,p.y,p.z,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),
            math.atan2(2*(q.w*q.x+q.y*q.z),1-2*(q.x*q.x+q.y*q.y)),
            math.asin(max(-1,min(1,2*(q.w*q.y-q.z*q.x))))]


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default='/workspace/outputs/controls.json'); args=parser.parse_args()
    rclpy.init(); node=rclpy.create_node('neptune_verify_controls'); latest={}; results={}; errors=[]; conn=None
    node.create_subscription(Odometry,'/neptune/ground_truth',lambda m:latest.update(odom=m),10)
    node.create_subscription(Float64MultiArray,'/neptune/thrusters',lambda m:latest.update(command=list(m.data)),10)
    client=node.create_client(Respawn,'/stonefish_ros2/respawn_robot')
    def wait(predicate,timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.02)
            if predicate(): return
        raise TimeoutError('Control verification condition timed out')
    def reset():
        request=Respawn.Request(); request.name='Neptune'; request.origin.position.x=-3.8; request.origin.position.z=1.5; request.origin.orientation.w=1.0
        future=client.call_async(request); wait(future.done)
        if not future.result().success: raise RuntimeError(future.result().message)
        wait(lambda:'odom' in latest and abs(pose(latest['odom'])[0]+3.8)<.01 and abs(pose(latest['odom'])[2]-1.5)<.01)
        end=time.monotonic()+.3
        while time.monotonic()<end: rclpy.spin_once(node,timeout_sec=.02)
    def send(values): conn.sendall((json.dumps({'cmd':values})+'\n').encode())
    def drain(sock):
        try:
            while sock.recv(65536): pass
        except OSError: pass
    try:
        if not client.wait_for_service(timeout_sec=30): raise RuntimeError('Respawn service unavailable')
        wait(lambda:'odom' in latest)
        cases=[('forward',[.6,.6,0],0,1,8),('reverse',[-.6,-.6,0],0,-1,4),
               ('right',[.6,-.6,0],3,1,4),('left',[-.6,.6,0],3,-1,4),
               ('up',[0,0,.6],2,-1,4),('down',[0,0,-.6],2,1,4)]
        for axis,command,index,sign,duration in cases:
            reset(); before=pose(latest['odom']); conn=socket.create_connection(('localhost',9090),timeout=2); conn.settimeout(None)
            threading.Thread(target=drain,args=(conn,),daemon=True).start()
            end=time.monotonic()+duration; next_send=0; max_roll=0; max_yaw=0
            while time.monotonic()<end:
                if time.monotonic()>=next_send: send(command); next_send=time.monotonic()+.1
                rclpy.spin_once(node,timeout_sec=.02)
                observed=pose(latest['odom']); max_roll=max(max_roll,abs(observed[4])); max_yaw=max(max_yaw,abs(observed[3]))
            after=pose(latest['odom']); delta=after[index]-before[index]
            if index==3: delta=math.atan2(math.sin(delta),math.cos(delta))
            results[axis]={'command':command,'duration_seconds':duration,'before_xyz_yaw_roll_pitch':before,'after_xyz_yaw_roll_pitch':after,'signed_delta':delta,'max_abs_roll_rad':max_roll,'max_abs_yaw_rad':max_yaw,'passed':delta*sign>.001}
            if not results[axis]['passed']: errors.append(axis+' motion has wrong sign or is absent')
            if axis=='forward':
                if max_roll>.05 or max_yaw>.05: errors.append('Straight forward command causes excessive rotation (>0.05 rad)')
                if delta<.15: errors.append('Forward mobility below 0.15 m in eight seconds at 60% command')
            if axis in ('left','right') and max_roll>.1:
                errors.append(axis+' turn causes excessive roll (>0.1 rad)')
            send([0,0,0]); wait(lambda:latest.get('command')==[0,0,0],timeout=1)
            conn.shutdown(socket.SHUT_RDWR); conn.close(); conn=None
        # Disconnect while thrust is nonzero; verify bridge immediately zeros it.
        reset(); conn=socket.create_connection(('localhost',9090),timeout=2); conn.settimeout(None)
        threading.Thread(target=drain,args=(conn,),daemon=True).start(); send([.3,.3,0]); wait(lambda:latest.get('command')==[.3,.3,0])
        conn.shutdown(socket.SHUT_RDWR); conn.close(); conn=None; start=time.monotonic(); wait(lambda:latest.get('command')==[0,0,0],timeout=.5)
        results['disconnect_stop_seconds']=time.monotonic()-start; results['emergency_stop']='zero command observed after each axis'; reset()
    except Exception as exc: errors.append(str(exc))
    finally:
        if conn is not None:
            try: send([0,0,0]); conn.shutdown(socket.SHUT_RDWR); conn.close()
            except OSError: pass
        report={'passed':not errors,'errors':errors,'results':results,'stop_semantics':'zero thrust; vehicle may coast'}
        Path(args.output).parent.mkdir(parents=True,exist_ok=True); Path(args.output).write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
        node.destroy_node(); rclpy.shutdown()
    raise SystemExit(bool(errors))

if __name__=='__main__': main()
