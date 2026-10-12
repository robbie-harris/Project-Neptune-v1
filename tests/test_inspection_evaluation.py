import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/tools'),str(ROOT/'src/neptune_perception')]
from evaluate_inspection import summarize


def row(class_name, predictions, water='clear', eligible=True):
    return {'boxes':[{'class':class_name,'bbox':[0,0,20,20],'eligible':eligible}],
            'predictions':predictions,'optics':{'water':water,'natural':True,'lamps':False,'particles':False},'rpy':[0,0,0]}


def prediction(class_name,confidence=.8):
    return {'class':class_name,'bbox':[0,0,20,20],'confidence':confidence}


def test_confusion_cannot_count_as_correct_detection():
    result=summarize([row('flange',[prediction('valve')])],.25)
    assert result['per_class_clear_moderate']['flange']['recall']==0
    assert result['class_confusion']=={'flange->valve':1}
    assert not result['accuracy_passed']


def test_recall_matching_small_and_turbid_are_separate():
    rows=[row(c,[prediction(c)]) for c in ('pipe','valve','flange')]
    rows+=[row('pipe',[],water='turbid'),row('flange',[],eligible=False)]
    rows+=[{'boxes':[],'predictions':[],'optics':{'water':'clear'},'rpy':[0,0,0]}]
    result=summarize(rows,.25)
    assert result['accuracy_passed']
    assert result['slices']['pipe:water:turbid']['recall']==0
    assert result['small_targets']['flange']['recall']==0
    rows[-1]['predictions']=[prediction('pipe')]
    assert not summarize(rows,.25)['accuracy_passed']
