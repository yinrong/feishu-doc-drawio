# feishu-doc-drawio

Claude Code Skill：生成飞书文档创建脚本，支持富文本、表格、可编辑画板。

## 功能

- **富文本文档**：标题、加粗/斜体/链接、代码块、列表、引用、分割线
- **表格**：自动创建并填充数据，表头加粗
- **可编辑画板**：飞书原生 Whiteboard，通过 PlantUML/Mermaid 源码生成，渲染为可独立编辑的画板节点

## 工作方式

调用 `/feishu-doc` 后，Claude 会在当前目录生成 `feishu-output/run.py` —— 一个自包含的 Python 脚本，blocks 数据以 Python 列表的形式直接写在脚本里。

你审查 `run.py` 中的 blocks 列表无误后，运行 `python3 feishu-output/run.py` 即可创建飞书文档。

也可以配置为自动运行（见下方"运行模式"）。

> 早期版本会生成单独的 `content.json` 文件，但中文文本里的 ASCII `"` 经常导致 JSON 解析失败。现在 blocks 直接写成 Python 字面量，不存在转义问题。

## 安装

### 1. 飞书应用配置

1. 打开 [飞书开放平台](https://open.feishu.cn)，登录后进入 **开发者后台**
2. 点击 **创建企业自建应用**（如果已有应用可跳过）
3. 进入应用 → 左侧菜单 **权限管理** → 点击 **添加权限**
4. 搜索并勾选以下权限：

| 权限 scope | 在搜索框中搜索 | 说明 |
|---|---|---|
| `docx:document` | `docx:document` | 查看、编辑和管理新版文档 |
| `board:whiteboard:node:create` | `board:whiteboard:node:create` | 创建画板节点（PlantUML 写入所需） |
| `drive:drive` | `drive:drive` | 查看、编辑和管理云空间文件 |
| `contact:user.id:readonly` | `contact:user.id:readonly` | **可选**，仅在 `default_owner` 用 `phone:` 前缀时需要 |

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

## 多身份配置

编辑 `~/.claude/skills/feishu-doc/config.json`，可以配置多个飞书应用账号：

```json
{
  "mode": "auto",
  "default_account": "work",
  "accounts": {
    "work": {
      "app_id": "cli_xxxxxxxxxxxxx",
      "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
      "default_owner": "email:me@company.com"
    },
    "personal": {
      "app_id": "cli_yyyyyyyyyyyyy",
      "app_secret": "yyyyyyyyyyyyyyyyyyyyyyyy",
      "default_owner": "email:me@other.com"
    }
  }
}
```

| 字段 | 说明 |
|---|---|
| `mode: manual`（默认） | 生成文件后停下，你审查 `run.py` 中的 blocks 后手动运行 `python3 feishu-output/run.py` |
| `mode: auto` | 生成文件后自动运行脚本，直接返回飞书链接 |
| `default_account` | 默认使用的账号名；留空则取 `accounts` 中第一个 |
| `accounts` | 账号列表，每个账号有独立的 `app_id`、`app_secret`、`default_owner` |

账号级的 `default_owner` 会覆盖其他默认值。

**指定账号**：在 `/feishu-doc` 参数开头加 `account:名称`：

```
/feishu-doc account:personal 我的周报
```

### `default_owner` 格式

| 前缀 | 示例 | 说明 |
|---|---|---|
| `email:` | `email:user@company.com` | 飞书企业邮箱（最直接） |
| `phone:` | `phone:18800001234` | 手机号（需开通 `contact:user.id:readonly`，自动查 open_id 后转移）|
| `openid:` | `openid:ou_xxxx` | 飞书 open_id |
| `userid:` | `userid:xxxx` | 飞书 user_id |
| `unionid:` | `unionid:on_xxxx` | 飞书 union_id |
| 无前缀 | `user@company.com` | 默认按 email 处理（向后兼容） |

留空则不转移，文档归应用所有。

> **背景**：飞书应用创建的文档默认归应用所有，企业用户无法在自己的云文档列表里直接看到。配置 `default_owner` 后，每次创建文档会立即转给你，你就能在"我的文件"里看到。
>
> 转移失败**不会让脚本崩溃** —— 文档已创建，URL 会正常返回，失败信息以 `owner_transfer_warning` 字段附在 results 里。

### 向后兼容

- 若配置中没有 `accounts`，自动回退到环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
- 旧的顶层 `default_owner_email` 字段仍然支持（按 email 处理）
- 手动模式下也可以 export 环境变量后直接运行，不需要配置文件：

```bash
export FEISHU_APP_ID="cli_xxxxxxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"
python3 feishu-output/run.py
```

## 使用

在 Claude Code 对话中输入：

```
/feishu-doc 创建一个项目进度报告
```

## 故障排查

所有权转移类问题（`code 1063xxx`、`Cannot resolve phone ...`）现在是非致命的 —— 文档创建成功后才尝试转移，失败信息以 `owner_transfer_warning` 字段附在 results 里，不会让脚本退出。

| 报错 | 原因 | 解决 |
|---|---|---|
| `FEISHU_APP_ID and FEISHU_APP_SECRET must be set` | 环境变量未配置 | 手动模式：运行前 export；自动模式：检查 settings.json |
| `Auth failed` | App ID 或 Secret 错误 | 去飞书开放平台 → 凭证与基础信息 页面核对 |
| `code: 99991663` 或 `permission denied` | 权限不足 | 检查权限是否已添加并审批通过 |
| `code: 99991668` | 应用未发布 | 去版本管理创建版本并发布 |
| `code: 2890005` (forbidden) | 画板写入权限不足 | 确认已开通 `board:whiteboard:node:create` 权限 |
| `Cannot extract whiteboard token` | 文档内嵌画板未返回 token | 可能是飞书版本不支持，联系管理员 |
| `ModuleNotFoundError: feishu_api` | skill 安装路径不对 | 确认 clone 到了 `~/.claude/skills/feishu-doc/` |
| `Cannot resolve phone xxx`（warning） | `phone:` 配置查不到对应飞书用户 | 确认手机号在该企业飞书内注册；或改用 `openid:` |
| `code: 99991672 ... contact:user.id:readonly`（warning） | `phone:` 模式缺少联系人查询权限 | 开通 `contact:user.id:readonly` 权限并重新发布；或改用 `email:` / `openid:` |
| `code: 1063002`（warning） | 文档所有权转移失败：调用方不是文档所有者 | 正常情况不会触发；文档仍归应用所有 |
| `code: 1063003`（warning） | 转移失败：目标用户不在可见范围 | 检查 `default_owner` 指向的用户是否本组织成员 |
| `code: 1063001`（warning） | 转移失败：邮箱无效 | 核对邮箱拼写；个人邮箱（@163/@126/@qq）通常不被飞书接受 |

## License

MIT
