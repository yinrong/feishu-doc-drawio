---
name: feishu-doc
description: 生成飞书文档创建脚本（富文本+表格+可编辑画板），支持手动审查或自动运行
allowed-tools: Read, Write, Bash
---

生成 Python 脚本和内容文件，用于通过飞书 Open API 创建文档和画板。支持两种运行模式：手动审查后运行，或自动运行。

## 🔴 铁律：图形必须是 `board` 块，不得降级为文本

**任何下列内容出现在对话中，必须转换为 `board` 块，绝不允许退化成其他块：**

- ASCII 画的方框、线条、箭头（`┌─┐`、`│`、`└─┘`、`─>`、`▼` 等）
- Markdown 伪图（`[A] -> [B]`、`+----+`、缩进的树状结构表示层级）
- 文字描述的流程/架构（"A 调用 B，B 写入 C"）
- 任何用来表达**节点 + 连线**的内容，无论画得多粗糙

### ❌ 绝对禁止的降级

```json
{"type": "code", "content": "┌──┐   ┌──┐\n│A │──▶│B │\n└──┘   └──┘"}   // 错：把图塞代码块
{"type": "text", "elements": [{"text": "前端 → API → 数据库"}]}      // 错：用文字描述图
{"type": "quote", "text": "架构：A 调用 B"}                         // 错：用引用代替图
```

### ✅ 正确做法

解析 ASCII / 文字描述，识别出"节点"和"连线"，映射为 `board` 块：

输入（对话中）：
```
┌──────┐    ┌──────┐    ┌──────┐
│ 前端 │───▶│ API  │───▶│ 数据库│
└──────┘    └──────┘    └──────┘
```

输出（content.json）：
```json
{"type": "board", "title": "系统架构", "nodes": [
  {"id": "n1", "shape": "rectangle", "text": "前端", "x": 100, "y": 200},
  {"id": "n2", "shape": "rectangle", "text": "API", "x": 350, "y": 200},
  {"id": "n3", "shape": "rectangle", "text": "数据库", "x": 600, "y": 200},
  {"connect": ["n1", "n2"]},
  {"connect": ["n2", "n3"]}
]}
```

**哪怕画不像、节点数很少、布局不完美，也必须用 `board`。** 不要因为"文字更简洁""ASCII 足够清楚"等理由退化。如果 API 报权限错误，直接把异常抛给用户，让用户去开通 `board:whiteboard` 权限。

## 运行模式与配置

读取 `${CLAUDE_SKILL_DIR}/config.json`：

```json
{
  "mode": "manual",
  "default_owner_email": "someone@company.com"
}
```

- `mode`：
  - `manual`（默认）：生成文件后展示给用户审查，由用户手动运行
  - `auto`：生成文件后自动执行脚本
- `default_owner_email`：文档创建后立即转移所有权给此飞书邮箱（必须是飞书企业邮箱）。空字符串或缺失则不转移。

如果 config.json 不存在或读取失败，按 `manual` 处理、不转移所有权。

`run.py` 会从 config 读取这些值并传给共享库，不要在生成的内容里重复写死。

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

### Step 2: 构建 JSON

将内容组装为以下 JSON 格式，写入 `content.json`：

```json
{
  "blocks": [
    {"type": "document_title", "text": "文档标题"},
    {"type": "heading", "level": 1, "text": "一级标题"},
    {"type": "text", "elements": [
      {"text": "普通文字"},
      {"text": "加粗文字", "bold": true},
      {"text": "链接文字", "link": "https://example.com"},
      {"text": "行内代码", "code": true}
    ]},
    {"type": "code", "language": "python", "content": "print('hello')"},
    {"type": "bullet_list", "items": ["项目1", "项目2"]},
    {"type": "ordered_list", "items": ["步骤1", "步骤2"]},
    {"type": "quote", "text": "引用内容"},
    {"type": "divider"},
    {"type": "table", "headers": ["列1","列2"], "rows": [["a","b"],["c","d"]]},
    {"type": "board", "title": "流程图名称", "nodes": [
      {"id": "n1", "shape": "round_rectangle", "text": "开始", "x": 200, "y": 100, "w": 180, "h": 60},
      {"id": "n2", "shape": "rectangle", "text": "处理", "x": 200, "y": 250},
      {"id": "n3", "shape": "diamond", "text": "判断?", "x": 200, "y": 400, "w": 180, "h": 100},
      {"connect": ["n1", "n2"], "label": ""},
      {"connect": ["n2", "n3"], "label": "下一步"}
    ]}
  ]
}
```

