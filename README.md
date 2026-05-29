# Customer-Service-Automation-Multi-Agent

> 生产级 · 多 Agent 客服自动化平台
> AutoGen + LangGraph + LangChain + FastAPI + Chroma + SQLite

支持企业微信 / 邮件 / 网页客服 三种入口，由 4 个专业 Agent 自动协作处理：售前咨询、投诉处理、技术支持、售后服务。
内置 RAG 知识库、会话持久化、人工接管、定时日报、Web 管理后台、多租户。

---

## ✨ 功能演示

- **🤖 4 个专业 Agent 协作**：监督者节点（Supervisor）基于规则 + LLM 自动路由到对应 Agent；Agent 之间支持 Hand-off。
- **💬 多入口接入**：
    - 网页客服：内置 WebSocket 客户端 (`/static/chat.html`)
    - 企业微信：标准回调地址 + 主动推送
    - 邮件：SMTP 发送 + IMAP 轮询自动回复
- **📚 RAG 知识库**：基于 Chroma + OpenAI Embeddings，支持多租户隔离 (`kb_<tenant_id>`)。
- **🧾 自动工单 / 日志**：投诉自动创建工单；APScheduler 每天自动生成日报并通过邮件推送。
- **🧑‍💼 人工接管**：管理后台一键接管 / 释放，无缝切换。
- **🏢 多租户**：单一部署可服务多家店铺/企业。

---

## 🧠 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         入口适配层 (Channels)                     │
│  网页 WebSocket    │   企业微信回调   │   IMAP/SMTP 邮件          │
└──────┬───────────────────┬──────────────────┬────────────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
                  ┌─────────────────────┐
                  │   ChatService 编排   │
                  └─────────┬───────────┘
                            ▼
                ┌──────────────────────────┐
                │   LangGraph Supervisor   │
                └─┬────────┬────────┬──────┘
                  │        │        │
       ┌──────────▼─┐  ┌───▼───┐  ┌▼────────────┐  ┌─────────────┐
       │ Consult.   │  │ Tech  │  │ Aftersales  │  │ Complaint   │
       └──────────┬─┘  └───┬───┘  └──────┬──────┘  └──────┬──────┘
                  └────────┴──────┬──────┘                │
                                  ▼                       ▼
                       ┌─────────────────┐      ┌──────────────────┐
                       │  RAG (Chroma)   │      │  Tickets / Memory │
                       └─────────────────┘      └──────────────────┘
```

---

## 🚀 快速开始

### 1. 环境准备

- Python 3.11+
- macOS / Linux / Windows
- OpenAI API Key（或兼容 OpenAI Chat Completions 协议的接口）

### 2. 克隆并配置

```bash
git clone <YOUR_REPO_URL>.git
cd Customer-Service-Automation-Multi-Agent

cp .env.example .env
# 编辑 .env，至少填写 OPENAI_API_KEY
```

### 3. 安装依赖

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 4. 本地运行

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动后：
- 网页客服：<http://localhost:8000/>
- 管理后台：<http://localhost:8000/admin>（默认账号 admin / admin123）
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

### 5. 导入示例知识库

```bash
curl -X POST http://localhost:8000/kb/import-defaults -F "tenant_id=default"
```

### 6. Docker 部署

```bash
docker compose up -d --build
docker compose logs -f
```

### 7. 一键发布到 GitHub

```bash
# 已安装并登录 gh
bash init_github.sh
```

---

## 🛠️ 项目结构

```
Customer-Service-Automation-Multi-Agent/
├── main.py                       # FastAPI 入口
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── init_github.sh                # 一键 GitHub 发布
├── .env.example
├── .github/workflows/ci-cd.yml   # CI/CD
├── agents/                       # 4 个专业 Agent
│   ├── base.py
│   ├── consultation_agent.py
│   ├── complaint_agent.py
│   ├── tech_support_agent.py
│   └── aftersales_agent.py
├── workflows/                    # LangGraph 工作流
│   ├── graph.py                  # Supervisor + Hand-off
│   └── router.py                 # 规则路由
├── tools/
│   ├── knowledge_base.py         # Chroma 向量库
│   ├── order_lookup.py           # 订单工具
│   └── ticket.py                 # 工单工具
├── api/
│   ├── routes.py                 # 公开 REST API
│   ├── websocket.py              # 网页 WebSocket
│   ├── admin.py                  # 管理后台 API
│   └── auth.py                   # JWT 认证
├── core/
│   ├── chat_service.py           # 会话编排
│   ├── config.py                 # Pydantic 设置
│   ├── logger.py                 # Loguru 日志
│   └── memory.py                 # 会话记忆
├── integrations/
│   ├── wechat_work.py            # 企业微信
│   ├── email_handler.py          # SMTP / IMAP
│   └── webchat.py
├── models/
│   ├── database.py               # SQLAlchemy 异步
│   └── schemas.py                # Pydantic v2
├── scheduler/
│   └── daily_report.py           # APScheduler 日报
├── static/
│   ├── chat.html                 # 客户端
│   └── admin.html                # 管理后台 SPA
├── knowledge_base/               # 默认知识库 (.md / .txt)
└── tests/
    └── test_agents.py
