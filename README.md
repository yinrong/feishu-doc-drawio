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

Claude 会自动分析对话内容、调用飞书 API 创建文档和画板，完成后返回可点击的飞书链接。你不需要了解任何内部格式或 API 细节。

## 故障排查

| 报错 | 原因 | 解决 |
|---|---|---|
| `FEISHU_APP_ID and FEISHU_APP_SECRET must be set` | 环境变量未配置 | 检查 `~/.claude/settings.json` 中的 env 配置，重启 Claude Code |
| `Auth failed` | App ID 或 Secret 错误 | 去飞书开放平台 → 凭证与基础信息 页面核对 |
| `code: 99991663` 或 `permission denied` | 权限不足 | 检查 3 个权限是否已添加并审批通过 |
| `code: 99991668` | 应用未发布 | 去版本管理创建版本并发布 |

## License

MIT
