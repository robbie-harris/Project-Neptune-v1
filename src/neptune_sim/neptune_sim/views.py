"""Display visibility and native renderer priority protocol."""
DEFAULTS={'camera':True,'overview':True}
def validate_views(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS) or any(type(v) is not bool for v in value.values()):
        raise ValueError('Views requires boolean camera and overview')
    return dict(value)
def view_rates(profile):
    p=validate_views(profile);both=p['camera'] and p['overview']
    return {'left':10 if p['camera'] else 5,'right':10 if p['camera'] else 5,
            'down':10 if both else 2,'sonar':10 if both else 2,
            'overview':(5 if p['camera'] else 10) if p['overview'] else 0}
