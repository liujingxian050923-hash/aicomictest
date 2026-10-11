# 心动工坊 · AI 漫剧自动制作工作台

面向 Windows 本地使用的中文 Web 工作台。第一阶段 MVP：导入剧本、编辑分镜与角色档案、生成中英提示词、手动上传图片/视频与对白录音、字幕时间轴、背景音乐、FFmpeg 导出 1080×1920 MP4。免费本地核心，无须付费 AI API。

## Windows 安装与启动

1. Windows 启动脚本使用 **Python 3.12**。如果已安装新版 Python 安装管理器，在命令提示符运行 `py install 3.12`，再运行 `py -3.12 --version` 验证。也可从 python.org 安装 Python 3.12（勾选 Add Python to PATH）。
2. 安装带 `libx264`、AAC 的完整 FFmpeg；将包含 `ffmpeg.exe`、`ffprobe.exe` 的 `bin` 目录加入 Windows 用户 PATH。可从 [FFmpeg 官方下载页面](https://ffmpeg.org/download.html) 选择 Windows 构建。打开新终端运行 `ffmpeg -version`、`ffprobe -version` 确认。
3. 在本项目目录双击 **`setup.bat`**，安装项目虚拟环境并检查依赖、编码器及中文字体。
4. 双击 **`start.bat`**，在浏览器地址栏输入 `http://127.0.0.1:8000`。保持终端开启，按 Ctrl+C 停止。

工作台只监听本机。不需要 Node.js、数据库、Docker 或前端构建。首次安装需要联网下载 Python 包；之后解析、手动制作和导出可以离线工作。启动脚本不会自动下载 FFmpeg 或更改系统 PATH；仅在当前进程临时将 `D:\ffmpeg\bin` 加入 PATH。脚本以 CRLF 换行保存，启动失败时保留窗口和错误。

若 FFmpeg 未加入 PATH，可在启动前设置（不加引号到变量值中）：

```bat
set "FFMPEG_PATH=C:\tools\ffmpeg\bin\ffmpeg.exe"
set "FFPROBE_PATH=C:\tools\ffmpeg\bin\ffprobe.exe"
set "STUDIO_FONT=C:\Windows\Fonts\msyh.ttc"
start.bat
```

`STUDIO_FONT` 可选，默认寻找 Windows 微软雅黑/黑体或 Linux Noto CJK。工作台用 Pillow 绘制中文透明字幕，再用 FFmpeg 叠加；不依赖 `drawtext` 的 Windows 路径转义。环境变量必须在启动服务前设置。`.env` 文件不会自动加载。

## 制作《老板，你的恋爱脑藏不住了》

1. **项目管理**：新建项目，填写名称。项目默认保存在项目目录 `data/`，关闭程序后不丢失。
2. **剧本**：上传你自己的原始 Word；仓库不包含完整剧本或角色参考图片。也可先导入 `examples/一分钟示例.txt` 测试工作流。已实测识别 **5 集、30 镜，每集 60 秒**。表格中的角色描述也按文档顺序解析；Word 内嵌图片不会自动绑定角色。
3. **角色**：上传男女主参考图片，编辑固定外观；可补充英文外观。在 Windows 上选择不同系统音色。屏幕消息也可能被识别为发言者，可在分镜中删掉该对白并改用整镜字幕。
4. **分镜**：选择集数，调整场景、动作、镜头运动、光线、时长。对白每行 `角色 | 台词`。编辑后点击右上角 **保存更改**；修改对白会清空该句关联的录音。可新增、删除镜头。无明确镜头标记时按非空段落拆分，需人工校正。
5. **提示词**：点击“为所有镜头生成提示词”。自动引用角色外观，生成中文/英文生图和中英图生视频提示词，均可修改复制。**英文是离线关键词模板，不是完整逐句翻译**；填写英文场景、动作、运镜和外观可以覆盖模板推断。外部生成服务还需接收参考图，单纯复制文字不能锁定面孔。
6. **素材**：逐镜上传 JPG/PNG/WebP 图片或 MP4/MOV/WebM/MKV 视频。可替换任意镜头。图片支持缓慢推近、拉远、平移、静止；视频循环到指定镜头时长，居中填满 9:16 并裁切；素材原声默认静音。
7. **配音**：逐句上传 WAV/MP3/M4A/OGG/FLAC。自动探测录音长度，按实际录音长度/未录音文本长度比例分配时间槽。点击“按配音自动增加镜头时长”避免截断录音；长台词可能让整集超过 60 秒，需调整分镜或缩短台词。可上传背景音乐并设置音量。未配音的句子仍有字幕，声音为空。
8. **预览与导出**：导出当前集。任务显示进度和错误；失败后修正素材/配音并重试。完成后可播放真实成片，下载 MP4 和 SRT。导出历史在重启后仍可查看。

每镜可选择直接切换或淡入淡出至黑场（两侧各 0.2 秒，不重叠时间轴）。默认逐句字幕；整镜字幕字段非空时覆盖对白字幕。字幕每条最多五行，过长会明确报错。时长限制 0.2～120 秒/镜，每个文件最多 500 MB，剧本最多 20 MB。导出为 1080×1920、25 fps、H.264/AAC MP4；不默认硬改到 60 秒，实际时长是镜头时长之和。

## 免费自动配音

自动配音通过 **Windows PowerShell + System.Speech / SAPI** 调用系统本地语音。角色页列出实际安装的音色，各角色可选择不同音色。中文效果和男女声是否齐全取决于操作系统及语音包；不保证所有 Windows 都自带两种中文音色。请在 Windows 设置中安装可供桌面 SAPI 使用的中文语音包，或录制/外部制作后导入配音。

“为当前集自动配音”会替换该集已有的所有对白录音，并显示逐句进度。无 SAPI 时返回明确错误，不会生成假录音。**当前验证环境是 Linux，因此实际 Windows SAPI 测试未运行**；已附带 Windows 原生测试供本机验证。

## AI 服务扩展

当前为真实的 **手动素材模式**，尚未接入 Runway 或其他远程生成服务。`/api/projects/{id}/generate` 返回 501 并明确说明未配置；不会凭空返回视频。

`studio/providers.py` 定义图像/视频共用的 `GenerationProvider.submit(kind, prompt, references)` 与 `poll(task_id)` 接口以及服务注册表。新增适配器需实现真实提交、轮询、失败处理及下载验证，再接入任务 API。预留接口目前是扩展入口，**不是已可调用的 Runway 客户端**。密钥只能通过 `os.environ` 读取（例如 `RUNWAY_API_KEY`），不要写入源代码、项目 JSON、日志或提交 `.env`。

## 测试与示例

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe examples\make_demo.py
```

`make_demo.py` 生成 6 张明确标注“非 AI 人物画面”的测试图及 1 秒测试音。导入 `examples/一分钟示例.txt`，将 `examples/demo_assets/shot_1.png` 到 `shot_6.png` 上传到对应镜头，即可导出 60 秒测试片。测试音用于检查音频通路，**不是台词配音**。

自动化测试覆盖合成五集剧本解析、五集时长、角色提示词、API 存储、路径与跨站保护、缺失素材错误、真正的图片/视频拼接、中文字幕、导入录音、BGM、MP4/SRT 输出及画面/音频解码。Windows 原生语音测试仅在 Windows 执行；Linux 上明确跳过。浏览器流程另已用 Chromium 验证，不作为默认 pytest 依赖。

Linux/macOS 开发：

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python check_environment.py
.venv/bin/python -m uvicorn studio.app:app --host 127.0.0.1 --port 8000
```

Linux 需系统 FFmpeg 和中文字体（例如 Noto CJK）。macOS 可用导入录音，当前不提供 SAPI。

## 文件与备份

- `studio/app.py`：本地 FastAPI、项目/素材 API、后台任务与进度。
- `studio/parser.py`：DOCX/TXT 解析、提示词、配音时间轴。
- `studio/media.py`：FFmpeg 合成、字幕绘制、媒体探测。
- `studio/tts.py`：Windows 原生配音。
- `studio/static/`：无前端构建依赖的中文界面。
- `data/<项目ID>/project.json`：持久化项目。
- `data/<项目ID>/assets/`：角色图、镜头素材、配音、背景音乐。
- `data/<项目ID>/exports/<任务ID>/`：成片、SRT 与中间产物。
- `data/.jobs/`：任务状态；重启会将未完成任务标记为中断。

完整备份/迁移请在停止服务后复制 **整个 data 文件夹**。项目管理页可下载/恢复 JSON，但 JSON 不包含媒体，恢复到新项目后要重新上传。可用 `STUDIO_DATA` 指定数据目录。工作台不自动删除替换后旧素材和失败导出的中间文件，方便恢复；磁盘不足时停止服务后备份再清理。导出较长剧集需要足够磁盘空间和 CPU；任务串行执行，每个 FFmpeg 最多两条编码线程。

## 常见错误

- **安装管理器选择了 Python 3.15**：运行 `py install 3.12`，然后 `setup.bat`。若提示已有虚拟环境版本不符，将项目内 `.venv` 文件夹改名为 `.venv-old` 后重试；不需要卸载系统 Python，也不要删除 `data`。

- **找不到 FFmpeg**：安装完整构建，加入 PATH 后重新开终端；或设置 `FFMPEG_PATH` / `FFPROBE_PATH`。
- **找不到中文字体**：设置 `STUDIO_FONT` 为支持中文的 TTF/TTC 文件。
- **配音超过时间槽**：在配音页自动适配，检查是否超出 60 秒目标，再导出。
- **缺少镜头素材**：给报错镜头逐个上传图片或视频。
- **8000 端口占用**：停止原工作台，或手动用 `--port 8001` 启动并在对应地址访问。
- **任务中断**：服务重启不会恢复 FFmpeg 进程，任务会标记失败；已有完整成片可从导出历史访问，其他任务需重试。

第一阶段交付不包含在线 AI 视频生成、自动口型同步或专业多轨剪辑器。当前版本提供可检查、可替换、可导出的本地制作闭环。
