# 接入说明

## NOMI 前端（官方镜像 + 产物层定制）

用户界面基于 **研发引擎 官方前端镜像**（下拉框等交互行为完好），
在构建镜像时做产物层定制，不重新编译源码，因此上游行为完全不受影响：

- `docker/nomi-web/rebrand.sh`：字符串替换（品牌 引擎→NOMI、登录文案、
  侧边栏硬编码标签、登录错误提示、日期/时区格式、默认语言 zh-CN）、
  资源目录加版本号（`assets-nomi`，用于刷新客户端缓存）
- `docker/nomi-web/nomi-theme.css`：品牌令牌覆盖（浅色墨黑/深色墨绿），
  经追加进应用自身样式表生效（React Router hydration 会移除额外 `<link>`）
- `docker/nomi-web/nomi-brand.js`：运行时注入器（品牌标、相对时间中文化、
  清除 GitHub 推广链接与版本徽章），同时附加到入口 chunk，
  使持有旧缓存 HTML 的会话也能自愈
- `docker/nomi-web/icons/`：NOMI 图标与加载动画（品牌标脉动）

**改动前端必须走语法门禁**：文本替换若误删对象键会产出非法 JS，只表现为白屏。

```bash
docker compose build web
node docker/nomi-web/check-chunks.mjs pmo-web:latest   # 解析全部 900+ bundle
docker compose up -d web
```

`deploy/engine/` 为研发引擎编排。早期上游基线（含历史版本的下拉框定位缺陷
使其无法直接构建使用）；若将来上游修复，可切回源码构建。

## 内嵌 引擎 引擎（单系统架构）

基础项目管理由内嵌的 研发引擎 承载：引擎（`deploy/engine/`，随根 Compose 启动）+
**NOMI 定制前端**（`docker/nomi-web/` 产物层构建）。
主题改造点：propel 设计令牌覆盖（浅色墨黑/深色 示例 绿）、品牌标与登录页
（过渡动画、「目标向下。事实向上。」文案）、i18n 修复（`import.meta.glob` 静态打包）。
修改源码后重建：`docker compose build web && docker compose up -d web`。

日常入口 `http://localhost:8090`（引擎 全部 PM 能力）；PMO 控制台 `http://localhost:8080`
提供总览/看板/风险/AI 核验/GitLab 写操作，经 `ENGINE_SERVER_URL` 内网直连引擎。

首次部署后的初始化流程：

1. 打开 `http://localhost:8090`，按引导完成实例设置（管理员邮箱/密码）。
2. 创建工作区与项目（或用已有项目）。
3. 在个人设置 → Developer → Personal Access Tokens 创建 API Token。
4. PMO 控制台「系统设置」填：引擎 URL `http://localhost:8090`、Token、
   Workspace Slug、Project ID，「保存并导入项目」。

## 本地项目

项目中心可新建「本地项目」：需求、排期、负责人、状态全部在控制台内管理，
不连接 引擎/GitLab，看板拖拽直接写本地库。需求编号从 REQ-001 顺序分配；
负责人、模块为自由输入（自动提示已有值）；管理员可重命名或调整周期。

边界：本地项目暂不接入 GitLab 与 AI 核验（创建分支/MR/运行核验需要导入
连接 引擎 的真实项目）；可与演示项目、引擎 项目共存于同一工作区。

## 引擎

在系统设置填写：

- 引擎 URL：服务根地址，不带 `/api/v1`。
- Workspace Slug：工作区 URL 中的 slug。
- Project ID：项目 UUID。
- API Token：查看需要读取项目、成员、状态、Module、Cycle、Work Item 的权限；
  控制台内管理需求还需要 Work Item、Module、Cycle 写权限。

选择“保存并导入项目”，完成后从顶部项目选择器选择新项目。
Demo 数据和真实项目隔离。当前版本保存一组 引擎/Git/LLM 连接配置，
多项目历史可查看，但同步只针对当前配置对应的真实项目。

适配器读取 `/api/v1/workspaces/{workspace}/projects/{project}/`，
优先使用 `work-items/`，404 时兼容旧 `issues/`；处理 cursor 分页。
Module 和 Cycle 使用 `module-issues/` 与 `cycle-issues/` 关联接口映射到内部模块及周序号。
项目无周期日期时，以项目日期或导入当日建立六周窗口。

统一需求号使用 `REQ-{sequence_id:03d}`。请在代码分支和 MR 中使用该编号。
验收项从描述中的 `Acceptance Criteria` / `验收标准` / `验收条件` 后逐行读取；
建议将验收标准放在描述末尾，每行一条。没有验收项时拒绝 AI 核验。

状态依据 引擎 group 和名称映射；取消状态不进入活动需求聚合。

### 控制台内管理

