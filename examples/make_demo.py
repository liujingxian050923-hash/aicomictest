"""Create explicitly labelled synthetic TEST assets, never AI footage.
Usage: python examples/make_demo.py
"""
import math
import struct
import sys
import wave
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.media import subtitle_font
out=Path(__file__).parent/'demo_assets';out.mkdir(exist_ok=True)
font=subtitle_font()
for i in range(1,7):
    im=Image.new('RGB',(1080,1920),(60+i*12,42+i*5,110+i*10));d=ImageDraw.Draw(im)
    d.text((110,650),f'测试素材 / 镜头 {i}',font=font,fill='white')
    d.text((110,740),'非 AI 人物画面',font=font,fill='white');im.save(out/f'shot_{i}.png')
with wave.open(str(out/'test_tone.wav'),'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
    w.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(2*math.pi*440*j/48000))) for j in range(48000)))
print(f'生成了 6 张明确标记的测试图片和 1 秒测试音，不是配音：{out.resolve()}')
