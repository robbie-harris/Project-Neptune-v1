import json
from quarantine_captures import quarantine


def test_suspect_groups_preserved_and_removed_from_active_manifest(tmp_path):
    data=tmp_path/'active'; data.mkdir(); records=[]
    for group in [227,228]:
        key=f'o{group:03d}_v00'; image=data/'images/train'/f'{key}.png'; label=data/'labels/train'/f'{key}.txt'
        image.parent.mkdir(parents=True,exist_ok=True); label.parent.mkdir(parents=True,exist_ok=True)
        image.write_bytes(key.encode()); label.write_text('')
        records.append({'id':key,'group':f'sim-o{group:03d}','source':'stonefish','split':'train','image':str(image.relative_to(data))})
    (data/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records)); (data/'generation.json').write_text('{}')
    destination=tmp_path/'quarantine'; report=quarantine(data,destination,228)
    assert report['retained']==1 and report['quarantined']==1
    assert json.loads((data/'manifest.jsonl').read_text())['id']=='o227_v00'
    assert (destination/'images/train/o228_v00.png').read_bytes()==b'o228_v00'
    assert (destination/'labels/train/o228_v00.txt').exists()
    assert not (data/'images/train/o228_v00.png').exists()
