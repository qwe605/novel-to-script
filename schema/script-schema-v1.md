# 通用剧本 YAML Schema v1.0 设计文档

> 为 AI 辅助小说转剧本工具定义的结构化格式。
> **核心服务场景：网文漫剧（动态漫画/有声漫画）**，同时兼容影视剧本、广播剧/有声书剧本、舞台剧。

---

## 一、设计目标

1. **网文 → 漫剧一键转换**：网文漫剧是当下最流行的小说衍生形态（抖音/快手/B站 3-5 分钟短集），降低漫剧改编门槛是本 Schema 的首要目标。
2. **按集组织，独立传播**：漫剧以"集"为消费单元，每集必须有独立悬念钩子（卡点），Schema 必须原生支持集数规划与钩子管理。
3. **AI 友好 + 人类可编辑**：YAML 格式便于程序生成和校验，同时层级清晰，作者用任何文本编辑器都能直接修改。
4. **保留溯源信息**：改编是反复打磨的过程，必须能从剧本的任意单元追溯到小说原文出处。
5. **支持增量完善**：初稿可能只有场景和对白，镜头、音效、特效等可在第二轮填充，Schema 不强制要求一步到位。

---

## 二、核心设计决策与原因

### 2.1 通用核心 + `extensions` 扩展字段

**决策**：所有剧本类型共享同一套核心字段（`script`, `characters`, `sequences`, `scenes`, `beats`），仅在 `beat.extensions` 中通过子字段区分类型专属信息。

**原因**：
- 影视剧本、广播剧、舞台剧、漫剧的底层叙事单元本质相同：**场景（Scene）** 内包含 **动作（Action）** 与 **对白（Dialogue）** 的交替。
- 差异仅在于"如何呈现"：影视用镜头和画面，广播剧用声音和音效，舞台剧用舞台走位和灯光，**漫剧融合画面+配音+音效+字幕**。
- 如果为每种类型独立设计 Schema，会导致大量重复字段（如 `scene_id`, `heading`, `content` 等），维护成本高，且难以支持"混合类型"。
- `extensions` 采用"留空提示"策略：即使初稿未填镜头或音效，字段存在本身就在提示作者"这里还可以细化"。

### 2.2 Episode（集）层级的引入

**决策**：在 `Sequence → Scene → Beat` 之上增加 `Episode` 层级，作为漫剧的核心组织单元。

**原因**：
- **漫剧的消费单元是"集"不是"幕"**：观众追更的是"第 8 集"，不会关心"第 3 幕"。如果 Schema 没有 Episode 层，后期团队需要在外部 Excel 中手动维护集数映射，信息容易脱节。
- **每集需要独立钩子（卡点）**：网文漫剧依赖"卡点"吸引观众点击下一集。Episode 的 `hook` 字段专门承载这一需求，让编剧在初稿阶段就思考"这集在哪里断"。
- **自动规划 vs 手动调整**：集数规划算法按 3-5 分钟/集自动拆分，但作者可以通过调整 Episode 的 `scenes` 数组手动重组，Schema 同时支持两种工作流。
- **集级元数据**：封面图提示（`cover_prompt`）、片头标志性音效（`opening_sfx`）等是漫剧宣发和后期制作的刚需，需要在集层面统一管理。

### 2.3 Sequence → Scene → Beat 三级结构

**决策**：保留 Scene 之下的 Beat（节拍）细分，以及 Scene 之上的 Sequence（序列/幕）。

**原因**：
- **Sequence 层**：对应小说的"章"或经典戏剧结构。在漫剧中，Sequence 可以作为"季/篇章"的划分（如"第一季：相遇"），而 Episode 是"集"的划分。两者互补：Sequence 管叙事结构，Episode 管传播单元。
- **Scene 层**：时空统一的叙事单位。漫剧中一个 Scene 通常对应一组连续的画面（同一地点、连续时间），是后期制作的最小独立渲染单元。
- **Beat 层**：场景内的最小叙事动作。在漫剧中，**一个 Beat 通常对应一格漫画/一镜画面**。Beat 粒度让画师能精准定位到要修改的某一格，而不必重写整个 Scene。

