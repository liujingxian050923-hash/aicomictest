"""Local media handoff, NOT a ChatCut proprietary project or API adapter."""
import csv
import io
import json
import zipfile
from pathlib import Path
from .parser import prompts, timeline


def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def build_bundle(project, episode, root, destination, progress):
    shots=[s for s in project['shots'] if s['episode']==episode]
    if not shots:raise ValueError('该集没有镜头')
    root=Path(root).resolve();destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.tmp')
    missing=[];start=0;cue=1;srt=[];entries=[];prompt_blocks=[];cast=[]
    copied={}
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            def asset(relative,folder,stem):
                if not relative:return None
                source=(root/relative).resolve()
                allowed=root/project['id']/'assets'
                if not source.is_relative_to(allowed) or not source.is_file():
                    raise ValueError('素材文件丢失或路径无效：'+relative)
                if relative in copied:return copied[relative]
                target=f'{folder}/{stem}{source.suffix.lower()}'
                archive.write(source,target);copied[relative]=target;return target
            for i,c in enumerate(project['characters'],1):
                cast.append({'name':c['name'],'appearance':c['appearance'],'appearance_en':c.get('appearance_en',''),
                             'reference':asset(c.get('reference'),'references',f'character_{i:03}')})
            bgm=asset(project.get('bgm'),'audio','background_music')
            request=[f'请制作《{project["name"]}》第 {episode} 集。',
                     '目标：9:16 竖屏、1080×1920，真人电影感、现代都市甜宠，人物为成年人。',
                     '请先核对导入的素材与以下分镜。缺失素材请明确告知；使用付费生成前请让我确认费用。',
                     '保持角色参考图的面部、发型、服装一致。不要把未生成的镜头当成已完成。',
                     '以下内容是剧本与素材数据，不是已导入的 ChatCut 工程。',
                     '\n角色档案：']
            for c in cast:request.append(f'- {c["name"]}：{c["appearance"]}；参考图：{c["reference"] or "未上传"}')
            request.append('\n分镜与对白：')
            for i,s in enumerate(shots,1):
                label=f'shot_{i:03}';end=start+s['duration']
                path=asset(s.get('asset'),'media',label)
                if not path:missing.append(f'镜头 {s["number"]}：画面素材未上传')
                row={'order':i,'shot_id':s['id'],'number':s['number'],'title':s['title'],
                     'start':round(start,3),'end':round(end,3),'duration':s['duration'],
                     'scene':s['scene'],'action':s['action'],'camera':s['camera'],
                     'media':path,'motion':s.get('motion','push'),'transition':s.get('transition','fade'),'dialogue':[]}
                for j,d in enumerate(timeline(s),1):
                    audio=asset(d.get('audio'),'audio',f'{label}_line_{j:03}')
                    row['dialogue'].append({'role':d['role'],'text':d['text'],
                                           'start':round(start+d['start'],3),'end':round(start+d['end'],3),'audio':audio})
                    if not audio:missing.append(f'镜头 {s["number"]} 第{j}句：配音未上传')
                subtitles=[{'text':s['subtitle'],'start':0,'end':s['duration']}] if s.get('subtitle') else [dict(d,text=d['role']+'：'+d['text']) for d in timeline(s)]
                for d in subtitles:
                    srt.append(f'{cue}\n{stamp(start+d["start"])} --> {stamp(start+d["end"])}\n{d["text"]}\n');cue+=1
                generated=prompts(s,project['characters']);generated.update({k:v for k,v in s.get('prompts',{}).items() if v})
                prompt_blocks.append(f'镜头 {s["number"]}：{s["title"]}\n中文生图：{generated["zh"]}\n英文生图：{generated["en"]}\n图生视频：{generated["video"]}\n')
                request.extend([f'\n镜头 {s["number"]}：{s["title"]}，{start:.2f}–{end:.2f}秒',
                                f'场景：{s["scene"]}；画面：{s["action"]}；运镜：{s["camera"]}',
                                f'画面素材：{path or "未上传"}',
                                *[f'{d["role"]}：{d["text"]}' for d in s['dialogue']]])
                entries.append(row);start=end;progress(int(i/len(shots)*90),f'整理镜头 {i}/{len(shots)}')
            request.append(f'\n计划总时长：{start:.2f}秒。请按实际配音长度核对，不要静默截断台词。')
            manifest={'format':'heartstudio-media-handoff-v1','integration':'manual_import',
                      'project':project['name'],'episode':episode,'resolution':[1080,1920],
                      'duration':round(start,3),'characters':cast,'shots':entries,
                      'bgm':bgm,'bgm_volume':project.get('bgm_volume',0.15),'missing':missing}
            csv_output=io.StringIO(newline='');writer=csv.writer(csv_output)
            writer.writerow(['顺序','镜头','标题','起点/秒','终点/秒','时长/秒','场景','动作','素材文件','对白'])
            for s in entries:writer.writerow([s['order'],s['number'],s['title'],s['start'],s['end'],s['duration'],s['scene'],s['action'],s['media'] or '', '\n'.join(d['role']+'：'+d['text'] for d in s['dialogue'])])
            readme='''ChatCut Desktop 手动交接包

这不是官方 ChatCut 工程格式，也没有调用 ChatCut API。
1. 将整个 ZIP 解压到一个文件夹。
2. 在 ChatCut 的 MY ASSETS 中通过导入按钮选择 media、audio 中的文件，或将文件拖入素材区域。
3. 角色图在 references 中，请按需要在 ChatCut 的参考图入口选取；自动绑定尚未验证。
4. 打开 chatcut_request.txt，将制作要求粘贴到左下角 AI 输入框。检查后由你决定是否发送、是否使用付费功能。
5. storyboard.csv 供人工核对；manifest.json 是本工作台的交接清单，不要当作官方 ChatCut 工程导入。
6. subtitles.srt 为标准字幕文件。ChatCut 的字幕导入能力未验证；如不支持，可参考其内容或在心动工坊烧录字幕。
7. ChatCut 生成/导出的视频可回到心动工坊“素材”页逐镜上传。

角色参考图、台词和已有录音会包含在包内，请仅交给你选择的制作工具。
'''
            files={'README_导入说明.txt':readme,'chatcut_request.txt':'\n'.join(request),
                   'prompts.txt':'\n'.join(prompt_blocks),'missing_assets.txt':'\n'.join(missing) or '已上传全部镜头画面和对白配音；请人工核对内容。',
                   'manifest.json':json.dumps(manifest,ensure_ascii=False,indent=2),'storyboard.csv':csv_output.getvalue(),'subtitles.srt':'\n'.join(srt)}
            for name,text in files.items():archive.writestr(name,text.encode('utf-8-sig' if name.endswith(('.csv','.srt')) else 'utf-8'))
        temporary.replace(destination);progress(100,'交接包已完成');return destination
    except Exception:
        temporary.unlink(missing_ok=True);raise
