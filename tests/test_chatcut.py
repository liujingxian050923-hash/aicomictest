import io
import json
import zipfile
from pathlib import Path
import pytest
from PIL import Image
from test_api import client, create, wait_job
from studio.chatcut import build_bundle
from studio.models import Shot


def test_handoff_contains_current_episode_assets_and_absolute_subtitles(client):
    p=create(client);pid=p['id']
    text='''测试角色｜女主
成年角色，丸子头。
第01集
镜头 01 [0—10s]
对白：测试角色：“你好。”
镜头 02 [10—20s]
对白：测试角色：“第二句。”
第02集
镜头 01 [0—10s]
对白：测试角色：“其他集。”'''
    p=client.post(f'/api/projects/{pid}/script',files={'file':('script.txt',text.encode())}).json()
    image=io.BytesIO();Image.new('RGB',(100,100),'purple').save(image,'PNG')
    assert client.post(f'/api/projects/{pid}/shots/1/asset',files={'file':('shot.png',image.getvalue())}).status_code==200
    assert client.post(f'/api/projects/{pid}/characters/0/reference',files={'file':('reference.png',image.getvalue())}).status_code==200
    task=client.post(f'/api/projects/{pid}/chatcut-bundle?episode=1').json()
    job=wait_job(client,task['id']);assert job['status']=='completed',job
    assert job['output']['mode']=='manual_import'
    response=client.get(job['output']['bundle']);assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        manifest=json.loads(archive.read('manifest.json'))
        assert len(manifest['shots'])==2 and manifest['duration']==20
        assert manifest['shots'][0]['media']=='media/shot_001.png'
        assert manifest['characters'][0]['reference']=='references/character_001.png'
        assert archive.read('media/shot_001.png')==image.getvalue()
        assert manifest['missing'] and not any('其他集' in x for x in manifest['missing'])
        assert '00:00:10,000' in archive.read('subtitles.srt').decode('utf-8-sig')
        assert '其他集' not in archive.read('chatcut_request.txt').decode()
        assert '不是官方 ChatCut' in archive.read('README_导入说明.txt').decode()
        assert '图生视频' in archive.read('prompts.txt').decode()
        assert '第二句' in archive.read('storyboard.csv').decode('utf-8-sig')
    assert len(client.get(f'/api/projects/{pid}/chatcut-bundles').json())==1


def test_no_shots_fails_with_a_real_error(client):
    p=create(client)
    task=client.post(f'/api/projects/{p["id"]}/chatcut-bundle').json()
    assert wait_job(client,task['id'])['error']=='该集没有镜头'


def test_bundle_rejects_assets_outside_project_and_cleans_partial_file(tmp_path):
    pid='a'*32
    external=tmp_path/'outside.png';external.write_bytes(b'secret')
    shot=Shot(id=1,episode=1,number=1,asset='outside.png').model_dump()
    p={'id':pid,'name':'test','characters':[],'shots':[shot]}
    destination=tmp_path/'handoff.zip'
    with pytest.raises(ValueError,match='路径无效'):
        build_bundle(p,1,tmp_path,destination,lambda *_:None)
    assert not destination.exists() and not destination.with_suffix('.tmp').exists()
