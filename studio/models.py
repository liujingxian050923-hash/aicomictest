from pydantic import BaseModel, Field, ConfigDict

class Dialogue(BaseModel):
    role: str = Field(max_length=80)
    text: str = Field(max_length=2000)
    audio: str | None = None
    audio_seconds: float | None = Field(default=None,ge=0,le=300)

class Shot(BaseModel):
    id: int = Field(ge=1)
    episode: int = Field(ge=1,le=1000)
    number: int = Field(ge=1)
    title: str = Field(default='',max_length=200)
    duration: float = Field(default=10,ge=0.2,le=120)
    scene: str = Field(default='',max_length=2000)
    action: str = Field(default='',max_length=4000)
    camera: str = Field(default='缓慢推近',max_length=2000)
    framing: str = Field(default='中近景',max_length=1000)
    light: str = Field(default='柔和暖光',max_length=1000)
    dialogue: list[Dialogue] = Field(default_factory=list,max_length=100)
    subtitle: str = Field(default='',max_length=2000)
    asset: str | None = None
    motion: str = Field(default='push',pattern='^(push|pull|pan|still)$')
    transition: str = Field(default='fade',pattern='^(fade|cut)$')
    prompts: dict[str,str] = Field(default_factory=dict)
    scene_en: str = Field(default='',max_length=2000)
    action_en: str = Field(default='',max_length=4000)
    camera_en: str = Field(default='',max_length=2000)

class Character(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    appearance: str = Field(default='',max_length=4000)
    appearance_en: str = Field(default='',max_length=4000)
    voice: str = Field(default='',max_length=300)
    reference: str | None = None

class Project(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = ''
    name: str = Field(min_length=1,max_length=200)
    script: str = Field(default='',max_length=1000000)
    shots: list[Shot] = Field(default_factory=list,max_length=1000)
    characters: list[Character] = Field(default_factory=list,max_length=100)
    bgm: str | None = None
    bgm_volume: float = Field(default=0.15,ge=0,le=1)