```

---

## 🧩 真实客服对话案例演示

下面 3 个场景全部为系统在 LangGraph Supervisor + 4 个 Agent 协作下的真实样例（已脱敏）。

### 场景 1：售前咨询 + Hand-off 至售后

```
👤 用户: 你好，智能手表 Pro 这款现在多少钱？有什么活动吗？
🤖 [consultation] 您好~ 智能手表 Pro 目前售价 1299 元，本月新品节立减 100，叠加店铺会员券再减 50。
                 配色有黑色/银色/玫瑰金三款，购买后享一年整机质保 + 7 天无理由退货。
                 请问您倾向哪种风格呢？需要我帮您下单吗？

👤 用户: 那我下周买，先帮我看下我之前那单 20240518001 到哪了？
🤖 [supervisor] HANDOFF: aftersales
🤖 [aftersales] 您好，已为您查询到订单 20240518001：
                  - 商品：智能手表 Pro
                  - 状态：已发货
                  - 运单号：SF1234567890（顺丰）
                  - 预计明日送达
                如有变化我们会第一时间通知您。
```

### 场景 2：投诉 → 自动开工单 → 升级人工

```
👤 用户: 客服你好，我下单后等了 7 天还没发货，要求立即处理！否则我就投诉到 12315！
🤖 [supervisor] 路由 -> complaint
🤖 [complaint] 非常抱歉给您带来这么糟糕的体验，深表歉意。
              我们立刻为您加急核查仓库出库情况，预计 30 分钟内会回复您具体进度，并优先安排顺丰发货。
              已为您安排专属客服后续 24 小时跟进；如未解决，将由主管直接联系您。
              （系统提示：已为您创建投诉工单 T-A1B2C3D4E5，专员将在 24 小时内联系您。）
              HUMAN_TAKEOVER: yes
🛎️ [system]   会话状态：takeover（已转人工） · 当前坐席：admin
```

### 场景 3：技术支持 + 多轮排错

```
👤 用户: 我的手表连不上手机蓝牙，反复断开
🤖 [tech_support] 复述确认：手表与手机蓝牙连接异常、反复断开。
                  请按以下步骤尝试：
                  1) 确认手机蓝牙开启，距离 1 米内；
                  2) 在 App 中点击「重新配对」；
                  3) 长按手表电源键 10 秒重启。
                  若仍无法解决，请告诉我手表型号 + 手机系统版本，我为您升级技术工程师。

👤 用户: 试了都没用，型号 Watch Pro 1, 手机 iPhone 13 iOS17
🤖 [tech_support] 收到。这是 iOS 17 已知的 BLE 兼容问题。请：
                  1) 升级 App 到最新版 (≥ 3.7.2)；
                  2) 在 iOS 设置 > 蓝牙 中点击「忘记此设备」后再配对。
                  HUMAN_TAKEOVER: yes
                  （系统提示：建议工程师远程协助，请稍候）
