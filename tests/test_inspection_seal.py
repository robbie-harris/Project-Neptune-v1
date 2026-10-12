import pytest
from inspection_dataset import validate_sealed, viewpoints


def test_reduced_contract_keeps_counts_hash_and_split_balance():
    report={'images':6530,'groups':653,'splits':{'train':4570,'val':980,'test':980},
            'target_absent':1630,'manifest_sha256':'frozen'}
    contract={**report,'authorization':'User-approved reduced simulator dataset'}
    validate_sealed(report,contract)
    with pytest.raises(ValueError):validate_sealed({**report,'manifest_sha256':'changed'},contract)
    with pytest.raises(ValueError):validate_sealed(report,{**contract,'images':9000})
    bad={**report,'target_absent':0}
    with pytest.raises(ValueError):validate_sealed(bad,{**bad,'authorization':contract['authorization']})


def test_viewpoint_refactor_preserves_generation_and_partitions():
    views=list(viewpoints())
    assert len(views)==900 and sum(v['negative'] for v in views)==225
    assert {s:sum(v['split']==s for v in views) for s in ('train','val','test')}=={'train':630,'val':135,'test':135}
    assert views[0]['split']=='train' and views[0]['negative']
