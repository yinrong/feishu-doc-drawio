---
name: feishu-doc
description: 生成飞书文档创建脚本（富文本+表格+可编辑画板），支持手动审查或自动运行
allowed-tools: Read, Write, Bash
---

生成单个 Python 脚本，用于通过飞书 Open API 创建文档（内嵌画板）。支持两种运行模式：手动审查后运行，或自动运行。

**架构**：blocks 数据**直接以 Python 列表写在 `run.py` 里**，不再生成单独的 `content.json`。原因是历史上 JSON 模式下中文文本里的 ASCII `"` 经常导致 JSON 解析失败；Python 字符串字面量天然不需要转义这类问题。

## 🔴 铁律：图形必须是 `board` 块，不得降级为文本

**任何下列内容出现在对话中，必须转换为 `board` 块，绝不允许退化成其他块：**

- ASCII 画的方框、线条、箭头（`┌─┐`、`│`、`└─┘`、`─>`、`▼` 等）
- Markdown 伪图（`[A] -> [B]`、`+----+`、缩进的树状结构表示层级）
- 文字描述的流程/架构（"A 调用 B，B 写入 C"）
- 任何用来表达**节点 + 连线**的内容，无论画得多粗糙

### ❌ 绝对禁止的降级

```python
{"type": "code", "content": "┌──┐   ┌──┐\n│A │──▶│B │\n└──┘   └──┘"}   # 错：把图塞代码块
{"type": "text", "elements": [{"text": "前端 → API → 数据库"}]}      # 错：用文字描述图
{"type": "quote", "text": "架构：A 调用 B"}                         # 错：用引用代替图
```

### ✅ 正确做法

把图形意图翻译成 **PlantUML 源码**，放在 `board` 块的 `plantuml` 字段里。飞书只接受 PlantUML（或 Mermaid）作为画板输入，不再支持手工 nodes/connectors 格式。

输入（对话中）：
```
┌──────┐    ┌──────┐    ┌──────┐
│ 前端 │───▶│ API  │───▶│ 数据库│
└──────┘    └──────┘    └──────┘
```

输出（run.py 中的 blocks 列表项）：
```python
{
    "type": "board",
    "title": "系统架构",
    "plantuml": "@startuml\n[前端] --> [API]\n[API] --> [数据库]\n@enduml",
}
```

**哪怕画不像、节点数很少、PlantUML 不优美，也必须用 `board`。** 不要因为"文字更简洁""ASCII 足够清楚"等理由退化。如果 API 报权限错误，直接把异常抛给用户，让用户去开通 `board:whiteboard:node:create` 权限。

## 运行模式与配置

读取 `${CLAUDE_SKILL_DIR}/config.json`：

```json
{
  "mode": "manual",
  "default_owner": "phone:18800001234"
}
```

- `mode`：
  - `manual`（默认）：生成文件后展示给用户审查，由用户手动运行
  - `auto`：生成文件后自动执行脚本
- `default_owner`：文档创建后立即转移所有权给此用户。支持的格式：
  - `email:user@company.com` — 飞书企业邮箱
  - `phone:18800001234` — 手机号（内部自动查 open_id 后转移）
  - `openid:ou_xxxx` — open_id
  - `userid:xxxx` / `unionid:on_xxxx`
  - 裸字符串（无 `:`）默认按 email 处理（向后兼容旧配置 `default_owner_email`）

  转移失败不会让脚本崩溃 —— 文档已创建，URL 一定返回，失败信息以 `owner_transfer_warning` 字段附在 results 里。

如果 config.json 不存在或读取失败，按 `manual` 处理、不转移所有权。

`run.py` 会从 config 读取这些值并传给共享库，不要在生成的脚本里重复写死。

## 工作流程

当用户调用 `/feishu-doc` 时：

### Step 1: 分析内容

扫描当前对话，识别需要导出到飞书的内容：

| 对话内容 | 映射块类型 |
|---|---|
| 文本段落 | `text` |
| 标题 | `heading` |
| **任何图形（ASCII图/流程图/架构图/方框+箭头/文字描述的节点-连线关系）** | **`board`（铁律，不可降级）** |
| Markdown 表格 | `table`（headers + rows） |
| 代码片段 | `code`（带语言标注） |
| 有序/无序列表 | `ordered_list` / `bullet_list` |
| 引用 | `quote` |

**识别 board 的触发条件**：对话中只要存在"节点 + 连接关系"的意图（不管具体长什么样），就必须生成 `board` 块。拿不准时默认选 `board`，不要选文本。

如果用户在 `/feishu-doc` 后带了参数 (`$ARGUMENTS`)，用参数作为文档标题或过滤导出范围。

### Step 2: 构建 blocks（Python 数据结构）

把内容组装为 Python 列表。**直接当作 Python 数据写**，不要先序列化为 JSON 字符串。

```python
blocks = [
    {"type": "document_title", "text": "文档标题"},
    {"type": "heading", "level": 1, "text": "一级标题"},
    {"type": "text", "elements": [
        {"text": "普通文字"},
        {"text": "加粗文字", "bold": True},
        {"text": "链接文字", "link": "https://example.com"},
        {"text": "行内代码", "code": True},
    ]},
    {"type": "code", "language": "python", "content": "print('hello')"},
    {"type": "bullet_list", "items": ["项目1", "项目2"]},
    {"type": "ordered_list", "items": ["步骤1", "步骤2"]},
    {"type": "quote", "text": "引用内容"},
    {"type": "divider"},
    {"type": "table", "headers": ["列1", "列2"], "rows": [["a", "b"], ["c", "d"]]},
    {
        "type": "board",
        "title": "流程图名称",
        "plantuml": "@startuml\nstart\n:开始;\n:处理;\nif (条件?) then (是)\n  :下一步;\nelse (否)\n  :跳过;\nendif\nstop\n@enduml",
    },
]
```