```

---

## 🧑‍💼 人工接管流程

1. 任意 Agent 在回复末尾输出 `HUMAN_TAKEOVER: yes` 或客户连续两次表达不满 → 系统自动将会话状态置为 `takeover`。
2. 管理员登录 <http://localhost:8000/admin>（admin / admin123）。
3. 在「会话列表」中筛选状态 `takeover`，点击进入。
4. 点击「人工接管」 → 后续客户消息不再调用 LLM，由人工通过「人工回复」输入框发送。
5. 完成后点击「释放」按钮，系统恢复 AI 自动回复。
6. 所有交接行为都会写入 `messages` 表，可在日报中体现。

人工接管期间客户在网页端会收到提示：「您的问题已提交人工客服，请稍候」。

---

## 🟢 企业微信接入教程

> 完整文档：<https://developer.work.weixin.qq.com/document/path/90665>

1. **创建自建应用**：登录企业微信管理端 → 应用管理 → 创建自建应用。
2. **获取关键信息**：复制 `CorpID` / `AgentId` / `Secret`。
3. **配置 .env**：
   ```bash
   WECHAT_WORK_CORP_ID=ww1234567890abcdef
   WECHAT_WORK_AGENT_ID=1000002
   WECHAT_WORK_SECRET=xxxxxxxxxxxxxxxx
   WECHAT_WORK_TOKEN=自定义随机字符串
   WECHAT_WORK_AES_KEY=43位Base64编码的AESKey
   ```
4. **配置接收消息**：在企业微信后台「接收消息 → 设置 API 接收消息」中：
    - URL: `https://your-domain.com/integrations/wechat/callback`
    - Token / EncodingAESKey 与 .env 中保持一致。
5. **可信域名 / 出口 IP**：将服务器公网 IP 加入应用「企业可信 IP」白名单。
6. **联调验证**：点击「保存」，企业微信会发送一条 GET 验证请求，服务器需正确解密并返回 echostr。本项目已内置该流程。
7. **测试**：在企业微信对话窗口发送消息，应能在 1-3 秒内收到 AI 回复。

---

## 🔌 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/chat` | 发起一次客服对话（非 WS 客户端可用） |
| GET  | `/sessions` | 列出会话（可按 tenant_id / status 过滤） |
| GET  | `/sessions/{id}/messages` | 查询会话消息 |
| POST | `/sessions/{id}/takeover` | 人工接管 |
| POST | `/sessions/{id}/release` | 释放接管 |
| POST | `/sessions/{id}/human-reply` | 人工回复 |
| POST | `/tickets` | 创建工单 |
| GET  | `/tickets` | 查询工单 |
| POST | `/kb/upload` | 上传 .md/.txt 到知识库 |
| POST | `/kb/text` | 纯文本写入知识库 |
| POST | `/kb/import-defaults` | 导入 `knowledge_base/` 目录 |
| GET  | `/stats` | 获取统计概览 |
| WS   | `/ws/chat` | 网页客户端 WebSocket |
| ANY  | `/integrations/wechat/callback` | 企业微信回调 |
| POST | `/admin/login` | 管理员登录获取 JWT |

完整 OpenAPI 文档：<http://localhost:8000/docs>

---

## 🧪 测试

```bash
pytest -q
```

CI 流水线 `.github/workflows/ci-cd.yml` 会在每次 push 到 `main` 时：

1. 运行 `pytest`
2. 通过后构建并推送 Docker 镜像到 GHCR (`ghcr.io/<user>/customer-service-automation-multi-agent`)。

---

## 📅 定时日报

- 默认每天 09:00 (Asia/Shanghai) 运行 `scheduler.daily_report.generate_daily_report`。
- 自动汇总：会话数、消息数、解决数、升级人工数、当日新增工单。
- 通过 SMTP 发送给 `DAILY_REPORT_RECIPIENTS` 中配置的收件人，并写入 `daily_reports` 表。

修改频率：编辑 `.env` 中的 `DAILY_REPORT_CRON`（标准 5 段 cron 表达式）。

---

## 🏷️ 多租户

- 在 `.env` 中设置 `MULTI_TENANT_ENABLED=true`。
- 每个会话 / 工单 / KB collection 都按 `tenant_id` 隔离。
- 调用 `/chat` 时通过请求体的 `tenant_id` 字段切换租户：
  ```json
  { "tenant_id": "shop_001", "message": "你好", "channel": "web" }
  ```

---

## 📝 下一步建议

- ✅ 替换 `tools/order_lookup.py` 为真实 ERP / 订单系统对接。
- ✅ 接入更强的 LLM (GPT-4o, Qwen2.5, DeepSeek-V3) 以提升投诉处理质量。
- ✅ 在 `static/chat.html` 上嵌入到自家网站（`<iframe>` 或自定义嵌入）。
- ✅ 增加 Slack / 飞书 / 钉钉等更多渠道，复用 `ChatService.handle_user_turn`。
- ✅ 接入 Sentry / OpenTelemetry 做生产级监控。

---

## 📄 License

MIT
