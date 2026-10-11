import importlib
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path))
    import studio.app as module
    module=importlib.reload(module)
    with TestClient(module.app) as client:yield client
    module.executor.shutdown(wait=True)

def create(client):return client.post('/api/projects',json={'name':'测试项目'}).json()

def test_five_episode_import_and_persistence(client):
    p=create(client);pid=p['id']
    lines=['测试女主｜女主','成年角色，丸子头、奶油色开衫。']
    for episode in range(1,6):
        lines.append(f'第{episode:02}集 自动化测试')
        for shot in range(1,7):
            lines.extend([f'镜头 {shot:02} [{(shot-1)*10}—{shot*10}s]', '场景：办公室', '画面动作：测试女主微笑', '对白：测试女主：“测试台词。”'])
    text='\n'.join(lines).encode('utf-8')
    r=client.post(f'/api/projects/{pid}/script',files={'file':('sample.txt',text)})
    assert r.status_code==200
    p=r.json();assert len(p['shots'])==30
    assert {s['episode'] for s in p['shots']}=={1,2,3,4,5}
    assert all(sum(s['duration'] for s in p['shots'] if s['episode']==e)==60 for e in range(1,6))
    assert '奶油色' in next(c for c in p['characters'] if c['name']=='测试女主')['appearance']
    p=client.post(f'/api/projects/{pid}/prompts').json()
    assert 'hair in a bun' in p['shots'][0]['prompts']['en']
    assert client.get(f'/api/projects/{pid}').json()['shots'][0]['prompts']

def test_validation_and_local_access(client):
    p=create(client);pid=p['id'];p['bgm']='../other.wav'
    assert client.put(f'/api/projects/{pid}',json=p).status_code==400
    assert client.post(f'/api/projects/{pid}/script',files={'file':('bad.exe',b'text')}).status_code==400
    assert client.get('/api/health',headers={'Host':'attacker.com'}).status_code==403
    assert client.post('/api/projects',headers={'Origin':'https://evil.example'},json={'name':'bad'}).status_code==403
    assert client.post(f'/api/projects/{pid}/generate').status_code==501

def wait_job(client,jid):
    for _ in range(300):
        job=client.get('/api/jobs/'+jid).json()
        if job['status'] in ('failed','completed'):return job
        time.sleep(.2)
    raise AssertionError('job timeout')

def test_missing_assets_reports_failure(client):
    p=create(client);pid=p['id']
    client.post(f'/api/projects/{pid}/script',files={'file':('sample.txt','镜头 01 [0—2s]\n字幕：你好'.encode())})
    job=client.post(f'/api/projects/{pid}/export').json()
    assert wait_job(client,job['id'])['error'].startswith('请先上传镜头素材')