需求页新增需求，详情页编辑内容、验收标准、负责人、状态、优先级、日期、模块和周期。
模块、成员、周期下拉取完整目录，包括尚无需求的模块或成员。
需求内容用 Work Item POST/PATCH；模块、周期通过各自关联接口分开写入。
关联不是跨平台事务：内容已成功但后续失败时明确返回部分完成，不自动重建需求。
网络超时结果不明时先刷新核对，避免重复创建。当前没有持久化幂等请求队列。
不存在的状态不会降级映射成“开发中”；同名成员会拒绝模糊指派。
描述和验收标准采用纯文本表单，编辑描述会重新生成 HTML，不保留复杂富文本格式。
Demo 需求保持只读，已有工作区数据不会被这些操作改动。

## GitLab

- Git URL：实例根地址，不带 `/api/v4`。
- Repository：推荐 `namespace/project`，也可为数字 Project ID。
- Token：只读核验使用 `read_api` / 仓库读取权限；创建分支和 MR 需要具备 API 写权限、
  且服务账号在指定项目中有对应操作权限。服务端不绕过保护分支策略。

支持 Branch、Commit Message、MR 标题、描述识别完整 REQ ID。
`REQ-021` 不会误匹配 `REQ-0211`。多个 MR 匹配同一需求时，
当前 MVP 使用最近更新的 MR；需求详情允许人工指定 MR 编号覆盖自动选择。
GitHub、Gitea 的实现未提供，扩展边界为 `GitProvider` 抽象接口。

需求详情提供创建分支和创建 MR；分支名包含需求号，MR 标题由需求号和标题生成。
默认源基线/目标使用仓库默认分支。关联记录即时保存，界面无需跳转 GitLab。
不自动审批、合并或触发发布。创建操作前核对项目绑定；仓库绑定后，改变全局仓库
配置不会让已有项目静默改写到另一个仓库。

### Webhook

环境变量 `WEBHOOK_SECRET` 与 GitLab Webhook Secret Token 保持一致。
URL 为 `https://<你的部署域名>/api/webhooks/gitlab`，启用 Merge Request、
Push 和 Pipeline events。生产入口应配置 HTTPS。

Webhook 验证仓库匹配；新 MR / MR 更新可以自动核验，重复 SHA 不重复调用。
Push/Pipeline 只同步事实，不调用 LLM。第一次返回失败可由 GitLab 重试。
当前为同步处理，小团队使用；大型仓库请在接入持久任务队列前避免开启高频事件。

## LLM

统一 Provider 采用 OpenAI-compatible `POST {LLM_BASE_URL}/chat/completions`，
支持云端或本地兼容服务。Base URL 通常以 `/v1` 结尾。
本地服务没有密钥时可留空 API Key；Model 必须填写。
服务必须支持 JSON Object response format。

读取顺序：MR Diff、修改文件、Pipeline 测试汇总；不克隆整仓库，也不执行远程代码。
默认 20 个文件、50,000 字符 Diff、120,000 字符代码。跳过常见密钥文件。
代码与描述都作为不可信资料放入 Prompt；LLM 不能操作工具。
代码将发送到配置的模型服务，因此应使用团队批准的服务及最小权限凭据。
文件名规则不能保证去除业务代码中硬编码的所有敏感信息，接入前需确认代码可外发。

未知测试状态不会因 Pipeline 绿色而自动记为通过。需要 GitLab 的非空测试执行报告。
模型证据只是辅助判断，业务验收仍以 引擎 状态为准。

## 自动同步与已知边界

Waitress 单进程中运行一个后台调度线程，与人工同步共用互斥锁。
设置自动同步后，按配置间隔拉取；失败保留已有缓存和成功时间。
风险规则每分钟重新计算，不依赖重启跨日更新。

目前没有 引擎 Webhook 接收器，引擎 变化通过手动/定时同步处理；
进入测试/验收状态后可人工核验。Demo 首页的事实摘要由聚合数据生成，
不是伪装的 LLM 摘要。真实项目支持手动生成 AI 摘要；启用自动同步且模型已配置时，
调度器每天尝试生成一次并保存。失败当天不反复自动重试，可人工重试；
摘要数据变化后标记过期。持久异步任务队列尚未实现。

## 验证范围

适配器、分页、映射、核验与失败保留缓存使用模拟外部响应测试。
没有提供真实 引擎/GitLab/LLM 凭据时，不代表已完成真实服务联调。

`backend/tests/preview_workflow.py` 使用临时数据库和测试用模拟 Provider，
在 5101 端口提供构建后页面供浏览器测试；不代表真实 引擎/GitLab 已连接。

## 尚未完成的内嵌范围

与 引擎 的差距（按优先级待补）：标签（Labels）、子需求与关联、需求评论/动态、
保存的筛选视图、日历/电子表/甘特视图、项目成员邀请与角色管理、状态自定义、
周期/模块在控制台内创建（当前周期/模块/成员目录从引擎同步只读展示）。
多项目独立凭据、MR 评审合并和流水线操作尚未实现。
当前不是完整的"开箱即用内置 引擎/GitLab"，不把需求写回功能等同于整个目标完成。
