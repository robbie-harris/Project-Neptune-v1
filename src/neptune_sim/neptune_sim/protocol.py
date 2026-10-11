"""Small independently testable safety contract for the reused GUI bridge."""
import math

def command(payload):
    values=payload.get('cmd')
    if not isinstance(values,list) or len(values)!=3: raise ValueError('Expected three thruster commands')
    values=[float(v) for v in values]
    if not all(math.isfinite(v) for v in values): raise ValueError('Non-finite thruster command')
    return [max(-1.0,min(1.0,v)) for v in values]


def active_command(values,received_at,now,timeout=1.0):
    return list(values) if 0<=now-received_at<timeout else [0.0,0.0,0.0]
