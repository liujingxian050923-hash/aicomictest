import copy
import json
import os
import re
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from .models import Project
from .parser import extract_text, parse, prompts, timeline
from . import media, tts
from .chatcut import build_bundle

ROOT=Path(os.getenv('STUDIO_DATA',Path(__file__).resolve().parent.parent/'data')).resolve()
ROOT.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='AI 漫剧自动制作工作台')
lock=threading.RLock(); executor=ThreadPoolExecutor(max_workers=1); jobs={}
JOB_DIR=ROOT/'.jobs'
JOB_DIR.mkdir(exist_ok=True)

def persist_job(j):
    path=JOB_DIR/(j['id']+'.json'); tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(j,ensure_ascii=False),encoding='utf-8'); tmp.replace(path)

for state_file in JOB_DIR.glob('*.json'):
    try:
        state=json.loads(state_file.read_text(encoding='utf-8'))
        if state['status'] in ('queued','running'):
            state.update(status='failed',message='任务已中断',error='服务器在任务完成前停止，请重新提交任务')
            persist_job(state)
        jobs[state['id']]=state
    except (ValueError,KeyError): pass

STATIC=Path(__file__).parent/'static'
app.mount('/static',StaticFiles(directory=STATIC),name='static')
app.mount('/media',StaticFiles(directory=ROOT),name='media')

@app.middleware('http')
async def local_only(request:Request,call_next):
    host=request.url.hostname
    if host not in ('localhost','127.0.0.1','::1','testserver'):
        return JSONResponse({'detail':'工作台仅允许本机访问'},status_code=403)
    origin=request.headers.get('origin')
    if origin and origin!=str(request.base_url).rstrip('/'):
        return JSONResponse({'detail':'拒绝跨站请求'},status_code=403)
    return await call_next(request)

@app.exception_handler(ValueError)
async def value_error(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)

def project_dir(pid):
    if not re.fullmatch(r'[a-f0-9]{32}',pid): raise HTTPException(404,'项目不存在')
    return ROOT/pid

def load(pid):
    file=project_dir(pid)/'project.json'
    if not file.exists(): raise HTTPException(404,'项目不存在')
    return json.loads(file.read_text(encoding='utf-8'))

def save(p):
    p=Project.model_validate(p).model_dump()
    path=project_dir(p['id']); path.mkdir(exist_ok=True)
    for asset in [p.get('bgm')]+[s.get('asset') for s in p['shots']]+[c.get('reference') for c in p['characters']]+[d.get('audio') for s in p['shots'] for d in s['dialogue']]:
        if asset and (not asset.startswith(p['id']+'/assets/') or not (ROOT/asset).resolve().is_relative_to(path/'assets') or not (ROOT/asset).is_file()):
            raise ValueError('素材路径无效，请通过上传接口添加文件')
    if len({s['id'] for s in p['shots']})!=len(p['shots']): raise ValueError('镜头 ID 不能重复')
    if len({c['name'] for c in p['characters']})!=len(p['characters']): raise ValueError('角色名不能重复')
    tmp=path/'project.tmp'; tmp.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path/'project.json')

def shot_by_id(p,sid):
    for s in p['shots']:
        if s['id']==sid:return s
    raise HTTPException(404,'镜头不存在')