### 2.4 漫剧特效枚举（`ManjuEffect`）

**决策**：将网文漫剧常见的视觉特效预定义为枚举值（如 `FLASH_WHITE`、`ZOOM_IN_EYE`、`MEMORY_FILTER`）。

**原因**：
- **行业有固定套路**：网文漫剧的视觉语言已经高度模式化——回忆用滤镜、震惊用瞳孔放大、转场用闪白。预定义枚举能让 AI 在初稿阶段就自动匹配正确的特效，减少后期沟通成本。
- **枚举 ≠ 限制**：枚举值覆盖了 80% 的常见场景，作者仍可通过 `effect_note` 字段填写自定义说明，灵活性不受损。
- **后期可直接消费**：特效枚举值可以直接映射到后期软件（如 After Effects、Retas）的预设，减少人工翻译环节。

### 2.5 `source_chapters` 溯源字段

**决策**：每个 Scene 和 Episode 都记录 `source_chapters`（来源章节编号数组）。

**原因**：
- 小说改编成剧本不是一一映射，常常出现"小说半章 → 剧本一个 Scene"或"小说三章 → 剧本一集"。
- 作者在打磨对白时，需要随时对照原文语境。溯源字段让剧本与小说之间的跳转成为可能。
- 当小说后续修订时，溯源信息也有助于定位哪些 Scene/Episode 需要同步更新。

### 2.6 为什么用 YAML 而非 JSON/XML？

**原因**：
- **人类可读性**：YAML 支持注释（`#`），作者可以在字段旁直接写修改意见，JSON 不支持注释。
- **层级直观**：YAML 的缩进比 JSON 的括号更适合表达 Episode → Scene → Beat 的嵌套关系。
- **中文友好**：YAML 字符串无需转义 Unicode，中文对白可以直接写。
- **行业惯例**：Docker Compose、Kubernetes 等现代工具均以 YAML 为标准，作者学习成本低。

---

## 三、Schema 字段详解

### `script`（根对象）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | 是 | Schema 版本，当前为 `"1.0"` |
| `script_type` | enum | 是 | `"screenplay"` \| `"audio_drama"` \| `"stage_play"` \| `"manju"` |
| `title` | string | 是 | 剧本标题 |
| `source` | string | 否 | 来源小说名称或文件路径 |
| `metadata` | object | 是 | 全局元数据 |
| `characters` | array | 是 | 角色列表 |
| `sequences` | array | 是 | 序列/幕列表 |
| `episodes` | array | 否 | **【漫剧】** 集列表，按集组织场景 |
| `scenes` | array | 是 | 场景列表 |

### `metadata`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `total_scenes` | int | 是 | 场景总数 |
| `total_beats` | int | 是 | 节拍总数 |
| `total_episodes` | int | 否 | **【漫剧】** 总集数 |
| `estimated_duration_minutes` | float | 否 | 预估总时长（分钟） |
| `adapted_by` | string | 否 | 改编者 |
| `adaptation_notes` | string | 否 | 改编说明 |

### `character`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 角色唯一标识（英文蛇形命名） |
| `name` | string | 是 | 角色名 |
| `aliases` | array<string> | 否 | 别名/昵称 |
| `description` | string | 否 | 角色简述 |
| `voice_tags` | array<string> | 否 | 声音/语言风格标签 |
| `archetype` | string | 否 | 角色原型 |
| `visual_tags` | array<string> | 否 | **【漫剧】** 视觉特征标签，如 `["黑长直", "异色瞳"]` |

### `episode`（漫剧核心）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `episode_id` | string | 是 | 集唯一标识，如 `"ep_01"` |
| `episode_number` | int | 是 | 集序号（从 1 开始） |
| `title` | string | 否 | 集标题 |
| `hook` | string | 否 | **本集悬念钩子/卡点**，吸引观众追下一集 |
| `target_duration_seconds` | int | 是 | 目标时长（秒），默认 240（4 分钟） |
| `source_chapters` | array<int> | 否 | 来源小说章节编号 |
| `scenes` | array<string> | 是 | 属于该集的 Scene ID 列表 |
| `cover_prompt` | string | 否 | **【漫剧】** 封面图提示词/参考 |
| `opening_sfx` | string | 否 | **【漫剧】** 片头标志性音效/音乐 |

