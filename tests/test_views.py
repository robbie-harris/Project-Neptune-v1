import pytest
from neptune_sim.views import validate_views,view_rates

@pytest.mark.parametrize('camera,overview',[(True,True),(True,False),(False,True),(False,False)])
def test_view_modes_keep_perception_stereo_alive_and_prioritize_visible_feed(camera,overview):
    rates=view_rates({'camera':camera,'overview':overview})
    assert rates['left']==rates['right'] and rates['left']>=5
    assert (rates['overview']>0)==overview
    if camera!=overview:assert rates['down']==2 and rates['sonar']==2
    if overview and not camera:assert rates['overview']==10 and rates['left']==5

def test_malformed_visibility_is_rejected():
    for bad in ({'camera':1,'overview':True},{'camera':False},{'camera':True,'overview':False,'other':True}):
        with pytest.raises(ValueError):validate_views(bad)
