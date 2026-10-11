import json
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .parser import timeline

WIDTH, HEIGHT, FPS = 1080, 1920, 25

def binary(name):
    path=os.getenv(name.upper()+'_PATH') or shutil.which(name)
    if not path: raise ValueError(f'未找到 {name}，请安装 FFmpeg 并加入 PATH，或设置 {name.upper()}_PATH')
    return path

def run(args,cwd=None):
    result=subprocess.run(args,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=600)
    if result.returncode: raise ValueError(result.stderr[-3500:])
    return result.stdout

def probe(path):
    return json.loads(run([binary('ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(path)]))

def audio_duration(path):
    info=probe(path)
    if not any(s['codec_type']=='audio' for s in info['streams']): raise ValueError('文件不包含音轨')
    return float(info['format']['duration'])

def subtitle_font():
    candidates=[os.getenv('STUDIO_FONT',''), 'C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc']
    for path in candidates:
        if path and Path(path).is_file(): return ImageFont.truetype(path,48)
    raise ValueError('未找到中文字幕字体。请通过 STUDIO_FONT 指定支持中文的 TTF/TTC 字体路径')

def subtitle_png(text,path):
    font=subtitle_font(); canvas=Image.new('RGBA',(WIDTH,HEIGHT),(0,0,0,0)); draw=ImageDraw.Draw(canvas)
    lines=[]; line=''
    for char in text.replace('\n',' '):
        if draw.textlength(line+char,font=font)>930:
            lines.append(line); line=''
        line+=char
    if line: lines.append(line)
    if len(lines)>5: raise ValueError('单条字幕过长，请拆分对白（最多五行）')
    y=HEIGHT-200-65*len(lines)
    for line in lines:
        box=draw.textbbox((0,0),line,font=font); width=draw.textlength(line,font=font)
        draw.rounded_rectangle((int((WIDTH-width)/2)-20,y-10,int((WIDTH+width)/2)+20,y+62),radius=12,fill=(0,0,0,150))
        draw.text(((WIDTH-width)/2,y),line,font=font,fill='white',stroke_width=2,stroke_fill='black'); y+=65
    canvas.save(path)

def export(project,episode,root,work,progress):
    ffmpeg=binary('ffmpeg'); binary('ffprobe')
    shots=[s for s in project['shots'] if s['episode']==episode]
    if not shots: raise ValueError('该集没有镜头')
    missing=[str(s['number']) for s in shots if not s.get('asset')]
    if missing: raise ValueError('请先上传镜头素材：'+','.join(missing))
    work.mkdir(parents=True,exist_ok=True); segments=[]; global_start=0; srt=[]; cue=1
    for i,shot in enumerate(shots):
        duration=float(shot['duration'])
        if not 0.2<=duration<=120: raise ValueError('每镜时长须为 0.2～120 秒')
        asset=root/shot['asset']; info=probe(asset)
        if not any(s['codec_type']=='video' for s in info['streams']): raise ValueError(f"镜头 {shot['number']} 素材不含画面")
        image=asset.suffix.lower() in ('.jpg','.jpeg','.png','.webp')
        args=[ffmpeg,'-y','-hide_banner','-loglevel','error','-threads','2','-filter_complex_threads','1']
        args+=['-loop','1','-framerate',str(FPS),'-i',str(asset)] if image else ['-stream_loop','-1','-i',str(asset)]
        filters=[]
        base=f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1'
        if image:
            motion=shot.get('motion','push'); frames=int(duration*FPS)
            zoom="min(1.0+on*0.0004,1.12)" if motion=='push' else (f"max(1.12-on*0.0004,1.0)" if motion=='pull' else ('1.06' if motion=='pan' else '1.0'))
            x="(iw-iw/zoom)*on/"+str(max(frames,1)) if motion=='pan' else 'iw/2-iw/zoom/2'
            base+=f",zoompan=z='{zoom}':x='{x}':y='ih/2-ih/zoom/2':d=1:s={WIDTH}x{HEIGHT}:fps={FPS}"
        else: base+=f',fps={FPS}'
        base+=f',trim=duration={duration},setpts=PTS-STARTPTS,format=yuv420p'
        if shot.get('transition')=='fade': base+=f',fade=t=in:st=0:d=0.2,fade=t=out:st={max(0,duration-.2)}:d=0.2'
        filters.append('[0:v]'+base+'[v0]'); input_count=1; video_label='v0'
        rows=timeline(shot)
        if shot.get('subtitle'): subs=[{'text':shot['subtitle'],'start':0,'end':duration}]
        else: subs=[{**d,'text':d['role']+'：'+d['text']} for d in rows]
        for j,d in enumerate(subs):
            png=work/f'sub_{i}_{j}.png'; subtitle_png(d['text'],png)
            args+=['-loop','1','-framerate',str(FPS),'-i',str(png)]
            output=f'v{j+1}'; filters.append(f"[{video_label}][{input_count}:v]overlay=0:0:enable='between(t,{d['start']},{d['end']})'[{output}]")
            video_label=output; input_count+=1
            def stamp(seconds):
                ms=round(seconds*1000); return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
            srt.append(f"{cue}\n{stamp(global_start+d['start'])} --> {stamp(global_start+d['end'])}\n{d['text']}\n"); cue+=1
        audio_labels=[]
        for j,d in enumerate(rows):
            if not d.get('audio'): continue
            audio=root/d['audio']; actual=audio_duration(audio); slot=d['end']-d['start']
            if actual>slot+0.15: raise ValueError(f"镜头 {shot['number']} 第{j+1}句配音 {actual:.1f}s 超过时间槽 {slot:.1f}s；请在配音页自动适配或增加镜头时长")
            args+=['-i',str(audio)]
            label=f'a{j}'; delay=round(d['start']*1000)
            filters.append(f'[{input_count}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[{label}]'); input_count+=1; audio_labels.append(label)
        if audio_labels:
            filters.append(''.join('['+a+']' for a in audio_labels)+f'amix=inputs={len(audio_labels)}:normalize=0,apad,atrim=duration={duration}[audio]')
        else: filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={duration}[audio]')
        segment=work/f'shot_{i}.mp4'
        args+=['-filter_complex',';'.join(filters),'-map',f'[{video_label}]','-map','[audio]','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-threads','2',str(segment)]
        run(args); segments.append(segment); global_start+=duration; progress(int((i+1)/len(shots)*85),f'镜头 {i+1}/{len(shots)} 已合成')
    # Segment names are generated internally, so concat entries never contain user paths.
    listing=work/'concat.txt'; listing.write_text(''.join(f"file 'shot_{i}.mp4'\n" for i in range(len(segments))),encoding='utf-8')
    joined=work/'joined.mp4'; run([ffmpeg,'-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-c','copy',str(joined)])
    target=work/'encoding.mp4'
    if project.get('bgm'):
        run([ffmpeg,'-y','-v','error','-i',str(joined),'-stream_loop','-1','-i',str(root/project['bgm']),'-filter_complex',f"[1:a]volume={project.get('bgm_volume',0.15)},aresample=48000[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[a]",'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-t',str(global_start),'-movflags','+faststart',str(target)])
    else: run([ffmpeg,'-y','-v','error','-i',str(joined),'-c','copy','-movflags','+faststart',str(target)])
    (work/'subtitles.srt').write_text('\n'.join(srt),encoding='utf-8-sig')
    result=probe(target); video=next(s for s in result['streams'] if s['codec_type']=='video')
    if (video['width'],video['height'])!=(WIDTH,HEIGHT): raise ValueError('导出分辨率校验失败')
    completed=work/'final.mp4';target.replace(completed)
    progress(100,'导出完成'); return completed
