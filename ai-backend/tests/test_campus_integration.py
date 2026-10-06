import json
from app.agents import orchestrator, scholar, lab_mentor
from app.memory.store import store
from app.memory.artifacts import save_artifact, read_artifact


def _local(result):
    return [r for r in result["results"] if r["source"] == "local"]


def test_retry_replays_without_advancing_again():
    sid=store.create_session(goal='测试')
    store.update_state(sid,quest_status='professor')
    first=list(orchestrator.advance(sid,request_id='same-click',expected_status='professor'))
    second=list(orchestrator.advance(sid,request_id='same-click',expected_status='professor'))
    assert first==second
    assert orchestrator.get_quest(sid)['status']=='lab'
    assert orchestrator.get_quest(sid)['project'] is None


def test_stale_tab_cannot_skip_a_stage():
    sid=store.create_session(goal='测试')
    store.update_state(sid,quest_status='lab')
    events=list(orchestrator.advance(sid,expected_status='professor'))
    assert events[0]['type']=='error'
    assert orchestrator.get_quest(sid)['status']=='lab'


def test_roadmap_failure_does_not_unlock_library(monkeypatch):
    sid=store.create_session(goal='测试')
    store.update_state(sid,quest_status='quest_ready')
    monkeypatch.setattr(scholar,'generate_roadmap',lambda _:iter([{'type':'error','message':'failed'},{'type':'done'}]))
    assert any(e['type']=='error' for e in orchestrator.advance(sid))
    assert orchestrator.get_quest(sid)['status']=='quest_ready'


def test_lab_failure_does_not_create_project(monkeypatch):
    sid=store.create_session(goal='测试')
    store.update_state(sid,quest_status='lab')
    monkeypatch.setattr(lab_mentor,'generate_guidance',lambda *a,**kw:{'error':'failed'})
    assert list(orchestrator.advance(sid))[-1]['type']=='error'
    assert orchestrator.get_quest(sid)['project'] is None
    assert orchestrator.get_quest(sid)['status']=='lab'


def test_stage_handoffs_restore_with_project(client,session):
    store.update_state(session,quest_status='library')
    list(orchestrator.advance(session))
    r=client.post('/api/professor/chat',json={'session_id':session,'message':'如何定义可验证的问题？'})
    assert r.status_code==200
    assert read_artifact(session,'professor_result')['question']=='如何定义可验证的问题？'
    list(orchestrator.advance(session))
    list(orchestrator.advance(session))
    quest=client.get('/api/quest/'+session).json()
    assert quest['library_result']['results']
    assert quest['professor_result']['answer']
    assert quest['lab_result']['steps']
    assert quest['project']['artifact_type']=='project_plan'
    assert quest['project']['degraded'] is True
    assert quest['fallbacks']
    # Generating a plan must not claim real tasks were completed.
    assert quest['completed_tasks']==[]


def test_lab_receives_professor_result(monkeypatch,live_mode):
    sid=store.create_session(goal='机器人')
    save_artifact(sid,'professor_result',{'answer':'验证室内定位误差小于两米'})
    captured=[]
    def fake(messages,**kwargs):
        captured.extend(messages)
        return {'overview':'验证方案','steps':[],'deliverables':[],'pitfalls':[],'tools':[]}
    monkeypatch.setattr(lab_mentor.llm,'chat_json',fake)
    lab_mentor.generate_guidance(sid)
    assert '室内定位误差小于两米' in json.dumps(captured,ensure_ascii=False)


def test_inflight_duplicate_is_rejected(monkeypatch):
    sid=store.create_session(goal='测试')
    def stream(_sid):
        yield {'type':'status','stage':'working'}
        yield {'type':'roadmap','roadmap':{}}
    monkeypatch.setattr(scholar,'generate_roadmap',stream)
    store.update_state(sid,quest_status='quest_ready')
    first=orchestrator.advance(sid,request_id='one')
    next(first)
    duplicate=list(orchestrator.advance(sid,request_id='two'))
    assert duplicate[0]['type']=='error'
    list(first)
    assert orchestrator.get_quest(sid)['status']=='library'


def test_empty_provider_stream_is_an_error(monkeypatch):
    from types import SimpleNamespace as NS
    from app.agents.llm import llm, EmptyResponseError
    import pytest
    monkeypatch.setattr(llm, 'chat', lambda *a, **kw: iter([NS(choices=[NS(delta=NS(content=None))]), NS(choices=[NS(delta=NS(content='  '))])]))
    with pytest.raises(EmptyResponseError):
        list(llm.stream_text([]))


