from studio.parser import parse, prompts, timeline

def test_episodes_and_dialogue():
    text='''许莓｜女主
成年职场新人；丸子头、浅蓝衬衫。
第01集 测试
时长：约60秒 | 场景：办公室｜午后 | 核心：甜宠
镜头 01 · 偷看 [0—10s]
画面动作：许莓托腮看沈知行工作。
对白：沈知行：“看我干什么？”许莓：“因为你好看呀。”
第02集 测试
镜头 01 [10—18s]
对白：许莓（小声）：“喜欢你。”
'''
    shots,cast=parse(text)
    assert len(shots)==2 and shots[1]['episode']==2 and shots[1]['duration']==8
    assert shots[0]['dialogue'][1]['role']=='许莓'
    assert '丸子头' in cast[0]['appearance']
    p=prompts(shots[0],cast)
    assert '许莓' in p['zh'] and 'modern office' in p['en'] and 'hair in a bun' in p['en']
    t=timeline(shots[0]);assert t[0]['start']==0 and t[-1]['end']==10

def test_audio_timeline():
    s={'duration':7,'dialogue':[{'role':'甲','text':'短','audio_seconds':5},{'role':'乙','text':'很长的文本','audio_seconds':1}]}
    rows=timeline(s);assert rows[0]['end']>5 and rows[-1]['end']==7

def test_plain_text_fallback():
    shots,_=parse('第一段故事\n第二段故事')
    assert len(shots)==2 and shots[0]['subtitle']=='第一段故事'