**含双引号的文本怎么写**：用单引号包字符串，里面的 `"` 不需要转义。例如 `{"text": '定义"谁"做这事'}` 而不是 `{"text": "定义\"谁\"做这事"}`。这是改用 Python 数据结构的最大动机 —— 历史上 JSON 模式下中文文本里的 `"` 经常导致 `JSONDecodeError`。

### PlantUML 备忘（常用场景）

| 需要画的图 | PlantUML 写法 |
|---|---|
| 架构/组件图 | `@startuml\n[前端] --> [后端]\n[后端] --> [数据库]\n@enduml` |
| 带标签的连线 | `[A] --> [B] : 调用` |
| 流程图 | `@startuml\nstart\n:步骤A;\n:步骤B;\nif (条件?) then (是)\n  :分支1;\nelse (否)\n  :分支2;\nendif\nstop\n@enduml` |
| 时序图 | `@startuml\nAlice -> Bob: 请求\nBob --> Alice: 响应\n@enduml` |
| 思维导图 | `@startmindmap\n* 根\n** 子1\n** 子2\n@endmindmap` |
| 类图 | `@startuml\nclass A\nclass B\nA --> B\n@enduml` |

可选字段：`"syntax_type": 2` 切换为 Mermaid 语法；`"style_type"` 默认 1（生成可独立编辑的多节点），改为 2 则生成一张可重编辑源码的图片。

### Step 2.5: 自检（写文件前必做）

在写 `run.py` 前，扫一遍 `blocks` 列表：

1. 是否有 `type` 为 `code` / `text` / `quote` 的块，其内容包含 `┌`、`─`、`│`、`└`、`┘`、`┐`、`▼`、`▲`、`◀`、`▶`、`←`、`→`、`↑`、`↓`、`+--`、`|`、`-->`、`<--` 中的任何 2 个字符？
2. 是否有 `text` 块用文字描述"A → B"、"A 调用 B"、"A 连接到 B"这种节点关系？

**只要命中任一条，立即把该块替换为 `board` 块（plantuml 字段）**，然后重新自检。

同时检查 `board` 块：
- `plantuml` 字段必须存在、非空、以 `@startuml`/`@startmindmap`/`@startmermaid` 等起始标记开头，以对应的 `@end...` 结束。
- **绝不允许** `board` 块出现 `nodes` / `connectors` 字段 — 那是旧格式，现在只用 `plantuml`。

### Step 3: 生成 run.py

在当前工作目录下创建 `feishu-output/` 目录（如已存在则覆盖），只生成一个文件 `feishu-output/run.py`：

```python
#!/usr/bin/env python3
"""审查 blocks 列表无误后，运行：python3 feishu-output/run.py"""
import sys, os, json
SKILL_DIR = os.path.expanduser("~/.claude/skills/feishu-doc")
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
from feishu_api import FeishuAuth, process_blocks

with open(os.path.join(SKILL_DIR, "config.json")) as f:
    config = json.load(f)

# ============ 文档内容（审查这部分） ============
blocks = [
    {"type": "document_title", "text": "..."},
    # ...所有 block 直接以 Python 字面量写在这里...
]
# ============ 内容结束 ============

auth = FeishuAuth()
results = process_blocks(
    auth,
    blocks,
    default_owner=config.get("default_owner") or config.get("default_owner_email") or None,
)
print(json.dumps(results, ensure_ascii=False, indent=2))
```

使用 Write 工具写入这一个文件。**blocks 列表直接展开写在文件里**，不要再生成 content.json，也不要把数据 dump 成 JSON 字符串塞进字符串变量。

### Step 4: 根据模式执行

**手动模式**：

向用户展示：

```
已生成 feishu-output/run.py。审查 blocks 列表无误后运行：

  export FEISHU_APP_ID="your_app_id"
  export FEISHU_APP_SECRET="your_app_secret"
  python3 feishu-output/run.py
```

不要自动运行脚本。等待用户确认。

**自动模式**：

直接执行：

```bash
python3 feishu-output/run.py
```

解析输出，向用户展示文档链接。如果输出里 documents 有 `owner_transfer_warning` 字段，把警告内容也展示给用户（文档已创建，但所有权未转移）。

## ASCII → PlantUML 转换指引

识别对话中图形的意图后，选最合适的 PlantUML 图类型：

| 对话中的图形 | PlantUML 图类型 | 起始标签 |
|---|---|---|
| 架构图、组件/服务依赖 | 组件图 | `@startuml` + `[A] --> [B]` |
| 从上到下的流程（含判断分支） | 活动图 | `@startuml\nstart ... stop\n@enduml` |
| 调用顺序、请求/响应 | 时序图 | `@startuml\nAlice -> Bob\n@enduml` |
| 层级树 / 概念拆解 | 思维导图 | `@startmindmap` + `* 根 ** 子` |
| 实体关系 / 类继承 | 类图 | `@startuml\nclass A\nA --> B\n@enduml` |

节点文案直接写中文，PlantUML 完全支持。遇到歧义（例如一张图既能当流程图也能当组件图）时，优先选更能表达"节点 + 连线"本质的组件图。

## 支持的代码语言

python, java, javascript, typescript, go, rust, c, cpp, csharp, shell, bash, sql, json, xml, html, css, yaml, markdown, plain

## 错误处理

- 如果环境变量未设置（手动模式下），在输出的运行命令中提醒用户先 export 环境变量
- 如果自动模式下 API 报权限不足，**原样把错误抛给用户**，让用户去飞书开放平台开通 `board:whiteboard:node:create` 权限。不要改 content.json 绕过。
- 如果网络错误，显示具体错误信息并建议重试
