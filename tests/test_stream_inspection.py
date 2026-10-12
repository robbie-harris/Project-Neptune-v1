import json
from stream_inspection_upload import complete_records, save_checkpoint


def test_only_complete_groups_and_complete_manifest_lines_are_staged(tmp_path):
    rows=[{'group':0,'id':i} for i in range(10)]+[{'group':1,'id':i} for i in range(4)]
    (tmp_path/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"group":2')
    selected=complete_records(tmp_path)
    assert len(selected)==10 and {r['group'] for r in selected}=={0}


def test_checkpoint_replaces_atomically(tmp_path):
    path=tmp_path/'checkpoint.json'
    save_checkpoint(path,{'confirmed':{'i0001_v00':'hash'}})
    assert json.loads(path.read_text())=={'confirmed':{'i0001_v00':'hash'}}
    assert not path.with_suffix('.partial').exists()
