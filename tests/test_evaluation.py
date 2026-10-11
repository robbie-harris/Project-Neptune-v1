from evaluate import summarize


def row(truth,predicted,primary=True,angle=0):
    return {'truth_boxes':truth,'predicted_boxes':predicted,'scores':[.9]*len(predicted),'primary':primary,'angle_bin':angle,'latency_ms':10}


def test_matching_small_targets_and_angle_gate():
    box=[0,0,10,10]
    rows=[row([box],[box],angle=0),row([box],[],angle=1),row([box],[],primary=False),row([],[])]
    report=summarize(rows,.25)
    assert report['targets']==2 and report['hits']==1
    assert report['small_targets']['targets']==1
    assert report['negative_frame_fpr']==0 and not report['passed']
    report=summarize([row([box,box],[box]),row([],[])],.25)
    assert report['hits']==1 # One detection cannot match two targets.


def test_negatives_and_confidence_filtering():
    box=[0,0,10,10]; rows=[row([box],[box]),row([],[box])]
    assert summarize(rows,.25)['negative_frame_fpr']==1
    rows[1]['scores']=[.1]
    assert summarize(rows,.25)['passed']
