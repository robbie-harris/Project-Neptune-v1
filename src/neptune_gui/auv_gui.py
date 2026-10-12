#!/usr/bin/env python3
"""Native Mac GUI for the pool AUV: drive the thrusters, see the camera and YOLO inspection detections.

Connects to the bridge in the container (localhost:9090). Standard library only (tkinter).
Hold W/S forward/back, A/D turn left/right, R/F up/down. Release cuts thrust; Space stops all.
"""
from collections import deque
import argparse
import logging
import math
import json
import queue
import socket
import threading
import time
import tkinter as tk
from controls import ManualControls, KEY_AXES

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("host", nargs="?", default="localhost")
parser.add_argument("port", nargs="?", type=int, default=9090)
parser.add_argument("--preview", choices=["raw", "annotated"], default="annotated")
parser.add_argument("--diagnostics", action="store_true")
options = parser.parse_args()
HOST, PORT = options.host, options.port
logging.basicConfig(level=logging.INFO if options.diagnostics else logging.WARNING)
SEND_MS = 100
POLL_MS = 33
BG, FG, ACCENT, WARN = "#1e2227", "#e6e6e6", "#4fb3d9", "#e5534b"


class Link:
    """Background TCP client with automatic reconnect."""

    def __init__(self):
        self.inbox = queue.Queue(maxsize=30)
        self.sock = None
        self.connected = False
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            s = None
            try:
                s = socket.create_connection((HOST, PORT), timeout=2)
                s.settimeout(None)
                self.sock, self.connected = s, True
                buf = b""
                while True:
                    data = s.recv(65536)
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            payload = json.loads(line)
                            if self.inbox.full(): self.inbox.get_nowait()
                            self.inbox.put_nowait(payload)
                        except ValueError:
                            pass
            except OSError:
                pass
            if s is not None: s.close()
            self.connected, self.sock = False, None
            time.sleep(1.0)

    def send_preview(self, preview):
        self.send_payload({'preview':preview})

    def send_cmd(self, cmd):
        self.send_payload({'cmd':cmd})

    def send_payload(self, payload):
        s = self.sock
        if s is None:
            return
        try:
            s.sendall((json.dumps(payload) + "\n").encode())
        except OSError:
            pass


