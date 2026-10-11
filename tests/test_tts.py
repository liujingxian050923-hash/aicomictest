import pytest
from studio import tts
from studio.media import audio_duration

@pytest.mark.skipif(not tts.available(),reason='Windows SAPI requires a real Windows machine')
def test_native_windows_sapi(tmp_path):
    voices=tts.voices()
    assert voices, '请安装系统语音包'
    output=tmp_path/'voice.wav'
    tts.synthesize('你好，这是漫剧工作台的本地配音测试。',voices[0],output)
    assert audio_duration(output)>0
