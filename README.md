# feishu-doc-drawio

Claude Code Skill：生成飞书文档创建脚本，支持富文本、表格、可编辑画板。

## 功能

- **富文本文档**：标题、加粗/斜体/链接、代码块、列表、引用、分割线
- **表格**：自动创建并填充数据，表头加粗
- **可编辑画板**：飞书原生 Whiteboard，支持形状、连线、文本，完全可在飞书中编辑

## 工作方式

调用 `/feishu-doc` 后，Claude 会在当前目录生成 `feishu-output/` 文件夹：

```
feishu-output/
  content.json   ← 文档内容（你需要审查这个）
  run.py         ← 运行脚本（调用共享库，不含重复代码）
```

你审查 `content.json` 无误后，运行 `python3 feishu-output/run.py` 即可创建飞书文档。

也可以配置为自动运行（见下方"运行模式"）。

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

### 2. 安装 Python 依赖

```bash
pip install requests
```

> 如果系统提示权限不足，用 `pip install --user requests`。

### 3. 安装 Skill

```bash
git clone git@github.com:yinrong/feishu-doc-drawio.git ~/.claude/skills/feishu-doc
```

安装完成后 **重启 Claude Code**。

## 运行模式与默认所有人

编辑 `~/.claude/skills/feishu-doc/config.json`：

```json
{
  "mode": "manual",
  "default_owner_email": "yourname@company.com"
}
```

| 字段 | 说明 |
|---|---|
| `mode: manual`（默认） | 生成文件后停下，你审查 `content.json` 后手动运行 `python3 feishu-output/run.py` |
| `mode: auto` | 生成文件后自动运行脚本，直接返回飞书链接 |
| `default_owner_email` | 文档创建后立即转移所有权给此邮箱（**必须是飞书企业邮箱**）。留空则不转移，文档归应用所有 |

> **关于 default_owner_email**：飞书应用创建的文档默认归应用所有，企业用户无法在自己的云文档列表里直接看到。填写你的飞书邮箱后，每次创建文档会立即转给你，你就能在"我的文件"里看到。
>
> 只支持 **email 方式的 member_id**（飞书企业邮箱），不支持 openid / userid。

**手动模式运行时**，需要先设置环境变量：

```bash
export FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"
python3 feishu-output/run.py
```

**自动模式运行时**，需要在 `~/.claude/settings.json` 的 `"env"` 中配置：

```json
{
  "env": {
    "FEISHU_APP_ID": "cli_xxxxxxxxxxxxx",
    "FEISHU_APP_SECRET": "xxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

> `~/.claude/settings.json` 是 Claude Code 的配置文件，位于你的用户主目录下的 `.claude` 文件夹中。如果文件中已有其他配置项，把这两行追加到已有的 `env` 对象中即可。修改后需要 **重启 Claude Code** 生效。

## 使用

在 Claude Code 对话中输入：

```
/feishu-doc 创建一个项目进度报告
```

## 故障排查

| 报错 | 原因 | 解决 |
|---|---|---|
| `FEISHU_APP_ID and FEISHU_APP_SECRET must be set` | 环境变量未配置 | 手动模式：运行前 export；自动模式：检查 settings.json |
| `Auth failed` | App ID 或 Secret 错误 | 去飞书开放平台 → 凭证与基础信息 页面核对 |
| `code: 99991663` 或 `permission denied` | 权限不足 | 检查 3 个权限是否已添加并审批通过 |
| `code: 99991668` | 应用未发布 | 去版本管理创建版本并发布 |
| `ModuleNotFoundError: feishu_api` | skill 安装路径不对 | 确认 clone 到了 `~/.claude/skills/feishu-doc/` |
| `code: 1063002` | 文档所有权转移失败：调用方不是文档所有者 | 正常情况不会触发；如出现说明 API 权限异常 |
| `code: 1063003` | 转移失败：目标用户不在可见范围 | 检查 `default_owner_email` 是否是本组织的飞书企业邮箱 |
| `code: 1063001` | 转移失败：邮箱无效 | 核对 `default_owner_email` 拼写，确保是飞书注册邮箱 |

## License

MIT
