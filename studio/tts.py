import json
import platform
import shutil
import subprocess
from pathlib import Path

SCRIPT = r'''
param([string]$RequestPath)
Add-Type -AssemblyName System.Speech
$request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($request.voice) { $synth.SelectVoice([string]$request.voice) }
    $synth.SetOutputToWaveFile([string]$request.output)
    $synth.Speak([string]$request.text)
} finally { $synth.Dispose() }
'''

def available(): return platform.system()=='Windows' and bool(shutil.which('powershell'))

def voices():
    if not available(): return []
    code='[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; @($s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }) | ConvertTo-Json -Compress; $s.Dispose()'
    r=subprocess.run(['powershell','-NoProfile','-Command',code],capture_output=True,timeout=30)
    if r.returncode: raise ValueError('无法读取 Windows SAPI 音色')
    value=json.loads(r.stdout.decode('utf-8-sig',errors='replace') or '[]')
    return value if isinstance(value,list) else [value]

def synthesize(text,voice,output):
    if not available(): raise ValueError('本机未提供 Windows SAPI。请在 Windows 上使用自动配音，或导入已有配音文件')
    script=output.with_suffix('.ps1'); request=output.with_suffix('.json')
    script.write_text(SCRIPT,encoding='utf-8-sig'); request.write_text(json.dumps({'text':text,'voice':voice,'output':str(output.resolve())},ensure_ascii=False),encoding='utf-8-sig')
    try:
        r=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-RequestPath',str(request)],capture_output=True,timeout=180)
        if r.returncode or not output.exists(): raise ValueError('Windows 配音失败；请检查所选音色和系统语音包：'+r.stderr.decode(errors='replace')[-1000:])
    finally:
        script.unlink(missing_ok=True); request.unlink(missing_ok=True)
