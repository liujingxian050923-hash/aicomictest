import io
import json
import shutil
import subprocess
import wave
from pathlib import Path
import pytest
from PIL import Image
from test_api import client, create, wait_job
from studio.media import probe, subtitle_font

@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg required')
def test_real_export_image_video_subtitle_audio_bgm(client,tmp_path):
    subtitle_font() # Required for this workflow; do not silently skip missing fonts.
    p=create(client);pid=p['id']
    script='''第01集 测试
镜头 01 [0—1s]
画面动作：许莓微笑
对白：许莓：“你好”
镜头 02 [1—2s]
字幕：沈知行：我在
'''
    p=client.post(f'/api/projects/{pid}/script',files={'file':('demo.txt',script.encode())}).json()
    image=io.BytesIO();Image.new('RGB',(320,480),(110,70,155)).save(image,'PNG')
    r=client.post(f'/api/projects/{pid}/shots/1/asset',files={'file':('image.png',image.getvalue())});assert r.status_code==200
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=navy:s=320x480:r=25','-t','0.5','-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
    assert client.post(f'/api/projects/{pid}/shots/2/asset',files={'file':('source.mp4',source.read_bytes())}).status_code==200
    wav=tmp_path/'voice.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.4','-ar','48000',str(wav)],check=True)
    assert client.post(f'/api/projects/{pid}/shots/1/dialogue/0/audio',files={'file':('voice.wav',wav.read_bytes())}).status_code==200
    assert client.post(f'/api/projects/{pid}/bgm',files={'file':('music.wav',wav.read_bytes())}).status_code==200
    task=client.post(f'/api/projects/{pid}/export?episode=1').json();job=wait_job(client,task['id'])
    assert job['status']=='completed',job
    video=job['output']['video'];response=client.get(video);assert response.status_code==200
    final=tmp_path/'output.mp4';final.write_bytes(response.content);info=probe(final)
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'])==(1080,1920) and v['codec_name']=='h264'
    assert abs(float(info['format']['duration'])-2)<.15
    assert any(s['codec_type']=='audio' for s in info['streams'])
    srt=client.get(job['output']['subtitles']).content.decode('utf-8-sig')
    assert '许莓：你好' in srt and '00:00:01,000' in srt
    # Decode an actual frame and audio; streams alone would not prove content.
    frame=tmp_path/'frame.png';subprocess.run(['ffmpeg','-y','-v','error','-ss','0.5','-i',str(final),'-frames:v','1',str(frame)],check=True)
    im=Image.open(frame).convert('RGB');assert max(sum(im.getpixel((x,1690))) for x in range(350,730))>650
    decoded=tmp_path/'decoded.wav';subprocess.run(['ffmpeg','-y','-v','error','-i',str(final),'-vn','-c:a','pcm_s16le',str(decoded)],check=True)
    with wave.open(str(decoded)) as audio:assert any(audio.readframes(20000))
    assert len(client.get(f'/api/projects/{pid}/exports').json())==1