### `sequence`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 序列唯一标识 |
| `name` | string | 是 | 序列名称 |
| `description` | string | 否 | 序列内容简述 |
| `scenes` | array<string> | 是 | 属于该序列的 Scene ID 列表 |

### `scene`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scene_id` | string | 是 | 场景唯一标识 |
| `sequence_id` | string | 是 | 所属序列 ID |
| `heading` | object | 是 | 场景标题 |
| `source_chapters` | array<int> | 否 | 来源小说章节编号 |
| `estimated_duration_seconds` | int | 否 | 预估时长（秒） |
| `type` | enum | 否 | `"dialogue_heavy"` \| `"action"` \| `"montage"` \| `"transition"` \| `"static"` |
| `mood` | string | 否 | 场景情绪 |
| `beats` | array | 是 | 节拍列表 |

#### `heading`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `int_ext` | enum | 是 | `"INT."` \| `"EXT."` \| `"INT./EXT."` |
| `location` | string | 是 | 地点 |
| `time` | enum/string | 是 | `DAY` / `NIGHT` / `DAWN` / `DUSK` / `LATER` / `CONTINUOUS` |

### `beat`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `beat_id` | string | 是 | 节拍唯一标识 |
| `type` | enum | 是 | `action` / `dialogue` / `transition` / `sfx` / `music` / `narration` / `vos` |
| `character` | string | 否 | 关联角色 ID |
| `content` | string | 是 | 内容 |
| `parenthetical` | string | 否 | 括号提示 |
| `extensions` | object | 否 | 类型专属扩展字段 |

---

## 四、扩展字段详解

### 影视剧本 (`screenplay`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `shot` | string | 景别：`CLOSE-UP`, `WIDE`, `POV`, `EXTREME_CLOSE-UP` |
| `camera_move` | string | 镜头运动：`PAN`, `TILT`, `TRACK`, `DOLLY`, `HANDHELD` |
| `transition` | string | 转场：`CUT TO`, `FADE IN`, `DISSOLVE TO`, `SMASH CUT` |

### 广播剧/有声书 (`audio_drama`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `sfx` | array<string> | 音效列表 |
| `bgm` | string | 背景音乐提示 |
| `narration_tone` | string | 旁白语气 |
| `pan` | string | 声像定位：`L→R`, `远→近` |

### 舞台剧 (`stage_play`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `stage_direction` | string | 舞台走位/动作指示 |
| `lighting` | string | 灯光提示 |
| `set_change` | string | 换景说明 |

### 网文漫剧 (`manju`) — 核心扩展

漫剧是画面+配音+音效+字幕的融合形态，`manju` 扩展字段覆盖四层：

#### 画面层

| 字段 | 类型 | 说明 |
|------|------|------|
| `shot` | string | 景别（同 screenplay） |
| `frame_description` | string | **【详细模式】** 格内画面描述，供画师参考 |
| `dialogue_bubble` | string | **【详细模式】** 台词气泡位置：`左上/右上/左下/右下/中央` |
| `sfx_visual` | array<string> | **【详细模式】** 视觉拟声词，如 `["砰", "咔嚓"]` |

#### 特效与转场

| 字段 | 类型 | 说明 |
|------|------|------|
| `transition` | string | 转场方式 |
| `visual_effect` | enum | 视觉特效枚举，见下表 |
| `effect_note` | string | 特效补充说明 |

**漫剧视觉特效枚举（`ManjuEffect`）**：

