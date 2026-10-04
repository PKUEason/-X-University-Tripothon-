import pytest
from app.api.routes import _using_session
from app.memory.store import store


def test_delete_removes_all_project_data_only(client):
    deleted = store.create_session('delete me')
    kept = store.create_session('keep me')
    for sid in (deleted, kept):
        store.add_message(sid, 'user', 'goal', agent='scholar')
        store.save_roadmap(sid, {'stages': []})
        store.remember(sid, 'note', 'library_result', 'references')
        store.save_summary(sid, 'scholar', 'summary', 1)
    assert client.delete(f'/api/session/{deleted}').json() == {'ok': True}
    for table in ('sessions', 'messages', 'roadmaps', 'memories', 'summaries'):
        assert store.conn.execute(f'SELECT COUNT(*) FROM {table} WHERE session_id=?', (deleted,)).fetchone()[0] == 0
        assert store.conn.execute(f'SELECT COUNT(*) FROM {table} WHERE session_id=?', (kept,)).fetchone()[0] == 1
    assert client.get(f'/api/session/{deleted}').status_code == 404
    assert client.get(f'/api/quest/{deleted}').status_code == 404
    assert client.delete(f'/api/session/{deleted}').json() == {'ok': True}
    assert client.post('/api/scholar/clarify', json={'session_id': deleted, 'message': 'late reply'}).status_code == 404


def test_delete_refuses_active_agent_and_releases_after_failure(client, session):
    with pytest.raises(RuntimeError):
        with _using_session(session):
            assert client.delete(f'/api/session/{session}').status_code == 409
            assert store.get_session(session)
            raise RuntimeError('provider error')
    assert client.delete(f'/api/session/{session}').status_code == 200


def test_delete_transaction_rolls_back_on_error(client, session):
    store.add_message(session, 'user', 'preserve')
    store.conn.execute("CREATE TEMP TRIGGER reject_project_delete BEFORE DELETE ON sessions BEGIN SELECT RAISE(ABORT, 'injected'); END")
    try:
        with pytest.raises(Exception, match='injected'):
            store.delete_session(session)
        assert store.get_session(session)
        assert store.list_messages(session)[0]['content'] == 'preserve'
    finally:
        store.conn.execute('DROP TRIGGER reject_project_delete')
