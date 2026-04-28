# feishu-doc-drawio

Claude Code Skill：通过飞书 Open API 直接创建文档和画板。

## 功能

- **富文本文档**：标题、加粗/斜体/链接、代码块、列表、引用、分割线
- **表格**：自动创建并填充数据，表头加粗
- **可编辑画板**：通过飞书原生 Whiteboard API 创建流程图、架构图，支持形状、连线、文本，完全可在飞书中编辑

## 安装

### 1. 飞书应用配置

在 [飞书开放平台](https://open.feishu.cn) 创建应用，开通以下权限：

| 权限 scope | 说明 |
|---|---|
| `docx:document` | 查看、编辑和管理新版文档 |
| `board:whiteboard` | 查看、编辑和管理画板 |
| `drive:drive` | 查看、编辑和管理云空间文件 |

### 2. 环境变量

在 Claude Code settings 中添加：

```json
{
  "env": {
    "FEISHU_APP_ID": "your_app_id",
    "FEISHU_APP_SECRET": "your_app_secret"
  }
}
```

### 3. 安装依赖

```bash
pip install requests
```

### 4. 安装 Skill

```bash
claude skill install github:yinrong/feishu-doc-drawio
```

## 使用

在 Claude Code 中：

```
/feishu-doc 创建一个项目进度报告
```

Claude 会分析对话内容，自动创建飞书文档和画板，返回链接。

### 直接调用脚本

```bash
# 创建文档
python3 scripts/feishu_api.py create-doc --title "报告" --content-file content.json

# 创建画板
python3 scripts/feishu_api.py create-board --title "流程图" --nodes-file flowchart.json

# 文档 + 画板
python3 scripts/feishu_api.py create-all --title "完整报告" --content-file content.json
```

### Content JSON 格式

```json
{
  "blocks": [
    {"type": "heading", "level": 1, "text": "项目概述"},
    {"type": "text", "elements": [
      {"text": "这是", "bold": false},
      {"text": "重要内容", "bold": true}
    ]},
    {"type": "table", "headers": ["任务", "状态"], "rows": [
      ["开发", "进行中"],
      ["测试", "待开始"]
    ]},
    {"type": "board", "title": "架构图", "nodes": [
      {"id": "n1", "shape": "round_rectangle", "text": "前端", "x": 100, "y": 100},
      {"id": "n2", "shape": "rectangle", "text": "API", "x": 100, "y": 250},
      {"id": "n3", "shape": "rectangle", "text": "数据库", "x": 100, "y": 400},
      {"connect": ["n1", "n2"]},
      {"connect": ["n2", "n3"]}
    ]}
  ]
}
```

## 画板节点类型

| shape_type | 说明 | 适用场景 |
|---|---|---|
| `round_rectangle` | 圆角矩形 | 开始/结束节点 |
| `rectangle` | 矩形 | 处理步骤 |
| `diamond` | 菱形 | 判断/条件 |
| `ellipse` | 椭圆 | 状态节点 |
| `triangle` | 三角形 | 警告/注意 |
| `parallelogram` | 平行四边形 | 数据输入/输出 |

## License

MIT
