---
name: feishu-doc
description: 通过飞书 API 直接创建文档（富文本+表格+可编辑画板），全自动无需手动粘贴
allowed-tools: Read, Bash
---

通过飞书 Open API 创建文档和画板，支持富文本、表格、代码块、可编辑的飞书原生画板。

## 前置条件

环境变量必须已设置：
- `FEISHU_APP_ID` — 飞书应用 App ID
- `FEISHU_APP_SECRET` — 飞书应用 App Secret

如果未设置，提示用户先配置。

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

将内容组装为以下 JSON 格式：

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

### Step 3: 调用脚本

将 JSON 写入临时文件，然后执行：

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/feishu_api.py" create-all \
  --title "文档标题" \
  --content-file /tmp/feishu_content.json
```

### Step 4: 返回结果

解析脚本输出，向用户展示：
- 文档链接（可直接点击打开飞书文档）
- 画板链接（可直接点击打开飞书画板编辑）

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

- 如果环境变量未设置，输出配置指引
- 如果 API 报权限不足，提示用户检查飞书应用权限（需要 `docx:document`, `board:whiteboard`, `drive:drive`）
- 如果网络错误，显示具体错误信息并建议重试
