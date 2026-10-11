"""Non-destructive preflight used by Windows launchers and cloud setup."""
import importlib.util
import os
import platform
import subprocess
import sys

errors=[]
print(f'Python: {sys.version.split()[0]} / {platform.system()}')
if sys.version_info<(3,11):errors.append('请安装 Python 3.11 或更高版本，建议 Python 3.12')
for name in ('fastapi','uvicorn','multipart','docx','PIL'):
    if not importlib.util.find_spec(name):errors.append(f'缺少 Python 依赖 {name}，请运行 setup.bat')
if not errors:
    from studio.media import binary,run,subtitle_font
    for name in ('ffmpeg','ffprobe'):
        try:
            value=run([binary(name),'-version']);print(value.splitlines()[0])
        except Exception as exc:errors.append(str(exc))
    try:
        encoders=run([binary('ffmpeg'),'-hide_banner','-encoders'])
        if 'libx264' not in encoders or ' aac ' not in encoders:errors.append('FFmpeg 须支持 libx264 和 AAC 编码')
        filters=run([binary('ffmpeg'),'-hide_banner','-filters'])
        for f in ('zoompan','overlay','amix','fade'):
            if f not in filters:errors.append('FFmpeg 缺少滤镜 '+f)
    except Exception as exc:errors.append(str(exc))
    try:subtitle_font();print('中文字幕字体：就绪')
    except Exception as exc:errors.append(str(exc))
    from studio.tts import available
    print('离线配音：'+('Windows SAPI（音色请在角色页选择）' if available() else '本系统不支持 SAPI，可导入录音'))
if errors:
    for e in errors:print('错误：'+e)
    sys.exit(1)
print('环境检查通过。')
