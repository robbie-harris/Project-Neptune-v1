import pytest
from roboflow_checkpoint import pending


def test_failed_or_unconfirmed_actions_remain_pending():
    requests = [{'image_id': str(i), 'annotation_name': f'{i}.txt'} for i in range(3)]
    outcomes = [{**requests[0], 'success': False}, {**requests[0], 'success': True}, {**requests[1], 'success': False}]
    todo, report = pending(requests, outcomes)
    assert todo == requests[1:]
    assert report['confirmed_successes'] == 1 and report['unresolved_failures'] == 1


def test_checkpoint_for_different_request_is_rejected():
    with pytest.raises(ValueError, match='match'):
        pending([{'image_id': 'a', 'annotation_name': 'new.txt'}], [{'image_id': 'a', 'annotation_name': 'old.xml', 'success': True}])