class App:
    def __init__(self, root):
        self.root = root
        self.link = Link()
        self.controls = ManualControls()
        self.release_jobs = {}
        self.applied_command = [0., 0., 0.]
        self.photo = None
        self.overview_photo=None
        self.overview_at=0.
        self.preview_reported = set()
        self.reported_detector_state = None
        self.detection_reported = False
        self.sensors_reported = False
        self.frame_times = deque(maxlen=30)
        self.last_send = 0.0
        self.fps_report_at = 0.0

        root.title("Neptune — Inspection Perception")
        root.configure(bg=BG)
        root.resizable(False, False)

        self.status = tk.Label(root, text="Connecting...", bg=BG, fg=WARN, anchor="w", font=("Helvetica", 12, "bold"))
        self.status.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 2))

        # Keep STOP visible even on smaller screens; video and telemetry scroll together.
        body=tk.Frame(root,bg=BG); body.grid(row=1,column=0,columnspan=2,sticky='nsew')
        viewport=tk.Canvas(body,bg=BG,highlightthickness=0,width=1100,height=min(790,max(400,root.winfo_screenheight()-190)))
        viewport.pack(side='left',fill='both',expand=True)
        scrollbar=tk.Scrollbar(body,orient='vertical',command=viewport.yview); scrollbar.pack(side='right',fill='y')
        viewport.configure(yscrollcommand=scrollbar.set)
        content=tk.Frame(viewport,bg=BG); viewport.create_window(0,0,window=content,anchor='nw')
        content.bind('<Configure>',lambda e:viewport.configure(scrollregion=viewport.bbox('all'),width=content.winfo_reqwidth()))
        root.bind('<MouseWheel>',lambda e:viewport.yview_scroll(-int(e.delta/120 if abs(e.delta)>=120 else e.delta),'units'))
        self.canvas = tk.Canvas(content, width=640, height=480, bg="#000", highlightthickness=1, highlightbackground="#444")
        self.canvas.grid(row=1, column=0, padx=10, pady=6, sticky="n")
        self.canvas.create_text(320, 240, text="waiting for camera", fill="#888", tags="hint")

        overview=tk.Frame(content,bg=BG); overview.grid(row=2,column=0,padx=10,pady=(0,6),sticky='n')
        tk.Label(overview,text='TANK OVERVIEW · FIXED CAMERA',bg=BG,fg=ACCENT,font=('Helvetica',11,'bold')).pack(anchor='w')
        self.overview_canvas=tk.Canvas(overview,width=640,height=240,bg='#000',highlightthickness=1,highlightbackground='#444')
        self.overview_canvas.pack(); self.overview_canvas.create_text(320,120,text='waiting for tank overview',fill='#888',tags='hint')

        right = tk.Frame(content, bg=BG)
        right.grid(row=1, column=1, rowspan=2, padx=(0, 10), pady=6, sticky="n")

        tk.Label(right, text="OBJECT DETECTIONS", bg=BG, fg=ACCENT, font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.pose_vars = {}
        for key, label in [("state", "Model"), ("visible", "Objects"), ("confidence", "Confidence"),
                           ("bbox", "Box pixels"), ("latency", "Inference"), ("fps", "Feed FPS"), ("sensors", "Sensors"), ("reason", "Status")]:
            row = tk.Frame(right, bg=BG)
            row.pack(fill="x")
            tk.Label(row, text=label, bg=BG, fg="#9aa", width=12, anchor="w").pack(side="left")
            value = tk.StringVar(value="--")
            self.pose_vars[key] = value
            tk.Label(row, textvariable=value, bg=BG, fg=FG, wraplength=280, justify="left").pack(side="left")
        self.preview = tk.StringVar(value=options.preview)
        self.view_vars={'camera':tk.BooleanVar(value=True),'overview':tk.BooleanVar(value=True)}
        self.pending_views=None
        for key,label in [('camera','AUV camera view'),('overview','Tank overview')]:
            tk.Checkbutton(right,text=label,variable=self.view_vars[key],bg=BG,fg=FG,selectcolor=BG,command=self.set_views).pack(anchor='w')
        self.views_text=tk.StringVar(value='Views: waiting for simulator')
        tk.Label(right,textvariable=self.views_text,bg=BG,fg=FG,wraplength=440,justify='left').pack(anchor='w')
        for value in ("raw", "annotated"):
            tk.Radiobutton(right, text=value.title(), variable=self.preview, value=value,
                bg=BG, fg=FG, selectcolor=BG, command=lambda: self.link.send_preview(self.preview.get())).pack(anchor="w")
        self.realistic = tk.BooleanVar(value=False)
        tk.Checkbutton(right,text='Realistic sensor / camera errors',variable=self.realistic,
                       bg=BG,fg=FG,selectcolor=BG,command=self.set_errors).pack(anchor='w')
        self.pending_optics=None
        self.optics_vars={'natural':tk.BooleanVar(value=True),'lamps':tk.BooleanVar(value=True),
                          'water':tk.StringVar(value='clear'),'particles':tk.BooleanVar(value=False)}
        tk.Label(right,text='UNDERWATER OPTICS',bg=BG,fg=ACCENT,font=('Helvetica',12,'bold')).pack(anchor='w',pady=(8,0))
        for key,label in [('natural','Natural lighting'),('lamps','AUV lights'),('particles','Suspended particles')]:
            tk.Checkbutton(right,text=label,variable=self.optics_vars[key],bg=BG,fg=FG,
                           selectcolor=BG,command=self.set_optics).pack(anchor='w')
        water=tk.OptionMenu(right,self.optics_vars['water'],'clear','moderate','turbid',command=lambda _:self.set_optics())
        water.config(bg=BG,fg=FG,highlightthickness=0); water.pack(anchor='w')
        self.optics_text=tk.StringVar(value='Optics: waiting for simulator')
        tk.Label(right,textvariable=self.optics_text,bg=BG,fg=FG,wraplength=440,justify='left').pack(anchor='w')
        self.objects_text=tk.StringVar(value='No detections')
        tk.Label(right,textvariable=self.objects_text,bg=BG,fg=FG,wraplength=440,justify='left',font=('Menlo',12)).pack(anchor='w')
        tk.Label(right,text='TELEMETRY · ESTIMATE vs GROUND TRUTH',bg=BG,fg=ACCENT,font=('Helvetica',12,'bold')).pack(anchor='w',pady=(8,0))
        self.telemetry_text=tk.StringVar(value='Waiting for telemetry')
        tk.Label(right,textvariable=self.telemetry_text,bg=BG,fg=FG,justify='left',anchor='w',font=('Menlo',13),wraplength=440).pack(anchor='w')
        tk.Label(right,text='Pose score: 100% = match; 0% at ≥1 m or ≥15° error',bg=BG,fg='#9aa',font=('Helvetica',9),wraplength=320).pack(anchor='w')
        self.return_button=tk.Button(right,text='Return to spawn',command=self.return_to_spawn,highlightbackground=BG,state='disabled')
        self.return_button.pack(anchor='w',pady=(4,0))
        self.mission_text=tk.StringVar(value='Inspection: idle')
        tk.Label(right,textvariable=self.mission_text,bg=BG,fg=FG,wraplength=440,justify='left',font=('Menlo',12)).pack(anchor='w')
        self.mission_button=tk.Button(right,text='Start mapped inspection',command=self.start_inspection,highlightbackground=BG,state='disabled')
        self.mission_button.pack(anchor='w',pady=(4,0))
        self.autonomous_power=tk.DoubleVar(value=100.)
        self.power_applied=None;self.pending_power=None
        self.power_text=tk.StringVar(value='Autonomous power: waiting for simulator')
        self.autonomous_power_slider=tk.Scale(right,from_=20,to=100,resolution=5,orient='horizontal',
            label='Autonomous power (%)',variable=self.autonomous_power,bg=BG,fg=FG,highlightthickness=0,
            length=260,command=self.set_autonomous_power)
        self.autonomous_power_slider.pack(anchor='w')
        tk.Label(right,textvariable=self.power_text,bg=BG,fg=FG,wraplength=440,justify='left').pack(anchor='w')
        tk.Label(right,text='Adjusts inspection/return speed and translation thrust.\nDepth/yaw stabilization stays active. Lower settings may hit the 60 s cutoff.',
            bg=BG,fg='#9aa',wraplength=440,justify='left').pack(anchor='w')

        tk.Button(right,text='Stop mission',command=self.stop,highlightbackground=BG).pack(anchor='w')

        tk.Label(right, text="THRUSTER COMMANDS", bg=BG, fg=ACCENT, font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(12, 2))
        tk.Label(right, text="Horizontal + = forward; heave + = up", bg=BG, fg=FG).pack(anchor='w')
        self.bars = {}
        for name in ("Port", "Starboard", "Heave"):
            row = tk.Frame(right, bg=BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=name, bg=BG, fg="#9aa", width=10, anchor="w", font=("Menlo", 11)).pack(side="left")
            c = tk.Canvas(row, width=150, height=14, bg="#2b3038", highlightthickness=0)
            c.pack(side="left")
            c.create_line(75, 0, 75, 14, fill="#666")
            rect = c.create_rectangle(75, 2, 75, 12, fill=ACCENT, width=0)
            val = tk.Label(row, text="+0.0", bg=BG, fg=FG, width=5, font=("Menlo", 11))
            val.pack(side="left", padx=4)
            self.bars[name] = (c, rect, val)

        pad = tk.Frame(root, bg=BG)
        pad.grid(row=2, column=0, columnspan=2, pady=(2, 10))
        tk.Label(right, text="Hold keys/buttons to drive; release to cut thrust.\nW/S: forward/reverse · A/D: turn · R/F: up/down",
                 bg=BG, fg=FG, justify='left', wraplength=290).pack(anchor='w', pady=(10, 0))
        power = tk.Scale(right, from_=20, to=100, orient='horizontal', label='Manual power (%)',
                         bg=BG, fg=FG, highlightthickness=0, command=lambda x: setattr(self.controls, 'power', float(x)/100))
        power.set(60)
        power.pack(anchor='w')
        buttons = [('Up (R)',0,0,'r'),('Fwd (W)',0,1,'w'),('Down (F)',0,2,'f'),
                   ('Left (A)',1,0,'a'),('Back (S)',1,1,'s'),('Right (D)',1,2,'d')]
        for text, r, c, key in buttons:
            button = tk.Button(pad, text=text, width=9, highlightbackground=BG, takefocus=False)
            button.grid(row=r, column=c, padx=3, pady=2)
            button.bind('<ButtonPress-1>', lambda e,k=key: self.controls.press(k))
            button.bind('<ButtonRelease-1>', lambda e,k=key: self.release_control(k))
            button.bind('<Leave>', lambda e,k=key: self.release_control(k))
        tk.Button(pad, text="STOP (space)", width=14, command=self.stop, fg=WARN,
                  highlightbackground=BG).grid(row=0, column=3, rowspan=2, padx=(14, 0), sticky="ns")

        # Handle driving keys before widget class bindings (e.g. slider arrows).
        root.bind_class('NeptuneDrive', '<KeyPress>', self.on_key)
        root.bind_class('NeptuneDrive', '<KeyRelease>', self.on_release)
        def bind_drive(widget):
            widget.bindtags(('NeptuneDrive',) + widget.bindtags())
            for child in widget.winfo_children(): bind_drive(child)
        bind_drive(root)
        root.bind('<FocusOut>', lambda e: root.after_idle(self.check_focus))
        root.bind('<Deactivate>', lambda e: self.stop())
        root.bind('<Unmap>', lambda e: self.stop() if e.widget is root else None)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(POLL_MS, self.loop)

    def stop(self):
        self.controls.stop()
        self.link.send_cmd([0., 0., 0.])
        self.link.send_payload({'mission':'cancel'})

    def set_autonomous_power(self,value):
        percent=float(value)
        if self.power_applied is not None and abs(percent-self.power_applied)<.1 and self.pending_power is None:return
        self.pending_power=percent
        self.link.send_payload({'autonomous_power_percent':percent})
        self.power_text.set(f'Autonomous power: {percent:.0f}% pending')

    def set_optics(self):
        self.pending_optics={k:v.get() for k,v in self.optics_vars.items()}
        self.link.send_payload({'optics':self.pending_optics})
        self.optics_text.set('Optics: pending confirmation')

    def set_views(self):
        self.pending_views={k:v.get() for k,v in self.view_vars.items()}
        self.link.send_payload({'views':self.pending_views})
        self.views_text.set('Views: pending renderer confirmation')
        for key,canvas in [('camera',self.canvas),('overview',self.overview_canvas)]:
            if not self.pending_views[key]:
                canvas.delete('all');canvas.create_text(320,240 if key=='camera' else 120,text='View off',fill='#888')
        if not self.pending_views['camera']:self.frame_times.clear();self.pose_vars['fps'].set('off')

    def set_errors(self):
        selected=self.realistic.get()
        self.stop()
        self.link.send_payload({'realistic':selected})

    def return_to_spawn(self):
        self.stop()
        self.link.send_payload({'mission':'return'})

    def start_inspection(self):
        self.stop()
        self.link.send_payload({'mission':'inspect'})

    def check_focus(self):
        if self.root.focus_displayof() is None:
            self.stop()

    def release_control(self, key):
        self.controls.release(key)
        self.link.send_cmd(self.command())

    def on_key(self, e):
        k = e.keysym.lower()
        pending = self.release_jobs.pop(k, None)
        if pending is not None:
            self.root.after_cancel(pending)
        if k == "space":
            self.stop()
            return 'break'
        elif k in KEY_AXES:
            self.controls.press(k)
            return 'break'

    def on_release(self, e):
        k = e.keysym.lower()
        if k in KEY_AXES:
            # Tk on some platforms emits release/press pairs for auto-repeat.
            pending = self.release_jobs.pop(k, None)
            if pending is not None:
                self.root.after_cancel(pending)
            def release():
                self.release_jobs.pop(k, None)
                self.release_control(k)
            self.release_jobs[k] = self.root.after(20, release)
            return 'break'

    def command(self):
        return self.controls.command()

    def loop(self):
        now = time.monotonic()
        if now - self.last_send >= SEND_MS / 1000:
            self.link.send_cmd(self.command())
            self.link.send_preview(self.preview.get())
            self.last_send = now
        try:
            while True:
                self.handle(self.link.inbox.get_nowait())
        except queue.Empty:
            pass
        if self.link.connected:
            self.status.config(text=f"Connected to {HOST}:{PORT}", fg="#57ab5a")
        else:
            self.status.config(text=f"Not connected to {HOST}:{PORT} - is Neptune running?", fg=WARN)
            self.stop()
            self.applied_command = [0., 0., 0.]
            self.frame_times.clear()
            self.set_pose(None)
        if self.frame_times and time.monotonic()-self.frame_times[-1]>2:
            self.pose_vars["fps"].set("0.0")
        if self.overview_at and now-self.overview_at>2:
            self.overview_canvas.delete('all')
            self.overview_canvas.create_text(320,120,text='Tank overview unavailable',fill='#888')
            self.overview_at=0.
        self.draw_bars(self.applied_command)
        self.root.after(POLL_MS, self.loop)

    def handle(self, msg):
        if "state" in msg:
            self.set_pose(msg["state"])
        elif 'overview' in msg:
            if not self.view_vars['overview'].get():return
            try:
                self.overview_photo=tk.PhotoImage(data=msg['overview'])
                self.overview_canvas.delete('all')
                self.overview_canvas.create_image(0,0,anchor='nw',image=self.overview_photo)
                self.overview_at=time.monotonic()
                if 'overview' not in self.preview_reported:
                    logging.info('Tank overview rendered: %s x %s',self.overview_photo.width(),self.overview_photo.height())
                    self.preview_reported.add('overview')
            except tk.TclError as exc:
                logging.error('Tank overview failed: %s',exc)
        elif "img" in msg:
            if not self.view_vars['camera'].get():return
            try:
                self.photo = tk.PhotoImage(data=msg["img"])
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
                self.frame_times.append(time.monotonic())
                if len(self.frame_times) > 1:
                    fps = (len(self.frame_times)-1)/(self.frame_times[-1]-self.frame_times[0])
                    self.pose_vars["fps"].set(f"{fps:.1f}")
                    if self.frame_times[-1]-self.fps_report_at>=5:
                        logging.info("GUI feed FPS: %.2f", fps)
                        self.fps_report_at=self.frame_times[-1]
                actual_preview = msg.get("preview", self.preview.get())
                if actual_preview not in self.preview_reported:
                    logging.info("%s camera preview rendered: %s x %s", actual_preview, self.photo.width(), self.photo.height())
                    self.preview_reported.add(actual_preview)
            except tk.TclError as exc:
                self.pose_vars["reason"].set("Camera preview error: " + str(exc))
                logging.error("Camera preview failed: %s", exc)

    def set_pose(self, st):
        v = self.pose_vars
        if not st:
            for value in v.values(): value.set("--")
            self.telemetry_text.set('Telemetry unavailable')
            self.return_button.config(state='disabled')
            self.mission_button.config(state='disabled')
            self.mission_text.set('Inspection: telemetry unavailable')
            return
        self.applied_command = st.get('thrusters', [0., 0., 0.])
        self.realistic.set(st.get('realistic',False))
        optics=st.get('optics',{})
        views=st.get('views',{})
        confirmed_views=views.get('applied')
        self.views_text.set('Views: '+views.get('state','unavailable')+(' · '+views['reason'] if views.get('reason') else ''))
        if views.get('state')=='applied' and confirmed_views and (self.pending_views is None or confirmed_views==self.pending_views):
            self.pending_views=None
            for key,value in confirmed_views.items():self.view_vars[key].set(value)
            active=[k for k,v in confirmed_views.items() if v]
            self.views_text.set('Views: applied · '+('priority '+active[0] if len(active)==1 else 'both active' if active else 'both off; perception remains active'))
        confirmed=optics.get('applied')
        text='Optics: '+optics.get('state','unavailable')
        if confirmed:
            text+=f" · natural {'on' if confirmed['natural'] else 'off'}, lamps {'on' if confirmed['lamps'] else 'off'}, {confirmed['water']}, particles {'on' if confirmed['particles'] else 'off'}"
            if optics.get('state')=='applied' and (self.pending_optics is None or confirmed==self.pending_optics):
                self.pending_optics=None
                for k,val in confirmed.items(): self.optics_vars[k].set(val)
        if self.pending_optics is not None and optics.get('state')=='applied': text='Optics: pending; currently '+text.split(' · ',1)[-1]
        if optics.get('reason'): text+=' · '+optics['reason']
        self.optics_text.set(text)
        telemetry=st.get('telemetry',{})
        percent=telemetry.get('autonomous_power_percent')
        if isinstance(percent,(int,float)) and math.isfinite(percent) and 20<=percent<=100:
            self.power_applied=float(percent)
            if self.pending_power is not None and abs(percent-self.pending_power)<.1:self.pending_power=None
            if self.pending_power is None:
                self.autonomous_power.set(percent)
                self.power_text.set(f'Autonomous power: {percent:.0f}% applied')
            else:self.power_text.set(f'Autonomous power: {self.pending_power:.0f}% pending · applied {percent:.0f}%')
        else:self.power_text.set('Autonomous power: telemetry unavailable')
        inspection=telemetry.get('inspection',{})
        active=telemetry.get('autonomy',telemetry.get('return',{})).get('active',False)
        target=inspection.get('target') or {}
        mission_label='Inspection: '+inspection.get('state','unavailable')
        hold=inspection.get('perception_hold',{})
        if hold.get('active'):mission_label+=' · PAUSED: '+hold.get('reason','Waiting for perception')
        if inspection.get('state')=='returning':mission_label+=' · return to spawn'
        elif inspection.get('active'):mission_label+=f" · {inspection.get('waypoint',0)+1}/{inspection.get('total_waypoints',0)} · {target.get('label','inspection')}"
        if inspection.get('deadline_s')==60:mission_label+=' · 60 s limit'
        if inspection.get('reason'):mission_label+=' · '+inspection['reason']
        self.mission_text.set(mission_label)
        self.mission_button.config(state='normal' if telemetry.get('ready') and inspection.get('can_start') and not active else 'disabled')
        self.return_button.config(state='normal' if telemetry.get('ready') and not telemetry.get('return',{}).get('active') else 'disabled')
        est=telemetry.get('estimated',{}); truth=telemetry.get('ground_truth',{}); comparison=telemetry.get('comparison',{})
        fmt=lambda values: ', '.join(f'{x:.2f}' for x in values) if values else '--'
        norm=lambda values: f'{math.sqrt(sum(x*x for x in values)):.3f}' if values else '--'
        score=comparison.get('pose_accuracy_percent')
        mission=telemetry.get('return',{})
        lines=[f"XYZ est (m)   {fmt(est.get('position'))}",f"XYZ truth (m) {fmt(truth.get('position'))}",
               f"RPY est (°)   {fmt(est.get('rpy_deg'))}",f"RPY truth (°) {fmt(truth.get('rpy_deg'))}",
               f"Speed est/GT  {norm(est.get('velocity_world'))} / {norm(truth.get('velocity_world'))} m/s"]
        if est.get('pressure_pa') is not None and truth.get('pressure_pa') is not None:
            lines.append(f"Pressure kPa  {est['pressure_pa']/1000:.2f} / {truth['pressure_pa']/1000:.2f}")
        if score is not None:
            lines.extend([f"Pose accuracy {score:.1f}%",f"Error {comparison['position_error_m']:.3f} m / {comparison['attitude_error_deg']:.2f}°"])
        else: lines.append('Pose accuracy unavailable')
        if 'dvl_bottom_lock_valid' in telemetry:
            lines.append('DVL lock: '+('valid' if telemetry['dvl_bottom_lock_valid'] else 'temporarily lost'))
        lines.append('Return: '+mission.get('state','unavailable')+(' · '+mission['reason'] if mission.get('reason') else ''))
        self.telemetry_text.set('\n'.join(lines))
        detector = st.get("detector", {})
        state = detector.get("state", "unavailable")
        if state != self.reported_detector_state:
            logging.info("Detector state: %s; %s", state, detector.get("reason", ""))
            self.reported_detector_state = state
        boxes = detector.get("detections", [])
        self.objects_text.set('\n'.join(f"{d['class']}: {d['confidence']:.1%} · {[round(x) for x in d['bbox']]}" for d in boxes) or 'No detections')
        best = max(boxes, key=lambda box: box["confidence"], default=None)
        v["state"].set(detector.get("state", "unavailable"))
        v["visible"].set("Detected" if best else "Not visible")
        v["confidence"].set(f"{best['confidence']:.1%}" if best else "--")
        v["bbox"].set(str([round(x) for x in best['bbox']]) if best else "--")
        latency = detector.get("latency_ms")
        v["latency"].set(f"{latency:.1f} ms" if latency is not None else "--")
        v["sensors"].set(" | ".join(f"{k}: {'OK' if ok else 'stale'}" for k, ok in st.get("sensors", {}).items()))
        v["reason"].set("Camera stale" if detector.get("camera_stale") else detector.get("reason", ""))
        if best and not self.detection_reported:
            logging.info("Object displayed: confidence=%s bbox=%s latency=%s", v["confidence"].get(), v["bbox"].get(), v["latency"].get())
            self.detection_reported = True
        sensors = st.get("sensors", {})
        if not self.sensors_reported and all(sensors.get(k, False) for k in ["raw", "right", "down", "sonar", "imu", "pressure", "dvl"]):
            logging.info("All required sensor status indicators are current")
            self.sensors_reported = True

    def draw_bars(self, cmd):
        for (c, rect, val), x in zip(self.bars.values(), cmd):
            c.coords(rect, 75, 2, 75 + x * 73, 12)
            val.config(text=f"{x:+.1f}")

    def close(self):
        self.stop()
        self.link.send_cmd([0.0, 0.0, 0.0])
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
