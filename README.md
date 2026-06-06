# Novel-to-Script — AI 小说转剧本工具

**核心场景：网文漫剧（动态漫画/有声漫画）**，同时兼容影视剧本、广播剧/有声书剧本、舞台剧。

将网文小说自动转换为结构化剧本（YAML 格式），支持按集组织（每集 3-5 分钟）、自动规划集数、生成悬念钩子（卡点）。兼容 [notel](https://github.com/worldwonderer/oh-story-claudecode) 网文写作项目结构，也支持任意文本文件输入。

---

## 功能特性

- **网文漫剧为核心**：原生支持按集组织（Episode）、自动规划集数（3-5 分钟/集）、生成悬念钩子
- **四种剧本类型**：网文漫剧（`manju`，默认）、影视剧本（`screenplay`）、广播剧/有声书（`audio_drama`）、舞台剧（`stage_play`）
- **双模式转换**：
  - **规则模式（默认）**：零成本，基于启发式规则快速生成初稿
  - **AI 模式（可选）**：调用 Claude API 进行高精度场景拆解和对白归因
- **两种画面粒度**（漫剧）：
  - **简单模式**：文字分镜（景别 + 内容描述）
  - **详细模式**：标准漫画分镜格（格内画面 + 气泡位置 + 视觉拟声词）
- **漫剧特效枚举**：预定义 15 种常见漫剧视觉特效（闪白、瞳孔放大、回忆滤镜、弹幕式字幕等）
- **溯源保留**：每个 Scene/Episode 自动标注来源小说章节号
- **Schema 校验**：内置 Pydantic 模型校验，确保输出结构正确

---

## 快速开始

### Docker 一键启动（推荐）

```bash
git clone https://github.com/qwe605/novel-to-script.git
cd novel-to-script
docker compose up -d
```

打开 http://localhost:5173 ，点击 **🎲 加载示例小说** → **🚀 开始转换**，30 秒内看到结果。

### 本地开发

```bash
cd novel-to-script/scripts
pip install -r requirements.txt
```

### 2. 转换 notel 项目为漫剧

```bash
python novel_to_script.py \
  --input "穿成病娇大佬的亡妻" \
  --script-type manju \
  --validate
```

输出：`穿成病娇大佬的亡妻/剧本/穿成病娇大佬的亡妻_剧本.yaml`

### 3. 漫剧详细分镜模式

```bash
python novel_to_script.py \
  --input "穿成病娇大佬的亡妻" \
  --script-type manju \
  --panel-mode detailed \
  --validate
```

### 4. 转换任意文本文件

```bash
python novel_to_script.py \
  --input "novel.txt" \
  --source-type text \
  --script-type manju
```

### 5. AI 深度模式（需 API Key）

```bash
export ANTHROPIC_API_KEY="sk-..."
python novel_to_script.py \
  --input "novel.txt" \
  --mode ai \
  --script-type manju
```

---

## CLI 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--input`, `-i` | 是 | — | 输入路径：notel 项目目录或小说文本文件 |
| `--output`, `-o` | 否 | 自动 | 输出 YAML 文件路径 |
| `--script-type`, `-t` | 否 | `manju` | 剧本类型：`manju` / `screenplay` / `audio_drama` / `stage_play` |
| `--source-type`, `-s` | 否 | `auto` | 输入源类型：`auto` / `notel` / `text` |
| `--mode`, `-m` | 否 | `rule` | 检测模式：`rule`（规则）/ `ai`（AI 深度） |
| `--panel-mode` | 否 | `simple` | **【漫剧】** 画面粒度：`simple` / `detailed` |
| `--api-key` | 否 | 环境变量 | Anthropic API Key（AI 模式） |
| `--validate`, `-v` | 否 | False | 输出后执行 Schema 校验 |

---

## Claude Code Skill 用法

在 Claude Code 环境中，使用以下命令触发转换：

```
/story-to-script
```

或中文别名：

```
/转剧本
```

Skill 会自动：
1. 发现当前活跃 notel 项目
2. 读取 `正文.md` + `设定.md` + `小节大纲.md`
3. 调用 `script-converter` Agent 进行 AI 深度转换
4. **漫剧模式下自动规划集数**，生成每集悬念钩子
5. 将 YAML 剧本落盘到 `{书名}/剧本/` 目录

---

## 演示流程

1. 打开前端 → 点击 **🎲 加载示例小说（3章）** 或上传自己的小说文件
2. 选择剧本类型（默认：网文漫剧）→ 点击 **🚀 开始转换**
3. 实时查看进度条，转换完成后自动展示：
   - **剧本预览**：场景/节拍卡片，点击展开编辑对白
   - **分镜预览**（漫剧）：按集筛选，景别/特效可视化
   - **YAML 源码**：语法高亮，可直接编辑后下载
4. 点击 **⬇️ 下载 YAML** 导出编辑后的剧本

---

## 运行测试

```bash
cd scripts
pip install pytest
python -m pytest tests/ -v
```

当前覆盖 59 个测试用例：YAML Schema 校验、集数规划算法、小说解析器。

---

## 项目目录结构

```
novel-to-script/
├── schema/
│   ├── script-schema-v1.md      # Schema 设计文档（含设计原因、漫剧特效枚举）
│   └── script-schema-v1.yaml    # 正式 Schema 模板（影视+漫剧示例）
├── scripts/
│   ├── novel_to_script.py       # CLI 主入口（含集数自动规划算法）
│   ├── novel_parser.py          # 小说解析器（notel + 通用文本）
│   ├── scene_detector.py        # 场景检测引擎（规则 + AI 双模）
│   ├── yaml_exporter.py         # YAML 序列化与 Pydantic 校验（含 Episode/ManjuExtensions）
│   └── requirements.txt
├── references/                  # 【专业提示词】直接复用自超无穹大师 skill
│   ├── screenwriting-master-SKILL.md   # 编剧铁律、戏剧动作、潜台词、双轨节奏、自检体系
│   ├── director-master-SKILL.md        # 导演五步工作流、叙事目的分析法、镜头设计逻辑
│   ├── shot-design.md                  # 动作-反应单元（12种变体）、切镜逻辑、对白场景处理、70/30出彩配比
│   ├── core-methodology.md             # 叙事目的分析法、六维定调、节奏规划
│   ├── storyboard-format.md            # 九列分镜格式、时长估算（551镜头统计）
│   ├── screenwriting-master-brain.js   # 格式路由、选题路径、写作红线检查（决策引擎）
│   ├── director-master-brain.js        # 六维度检测、镜头组类型判断、景别推荐（决策引擎）
│   ├── genre-A-mood.md                 # 六维定调-A：情绪基调与风格（8个子类）
│   ├── genre-B-genre.md                # 六维定调-B：类型片（8个子类）
│   ├── genre-C-action.md               # 六维定调-C：动作与对抗（4个子类）
│   ├── genre-D-theme.md                # 六维定调-D：题材与关系（6个子类）
│   ├── genre-E-form.md                 # 六维定调-E：形式与叙事手法（5个子类）
│   └── genre-F-social.md               # 六维定调-F：社会视角（4个子类+附录）
├── examples/
│   ├── demo_manju.yaml          # 【漫剧示例】用现有小说前3章生成（3集）
│   ├── demo_screenplay.yaml     # 影视剧本示例
│   ├── demo_audio_drama.yaml    # 广播剧示例
│   └── demo_stage_play.yaml     # 舞台剧示例
└── README.md
```

---

## Schema 设计概览

### 漫剧核心结构

```yaml
script:
  script_type: "manju"
  episodes:           # 集列表（漫剧核心组织单元）
    - episode_id: "ep_01"
      episode_number: 1
      title: "亡妻归来"
      hook: "林婉猛然睁眼，发现自己躺在太平间——而她已经是'死人'。"
      target_duration_seconds: 240
      scenes: ["sc_001", "sc_002"]
      cover_prompt: "黑底，女主睁眼特写，标题大字"
  scenes:
    - scene_id: "sc_001"
      beats:
        - beat_id: "b_001"
          type: "action"
          content: "林婉猛然睁眼，瞳孔在黑暗中急剧收缩。"
          extensions:
            manju:          # 漫剧专属扩展
              shot: "EXTREME_CLOSE-UP"
              visual_effect: "ZOOM_IN_EYE"
              effect_note: "瞳孔聚焦瞬间叠加ZOOM IN，持续0.5秒"
              subtitle_style: "NORMAL"
              duration_seconds: 2.5
```

### 设计要点

| 设计决策 | 原因 |
|---------|------|
| **Episode 层级** | 漫剧以"集"为消费和传播单元，每集需独立钩子（卡点）吸引追更 |
| **通用核心 + `extensions`** | 影视/广播剧/舞台剧/漫剧共享场景+对白核心，差异仅在呈现层 |
| **Beat = 一格/一镜** | 漫剧中一个 Beat 对应一格漫画或一镜画面，精准定位修改粒度 |
| **`ManjuEffect` 枚举** | 网文漫剧视觉语言已高度模式化（回忆滤镜、瞳孔放大、闪白），预定义枚举减少后期沟通成本 |
| **两种画面粒度** | 简单模式供编剧快速出稿，详细模式供画师直接参照 |
| **留空提示策略** | 初稿未确定的镜头/特效保留空结构，提示作者"这里还可细化" |

详见 [`schema/script-schema-v1.md`](schema/script-schema-v1.md)。

---

## 漫剧特效速查

| 枚举值 | 中文 | 典型场景 |
|--------|------|---------|
| `FLASH_WHITE` | 闪白 | 转场、冲击 |
| `FLASH_BLACK` | 闪黑 | 沉重打击、昏迷 |
| `ZOOM_IN_EYE` | 瞳孔放大 | 震惊、发现关键信息 |
| `MEMORY_FILTER` | 回忆滤镜 | 回忆片段（泛黄/黑白） |
| `SLOW_MOTION` | 慢动作 | 关键动作特写 |
| `SHAKE` | 画面震动 | 爆炸、撞击 |
| `SPLIT_SCREEN` | 分屏 | 两人同时行动 |
| `MONTAGE` | 蒙太奇快切 | 时间流逝 |
| `DANMAKU` | 弹幕式字幕 | 搞笑吐槽 |
| `SPEED_LINE` | 速度线 | 动作场面 |
| `FOCUS_BLUR` | 聚焦模糊 | 背景虚化、意识模糊 |
| `SILHOUETTE` | 剪影 | 神秘感、反派登场 |
| `RIPPLE` | 水波纹 | 梦境、幻觉 |
| `PARTICLE` | 粒子特效 | 浪漫场景（花瓣/雪花） |
| `COLOR_INVERT` | 颜色反相 | 诡异氛围 |

---

## 与现有工具的关系

本工具是 notel 网文写作工具集的扩展，与以下现有模块协同工作：

| 模块 | 关系 |
|------|------|
| `chaowuqiong-screenwriting-master/` | 本工具的 screenplay 输出可直接进入编剧大师的"剧本医生"步骤打磨 |
| `chaowuqiong-director-master/` | 本工具的 screenplay YAML 可作为导演大师的分镜拆解输入 |
| `story-setup/` | 共享 `.claude/agents/` 和 `.claude/rules/` 基础设施 |

---

## 许可证

与 notel 主项目一致。
