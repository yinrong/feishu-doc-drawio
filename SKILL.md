---
name: feishu-doc
description: 生成飞书文档创建脚本（富文本+表格+可编辑画板），支持手动审查或自动运行
allowed-tools: Read, Write, Bash
---

生成 Python 脚本和内容文件，用于通过飞书 Open API 创建文档和画板。支持两种运行模式：手动审查后运行，或自动运行。

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
- 文本段落、标题 → `heading` / `text` 块
- Markdown 表格 → `table` 块（解析 headers + rows）
- 代码片段 → `code` 块（带语言标注）
- 列表 → `bullet_list` / `ordered_list` 块
- 流程图/架构图/ASCII 图 → `board` 块（转换为形状+连线）
- 引用 → `quote` 块

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

将对话中的 ASCII 图/流程图转换为画板节点：

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

## 支持的代码语言

python, java, javascript, typescript, go, rust, c, cpp, csharp, shell, bash, sql, json, xml, html, css, yaml, markdown, plain

## 错误处理

- 如果环境变量未设置（手动模式下），在输出的运行命令中提醒用户先 export 环境变量
- 如果自动模式下 API 报权限不足，提示用户检查飞书应用权限（需要 `docx:document`, `board:whiteboard`, `drive:drive`）
- 如果网络错误，显示具体错误信息并建议重试

## 关键约束

**画板禁止降级**：画板是产品刚需。如果画板创建 API 失败（通常是 `board:whiteboard` 权限未开通，返回 404），**必须停下并报错**，让用户去飞书开放平台开通权限。严禁降级为以下任何形式：

- ❌ 在文档中嵌入 ASCII 图
- ❌ 在文档中嵌入 draw.io XML 代码块
- ❌ 以纯文本方式描述图形结构
- ❌ 直接跳过画板块

scripts/feishu_api.py 已经在画板 API 404 时给出清晰的错误信息，直接把异常抛给用户即可。
