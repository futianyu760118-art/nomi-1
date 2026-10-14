# REST API

所有路径以 `/api` 开头。同源 Cookie Session；写请求必须发送
`Content-Type: application/json` 和 `X-PMO-Request: 1`。

错误统一为 `{"error":"描述","source":"可选外部来源"}`。
401 未登录；403 权限不足；404 不存在；409 操作正在执行；502 外部系统失败。

| 方法 | 路径 | 权限 | 内容 |
| --- | --- | --- | --- |
| GET | `/health` | 无 | 进程探活 |
| POST | `/auth/login` | 无 | `username`, `password` |
| GET | `/auth/me` | 成员 | 当前账号与角色 |
| POST | `/auth/logout` | 无 | 清理 Session |
| GET | `/projects` | 成员 | 项目选择列表，含 demo/live 标识 |
| GET | `/bootstrap?project=1` | 成员 | 同一项目的总览、需求、风险、同步日志 |
| GET | `/dashboard?project=1` | 成员 | 计算后的统计 |
| GET | `/requirements?project=1&q=Skill` | 成员 | 需求列表 |
| GET | `/requirements/REQ-012?project=1` | 成员 | Git 与 AI 证据附于需求详情 |
| GET | `/management/options?project=1` | 管理员 | 完整成员、模块、周期和可映射状态目录 |
| POST | `/requirements?project=1` | 管理员 | 在 引擎 创建需求并回读，不允许 Demo 写入 |
| PATCH | `/requirements/REQ-012?project=1` | 管理员 | 写回 引擎，再回读当前需求 |
| POST | `/requirements/REQ-012/branch?project=1` | 管理员 | 可选 `name`、`ref`；创建并关联开发分支 |
| POST | `/requirements/REQ-012/merge-request?project=1` | 管理员 | `branch`、可选 `target`；创建并绑定 MR，不合并 |
| GET | `/weekly?project=1` | 成员 | 周计划与需求 |
| GET | `/risks?project=1` | 成员 | 风险列表 |
| POST | `/risks?project=1` | 管理员 | 人工风险：`requirementId`, `level`, `title`, `action` |
| POST | `/sync?project=1` | 管理员 | Demo 只重新计算；真实项目读取 引擎/Git |
| POST | `/risks/scan?project=1` | 管理员 | 重新应用风险规则，不调用 LLM |
| PATCH | `/risks/1?project=1` | 管理员 | `status`: `OPEN` / `ACKNOWLEDGED`；人工风险还可 `RESOLVED` |
| POST | `/summary?project=1` | 管理员 | 生成并保存真实项目的 LLM 摘要 |
| GET | `/settings` | 管理员 | 配置；密钥只返回 `*Configured` 布尔值 |
| PATCH | `/settings` | 管理员 | 部分更新；未传密钥保留旧值 |
| POST | `/connections/engine` | 管理员 | 从配置导入或刷新真实项目，不覆盖 Demo |
| POST | `/connections/git?project=1` | 管理员 | 同步真实项目的 Git 关联 |
| POST | `/requirements/REQ-012/git-link?project=1` | 管理员 | `mr`: 正整数，校验远程 MR 后绑定 |
| POST | `/requirements/REQ-012/inspect?project=1` | 管理员 | 限量获取 Diff/代码/测试报告，校验 AI JSON 后保存 |
| POST | `/webhooks/gitlab` | Webhook 密钥 | `X-Gitlab-Token`，处理 MR/Push/Pipeline |

## 数据语义

需求写字段：`title`, `description`, `criteria`（字符串数组）, `owner`, `priority`,
`status`, `module`, `week`（整数，对应排序后的 引擎 Cycle）, `start`, `due`。
新增必须有非空标题；未传模块/周期保持未分配。修改只发送变化字段。
描述编辑为纯文本，写回会重新生成 HTML。成员仅有读取权限，写接口需管理员。
外部写入已完成但关联/回读失败时返回 502 和 `partial: true`，
需刷新核对，不应当作“完全未写入”再次创建。接口不承诺跨系统原子事务。

- 项目完成度为需求优先级加权的证据进度，非 AI 分数平均值。
- 需求阶段：未开始 0、进行中 30、关联 MR 50、AI 主体完成 70、
  有通过的测试证据且 Pipeline 通过 90、引擎 已验收 100。
- 阻塞时保存此前进度。延期是截止日已过且状态不是 DONE。
- 旧 AI 结果在 MR SHA 或需求描述/验收项变化后标记 stale，不再提升进度。
- 已取消/删除的外部需求从活动聚合中排除，本地历史证据不被删除。
- 自动风险被人工确认后仍保留；只有风险条件消失才自动关闭。
- LLM 输出必须逐项匹配原验收标准；非法 JSON 不会覆盖成功结果。
- 设置中的 Token 加密保存；环境变量可提供缺省值。固定 SECRET_KEY 是解密前提。