def test_empty_professor_retries_once_then_saves_real_answer(monkeypatch, live_mode, session):
    from app.agents import professor
    calls=[]
    def stream(*a, **kw):
        calls.append(kw['max_tokens'])
        return iter([] if len(calls)==1 else ['先定义验收标准，再运行最小实验。'])
    monkeypatch.setattr(professor.llm,'stream_text',stream)
    events=list(professor.stream_chat(session,'下一步是什么'))
    assert calls==[1500,3000]
    assert not any(e['type'] in ('error','fallback') for e in events)
    assert ''.join(e['delta'] for e in events if e['type']=='token').strip()


def test_empty_professor_never_saved_as_success(monkeypatch, live_mode, session, sse):
    from app.agents import professor
    live_mode.fallback_to_mock=False
    monkeypatch.setattr(professor.llm,'stream_text',lambda *a,**kw:iter([]))
    events=sse('/api/professor/chat',{'session_id':session,'message':'下一步是什么'})
    assert any(e['event']=='error' for e in events)
    assert read_artifact(session,'professor_result') is None
    assert not any(m['role']=='assistant' for m in store.list_messages(session,agent='professor'))


def test_empty_professor_fallback_is_explicit(monkeypatch, live_mode, session, sse):
    from app.agents import professor
    monkeypatch.setattr(professor.llm,'stream_text',lambda *a,**kw:iter([]))
    events=sse('/api/professor/chat',{'session_id':session,'message':'下一步是什么'})
    assert any(e['event']=='fallback' for e in events)
    result=read_artifact(session,'professor_result')
    assert result['answer'].strip() and result['degraded']


def test_ready_scholar_can_keep_clarifying_without_generating_roadmap(monkeypatch):
    sid=store.create_session(goal='柔性机器人')
    store.update_state(sid,quest_status='quest_ready')
    seen=[]
    def clarify(session_id,message):
        seen.append((session_id,message))
        yield {'type':'ready','ready':False}
    monkeypatch.setattr(scholar,'stream_clarify',clarify)
    list(orchestrator.advance(sid,message='做仿真，一个月',expected_status='quest_ready'))
    assert seen==[(sid,'做仿真，一个月')]
    assert store.get_roadmap(sid) is None
    assert orchestrator.get_quest(sid)['status']=='clarifying'


def test_scholar_explicit_false_is_not_overridden_by_keywords(monkeypatch,live_mode):
    sid=store.create_session(goal='有工科基础，每天一小时，想做可运行的柔性机器人')
    monkeypatch.setattr(scholar.llm,'stream_text',lambda *a,**kw:iter(['想做实物还是仿真？<<<READY:false>>>']))
    events=list(scholar.stream_clarify(sid,'我有工科基础，每天一小时，想做可运行的柔性机器人'))
    assert next(e['ready'] for e in events if e['type']=='ready') is False


def test_topic_filter_removes_wrong_nearest_neighbours(monkeypatch,live_mode):
    from app.agents import librarian
    from app.rag.corpus import LIBRARY_CORPUS
    monkeypatch.setattr(librarian._hybrid,'search',lambda *a,**kw:[{'title':d['title'],'url':d['url'],'type':d['type'],'snippet':d['content']} for d in LIBRARY_CORPUS])
    soft=librarian.retrieve('工科基础，每天一个小时，柔性机器人小项目')
    diffusion=librarian.retrieve('文生图 DDPM')
    assert len(_local(soft))==3
    assert not ({d['url'] for d in _local(soft)} & {d['url'] for d in _local(diffusion)})
    assert _local(librarian.retrieve('菠萝种植'))==[]


def test_library_refresh_uses_own_goal_and_followups_without_advancing(client):
    sid=store.create_session(goal='柔性机器人')
    store.update_state(sid,quest_status='professor')
    store.add_message(sid,'user','选择 SOFA 仿真，周期一个月',agent='scholar')
    other=store.create_session(goal='扩散模型文生图')
    save_artifact(other,'library_result',{'results':[{'title':'other-project','source':'local','type':'doc','url':'','snippet':''}]})
    result=client.post('/api/library/retrieve',json={'session_id':sid,'query':''}).json()
    assert 'SOFA' in result['query']
    assert result['retrieval_version']==4
    assert len(_local(result))==3
    assert read_artifact(sid,'library_result')==result
    assert read_artifact(other,'library_result')['results'][0]['title']=='other-project'
    assert orchestrator.get_quest(sid)['status']=='professor'
