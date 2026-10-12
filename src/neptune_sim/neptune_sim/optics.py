"""Validated optical profile protocol; rendering remains native Stonefish."""
WATER_PRESETS={'clear':.02,'moderate':.25,'turbid':.65}
DEFAULTS={'natural':True,'lamps':True,'water':'clear','particles':False}

def validate_profile(payload):
    if not isinstance(payload,dict) or set(payload)!=set(DEFAULTS):
        raise ValueError('Optics requires natural, lamps, water and particles')
    for name in ('natural','lamps','particles'):
        if not isinstance(payload[name],bool): raise ValueError(name+' must be boolean')
    if payload['water'] not in WATER_PRESETS: raise ValueError('Unknown water preset')
    return dict(payload)

def native_request(profile,request_id):
    p=validate_profile(profile)
    return [float(request_id),float(p['natural']),float(p['lamps']),WATER_PRESETS[p['water']],float(p['particles'])]

def applied_profile(values):
    if len(values)!=6 or values[5]!=1: raise ValueError('Native optical update failed')
    water=next((k for k,v in WATER_PRESETS.items() if abs(v-values[3])<1e-5),None)
    if water is None: raise ValueError('Native water preset mismatch')
    return {'natural':bool(values[1]),'lamps':bool(values[2]),'water':water,'particles':bool(values[4])}
