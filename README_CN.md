# Instagram 评论爬虫 (单贴版)

这是一个基于 Playwright 的 Python 工具，用于抓取 Instagram 单个公开帖子下的评论和回复。它通过接管登录后的浏览器会话来获取数据，无需申请官方 API。

[English README](README.md) | [中文说明](README_CN.md)

## 🛠 功能特性

使用本工具，你可以：

- **采集评论**：抓取指定公开帖子下的所有评论及回复。
- **自动抓包**：通过浏览器交互自动捕获所需的身份验证 Header、Cookie 和 API 端点，无需手动复制。
- **断点续传**：支持任务中断后从上次的位置继续爬取，防止数据丢失。

> **⚠️ 重要提示**
>
> 本爬虫依赖于 Instagram 的网页端结构。如果 Instagram 更新了反爬规则或 API 接口，工具可能会失效。  
> 如果遇到问题，请先重新运行“抓包步骤”更新凭证，或查看下方的疑难解答。

## 📋 前置要求

- **Python**: 3.10+（推荐 3.11 或 3.12）
- **系统终端**: Windows PowerShell（本文档演示命令基于 Windows）
- **账号**: 一个能够访问目标帖子的有效 Instagram 账号

## 🚀 快速开始

### 步骤 1：进入项目目录

```powershell
cd .\ig-comment-crawler
```

预期结果：目录下应包含 `ig_crawler.py`、`run_ig_crawler.py` 和 `config.example.json`。

### 步骤 2：创建并激活虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

预期结果：终端提示符前方显示 `(.venv)`。

### 步骤 3：安装依赖

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
```

预期结果：所有包安装成功，无报错。

### 步骤 4：创建本地配置文件

```powershell
copy config.example.json config.json
copy .env.example .env
```

预期结果：根目录下生成 `config.json` 和 `.env`。  
注意：这两个文件包含敏感信息，请勿提交到 GitHub。

### 步骤 5：抓取认证信息 (Auth Capture)

```powershell
python ig_auth_setup.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/"
```

操作指南：

1. 浏览器自动打开后，登录 Instagram。
2. 如果遇到二次验证，请完成验证。
3. 如果提示密码错误并要求二次验证，先完成验证，再把邮箱中的一次性登录链接复制到 Python 打开的 Playwright 浏览器中打开。
4. 登录成功后，浏览器会跳转到目标帖子。
5. 向下滚动评论区，直到至少加载出一页新的评论（这会触发网络请求）。
6. 等待几秒钟。
7. 回到终端，按 `Ctrl+C` 结束抓包。

预期结果：

- `config.json` 自动填充了 Cookies 和 API 端点。
- `.env` 更新了环境变量。
- 抓包日志保存在 `crawler_data/raw_responses/`。

### 步骤 6：验证配置

打开 `config.json`，确保以下字段不再是 `YOUR_...` 占位符：

- `instagram.authentication.cookies`
- `instagram.authentication.headers`
- `instagram.endpoints.comments`
- `instagram.endpoints.comment_replies`

### 步骤 7：运行爬虫

```powershell
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/"
```

预期结果：终端显示进度，最终 JSON 结果保存在 `crawler_data/ig_comments/`。

## ⚙️ 高级用法

### 运行时选项

```powershell
# 仅抓取前 400 条评论（含回复）后停止
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --max-comments 400

# 强制从上次中断的地方继续（断点续传）
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --resume

# 强制重新开始（不使用断点续传）
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --no-resume

# 不抓取楼中楼回复（仅抓取一级评论）
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --no-replies
```

### 运行测试

```powershell
python -m pytest -q
```

## 📊 输出结构

结果 JSON 文件包含：

- `post`: 帖子基础信息（URL、ID、说明文字）
- `comments`: 评论列表（包含嵌套的 `replies`）
- 统计信息：总数、抓取时间、页数

## 🔧 常见问题 (Troubleshooting)

- **403 / 429 错误（Rate Limit）**：请求过于频繁。请尝试降低 `config.json` 中的 `requests_per_minute`，或重新运行步骤 5 更新 Cookie。
- **缺少评论/回复**：API 端点可能已变动。请重新运行 `ig_auth_setup.py` 重新抓包。
- **ModuleNotFoundError**：请确保在项目根目录下运行命令，并已激活虚拟环境。

## ⚖️ 免责声明与合规使用

- **仅供学习**：本项目仅用于技术研究和学习 Python 爬虫技术。
- **合法使用**：请确保你有权访问抓取的数据，并遵守 Instagram 的服务条款及当地法律法规。
- **隐私保护**：请勿在没有法律依据的情况下收集用户的个人敏感数据。
- **禁止滥用**：请勿将本项目用于绕过平台安全措施或进行恶意攻击。

## 📄 开源协议

MIT License，详见 `LICENSE` 文件。