async def upload(file,pid,extensions):
    ext=Path(file.filename or '').suffix.lower()
    if ext not in extensions: raise ValueError('不支持的文件格式：'+ext)
    directory=project_dir(pid)/'assets'; directory.mkdir(exist_ok=True)
    path=directory/(uuid.uuid4().hex+ext); size=0
    try:
        with path.open('wb') as target:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>500*1024*1024:raise ValueError('文件不得超过 500 MB')
                target.write(chunk)
        if ext in {'.png','.jpg','.jpeg','.webp'}:
            with Image.open(path) as im: im.verify()
        else: media.probe(path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise ValueError('素材校验失败：'+str(exc)) from exc
    return path.relative_to(ROOT).as_posix()

def start_job(pid,kind,func):
    with lock:
        if any(j['project']==pid and j['status'] in ('queued','running') for j in jobs.values()): raise HTTPException(409,'该项目已有任务，请等待完成')
        jid=uuid.uuid4().hex; jobs[jid]={'id':jid,'project':pid,'kind':kind,'status':'queued','progress':0,'message':'等待执行','error':None,'output':None}
        persist_job(jobs[jid])
    def progress(percent,message):
        with lock:
            jobs[jid].update(progress=percent,message=message);persist_job(jobs[jid])
    def worker():
        with lock:
            jobs[jid]['status']='running';persist_job(jobs[jid])
        try:
            output=func(jid,progress)
            with lock:
                jobs[jid].update(status='completed',progress=100,message='任务完成',output=output);persist_job(jobs[jid])
        except Exception as exc:
            with lock:
                jobs[jid].update(status='failed',error=str(exc),message='任务失败');persist_job(jobs[jid])
    executor.submit(worker);return jobs[jid].copy()

def idle(pid):
    if any(j['project']==pid and j['status'] in ('queued','running') for j in jobs.values()):raise HTTPException(409,'项目任务执行中，暂时不能修改')

@app.get('/')
def index():return FileResponse(STATIC/'index.html')

@app.get('/api/health')
def health():
    return {'ffmpeg':bool(os.getenv('FFMPEG_PATH') or shutil.which('ffmpeg')),'ffprobe':bool(os.getenv('FFPROBE_PATH') or shutil.which('ffprobe')),'tts':tts.available(),'resolution':'1080×1920','generation':'manual'}

@app.get('/api/projects')
def projects():
    with lock:
        return [{'id':p['id'],'name':p['name'],'shots':len(p['shots'])} for f in ROOT.glob('*/project.json') if (p:=json.loads(f.read_text(encoding='utf-8')))]

@app.post('/api/projects')
def create(p:Project):
    with lock:
        data=p.model_dump(); data['id']=uuid.uuid4().hex; save(data); return data

@app.get('/api/projects/{pid}')
def get_project(pid:str):
    with lock:return load(pid)

@app.put('/api/projects/{pid}')
def update(pid:str,p:Project):
    with lock:
        idle(pid);load(pid); data=p.model_dump();data['id']=pid;save(data);return data

@app.post('/api/projects/{pid}/script')
async def script(pid:str,file:UploadFile=File(...)):
    if Path(file.filename or '').suffix.lower() not in ('.txt','.docx'): raise ValueError('仅支持 DOCX/TXT')
    data=await file.read(20*1024*1024+1)
    if len(data)>20*1024*1024:raise ValueError('剧本文件不能超过 20 MB')
    try:text=extract_text(data,file.filename)
    except Exception as exc:raise ValueError('剧本读取失败：'+str(exc)) from exc
    shots,characters=parse(text)
    if len(shots)>1000:raise ValueError('镜头过多，请分批导入')
    with lock:
        idle(pid);p=load(pid);p.update(script=text,shots=shots,characters=characters);save(p)
    return p

@app.post('/api/projects/{pid}/prompts')
def generate_prompts(pid:str):
    with lock:
        idle(pid);p=load(pid)
        for s in p['shots']:s['prompts']=prompts(s,p['characters'])
        save(p);return p

@app.post('/api/projects/{pid}/shots/{sid}/asset')
async def asset(pid:str,sid:int,file:UploadFile=File(...)):
    with lock: idle(pid);shot_by_id(load(pid),sid)
    path=await upload(file,pid,{'.jpg','.jpeg','.png','.webp','.mp4','.mov','.webm','.mkv'})
    with lock:
        idle(pid);p=load(pid);shot_by_id(p,sid)['asset']=path;save(p)
    return p

@app.post('/api/projects/{pid}/characters/{index}/reference')
async def reference(pid:str,index:int,file:UploadFile=File(...)):
    with lock:
        idle(pid);p=load(pid)
        if not 0<=index<len(p['characters']): raise HTTPException(404,'角色不存在')
    path=await upload(file,pid,{'.jpg','.jpeg','.png','.webp'})
    with lock:idle(pid);p=load(pid);p['characters'][index]['reference']=path;save(p)
    return p

@app.post('/api/projects/{pid}/shots/{sid}/dialogue/{index}/audio')
async def audio(pid:str,sid:int,index:int,file:UploadFile=File(...)):
    with lock:
        idle(pid);s=shot_by_id(load(pid),sid)
        if not 0<=index<len(s['dialogue']):raise HTTPException(404,'对白不存在')
    path=await upload(file,pid,{'.wav','.mp3','.m4a','.ogg','.flac'})
    seconds=media.audio_duration(ROOT/path)
    with lock:
        idle(pid);p=load(pid);d=shot_by_id(p,sid)['dialogue'][index];d.update(audio=path,audio_seconds=seconds);save(p)
    return p

@app.post('/api/projects/{pid}/bgm')
async def bgm(pid:str,file:UploadFile=File(...)):
    with lock:idle(pid);load(pid)
    path=await upload(file,pid,{'.wav','.mp3','.m4a','.ogg','.flac'});media.audio_duration(ROOT/path)
    with lock:idle(pid);p=load(pid);p['bgm']=path;save(p)
    return p

@app.get('/api/voices')
def voice_list():
    try: return {'available':tts.available(),'voices':tts.voices(),'error':None}
    except Exception as exc: return {'available':False,'voices':[],'error':'系统音色读取失败，可使用导入配音：'+str(exc)}

@app.get('/api/projects/{pid}/timeline')
def get_timeline(pid:str):
    with lock:p=load(pid)
    return [{'shot':s['id'],'episode':s['episode'],'duration':s['duration'],'dialogue':timeline(s)} for s in p['shots']]

@app.post('/api/projects/{pid}/fit-audio')
def fit_audio(pid:str):
    with lock:
        idle(pid);p=load(pid)
        for s in p['shots']:
            weights=[(d.get('audio_seconds') or max(0.8,len(d['text'])/4))+.15 for d in s['dialogue']]
            if weights:s['duration']=round(max(s['duration'],sum(weights)),2)
            if s['duration']>120:raise ValueError('配音过长，请拆分镜头')
        save(p);return p

@app.post('/api/projects/{pid}/tts')
def generate_tts(pid:str,episode:int=1):
    with lock:
        idle(pid);p=load(pid)
        if not tts.available():raise ValueError('当前系统不支持 Windows SAPI，请上传配音文件。Windows 上安装中文语音包后可使用自动配音')
        def work(jid,progress):
            voices_by_role={c['name']:c['voice'] for c in p['characters']}
            rows=[d for s in p['shots'] if s['episode']==episode for d in s['dialogue']]
            if not rows:raise ValueError('该集没有对白')
            for i,d in enumerate(rows):
                folder=project_dir(pid)/'assets';folder.mkdir(exist_ok=True)
                output=folder/(uuid.uuid4().hex+'.wav');tts.synthesize(d['text'],voices_by_role.get(d['role'],''),output)
                d.update(audio=output.relative_to(ROOT).as_posix(),audio_seconds=media.audio_duration(output))
                progress(int((i+1)/len(rows)*100),f'配音 {i+1}/{len(rows)}')
            with lock:save(p)
            return None
        return start_job(pid,'tts',work)

@app.post('/api/projects/{pid}/export')
def export_video(pid:str,episode:int=1):
    with lock:
        idle(pid);p=copy.deepcopy(load(pid))
        def work(jid,progress):
            output=media.export(p,episode,ROOT,project_dir(pid)/'exports'/jid,progress)
            return {'video':'/media/'+output.relative_to(ROOT).as_posix(),'subtitles':'/media/'+output.with_name('subtitles.srt').relative_to(ROOT).as_posix()}
        return start_job(pid,'export',work)

@app.post('/api/projects/{pid}/chatcut-bundle')
def chatcut_bundle(pid:str,episode:int=1):
    with lock:
        idle(pid);p=copy.deepcopy(load(pid))
        def work(jid,progress):
            output=build_bundle(p,episode,ROOT,project_dir(pid)/'handoffs'/jid/'chatcut_bundle.zip',progress)
            return {'bundle':'/media/'+output.relative_to(ROOT).as_posix(),'mode':'manual_import'}
        return start_job(pid,'chatcut',work)

@app.get('/api/projects/{pid}/chatcut-bundles')
def chatcut_bundles(pid:str):
    load(pid)
    return [{'bundle':'/media/'+f.relative_to(ROOT).as_posix(),'name':f.parent.name} for f in sorted(project_dir(pid).glob('handoffs/*/chatcut_bundle.zip'),key=lambda p:p.stat().st_mtime,reverse=True)]

@app.get('/api/jobs/{jid}')
def job(jid:str):
    with lock:
        if jid not in jobs:raise HTTPException(404,'任务不存在（重启后请检查导出历史）')
        return jobs[jid].copy()

@app.get('/api/projects/{pid}/exports')
def exports(pid:str):
    load(pid)
    return [{'video':'/media/'+f.relative_to(ROOT).as_posix(),'subtitles':'/media/'+f.with_name('subtitles.srt').relative_to(ROOT).as_posix(),'name':f.parent.name} for f in sorted(project_dir(pid).glob('exports/*/final.mp4'),key=lambda p:p.stat().st_mtime,reverse=True)]

@app.post('/api/projects/{pid}/generate')
def generation(pid:str):
    load(pid)
    raise HTTPException(501,'未配置并验证 AI 图像/视频服务适配器。请使用手动上传素材；扩展入口为 studio/providers.py，API 密钥必须从环境变量读取')