### Step 2.5: 自检（生成 content.json 前必做）

在写入 `content.json` 前，扫一遍 `blocks` 数组：

1. 是否有 `type` 为 `code` / `text` / `quote` 的块，其内容包含 `┌`、`─`、`│`、`└`、`┘`、`┐`、`▼`、`▲`、`◀`、`▶`、`←`、`→`、`↑`、`↓`、`+--`、`|`、`-->`、`<--` 中的任何 2 个字符？
2. 是否有 `text` 块用文字描述"A → B"、"A 调用 B"、"A 连接到 B"这种节点关系？

**只要命中任一条，立即把该块替换为 `board` 块**，然后重新自检。

### Step 3: 生成文件

在当前工作目录下创建 `feishu-output/` 目录（如已存在则覆盖内容），生成两个文件：

**文件 1: `feishu-output/content.json`**

上一步构建的 JSON 数据。

**文件 2: `feishu-output/run.py`**

最小 runner 脚本，复用共享库，不重复生成 API 代码：

```python
#!/usr/bin/env python3
import sys, os, json
SKILL_DIR = os.path.expanduser("~/.claude/skills/feishu-doc")
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
from feishu_api import FeishuAuth, process_blocks

with open(os.path.join(SKILL_DIR, "config.json")) as f:
    config = json.load(f)

content_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.json")
with open(content_file) as f:
    data = json.load(f)

auth = FeishuAuth()
results = process_blocks(
    auth,
    data["blocks"],
    default_owner_email=config.get("default_owner_email") or None,
)
print(json.dumps(results, ensure_ascii=False, indent=2))
```

使用 Write 工具写入这两个文件。

### Step 4: 根据模式执行

**手动模式**：

向用户展示：

```
已生成飞书文档创建文件：

  feishu-output/content.json  — 文档内容（请审查）
  feishu-output/run.py        — 运行脚本

审查内容无误后，运行：

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

解析输出，向用户展示文档链接和画板链接。

## 画板节点转换规则

将对话中的 ASCII 图/流程图转换为画板节点的映射：

| 图形元素 | 画板 shape_type | 默认颜色 |
|---|---|---|
| 开始/结束（圆角框） | `round_rectangle` | 绿色 #E8F5E9 |
| 处理步骤（方框） | `rectangle` | 蓝色 #E3F2FD |
| 判断/条件（菱形） | `diamond` | 橙色 #FFF3E0 |
| 数据/IO（平行四边形） | `parallelogram` | 青色 #E0F7FA |
| 圆形节点 | `ellipse` | 紫色 #F3E5F5 |

布局规则：
- 垂直流程图：节点间 y 间距 150px，x 居中对齐
- 水平流程图：节点间 x 间距 250px，y 居中对齐
- 分支判断：向右/向下展开分支路径
- 默认节点尺寸：180x60（菱形 180x100）
- 不确定形状时，默认用 `rectangle`

## 支持的代码语言

python, java, javascript, typescript, go, rust, c, cpp, csharp, shell, bash, sql, json, xml, html, css, yaml, markdown, plain

## 错误处理

- 如果环境变量未设置（手动模式下），在输出的运行命令中提醒用户先 export 环境变量
- 如果自动模式下 API 报权限不足（画板 404），**原样把错误抛给用户**，让用户去飞书开放平台开通 `board:whiteboard` 权限。不要改 content.json 绕过。
- 如果网络错误，显示具体错误信息并建议重试
