# NOMI 项目管理系统

面向小型研发团队的一站式项目管理系统，**单系统部署**。提供完整的项目
管理能力（项目、工作项、周期、模块、成员、标签、看板、视图、评论）与
研发协作能力（GitLab 分支/MR 管理、AI 代码核验、风险跟踪、周报），
开箱即用，界面为简体中文。

系统由两部分组成，跑在同一套 Docker Compose 里：

- **NOMI 工作台**（`http://localhost:8090`）：日常研发主界面，
  需求/周期/模块/成员/标签/子需求/评论/视图等完整项目管理能力；
- **PMO 控制台**（`http://localhost:8080`）：管理视角的补充模块——
  项目总览、跨项目看板、风险管理、AI 核验、GitLab 写操作与系统设置。

界面已完成品牌化与中文本地化：登录页、侧边栏、创建项目/需求弹窗、
时间格式（`9月24日`、`3 小时前`）、默认语言简体中文、上海时区兜底。

## 启动

### Docker Compose（推荐）

需要运行中的 Docker Engine 与支持 `include` 的 Docker Compose（v2.20+）。

```powershell
Copy-Item .env.example .env
Copy-Item deploy/engine/variables.env.example deploy/engine/variables.env
docker compose up -d --build
```

一条命令启动整套栈：控制台前端/后端/MySQL + 项目管理引擎
（web/api/worker/postgres/valkey/rabbitmq/minio/proxy 等 13 个服务，
`deploy/engine/`）。控制台入口 `http://localhost:8080`；工作台入口
`http://localhost:8090`。后端通过内部网络直连引擎。

首次启动后需初始化引擎（管理员/工作区/项目/API Token），
再到控制台「系统设置」填入并导入项目，详见 docs/INTEGRATIONS.md。
镜像拉取如遇网络波动，重跑 `docker compose pull` 即可续传。

已在 Docker Engine 29 / Compose v5 下实测：构建启动、登录、MySQL 落库、
`docker compose restart` 后数据保留且服务自动恢复（Nginx 按请求解析后端地址，
后端入口等待数据库就绪后再启动）。

### 本地开发

Node 22+、Python 3.12+。默认系统 Python 3.8 不支持本项目后端依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
.\.venv\Scripts\python backend/app.py
```

另一个终端：

```powershell
npm ci
npm run dev
```

前端 `http://localhost:5173`，Flask API 在 `http://127.0.0.1:5000`，
Vite 通过同源 `/api` 代理访问后端。本地默认 SQLite，Docker 默认 MySQL，
使用相同 SQLAlchemy 模型和业务代码。可通过 `DATABASE_URL`
指定其他 MySQL/SQLite 连接。

首次 Demo 启动账号：

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| demo | demo | 管理员 |
| member | member | 只读成员 |

Demo 首次生成 1 个项目、6 周、4 个模块、30 条需求、4 位成员和演示 Git/AI 证据。
数据持久化后不会因刷新/重启重置。演示数据不会发送到真实模型服务。

## 当前功能

- 品牌化登录页、工作区布局、浅/深色模式。
- React/TypeScript/Vite、Tailwind、shadcn 风格基础组件和 Recharts 周进度图。
- 项目中心：全部项目的卡片总览（进度、需求统计、风险、成员、周期），
  一键新建本地项目（名称、开始日期、周期），登录后默认落在项目中心。
- 需求表格/看板双视图：看板按六个状态分列，管理员可拖拽卡片跨列修改状态
  （引擎项目写回远端，本地项目写本地库）；每列支持快捷新增；演示项目只读并给出引导。
- 服务端 Session 登录、管理员/成员两种权限，写请求安全头校验。
- 需求状态与代码证据加权进度；模块、周计划、成员、风险统计从同一数据集计算。
- 搜索和筛选、按周看板/只读时间轴、需求详情、Git/MR/Pipeline/Commit、验收证据。
- 在需求页创建需求，在详情页修改标题、描述、验收项、状态、负责人、模块与周期；写入引擎后回读确认。
- 在需求详情创建 GitLab 分支和 MR，自动绑定本需求；默认目标为仓库默认分支，不执行合并或发布。
- 写入权限校验、项目/仓库绑定校验、部分成功提示；Demo 需求只读，不向真实服务发送写入。
- 自动/人工风险、风险确认/重新打开、规则消失后自动关闭。
- 引擎分页同步、模块/周期映射、GitLab 自动关联和人工 MR 绑定。
- 统一 OpenAI-compatible LLM Provider、限量上下文、结构化结果校验及持久化。
- 手动同步、定时同步、GitLab Webhook；失败保留缓存并记录来源。
- AI 核验随代码或验收项变更失效；非法模型输出不会替换成功结果。
- 敏感设置加密，API 永不回传 Token 明文。
- 真实项目 AI 摘要：手动生成、每日缓存、过期标记；Demo 只展示事实摘要。

真实服务接入前需提供自己的地址和凭据。没有凭据的环境不会显示虚假的连接成功。

## 测试

```powershell
npm test
npm run build
cd backend
..\.venv\Scripts\python -m unittest discover -s tests -v
```

后端包含领域算法、权限、持久化、加密设置、Demo 隔离和模拟
引擎→GitLab→AI 完整流程测试。前端包含登录、首页、详情、风险、加载、
空态、错误和缓存保留测试。

外部服务模拟测试不能替代真实凭据下的联调。

## 数据与迁移

启动自动应用初始 Schema Revision 1，记录在 `schema_versions`；
也可在 `backend` 目录执行 `python -m pmo.migrate`。
迁移和 Demo 种子可重复运行，不清空现有数据。

核心表：projects、external_projects、requirements、requirement_git_links、
ai_inspections、risks、weekly_snapshots、sync_logs、system_settings；另有 users 与 schema_versions。
后续结构变更须增加显式版本迁移，不以删库方式升级。

本地数据库和自动生成的开发密钥在 `backend/data`；Docker 分别使用
`mysql_data` 和 `app_data` 数据卷。需要一起备份数据库与 SECRET_KEY，
否则已加密的外部系统凭据无法恢复。

## 部署边界

- Demo 默认凭据仅供本机演示；真实部署先关闭 `DEMO_MODE`、设置稳定的随机
  `SECRET_KEY` 和至少 12 字符的管理员密码，并替换数据库密码。
- 账号只在首次初始化时创建。修改环境变量不重置已有账号密码。
- 部署 TLS 反向代理后设置 `COOKIE_SECURE=true`。Compose 默认只绑定本机回环。
- 使用单 Waitress 进程，避免多进程调度重复触发。高频、大仓库接入前需要持久任务队列。
- 管理员配置的集成地址允许内部服务；不得把管理员权限开放给不可信用户。
- 仅查看/核验可使用只读 Token；管理操作需要对应项目写权限，按所用功能授予最小权限。
  代码核验会向所配置模型服务发送部分代码。

详细约定见 [API 文档](docs/API.md) 与 [接入说明及已知边界](docs/INTEGRATIONS.md)。

## 团队协作

仓库已开放给企业成员：提交、评审请遵循分支规范（feature/* → main），提交信息用中文简述变更。
