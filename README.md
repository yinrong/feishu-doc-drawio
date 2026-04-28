# feishu-doc-drawio

Claude Code Skill：通过飞书 Open API 直接创建文档和画板。

## 功能

- **富文本文档**：标题、加粗/斜体/链接、代码块、列表、引用、分割线
- **表格**：自动创建并填充数据，表头加粗
- **可编辑画板**：通过飞书原生 Whiteboard API 创建流程图、架构图，支持形状、连线、文本，完全可在飞书中编辑

## 安装

### 1. 飞书应用配置

1. 打开 [飞书开放平台](https://open.feishu.cn)，登录后进入 **开发者后台**
2. 点击 **创建企业自建应用**（如果已有应用可跳过）
3. 进入应用 → 左侧菜单 **权限管理** → 点击 **添加权限**
4. 搜索并勾选以下 3 个权限：

| 权限 scope | 在搜索框中搜索 | 说明 |
|---|---|---|
| `docx:document` | `docx:document` | 查看、编辑和管理新版文档 |
| `board:whiteboard` | `board:whiteboard` | 查看、编辑和管理画板 |
| `drive:drive` | `drive:drive` | 查看、编辑和管理云空间文件 |

5. 保存后，进入 **版本管理与发布** → 创建版本 → 申请发布
6. 需要企业管理员在 **飞书管理后台** 审批通过

记下应用的 **App ID** 和 **App Secret**（在应用的 **凭证与基础信息** 页面）。

### 2. 配置环境变量

编辑文件 `~/.claude/settings.json`（即你的用户主目录下 `.claude/settings.json`），在 `"env"` 对象中添加两行：

```json
{
  "env": {
    "FEISHU_APP_ID": "cli_xxxxxxxxxxxxx",
    "FEISHU_APP_SECRET": "xxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

> **注意**：如果文件中已有其他 `env` 配置项，把这两行追加到已有项后面即可，不要覆盖其他配置。
>
> 修改后需要 **重启 Claude Code** 才能生效。

### 3. 安装 Python 依赖

```bash
pip install requests
```

> 如果系统提示权限不足，可以用 `pip install --user requests` 或在 virtualenv 中安装。

### 4. 安装 Skill

将本仓库克隆到 Claude Code 的 skills 目录：

```bash
git clone git@github.com:yinrong/feishu-doc-drawio.git ~/.claude/skills/feishu-doc
```

安装完成后 **重启 Claude Code**，输入 `/feishu-doc` 即可使用。

## 使用

在 Claude Code 对话中输入：

```
/feishu-doc 创建一个项目进度报告
```

Claude 会分析对话内容，自动调用飞书 API 创建文档和画板，完成后返回可点击的飞书链接。

### 直接调用脚本（不通过 Skill）

也可以在终端直接运行 Python 脚本：

```bash
# 确保环境变量已设置
export FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"

# 创建文档
python3 ~/.claude/skills/feishu-doc/scripts/feishu_api.py create-doc \
  --title "报告" --content-file content.json

# 创建画板
python3 ~/.claude/skills/feishu-doc/scripts/feishu_api.py create-board \
  --title "流程图" --nodes-file flowchart.json

# 文档 + 画板一起创建
python3 ~/.claude/skills/feishu-doc/scripts/feishu_api.py create-all \
  --title "完整报告" --content-file content.json
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

## 故障排查

| 报错 | 原因 | 解决 |
|---|---|---|
| `FEISHU_APP_ID and FEISHU_APP_SECRET must be set` | 环境变量未配置 | 检查 `~/.claude/settings.json` 中的 env 配置，重启 Claude Code |
| `Auth failed` | App ID 或 Secret 错误 | 去飞书开放平台 → 凭证与基础信息 页面核对 |
| `code: 99991663` 或 `permission denied` | 权限不足 | 检查 3 个权限是否已添加并审批通过 |
| `code: 99991668` | 应用未发布 | 去版本管理创建版本并发布 |

## License

MIT