| 枚举值 | 中文名 | 典型使用场景 |
|--------|--------|-------------|
| `FLASH_WHITE` | 闪白 | 转场、角色受到冲击、时间跳跃 |
| `FLASH_BLACK` | 闪黑 | 沉重打击、角色昏迷、情绪低谷 |
| `ZOOM_IN_EYE` | 瞳孔放大 | 震惊、恐惧、发现关键信息 |
| `MEMORY_FILTER` | 回忆滤镜 | 回忆片段（泛黄/黑白/柔光） |
| `SLOW_MOTION` | 慢动作 | 关键动作特写、情感高潮 |
| `SHAKE` | 画面震动 | 爆炸、撞击、剧烈情绪 |
| `SPLIT_SCREEN` | 分屏 | 两人同时行动、电话对话 |
| `MONTAGE` | 蒙太奇快切 | 时间流逝、回忆碎片 |
| `DANMAKU` | 弹幕式字幕 | 搞笑吐槽、内心吐槽外化 |
| `SPEED_LINE` | 速度线 | 动作场面、追逐、快速移动 |
| `FOCUS_BLUR` | 聚焦模糊 | 背景虚化、意识模糊、醉酒 |
| `SILHOUETTE` | 剪影 | 神秘感、反派登场、情绪压抑 |
| `RIPPLE` | 水波纹 | 梦境、幻觉、水下场景 |
| `PARTICLE` | 粒子特效 | 浪漫场景（花瓣/雪花/光点） |
| `COLOR_INVERT` | 颜色反相 | 诡异氛围、精神异常 |

#### 声音层

| 字段 | 类型 | 说明 |
|------|------|------|
| `bgm` | string | 背景音乐提示 |
| `sfx` | array<string> | 音效列表 |
| `voice_direction` | string | 配音指导：语气、语速、情绪 |

#### 字幕层

| 字段 | 类型 | 说明 |
|------|------|------|
| `subtitle_style` | enum | 字幕样式：`NORMAL` / `DANMAKU` / `BUBBLE` / `NARRATION` / `PHONE` / `THOUGHT` |
| `subtitle_note` | string | 字幕补充说明 |

#### 时长

| 字段 | 类型 | 说明 |
|------|------|------|
| `duration_frames` | int | 持续帧数（24fps/30fps 项目） |
| `duration_seconds` | float | 持续秒数（优先使用） |

---

## 五、四种剧本类型的差异速查

| 维度 | 影视剧本 | 广播剧 | 舞台剧 | **网文漫剧（核心）** |
|------|---------|--------|--------|---------------------|
| **核心感知通道** | 视觉 + 听觉 | 纯听觉 | 视觉（现场） | **画面 + 配音 + 音效 + 字幕** |
| **消费单元** | 整场电影 | 整集 | 整场演出 | **3-5 分钟/集，可独立传播** |
| **组织层级** | Sequence → Scene | Sequence → Scene | Sequence → Scene | **Episode → Sequence → Scene** |
| **Scene 划分** | 拍摄可行性 | 录音可行性 | 舞台统一性 | **画面连贯性** |
| **Beat 粒度** | 一镜 | 声音单元 | 舞台动作 | **一格漫画/一镜画面** |
| **关键扩展字段** | shot, camera_move | sfx, bgm, pan | stage_direction, lighting | **shot, visual_effect, subtitle_style, frame_description** |
| **特殊需求** | 无 | narration, pan | set_change, lighting | **hook（卡点）, cover_prompt, opening_sfx** |
| **内部独白处理** | VO / 视觉隐喻 | narration / VOS | 独白/灯光聚焦 | **VOS / thought 字幕框 / 回忆滤镜** |

---

## 六、关于空 extensions 的说明

初稿阶段，若某些 Beat 尚未确定镜头/音效/特效，extensions 字段可以：

1. **完全省略**（最简洁）
2. **保留空对象**（提示此处待填充）
3. **保留结构但值为 null**（明确标记为"待定"）

**推荐方式 2 或 3**，因为字段存在本身就是对作者的"待办提醒"。

---

## 七、示例

见同目录 `script-schema-v1.yaml`，内含：
- 一个完整的 2-Scene 影视剧本示例
- 一个网文漫剧 Beat 的详细扩展示例
