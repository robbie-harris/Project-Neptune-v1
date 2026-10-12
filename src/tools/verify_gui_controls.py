#!/usr/bin/env python3
"""Exercise the real Tk control handlers without commanding the simulator."""
import json
import base64
from pathlib import Path
import queue
import runpy
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/neptune_gui'))
sys.argv = ['auv_gui.py']
scope = runpy.run_path(str(ROOT / 'src/neptune_gui/auv_gui.py'), run_name='gui_test')


class FakeLink:
    connected = True
    def __init__(self): self.inbox = queue.Queue(); self.commands = []; self.payloads=[]
    def send_cmd(self, values): self.commands.append(values)
    def send_preview(self, preview): pass
    def send_payload(self, payload): self.payloads.append(payload)


App = scope['App']
App.__init__.__globals__['Link'] = FakeLink
root = scope['tk'].Tk()
app = App(root)
root.update(); root.focus_force(); root.update()
event = lambda key: SimpleNamespace(keysym=key)


def settle():
    end = time.monotonic() + .05
    while time.monotonic() < end:
        root.update(); time.sleep(.002)


results = {}
try:
    app.on_key(event('a')); app.on_release(event('a')); settle()
    for _ in range(50): app.on_key(event('w'))
    assert app.command() == [.6, .6, 0]
    # Simulate a platform's release/press auto-repeat pair.
    app.on_release(event('w')); app.on_key(event('w')); settle()
    assert app.command() == [.6, .6, 0]
    app.on_release(event('w')); settle()
    assert app.command() == [0, 0, 0]
    results['repeat_and_release'] = True
    app.on_key(event('w')); app.on_key(event('space')); app.on_key(event('w'))
    assert app.command() == [0, 0, 0]
    app.on_release(event('w')); settle(); app.on_key(event('w'))
    assert app.command() == [.6, .6, 0]
    results['emergency_stop_repeat_block'] = True
    app.on_release(event('w')); settle()
    def widgets(widget):
        yield widget
        for child in widget.winfo_children(): yield from widgets(child)
    slider = next(w for w in widgets(root) if isinstance(w, scope['tk'].Scale))
    slider.focus_force(); root.update()
    for _ in range(50): slider.event_generate('<KeyPress-Up>')
    settle()
    assert app.controls.power == .6 and app.command() == [.6, .6, 0]
    slider.event_generate('<KeyRelease-Up>'); settle()
    assert app.command() == [0, 0, 0]
    results['focused_slider_arrow_repeat'] = True
    app.realistic.set(True); app.set_errors()
    assert app.link.payloads[-1]=={'realistic':True} and app.command()==[0,0,0]
    app.return_to_spawn(); assert app.link.payloads[-1]=={'mission':'return'}
    app.start_inspection();assert app.link.payloads[-1]=={'mission':'inspect'}
    app.stop(); assert app.link.payloads[-1]=={'mission':'cancel'}
    app.set_pose({'realistic':True,'telemetry':{'ready':True,'estimated':{'position':[-3.8,0,1.5],'rpy_deg':[0,0,.2],'velocity_world':[0,0,0]},
                  'ground_truth':{'position':[-3.8,0,1.5],'rpy_deg':[0,0,0],'velocity_world':[0,0,0]},
                  'comparison':{'pose_accuracy_percent':98.,'position_error_m':.01,'attitude_error_deg':.2},'return':{'state':'idle','active':False}}})
    assert '98.0%' in app.telemetry_text.get() and app.realistic.get() and str(app.return_button['state'])=='normal'
    results['error_toggle_telemetry_return_button']=True
    app.optics_vars['natural'].set(False);app.optics_vars['water'].set('turbid');app.set_optics()
    assert app.link.payloads[-1]=={'optics':{'natural':False,'lamps':True,'water':'turbid','particles':False}}
    app.set_pose({'optics':{'state':'applied','applied':{'natural':False,'lamps':True,'water':'turbid','particles':True}},
                  'detector':{'state':'ready','detections':[{'class':'valve','confidence':.9,'bbox':[10,20,50,60]}]}})
    assert 'natural off' in app.optics_text.get() and 'turbid' in app.optics_text.get()
    assert 'valve: 90.0%' in app.objects_text.get()
    results['optics_toggle_confirmation_and_multiclass_listing']=True
    app.set_pose({'detector':{'state':'ready','detections':[]},'telemetry':{'ready':True,'autonomy':{'active':True},
                  'inspection':{'state':'travel','active':True,'waypoint':2,'total_waypoints':9,'target':{'label':'valve'}}}})
    assert 'valve' in app.mission_text.get() and str(app.mission_button['state'])=='disabled'
    app.set_pose({'telemetry':{'ready':True,'autonomy':{'active':True},'inspection':{'state':'travel','active':True,
                  'perception_hold':{'active':True,'reason':'Inference results stale'}}}})
    assert 'PAUSED' in app.mission_text.get() and 'Inference results stale' in app.mission_text.get()
    app.stop();assert app.link.payloads[-1]=={'mission':'cancel'}
    app.set_pose({'telemetry':{'ready':True,'inspection':{'state':'idle','can_start':True}}})
    assert str(app.mission_button['state'])=='normal'
    app.set_pose({'telemetry':{'ready':True,'inspection':{'state':'idle','can_start':False}}})
    assert str(app.mission_button['state'])=='disabled'
    results['mission_start_stop_and_progress']=True
    before=len(app.link.payloads)
    app.set_autonomous_power('65')
    assert app.link.payloads[-1]=={'autonomous_power_percent':65.}
    assert len(app.link.payloads)==before+1 and 'pending' in app.power_text.get()
    app.set_pose({'telemetry':{'ready':True,'autonomous_power_percent':65.,'autonomy':{'active':True},'inspection':{'state':'travel','active':True}}})
    settle()
    assert app.autonomous_power.get()==65 and app.pending_power is None and '65% applied' in app.power_text.get()
    results['autonomous_power_slider_and_confirmation']=True

    app.view_vars['overview'].set(False);app.set_views()
    assert app.link.payloads[-1]=={'views':{'camera':True,'overview':False}}
    app.set_pose({'views':{'state':'applied','applied':{'camera':True,'overview':False}}})
    assert 'priority camera' in app.views_text.get()
    app.view_vars['camera'].set(False);app.set_views()
    assert app.pose_vars['fps'].get()=='off'
    app.view_vars['camera'].set(True);app.view_vars['overview'].set(True);app.set_views()
    results['independent_view_switches_and_priority_confirmation']=True
    image=scope['tk'].PhotoImage(width=640,height=240)
    image.put('#ffcc00',to=(0,0,640,240))
    png=image.tk.call(image.name,'data','-format','png')
    app.handle({'overview':base64.b64encode(png).decode()}); root.update()
    assert app.overview_photo.width()==640 and app.overview_photo.height()==240
    assert app.overview_canvas.winfo_rooty()>app.canvas.winfo_rooty()+app.canvas.winfo_height()
    label=next(w for w in widgets(root) if isinstance(w,scope['tk'].Label) and str(w['textvariable'])==str(app.telemetry_text))
    assert '13' in str(label['font'])
    results['overview_below_feed_and_larger_telemetry']=True
    app.on_key(event('w'))
    root.withdraw(); root.update(); app.check_focus()
    assert app.command() == [0, 0, 0]
    results['focus_loss_stop'] = True
    print(json.dumps(dict(passed=True, results=results), indent=2))
finally:
    root.destroy()
