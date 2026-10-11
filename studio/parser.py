"""Deterministic screenplay importer; document text is data, never executable instructions."""
import re
from io import BytesIO
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from zipfile import ZipFile

def extract_text(content, filename):
    if filename.lower().endswith('.docx'):
        with ZipFile(BytesIO(content)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 80*1024*1024:
                raise ValueError('DOCX 解压后过大，请简化文档')
        doc = Document(BytesIO(content))
        parts=[]
        for block in doc.iter_inner_content():
            if isinstance(block,Paragraph): parts.append(block.text)
            elif isinstance(block,Table):
                for row in block.rows:
                    for cell in row.cells: parts.append(cell.text)
        return '\n'.join(parts)
    for encoding in ('utf-8-sig', 'gb18030'):
        try: return content.decode(encoding)
        except UnicodeDecodeError: pass
    raise ValueError('TXT 请使用 UTF-8 或 GB18030 编码')

def episode_number(value):
    if value.isdigit(): return int(value)
    digits = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    if value in digits: return digits[value]
    if '十' in value:
        a,b=value.split('十'); return digits.get(a,1)*10+digits.get(b,0)
    return 1

def parse(text):
    shots=[]; characters={}; episode=1; scene='现代都市办公室'; current=None
    lines=[l.strip() for l in text.splitlines() if l.strip()]
    for i,line in enumerate(lines):
        ref=re.match(r'^([^｜|]{1,12})[｜|](男主|女主)',line)
        if ref:
            name=ref[1]; profile=lines[i+1] if i+1<len(lines) else ''
            characters[name]={'name':name,'appearance':profile,'appearance_en':'','voice':'','reference':None}
        ep=re.match(r'^第\s*([\d一二三四五六七八九十]+)\s*集',line)
        if ep: episode=episode_number(ep[1]); current=None; continue
        sc=re.search(r'场景[：:]\s*(.*?)(?:\s*\||$)',line)
        if sc:
            scene=sc[1]
            if current: current['scene']=scene
        sh=re.match(r'^(?:镜头|分镜|Shot)\s*(\d+)[\s：:·.-]*(.*)',line,re.I)
        if sh:
            time=re.search(r'\[(\d+(?:\.\d+)?)\s*[—–\-~至]\s*(\d+(?:\.\d+)?)\s*s?\]',line)
            duration=float(time[2])-float(time[1]) if time else 10
            current={'id':len(shots)+1,'episode':episode,'number':int(sh[1]),'title':re.sub(r'\[.*?\]','',sh[2]).strip(),'duration':duration,'scene':scene,'action':'','camera':'缓慢推近','framing':'中近景','light':'柔和午后暖光','dialogue':[],'subtitle':'','asset':None,'motion':'push','transition':'fade','prompts':{}}
            shots.append(current); continue
        if current:
            field=re.match(r'^(画面动作|动作|运镜/音效|运镜|景别/构图|景别|时长|字幕)[：:]\s*(.*)',line)
            if field:
                key={'画面动作':'action','动作':'action','运镜/音效':'camera','运镜':'camera','景别/构图':'framing','景别':'framing','字幕':'subtitle'}.get(field[1])
                if key: current[key]=field[2]
                elif field[1]=='时长':
                    n=re.search(r'[\d.]+',field[2]); current['duration']=float(n[0]) if n else 10
            speech=re.sub(r'^对白[：:]','',line)
            pairs=re.findall(r'([\w\u4e00-\u9fff]{1,12})(?:[（(][^）)]*[）)])?[：:]\s*[“"]([^”"]+)[”"]',speech)
            if not pairs and re.match(r'^[\w\u4e00-\u9fff]{1,12}[：:]',speech) and not field and not sc and not line.startswith(('剪辑提示','本集')):
                name,body=speech.split('：' if '：' in speech else ':',1); pairs=[(name,body)]
            for name,body in pairs:
                current['dialogue'].append({'role':name,'text':body,'audio':None})
                characters.setdefault(name,{'name':name,'appearance':'成年角色，固定面部、发型和服装','appearance_en':'adult character, consistent face, hairstyle and clothing','voice':'','reference':None})
    if not shots:
        for i,line in enumerate(lines):
            shots.append({'id':i+1,'episode':1,'number':i+1,'title':f'镜头 {i+1}','duration':max(3,min(15,len(line)/4)),'scene':scene,'action':line,'camera':'缓慢推近','framing':'中近景','light':'柔和暖光','dialogue':[],'subtitle':line,'asset':None,'motion':'push','transition':'fade','prompts':{}})
    return shots, list(characters.values())

def timeline(shot):
    rows=shot.get('dialogue',[])
    weights=[(d.get('audio_seconds') or max(0.8,len(d['text'])/4))+.15 for d in rows]
    total=sum(weights)
    start=0; result=[]
    for d,weight in zip(rows,weights):
        end=start+shot['duration']*weight/max(total,0.01)
        result.append({**d,'start':round(start,3),'end':round(end,3)}); start=end
    return result

def english_details(text, kind):
    dictionaries={
        'scene': {'办公室':'modern office','办公区':'open-plan office','茶水间':'office pantry','写字楼':'office tower','河边':'riverside walkway','客厅':'apartment living room','公寓':'apartment','露台':'rooftop terrace','门口':'entrance','楼下':'building entrance','傍晚':'evening','黄昏':'golden hour','午后':'afternoon'},
        'action': {'看':'looking toward each other','工作':'working at a desk','咖啡':'placing a coffee cup on the desk','歪头':'tilting the head inquisitively','抬眼':'looking up','靠近':'leaning closer','笑':'smiling softly','慌':'flustered expression','站起':'standing up','注视':'gentle affectionate gaze','低头':'lowering the gaze shyly','脸红':'subtle blushing','手机':'checking a phone','热饮':'holding a warm drink','递':'passing an object carefully','散步':'walking side by side','手背':'hands accidentally brushing','伸出手':'extending a hand','握':'holding hands gently','毯':'offering a blanket','书':'quietly reading a book','粥':'placing a bowl of porridge','疲惫':'tired expression','温柔':'tender expression','蛋糕':'a small cake on the table','便签':'holding a handwritten note','卡片':'offering a card','晚霞':'watching the sunset together'},
        'camera': {'推':'slow dolly in','拉远':'slow pull back','固定':'locked-off camera','特写':'close-up','近景':'medium close-up','全景':'wide shot','中景':'medium shot','跟随':'gentle tracking shot','手部':'insert shot of hands','正反打':'shot reverse shot'},
        'appearance': {'丸子头':'hair in a bun','浅蓝':'light blue shirt','针织':'cream knitted cardigan','牛仔裤':'jeans','工牌':'blue employee badge','黑色':'black hair','短发':'short fluffy hair','眼镜':'thin-frame glasses','白衬衫':'white shirt','领带':'dark necktie','西裤':'tailored trousers','家居服':'loose casual home clothes','男':'adult man','女':'adult woman'}
    }
    found=[value for key,value in dictionaries[kind].items() if key in text]
    return ', '.join(dict.fromkeys(found)) or {'scene':'modern urban setting','action':'natural subtle gestures and affectionate expressions','camera':'gentle cinematic camera movement','appearance':'adult character, consistent face and wardrobe'}[kind]

def prompts(shot,characters):
    names={d['role'] for d in shot['dialogue']}
    names.update(c['name'] for c in characters if c['name'] in shot['action'])
    cast=[c for c in characters if c['name'] in names]
    profiles='；'.join(f"{c['name']}：{c['appearance']}" for c in cast)
    english='; '.join(f"{c['name']}: {c.get('appearance_en') or english_details(c['appearance'],'appearance')}" for c in cast)
    scene=shot.get('scene_en') or english_details(shot['scene'],'scene')
    action=shot.get('action_en') or english_details(shot['action'],'action')
    camera=shot.get('camera_en') or english_details(shot['camera'],'camera')
    references=', '.join(c['name'] for c in cast if c.get('reference'))
    return {'zh':f"9:16竖屏，真人电影感，现代都市甜宠，自然皮肤纹理。角色锁定：{profiles}。场景：{shot['scene']}。动作与表情：{shot['action']}。构图：{shot['framing']}。光线：{shot['light']}。保持参考图面部一致，无文字水印。参考图角色：{references or '尚未上传'}。",
            'en':f"Vertical 9:16, photorealistic cinematic modern urban romance, natural skin texture. Consistent cast: {english}. Scene: {scene}. Action and expression: {action}. Framing: {english_details(shot['framing'],'camera')}. Lighting: soft warm cinematic light. Match reference identities ({references or 'upload reference images'}), no text or watermark.",
            'video':f"基于参考首帧，保持人物面部服装一致。{shot['action']}。镜头运动：{shot['camera']}。自然细微表情、稳定肢体、柔和光线，持续{shot['duration']}秒，9:16。\nImage-to-video: Preserve reference identity and wardrobe. {action}. Camera: {camera}. Natural micro-expressions, stable anatomy, soft lighting. Duration {shot['duration']} seconds, vertical 9:16."}
