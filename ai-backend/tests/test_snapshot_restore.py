import uuid


def payload():
    return dict(restore_id=uuid.uuid4().hex, goal='校园导览测试', nickname='验收', status='professor',
                roadmap={'title': '路线', 'stages': [{'id': 's1', 'name': '资料', 'space': 'library', 'tasks': [{'id': 't1', 'title': '阅读', 'status': 'done'}]}]},
                messages=[{'role': 'user', 'agent': 'scholar', 'content': '每天一小时'}],
                library_result={'retrieval_version': 4, 'results': [], 'sources': {}},
                fallbacks=['保留原有降级标记'])


def test_restore_snapshot_roundtrip_and_idempotency(client):
    data = payload()
    first = client.post('/api/session/restore', json=data)
    assert first.status_code == 200, first.text
    sid = first.json()['session_id']
    snapshot = client.get(f'/api/session/{sid}').json()
    quest = client.get(f'/api/quest/{sid}').json()
    assert snapshot['roadmap']['stages'][0]['tasks'][0]['status'] == 'done'
    assert snapshot['messages'][0]['content'] == '每天一小时'
    assert quest['status'] == 'professor'
    assert quest['library_result']['retrieval_version'] == 4
    data['goal'] = '重复请求不能覆盖已恢复内容'
    assert client.post('/api/session/restore', json=data).json()['session_id'] == sid
    assert client.get(f'/api/session/{sid}').json()['session']['goal'] == '校园导览测试'
    assert len(client.get(f'/api/session/{sid}').json()['messages']) == 1


def test_restore_rejects_missing_roadmap_and_system_messages(client):
    data = payload(); data['roadmap'] = None
    assert client.post('/api/session/restore', json=data).status_code == 422
    data = payload(); data['messages'][0]['role'] = 'system'
    assert client.post('/api/session/restore', json=data).status_code == 422
