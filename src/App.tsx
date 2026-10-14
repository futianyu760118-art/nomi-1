import { CSSProperties, FormEvent, ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronDown, Clock3, Code2, Eye, EyeOff,
  GitBranch, LayoutDashboard, LayoutGrid, ListChecks, LogOut, Menu, RefreshCw, Search, Settings, ShieldCheck,
  Sparkles, Target, UserRound, UsersRound, X, ExternalLink, Save, Link2, Moon, Sun, Columns3, List, LoaderCircle,
  Plus, FolderKanban,
} from 'lucide-react'
import { api, ApiError, errorMessage } from './api'
import type { Counts, Dashboard, ProjectMode, ProjectSummary, Requirement, Risk, SettingsData, Snapshot, Status, User, View } from './types'
import { Button } from './components/ui/button'
import { WeekChart } from './components/WeekChart'

const labels: Record<View, string> = { projects: '项目', dashboard: '总览', requirements: '需求', weekly: '周期', modules: '模块', members: '成员', risks: '风险', settings: '系统设置' }
const modeLabels: Record<ProjectMode, string> = { demo: '演示项目', live: 'Plane 项目', local: '本地项目' }
const boardColumns: Status[] = ['TODO', 'IN_PROGRESS', 'REVIEW', 'TESTING', 'DONE', 'BLOCKED']
const statusLabels: Record<Status, string> = { TODO: '未开始', IN_PROGRESS: '开发中', REVIEW: '待检查', TESTING: '测试中', DONE: '已完成', BLOCKED: '阻塞' }
const levelLabels = { HIGH: '高风险', MEDIUM: '中风险', LOW: '低风险' }
const riskStatuses = { OPEN: '待处理', ACKNOWLEDGED: '已确认', RESOLVED: '已关闭' }
const analysisStatuses: Record<string, string> = { IMPLEMENTED: '已实现', PARTIAL: '部分完成', MISSING: '缺少证据', UNKNOWN: '无法判断', PASSED: '测试通过', FAILED: '测试失败' }
const time = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未同步'

export function BrandMark({ small = false }: { small?: boolean }) {
  return <span className={`brand-mark ${small ? 'small' : ''}`}><img src="/brand/ztrz-mark-white.png" alt="" /></span>
}

function Loading({ text = '正在读取项目数据' }: { text?: string }) {
  return <div className="loading-state" role="status"><LoaderCircle className="spin" /><p>{text}</p></div>
}
function Empty({ text }: { text: string }) { return <div className="empty-state"><ListChecks /><p>{text}</p></div> }
function StatusBadge({ status }: { status: Status }) { return <span className={`status-badge status-${status.toLowerCase()}`}><span className="status-dot" />{statusLabels[status]}</span> }
function RiskBadge({ level }: { level: Risk['level'] }) { return <span className={`risk-badge risk-${level.toLowerCase()}`}>{levelLabels[level]}</span> }
function Bar({ value }: { value: number }) { return <div className="mini-progress" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${value}%` }} /></div> }
function External({ url, children }: { url?: string | null; children: ReactNode }) {
  if (!url || !/^https?:\/\//i.test(url)) return <span>{children}</span>
  return <a href={url} target="_blank" rel="noopener noreferrer" className="text-link">{children}<ExternalLink /></a>
}
function Info({ label, value }: { label: string; value: ReactNode }) { return <div className="info-item"><span>{label}</span><strong>{value || '—'}</strong></div> }
function PageHead({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return <div className="page-head"><div><span className="eyebrow">研发控制台</span><h1>{title}</h1><p>{subtitle}</p></div><div className="page-actions">{children}</div></div>
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try { onLogin(await api<User>('/auth/login', 'POST', { username: account, password })) }
    catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }
  return <section className="login-stage"><div className="login-grid">
    <div className="login-hero"><div className="login-brand-lockup"><BrandMark /><div><strong>NOMI</strong><span>项目管理系统 · NOMI</span></div></div><h1 className="hero-display"><span>目标向下。</span><span>事实向上。</span></h1></div>
    <div className="login-card-wrap"><div className="login-mobile-brand"><BrandMark /><h1>登录 NOMI</h1></div><div className="login-card"><div className="login-card-title"><h2>登录工作区</h2><p>使用你的项目账号继续</p></div>
      <form onSubmit={submit}><label className="field"><span>账号</span><div className="input-wrap"><UserRound /><input aria-label="账号" required autoComplete="username" autoFocus value={account} onChange={e => setAccount(e.target.value)} placeholder="输入账号" /></div></label>
        <label className="field"><span>密码</span><div className="input-wrap"><ShieldCheck /><input aria-label="密码" required type={visible ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="输入密码" /><button type="button" className="input-action" aria-label={visible ? '隐藏密码' : '显示密码'} onClick={() => setVisible(v => !v)}>{visible ? <EyeOff /> : <Eye />}</button></div></label>
        {error && <p className="login-error" role="alert">{error}</p>}
        <button className="btn primary login-submit" disabled={busy}>{busy ? <LoaderCircle className="spin" /> : <ArrowRight />}{busy ? '验证中' : '继续进入工作区'}</button></form></div>
      <div className="login-foot"><ShieldCheck />NOMI · 研发工作区</div></div></div></section>
}

function Transition({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 10 : 880)
    return () => clearTimeout(timer)
  }, [onDone])
  return <div className="transition-stage" role="status" aria-label="正在进入工作区"><BrandMark /></div>
}

type Actions = {
  open: (id: string) => void; navigate: (v: View) => void; sync: () => void
  summary: () => void
  mutate: (path: string, body?: unknown, method?: string) => Promise<boolean>
  busy: boolean; admin: boolean
}

function nextMonday() {
  const day = new Date(), weekday = day.getDay()
  day.setDate(day.getDate() + (weekday === 0 ? 1 : 8 - weekday))
  return day.toISOString().slice(0, 10)
}

function ProjectsPage({ items, currentId, admin, busy, onOpen, onCreate, createSignal = 0 }: {
  items: ProjectSummary[]; currentId: number | null; admin: boolean; busy: boolean
  onOpen: (id: number) => void; onCreate: (body: unknown) => Promise<boolean>; createSignal?: number
}) {
  const [creating, setCreating] = useState(false)
  useEffect(() => { if (createSignal) setCreating(true) }, [createSignal])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = Object.fromEntries(new FormData(event.currentTarget))
    const created = await onCreate({ name: String(values.name || '').trim(), start: values.start || undefined, weeks: Number(values.weeks || 6) })
    if (created) setCreating(false)
  }
  return <>
    <PageHead title="项目" subtitle={`${items.length} 个项目 · 本地项目在控制台内管理，真实项目从 Plane 导入`}>
      {admin && <Button variant="secondary" disabled={busy} onClick={() => setCreating(v => !v)}><Plus />新建项目</Button>}
    </PageHead>
    {creating && <form className="project-form requirement-form" onSubmit={submit}>
      <label>项目名称<input name="name" required maxLength={200} placeholder="例如：供应链中台二期" /></label>
      <label>开始日期<input name="start" type="date" required defaultValue={nextMonday()} /></label>
      <label>周期 / 周<input name="weeks" type="number" min={1} max={520} defaultValue={6} /></label>
      <div className="wide form-actions"><Button disabled={busy}><Save />创建项目</Button><Button type="button" variant="ghost" onClick={() => setCreating(false)}>取消</Button></div>
      <p className="wide form-hint">本地项目：需求、排期与看板直接在控制台内管理，不连接外部服务；之后仍可在系统设置导入 Plane 真实项目。</p>
    </form>}
    <section className="project-grid">
      {items.map(p => <article className={`project-card ${p.id === currentId ? 'current' : ''}`} key={p.id}>
        <div className="project-card-head"><span className={`mode-badge mode-${p.mode}`}>{modeLabels[p.mode]}</span><span className="project-week">Week {p.week} / {p.weeks}</span></div>
        <button className="project-card-title" onClick={() => onOpen(p.id)}><span>{p.name}</span><ArrowRight /></button>
        <Bar value={p.progress} />
        <div className="project-card-progress"><b>{p.progress}%</b><span>{p.startDate} 至 {p.endDate} · 剩 {p.remainingDays} 天</span></div>
        <div className="project-card-stats">
          <span><b>{p.requirements.total}</b>需求</span><span><b>{p.requirements.done}</b>已完成</span><span><b>{p.requirements.inProgress}</b>进行中</span>
          <span className={p.requirements.blocked ? 'danger-text' : ''}><b>{p.requirements.blocked}</b>阻塞</span>
          <span className={p.requirements.delayed ? 'warning-text' : ''}><b>{p.requirements.delayed}</b>延期</span>
        </div>
        <div className="project-card-foot">
          {p.riskSummary.HIGH > 0 && <span className="danger-text"><AlertTriangle />{p.riskSummary.HIGH} 高风险</span>}
          {p.members > 0 && <span><UserRound />{p.members} 成员</span>}
          {p.modules > 0 && <span><Columns3 />{p.modules} 模块</span>}
          <span className="project-sync">同步 {time(p.lastSync)}</span>
        </div>
      </article>)}
      {!items.length && <Empty text="暂无项目；点击「新建项目」创建本地项目，或在系统设置导入 Plane 项目" />}
    </section>
  </>
}
function Metric({ label, value, tone = '' }: { label: string; value: number | string; tone?: string }) {
  return <div className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong></div>
}

function Overview({ data, actions }: { data: Snapshot; actions: Actions }) {
  const d = data.dashboard, p = d.project, c = d.requirements, w = d.currentWeek
  const openRisks = data.risks.filter(r => r.status === 'OPEN')
  return <>
    <PageHead title={p.name} subtitle={`${p.stage} · Week ${p.week} / ${p.weeks} · ${modeLabels[p.mode]}`}>
      {actions.admin && <button className="btn secondary" disabled={actions.busy} onClick={actions.sync}><RefreshCw className={actions.busy ? 'spin' : ''} />{p.mode === 'demo' ? '刷新演示快照' : p.mode === 'local' ? '重新计算' : '同步数据'}</button>}
    </PageHead>
    <section className="project-strip"><div><Target /><span><b>当前阶段</b><strong>{p.stage} / Week {p.week}</strong></span></div><div><Clock3 /><span><b>计划周期</b><strong>{p.startDate} 至 {p.endDate}</strong></span></div><div className="strip-end"><b>剩余</b><strong>{p.remainingDays} 天</strong></div></section>
    <section className="progress-hero"><div className="progress-copy"><span>项目完成度</span><strong>{p.progress}<span>%</span></strong><small>需求优先级加权 · 实际研发状态</small></div><div className="progress-visual"><div className="progress-bar"><span style={{ width: `${p.progress}%` }} /></div><div className="progress-meta"><span>验收完成 {c.done} / {c.total}</span><span>{d.modules.length} 个模块 · {d.members.length} 位成员</span></div></div></section>
    <section className="metric-grid"><Metric label="总需求" value={c.total} /><Metric label="已完成" value={c.done} tone="success" /><Metric label="进行中" value={c.inProgress} /><Metric label="未开始" value={c.todo} /><Metric label="阻塞" value={c.blocked} tone="danger" /><Metric label="延期" value={c.delayed} tone="warning" /></section>
    <section className="weekly-strip"><b>本周</b><span>计划 <strong>{w.total}</strong></span><span>完成 <strong>{w.done}</strong></span><span>进行中 <strong>{w.inProgress}</strong></span><span>延期 <strong>{w.delayed}</strong></span><span>阻塞 <strong>{w.blocked}</strong></span><button className="text-link" onClick={() => actions.navigate('weekly')}>周计划 <ArrowRight /></button></section>
    <div className="dashboard-grid">
      <section className="surface"><div className="surface-head"><div><h2>模块进度</h2><p>{p.mode === 'demo' ? '演示模块' : p.mode === 'local' ? '本地模块' : 'Plane Modules'}</p></div><button className="text-link" onClick={() => actions.navigate('requirements')}>查看需求 <ArrowRight /></button></div><div className="module-list">{d.modules.map(m => <div className="module-row" key={m.name}><div className="module-label"><span>{m.name}</span><small>{m.done} / {m.total} 已验收</small></div><Bar value={m.progress} /><b>{m.progress}%</b></div>)}{!d.modules.length && <Empty text="暂无模块数据" />}</div></section>
      <section className="surface"><div className="surface-head"><div><h2>阶段进度</h2><p>{p.weeks} 周计划</p></div><span className="status-pill">Week {p.week} / {p.weeks}</span></div><WeekChart weeks={d.weeks} current={p.week} /><div className="week-list">{d.weeks.map(wk => <div className={`week-row ${wk.week === p.week ? 'current' : ''}`} key={wk.week}><span>Week {wk.week}</span><Bar value={wk.progress} /><b>{wk.progress}%</b><small>{wk.week === p.week ? '当前周' : `${wk.done}/${wk.total}`}</small></div>)}</div></section>
    </div>
    <div className="dashboard-grid lower">
      <section className="surface"><div className="surface-head"><div><h2>优先风险</h2><p>高 {d.riskSummary.HIGH} · 中 {d.riskSummary.MEDIUM} · 低 {d.riskSummary.LOW}</p></div><button className="text-link" onClick={() => actions.navigate('risks')}>查看全部 <ArrowRight /></button></div><div className="risk-list">{openRisks.slice(0, 5).map(r => <button className="risk-row" key={r.id} onClick={() => actions.open(r.requirementId)}><RiskBadge level={r.level} /><div><strong>{r.requirementId} · {r.title}</strong><small>{r.source} · {r.owner}</small></div><ArrowRight /></button>)}{!openRisks.length && <Empty text="暂无待处理风险" />}</div></section>
      <section className="surface ai-summary"><div className="surface-head"><div><h2>{data.aiSummary ? 'AI 项目摘要' : '项目事实摘要'}</h2><p>{data.aiSummary ? `${time(data.aiSummary.createdAt)} · 辅助判断${data.aiSummary.stale ? ' · 数据已有变化' : ''}` : '当前快照 · 非 LLM 分析'}</p></div>{actions.admin && p.mode !== 'demo' ? <Button variant="secondary" disabled={actions.busy} onClick={actions.summary}><Sparkles />生成摘要</Button> : <FileSummaryIcon />}</div>
        {data.aiSummary ? <p>{data.aiSummary.summary}</p> : <p>项目完成度 <b>{p.progress}%</b>，{c.done} 项需求已验收。本周计划 {w.total} 项，已完成 {w.done} 项。当前有 {c.delayed} 项延期、{c.blocked} 项阻塞，需要优先处理 {d.riskSummary.HIGH} 条高风险记录。</p>}
        <div className="summary-callout"><strong>优先关注</strong>{(data.aiSummary?.priorities || [...new Set(openRisks.map(r => r.requirementId))].slice(0, 3)).map(id => <button className="text-link" key={id} onClick={() => actions.open(id)}>{id}</button>)}</div></section>
    </div>
    <section className="surface member-section"><div className="surface-head"><div><h2>成员工作量</h2><p>项目任务分布</p></div></div><div className="members">{d.members.map(m => <div key={m.name}><span className="avatar">{m.name[0]}</span><span>{m.name}</span><strong>{m.done} / {m.total}</strong><small>{m.delayed} 项延期</small></div>)}</div></section>
  </>
}
function FileSummaryIcon() { return <ListChecks /> }

function PriorityBars({ priority }: { priority: Requirement['priority'] }) {
  return <span className={`priority-bars pb-${priority.toLowerCase()}`} title={priority}><i /><i /><i /></span>
}

const priorityLabels: Record<string, string> = { P0: 'P0 · 紧急', P1: 'P1 · 高', P2: 'P2 · 中' }
const groupLabels: Record<string, string> = { status: '状态', priority: '优先级', owner: '负责人', module: '模块', week: '周期' }

function RequirementsPage({ data, actions }: { data: Snapshot; actions: Actions }) {
  const [query, setQuery] = useState(''), [status, setStatus] = useState(''), [module, setModule] = useState('')
  const [display, setDisplay] = useState<'table' | 'board'>('table')
  const [groupBy, setGroupBy] = useState<'status' | 'priority' | 'owner' | 'module' | 'week'>('status')
  const [creating, setCreating] = useState(false), [presetStatus, setPresetStatus] = useState<Status>('TODO')
  const [dragging, setDragging] = useState<string | null>(null), [dropTarget, setDropTarget] = useState<string | null>(null)
  const [quickAdd, setQuickAdd] = useState<string | null>(null), [quickTitle, setQuickTitle] = useState('')
  const mode = data.dashboard.project.mode
  const editable = actions.admin && mode !== 'demo'
  const local = mode === 'local'
  const rows = data.requirements.filter(r => `${r.id} ${r.title} ${r.owner} ${r.module}`.toLowerCase().includes(query.toLowerCase()) && (!status || r.status === status) && (!module || r.module === module))
  const columns: { key: string; label: string; status?: Status }[] =
    groupBy === 'status' ? boardColumns.map(key => ({ key, label: statusLabels[key], status: key }))
      : groupBy === 'priority' ? ['P0', 'P1', 'P2'].map(key => ({ key, label: priorityLabels[key] }))
        : groupBy === 'owner' ? [...new Set(data.requirements.map(r => r.owner))].sort().map(key => ({ key, label: key }))
          : groupBy === 'module' ? [...new Set(data.requirements.map(r => r.module))].sort().map(key => ({ key, label: key }))
            : [...new Set(data.requirements.map(r => r.week))].sort((a, b) => a - b).map(week => ({ key: String(week), label: `Week ${week}` }))
  const groupValue = (r: Requirement) => groupBy === 'week' ? String(r.week) : groupBy === 'status' ? r.status : groupBy === 'priority' ? r.priority : groupBy === 'owner' ? r.owner : r.module
  const openCreate = (preset: Status) => { setPresetStatus(preset); setCreating(true) }
  function drop(target: string) {
    const item = data.requirements.find(r => r.id === dragging)
    setDragging(null); setDropTarget(null)
    if (!editable || !item || groupValue(item) === target) return
    void actions.mutate(`/requirements/${item.id}`, groupBy === 'week' ? { week: Number(target) } : { [groupBy]: target }, 'PATCH')
  }
  async function submitQuickAdd(columnKey: string) {
    const title = quickTitle.trim()
    setQuickTitle(''); setQuickAdd(null)
    if (!title) return
    const body: Record<string, unknown> = { title }
    if (groupBy === 'week') body.week = Number(columnKey)
    else body[groupBy] = columnKey
    await actions.mutate('/requirements', body)
  }
  return <><PageHead title="需求" subtitle={`${data.requirements.length} 条需求 · ${mode === 'demo' ? '演示快照' : mode === 'local' ? '本地管理' : 'Plane 同步缓存'}`}>
    <div className="page-actions">
      <div className="segmented" role="group" aria-label="需求视图">
        <button className={display === 'table' ? 'active' : ''} aria-pressed={display === 'table'} onClick={() => setDisplay('table')}><List />表格</button>
        <button className={display === 'board' ? 'active' : ''} aria-pressed={display === 'board'} onClick={() => setDisplay('board')}><Columns3 />看板</button>
      </div>
      {editable && <Button variant="secondary" disabled={actions.busy} onClick={() => openCreate('TODO')}><Plus />新增需求</Button>}
      {actions.admin && <button className="btn secondary" disabled={actions.busy} onClick={actions.sync}><RefreshCw />{mode === 'demo' ? '刷新' : mode === 'local' ? '重新计算' : '同步'}</button>}
    </div></PageHead>
    {creating && <form className="requirement-form" onSubmit={async event => {
      event.preventDefault()
      const values = Object.fromEntries(new FormData(event.currentTarget))
      const { week, module, ...fields } = values
      if (await actions.mutate('/requirements', { ...fields, ...(week ? { week: Number(week) } : {}), ...(module ? { module } : {}), criteria: String(values.criteria || '').split(/\r?\n/).map(v => v.trim()).filter(Boolean) })) setCreating(false)
    }}>
      <label>需求标题<input name="title" required maxLength={500} /></label>
      <label>模块{local
        ? <input name="module" list="module-options" placeholder="未分组" maxLength={200} />
        : <select name="module"><option value="">未分组</option>{data.management?.modules.map(name => <option key={name}>{name}</option>)}</select>}</label>
      <label>负责人{local
        ? <input name="owner" list="owner-options" placeholder="未分配" maxLength={200} />
        : <select name="owner"><option value="">未分配</option>{data.management?.owners.map(name => <option key={name}>{name}</option>)}</select>}</label>
      <label>优先级<select name="priority"><option>P2</option><option>P1</option><option>P0</option></select></label>
      <label>初始状态<select name="status" defaultValue={presetStatus}>{Object.entries(statusLabels).map(([key, text]) => <option value={key} key={key}>{text}</option>)}</select></label>
      <label>所属周<select name="week"><option value="">未安排周期</option>{data.management?.weeks.map(w => <option value={w.week} key={w.week}>{w.name}</option>)}</select></label>
      <label>计划完成<input name="due" type="date" /></label>
      <label className="wide">需求描述<textarea name="description" rows={3} /></label>
      <label className="wide">验收标准<textarea name="criteria" rows={3} /></label>
      <div className="wide form-actions"><Button disabled={actions.busy}><Save />创建需求</Button><Button type="button" variant="ghost" onClick={() => setCreating(false)}>取消</Button></div>
      <datalist id="module-options">{data.management?.modules.map(name => <option key={name} value={name} />)}</datalist>
      <datalist id="owner-options">{data.management?.owners.map(name => <option key={name} value={name} />)}</datalist>
    </form>}
    <div className="toolbar"><div className="search-box"><Search /><input aria-label="搜索需求" placeholder="搜索编号、需求或负责人" value={query} onChange={e => setQuery(e.target.value)} /></div>
      {display === 'board' && <select aria-label="看板分组" value={groupBy} onChange={e => setGroupBy(e.target.value as typeof groupBy)}><option value="status">按状态分组</option><option value="priority">按优先级分组</option><option value="owner">按负责人分组</option><option value="module">按模块分组</option><option value="week">按周期分组</option></select>}
      {display === 'table' && <select aria-label="需求状态" value={status} onChange={e => setStatus(e.target.value)}><option value="">全部状态</option>{Object.entries(statusLabels).map(([key, text]) => <option value={key} key={key}>{text}</option>)}</select>}
      <select aria-label="所属模块" value={module} onChange={e => setModule(e.target.value)}><option value="">全部模块</option>{data.dashboard.modules.map(m => <option key={m.name}>{m.name}</option>)}</select></div>
    {display === 'table'
      ? <section className="surface table-surface"><div className="table-wrap"><div className="data-table req-table"><div className="table-row table-head"><span>需求</span><span>模块</span><span>负责人</span><span>优先级</span><span>状态 / 周</span><span>计划完成</span><span>AI / 代码</span></div>
        {rows.map(r => <button className="table-row" key={r.id} onClick={() => actions.open(r.id)}><span><strong>{r.id}</strong><small>{r.title}</small></span><span>{r.module}</span><span>{r.owner}</span><span className={`priority priority-${r.priority.toLowerCase()}`}>{r.priority}</span><span><StatusBadge status={r.status} /><small>Week {r.week}</small></span><span className={r.delayed ? 'danger-text' : ''}>{r.due || '未排期'}{r.delayed && <small>已延期</small>}</span><span className="ai-cell"><b>{r.inspection ? r.inspection.stale ? '核验已过期' : `${r.inspection.implementation_score}%` : '待核验'}</b><small>{r.git ? '已关联代码' : '未关联'}</small></span></button>)}
      </div></div>{!rows.length && <Empty text={data.requirements.length ? '没有匹配的需求' : '暂无需求，等待 Plane 同步'} />}</section>
      : <div className="board-wrap">
        {!editable && <p className="notice board-notice">{actions.admin ? '演示项目为只读快照；新建本地项目或导入 Plane 项目后，即可拖拽卡片调整。' : '当前账号为成员，仅管理员可调整需求。'}</p>}
        <div className="board-scroll"><div className="req-board">
          {columns.map(col => { const items = rows.filter(r => groupValue(r) === col.key); return <div
            className={`board-column ${dropTarget === col.key ? 'drop-target' : ''}`} key={col.key}
            aria-label={`看板列 ${col.label}`}
            onDragOver={event => { if (editable) { event.preventDefault(); setDropTarget(col.key) } }}
            onDragLeave={() => setDropTarget(current => current === col.key ? null : current)}
            onDrop={event => { event.preventDefault(); drop(col.key) }}>
            <div className="board-column-head">
              {col.status ? <StatusBadge status={col.status} /> : <span className="board-group-label">{col.label}</span>}<b>{items.length}</b>
            </div>
            {items.map(r => <article className={`kanban-card board-card ${dragging === r.id ? 'dragging' : ''}`} key={r.id}
              draggable={editable}
              onDragStart={event => { setDragging(r.id); event.dataTransfer.setData('text/plain', r.id); event.dataTransfer.effectAllowed = 'move' }}
              onDragEnd={() => { setDragging(null); setDropTarget(null) }}
              onClick={() => actions.open(r.id)}>
              <div><PriorityBars priority={r.priority} /><strong>{r.id}</strong>{groupBy !== 'status' && <StatusBadge status={r.status} />}</div>
              <p>{r.title}</p>
              <div className="board-card-foot">
                <span className="card-owner">{r.owner !== '未分配' && <span className="avatar">{r.owner[0]}</span>}{r.owner}</span>
                {r.due && <small className={r.delayed ? 'danger-text' : ''}>{r.delayed ? '已延期 · ' : ''}{r.due.slice(5)}</small>}
                {groupBy === 'status' && <small>{r.inspection && !r.inspection.stale ? `AI ${r.inspection.implementation_score}%` : r.git?.mr ? '已关联代码' : r.module}</small>}
              </div>
            </article>)}
            {!items.length && <p className="board-empty">{editable ? '拖拽需求到此列' : '暂无需求'}</p>}
            {editable && (quickAdd === col.key
              ? <form className="quick-add" onSubmit={event => { event.preventDefault(); void submitQuickAdd(col.key) }}>
                <input autoFocus aria-label={`在「${col.label}」新增需求标题`} value={quickTitle} maxLength={500} placeholder="需求标题，回车创建"
                  onChange={event => setQuickTitle(event.target.value)}
                  onKeyDown={event => { if (event.key === 'Escape') { setQuickAdd(null); setQuickTitle('') } }}
                  onBlur={() => { if (quickTitle.trim()) void submitQuickAdd(col.key); else setQuickAdd(null) }} />
              </form>
              : <button className="quick-add-trigger" disabled={actions.busy} onClick={() => { setQuickAdd(col.key); setQuickTitle('') }}><Plus />新建</button>)}
          </div> })}
        </div></div>
      </div>}
  </>
}

function Detail({ item, data, back, mutate, admin, busy }: { item: Requirement; data: Snapshot; back: () => void; mutate: (path: string, body?: unknown, method?: string) => Promise<boolean>; admin: boolean; busy: boolean }) {
  const [iid, setIid] = useState(''), [branch, setBranch] = useState(item.git?.branch || `feat/${item.id.toLowerCase()}-development`)
  const [editing, setEditing] = useState(false), [edit, setEdit] = useState({ title: item.title, description: item.description, owner: item.owner === '未分配' ? '' : item.owner, priority: item.priority, status: item.status, module: item.module, week: String(item.week), start: item.start || '', due: item.due || '', criteria: item.criteria.join('\n') })
  const a = item.inspection, g = item.git
  const mode = data.dashboard.project.mode, demo = mode === 'demo', local = mode === 'local'
  const setValue = (key: string, value: string) => setEdit(current => ({ ...current, [key]: value }))
  const ownerOptions = [...new Set([item.owner === '未分配' ? '' : item.owner, ...data.management?.owners || []])].filter(Boolean)
  const moduleOptions = [...new Set([item.module, ...data.management?.modules || []])]
  const stateOptions = [...new Set([item.status, ...data.management?.statuses || []])]
  const weekOptions = data.management?.weeks || []
  return <div className="detail-view"><button className="back-link" onClick={back}><ArrowLeft />返回需求列表</button>
    <div className="detail-head"><div><span className="eyebrow">{item.id} · {item.module}</span><h1>{item.title}</h1><p className="description">{item.description || '暂无描述'}</p></div><div><StatusBadge status={item.status} />{item.delayed && <span className="status-badge status-blocked">已延期</span>}</div></div>
    <div className="detail-grid"><div className="detail-main"><section className="surface"><div className="surface-head"><div><h2>需求信息</h2></div><div className="surface-head-actions">{admin && !demo && <Button variant="secondary" disabled={busy} onClick={() => { setEdit({ title: item.title, description: item.description, owner: item.owner === '未分配' ? '' : item.owner, priority: item.priority, status: item.status, module: item.module, week: String(item.week), start: item.start || '', due: item.due || '', criteria: item.criteria.join('\n') }); setEditing(v => !v) }}>{editing ? <X /> : <Save />}{editing ? '取消编辑' : '编辑需求'}</Button>}<External url={item.planeUrl}>{demo ? '演示需求' : '源记录'}</External></div></div>
      {editing ? <form className="edit-requirement-form" onSubmit={async event => {
        event.preventDefault()
        const next = { ...edit, owner: edit.owner || '未分配', start: edit.start || null, due: edit.due || null, week: Number(edit.week), criteria: edit.criteria.split(/\r?\n/).map(v => v.trim()).filter(Boolean) }
        const body = Object.fromEntries(Object.entries(next).filter(([key, value]) => JSON.stringify(item[key as keyof Requirement]) !== JSON.stringify(value)))
        if (!Object.keys(body).length || await mutate(`/requirements/${item.id}`, body, 'PATCH')) setEditing(false)
      }}>
        <label>标题<input value={edit.title} onChange={e => setValue('title', e.target.value)} required /></label>
        <label>负责人{demo ? <span className="edit-static">{item.owner}</span> : local
          ? <input value={edit.owner} onChange={e => setValue('owner', e.target.value)} list="detail-owner-options" maxLength={200} />
          : <select value={edit.owner} onChange={e => setValue('owner', e.target.value)}><option value="">未分配</option>{ownerOptions.map(name => <option key={name}>{name}</option>)}</select>}</label>
        <label>模块{demo ? <span className="edit-static">{item.module}</span> : local
          ? <input value={edit.module} onChange={e => setValue('module', e.target.value)} list="detail-module-options" maxLength={200} />
          : <select value={edit.module} onChange={e => setValue('module', e.target.value)}>{moduleOptions.map(name => <option key={name}>{name}</option>)}</select>}</label>
        <label>优先级<select value={edit.priority} onChange={e => setValue('priority', e.target.value)}><option>P0</option><option>P1</option><option>P2</option></select></label>
        <label>状态<select value={edit.status} onChange={e => setValue('status', e.target.value)}>{stateOptions.map(key => <option value={key} key={key}>{statusLabels[key]}</option>)}</select></label>
        <label>所属周<select value={edit.week} onChange={e => setValue('week', e.target.value)}>{!weekOptions.some(w => w.week === item.week) && <option value={item.week}>Week {item.week}</option>}{weekOptions.map(w => <option value={w.week} key={w.week}>{w.name}</option>)}</select></label>
        <label>计划开始<input type="date" value={edit.start} onChange={e => setValue('start', e.target.value)} /></label>
        <label>计划完成<input type="date" value={edit.due} onChange={e => setValue('due', e.target.value)} /></label>
        <label className="wide">描述<textarea rows={4} value={edit.description} onChange={e => setValue('description', e.target.value)} /></label>
        <label className="wide">验收标准<textarea rows={4} value={edit.criteria} onChange={e => setValue('criteria', e.target.value)} /></label>
        <datalist id="detail-owner-options">{ownerOptions.map(name => <option key={name} value={name} />)}</datalist>
        <datalist id="detail-module-options">{moduleOptions.map(name => <option key={name} value={name} />)}</datalist>
        <div className="wide form-actions"><Button disabled={busy}><Save />保存需求</Button></div>
      </form> : <div className="info-grid"><Info label="负责人" value={item.owner} /><Info label="优先级" value={item.priority} /><Info label="所属周" value={`Week ${item.week}`} /><Info label="计划开始" value={item.start} /><Info label="计划完成" value={item.due} /><Info label="研发进度" value={`${item.progress}%`} /></div>}
      <div className="criteria"><h3>Acceptance Criteria</h3>{item.criteria.map((c, i) => <div key={i}><span className="subtle">{i + 1}.</span>{c}</div>)}{!item.criteria.length && <p className="subtle">尚未定义验收标准</p>}</div></section>
      <section className="surface"><div className="surface-head"><div><h2>Git 关联</h2><p>{g ? `${g.manual ? '人工绑定' : '自动关联'} · ${demo ? '演示证据' : g.source}` : '未找到关联代码'}</p></div><GitBranch /></div>
        {g ? <><div className="git-grid"><Info label="Repository" value={g.repository} /><Info label="Branch" value={g.branch} /><Info label="Merge Request" value={g.mr ? <External url={g.url}>!{g.mr} · {g.mrState}</External> : '暂无 MR'} /><Info label="Pipeline" value={g.pipeline} /><Info label="最近提交人" value={g.author} /><Info label="最后更新" value={time(g.updatedAt)} /></div>
          <div className="commit-list">{g.commits.slice(0, 8).map(c => <div key={c.sha}><code>{c.sha.slice(0, 10)}</code><span>{c.message}</span><small>{c.author}</small></div>)}</div></> : <Empty text="在分支、Commit 或 MR 中引用需求编号后同步" />}
        {admin && mode === 'live' && <><form className="binding-form" onSubmit={e => { e.preventDefault(); void mutate(`/requirements/${item.id}/git-link`, { mr: Number(iid) }) }}><label>MR 编号 <input aria-label="MR 编号" type="number" min={1} required value={iid} onChange={e => setIid(e.target.value)} /></label><button className="btn secondary" disabled={busy}><Link2 />绑定 MR</button></form>{!g && <form className="binding-form" onSubmit={e => { e.preventDefault(); void mutate(`/requirements/${item.id}/branch`, { name: branch }) }}><label>开发分支 <input aria-label="开发分支" value={branch} onChange={e => setBranch(e.target.value)} required /></label><button className="btn secondary" disabled={busy}><GitBranch />创建分支</button></form>}{g && !g.mr && <form className="binding-form" onSubmit={e => { e.preventDefault(); void mutate(`/requirements/${item.id}/merge-request`, { branch: g.branch }) }}><span>{g.branch}</span><button className="btn secondary" disabled={busy}><Link2 />创建 MR</button></form>}</>}
        {local && <p className="notice">本地项目暂未接入 GitLab：导入 Plane 项目并关联仓库后，可在这里创建分支、MR 并运行 AI 核验。</p>}
      </section></div>
      <aside className="detail-side"><section className="surface inspection"><div className="surface-head"><div><h2>AI 代码核验</h2><p>{a ? `${a.source === 'demo' ? '演示结果' : 'LLM 核验'} · ${time(a.createdAt)}` : '尚无核验结果'}</p></div><Sparkles /></div>
        {a ? <>{a.stale && <p className="notice warning">代码已更新，本次核验已过期，不参与当前进度计算。</p>}
          <div className="score-ring" style={{ '--score': `${a.implementation_score}%` } as CSSProperties}><strong>{a.implementation_score}<span>%</span></strong><small>需求实现度</small></div>
          <div className="inspection-state"><span className={`state-icon ${a.status === 'IMPLEMENTED' ? 'ok' : 'warn'}`}><ShieldCheck /></span><div><strong>{analysisStatuses[a.status]}</strong><small>{a.summary}</small></div></div>
          <div className="evidence-list">{a.acceptance_criteria.map((c, i) => <div key={i} className={c.status === 'IMPLEMENTED' ? '' : 'warn'}>{c.status === 'IMPLEMENTED' ? <CheckCircle2 /> : <AlertTriangle />}<span>{c.criterion}<small>{analysisStatuses[c.status]}</small>{c.evidence.map(e => <code key={e}>{e}</code>)}</span></div>)}</div>
          <div className="test-summary"><strong>测试 · {analysisStatuses[a.tests.status]}</strong><p>{a.tests.summary}</p>{a.context_truncated && <p>部分代码上下文已截断，结论仅覆盖本次读取范围。</p>}</div>
        </> : <Empty text="关联 MR 并配置模型后可运行核验" />}
        {admin && <button className="btn primary inspect-button" disabled={busy || mode !== 'live' || !g?.mr || !item.criteria.length} title={mode !== 'live' ? '演示与本地项目不调用真实模型' : '将关联 MR 的有限代码上下文发送到已配置的模型'} onClick={() => void mutate(`/requirements/${item.id}/inspect`)}><Sparkles />{busy ? '处理中' : '重新核验'}</button>}
      </section><section className="surface"><div className="surface-head"><h2>关联风险</h2></div>{data.risks.filter(r => r.requirementId === item.id && r.status !== 'RESOLVED').map(r => <div className="linked-risk" key={r.id}><RiskBadge level={r.level} /><span>{r.title}</span></div>)}{!data.risks.some(r => r.requirementId === item.id && r.status !== 'RESOLVED') && <Empty text="暂无关联风险" />}</section></aside></div>
  </div>
}

function Weekly({ data, open }: { data: Snapshot; open: (id: string) => void }) {
  const cycles = data.catalog?.cycles || data.dashboard.weeks.map(w => ({ ...w, name: `Week ${w.week}`, active: w.week === data.dashboard.project.week }))
  const [week, setWeek] = useState(data.dashboard.project.week), [mode, setMode] = useState<'board' | 'timeline'>('board')
  const rows = data.requirements.filter(r => r.week === week), selected = cycles.find(w => w.week === week)!
  const groups: { title: string; statuses: Status[] }[] = [{ title: '未开始', statuses: ['TODO'] }, { title: '开发中', statuses: ['IN_PROGRESS'] }, { title: '检查 / 测试', statuses: ['REVIEW', 'TESTING'] }, { title: '已完成', statuses: ['DONE'] }, { title: '阻塞', statuses: ['BLOCKED'] }]
  return <><PageHead title="周期" subtitle={`${cycles.length} 个周期 · ${selected.start} 至 ${selected.end}`}><div className="segmented" role="group" aria-label="周期视图"><button className={mode === 'board' ? 'active' : ''} aria-pressed={mode === 'board'} onClick={() => setMode('board')}><Columns3 />看板</button><button className={mode === 'timeline' ? 'active' : ''} aria-pressed={mode === 'timeline'} onClick={() => setMode('timeline')}><List />时间轴</button></div></PageHead>
    <div className="cycle-strip">{cycles.map(c => <button className={`cycle-card ${c.week === week ? 'selected' : ''} ${c.active ? 'active' : ''}`} key={c.week} onClick={() => setWeek(c.week)}>
      <div className="cycle-card-head"><b>{c.name}</b>{c.active && <span className="cycle-live">进行中</span>}</div>
      <small>{c.start.slice(5)} 至 {c.end.slice(5)}</small>
      <Bar value={c.progress} />
      <span className="cycle-meta"><b>{c.progress}%</b><small>{c.done} / {c.total}</small></span>
    </button>)}</div>
    <div className="weekly-strip"><span>计划 {selected.total}</span><span>完成 {selected.done}</span><span>进行中 {selected.inProgress}</span><span>延期 {selected.delayed}</span><span>阻塞 {selected.blocked}</span></div>
    {mode === 'board' ? <div className="kanban">{groups.map(group => { const items = rows.filter(r => group.statuses.includes(r.status)); return <div className="kanban-column" key={group.title}><div className="kanban-title"><span>{group.title}</span><b>{items.length}</b></div>{items.map(r => <button className="kanban-card" key={r.id} onClick={() => open(r.id)}><div><strong>{r.id}</strong><span className={`priority priority-${r.priority.toLowerCase()}`}>{r.priority}</span></div><p>{r.title}</p><small>{r.owner} · {r.due || '未排期'}</small>{r.delayed && <small className="danger-text">已延期</small>}</button>)}</div> })}</div>
      : <section className="surface timeline">{[...rows].sort((a, b) => (a.due || '9999').localeCompare(b.due || '9999')).map(r => <button key={r.id} onClick={() => open(r.id)}><span>{r.start || '待定'}<small>至 {r.due || '待定'}</small></span><strong>{r.id} · {r.title}</strong><StatusBadge status={r.status} /><span>{r.owner}</span></button>)}{!rows.length && <Empty text="该周期尚无计划需求" />}</section>}
  </>
}

function ModulesPage({ data, open }: { data: Snapshot; open: (id: string) => void }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const modules = data.catalog?.modules || []
  return <><PageHead title="模块" subtitle={`${modules.length} 个模块 · 需求按模块分组统计`} />
    <section className="module-card-grid">
      {modules.map(m => <article className={`module-card ${expanded === m.name ? 'expanded' : ''}`} key={m.name}>
        <button className="module-card-head" onClick={() => setExpanded(current => current === m.name ? null : m.name)}>
          <div><h2>{m.name}</h2><small>{m.description || '暂无描述'}</small></div><ChevronDown className={expanded === m.name ? 'flip' : ''} />
        </button>
        <Bar value={m.progress} />
        <div className="project-card-stats">
          <span><b>{m.total}</b>需求</span><span><b>{m.done}</b>已完成</span><span><b>{m.inProgress}</b>进行中</span>
          <span className={m.blocked ? 'danger-text' : ''}><b>{m.blocked}</b>阻塞</span>
          <span className={m.delayed ? 'warning-text' : ''}><b>{m.delayed}</b>延期</span>
        </div>
        {expanded === m.name && <div className="module-issues">{data.requirements.filter(r => r.module === m.name).map(r => <button key={r.id} onClick={() => open(r.id)}><strong>{r.id}</strong><span>{r.title}</span><StatusBadge status={r.status} /></button>)}{!data.requirements.some(r => r.module === m.name) && <Empty text="该模块暂无需求" />}</div>}
      </article>)}
      {!modules.length && <Empty text="暂无模块；在需求中填写模块后自动生成" />}
    </section>
  </>
}

function MembersPage({ data, open }: { data: Snapshot; open: (id: string) => void }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const members = data.catalog?.members || []
  return <><PageHead title="成员" subtitle={`${members.length} 位成员 · 工作量从同一数据集计算`} />
    <section className="member-card-grid">
      {members.map(m => <article className={`member-card ${expanded === m.name ? 'expanded' : ''}`} key={m.name}>
        <button className="module-card-head" onClick={() => setExpanded(current => current === m.name ? null : m.name)}>
          <div className="member-title"><span className="avatar">{m.name[0]}</span><div><h2>{m.name}</h2><small>{m.role}</small></div></div>
          <ChevronDown className={expanded === m.name ? 'flip' : ''} />
        </button>
        <Bar value={m.progress} />
        <div className="project-card-stats">
          <span><b>{m.total}</b>负责</span><span><b>{m.done}</b>已完成</span><span><b>{m.inProgress}</b>进行中</span>
          <span className={m.delayed ? 'warning-text' : ''}><b>{m.delayed}</b>延期</span>
        </div>
        {expanded === m.name && <div className="module-issues">{data.requirements.filter(r => r.owner === m.name).map(r => <button key={r.id} onClick={() => open(r.id)}><strong>{r.id}</strong><span>{r.title}</span><StatusBadge status={r.status} /></button>)}{!data.requirements.some(r => r.owner === m.name) && <Empty text="该成员暂无负责的需求" />}</div>}
      </article>)}
      {!members.length && <Empty text="暂无成员数据" />}
    </section>
  </>
}

function RisksPage({ data, actions, acknowledge, scan, add }: { data: Snapshot; actions: Actions; acknowledge: (id: number, status: string) => void; scan: () => void; add: (body: unknown) => Promise<boolean> }) {
  const [level, setLevel] = useState(''), [status, setStatus] = useState('OPEN')
  const [creating, setCreating] = useState(false)
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = Object.fromEntries(new FormData(event.currentTarget))
    if (await add(body)) setCreating(false)
  }
  const rows = data.risks.filter(r => (!level || r.level === level) && (!status || r.status === status))
  const summary = data.dashboard.riskSummary
  return <><PageHead title="风险" subtitle="需求状态、截止日期、代码和核验证据">{actions.admin && <><Button variant="secondary" disabled={actions.busy || !data.requirements.length} onClick={() => setCreating(v => !v)}><Plus />新增风险</Button><button className="btn secondary" disabled={actions.busy} onClick={scan}><RefreshCw />重新扫描</button></>}</PageHead>
    {creating && <form className="manual-risk-form" onSubmit={create}><label>关联需求<select name="requirementId" required>{data.requirements.map(r => <option key={r.id} value={r.id}>{r.id} · {r.title}</option>)}</select></label><label>风险等级<select name="level"><option value="HIGH">高风险</option><option value="MEDIUM">中风险</option><option value="LOW">低风险</option></select></label><label>风险名称<input name="title" required maxLength={500} /></label><label>建议动作<input name="action" required maxLength={2000} /></label><div><Button disabled={actions.busy}><Check />保存风险</Button><Button type="button" variant="ghost" onClick={() => setCreating(false)}>取消</Button></div></form>}
    <div className="risk-summary">{Object.entries(levelLabels).map(([key, name]) => <div key={key}><strong>{summary[key as keyof typeof summary]}</strong><span>{name}</span></div>)}<div><strong>{data.risks.filter(r => r.status === 'ACKNOWLEDGED').length}</strong><span>已确认</span></div></div>
    <div className="toolbar"><select aria-label="风险等级" value={level} onChange={e => setLevel(e.target.value)}><option value="">全部等级</option>{Object.entries(levelLabels).map(([k, v]) => <option value={k} key={k}>{v}</option>)}</select><select aria-label="风险状态" value={status} onChange={e => setStatus(e.target.value)}><option value="">全部状态</option>{Object.entries(riskStatuses).map(([k, v]) => <option value={k} key={k}>{v}</option>)}</select></div>
    <section className="surface"><div className="risk-table-list"><div className="risk-table-row head"><span>等级</span><span>风险名称</span><span>来源</span><span>关联需求</span><span>负责人</span><span>建议动作</span><span>状态</span></div>
      {rows.map(r => <div className="risk-table-row" key={r.id}><RiskBadge level={r.level} /><span><strong>{r.title}</strong><small>{time(r.createdAt)}</small></span><span>{r.source}</span><button className="text-link" onClick={() => actions.open(r.requirementId)}>{r.requirementId}</button><span>{r.owner}</span><span>{r.action}</span>
        {actions.admin && r.status !== 'RESOLVED' ? <div className="risk-row-actions"><button className="btn secondary" disabled={actions.busy} onClick={() => acknowledge(r.id, r.status === 'OPEN' ? 'ACKNOWLEDGED' : 'OPEN')}>{r.status === 'OPEN' ? <Check /> : <RefreshCw />}{r.status === 'OPEN' ? '确认' : '重开'}</button>{r.source === '人工' && <button className="header-icon" title="关闭人工风险" disabled={actions.busy} onClick={() => acknowledge(r.id, 'RESOLVED')}><X /></button>}</div> : <span>{riskStatuses[r.status]}</span>}</div>)}
    </div>{!rows.length && <Empty text="暂无匹配的风险" />}</section></>
}

function SettingsPage({ projectId, onConnected, admin, logs }: { projectId: number | null; onConnected: () => Promise<void>; admin: boolean; logs: Snapshot['logs'] }) {
  const [values, setValues] = useState<SettingsData | null>(null), [secrets, setSecrets] = useState<Record<string, string>>({})
  const [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!admin) return
    const controller = new AbortController()
    api<SettingsData>('/settings', 'GET', undefined, controller.signal).then(setValues).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [admin])
  if (!admin) return <><PageHead title="系统设置" subtitle="仅管理员可修改连接配置" /><Empty text="当前账号为项目成员" /></>
  if (!values) return error ? <p role="alert" className="notice error">{error}</p> : <Loading text="读取系统设置" />
  const change = (key: keyof SettingsData, value: string | number | boolean) => setValues(v => v && { ...v, [key]: value })
  async function action(kind: 'save' | 'plane' | 'git') {
    setBusy(true); setError(''); setMessage('')
    try {
      const body = Object.fromEntries(Object.entries(values!).filter(([key]) => !key.endsWith('Configured')))
      const saved = await api<SettingsData>('/settings', 'PATCH', { ...body, ...secrets })
      setValues(saved); setSecrets({})
      if (kind === 'plane') { await api('/connections/plane', 'POST'); await onConnected() }
      if (kind === 'git') { await api(`/connections/git?project=${projectId}`, 'POST'); await onConnected() }
      if (kind === 'save') await onConnected()
      setMessage(kind === 'save' ? '设置已保存' : '同步完成')
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }
  const field = (label: string, key: keyof SettingsData, type = 'text', min?: number, max?: number) => <label className="setting-field" key={key}><span>{label}</span><input aria-label={label} type={type} min={min} max={max} step={key === 'temperature' ? .1 : undefined} value={String(values[key])} onChange={e => change(key, type === 'number' ? Number(e.target.value) : e.target.value)} /></label>
  const secret = (label: string, key: string, configured: boolean) => <label className="setting-field"><span>{label}</span><input type="password" aria-label={label} autoComplete="new-password" value={secrets[key] ?? ''} placeholder={configured ? '已配置，留空不修改' : '未配置'} onChange={e => setSecrets(s => { const next = { ...s }; if (e.target.value) next[key] = e.target.value; else delete next[key]; return next })} /></label>
  return <><PageHead title="系统设置" subtitle="Plane · GitLab · AI Inspector">{<button className="btn primary" disabled={busy} onClick={() => void action('save')}><Save />保存设置</button>}</PageHead>
    {error && <p role="alert" className="notice error">{error}</p>}{message && <p role="status" className="notice success">{message}</p>}
    <div className="settings-grid">
      <section className="surface setting-card"><div className="setting-head"><Target /><div><h2>Plane</h2><p>{values.planeTokenConfigured ? '已保存凭据 · 连通性以同步结果为准' : '尚未配置'}</p></div></div>{field('Plane URL', 'planeUrl')}{field('Workspace Slug', 'workspace')}{field('Project ID', 'planeProject')}{secret('Plane API Token', 'planeToken', values.planeTokenConfigured)}<button className="btn secondary setting-action" disabled={busy} onClick={() => void action('plane')}><RefreshCw />保存并导入项目</button></section>
      <section className="surface setting-card"><div className="setting-head"><GitBranch /><div><h2>GitLab</h2><p>{values.gitTokenConfigured ? '已保存凭据 · 连通性以同步结果为准' : '尚未配置'}</p></div></div>{field('Git URL', 'gitUrl')}{field('Repository 路径', 'repository')}{secret('Git Token', 'gitToken', values.gitTokenConfigured)}<button className="btn secondary setting-action" disabled={busy || !projectId} onClick={() => void action('git')}><Link2 />保存并关联代码</button></section>
      <section className="surface setting-card"><div className="setting-head"><Sparkles /><div><h2>AI Inspector</h2><p>核验时向该服务发送关联 MR 的有限代码上下文</p></div></div>{field('API Base URL', 'llmUrl')}{field('Model', 'model')}{secret('API Key', 'llmKey', values.llmKeyConfigured)}{field('Temperature', 'temperature', 'number', 0, 2)}{field('Max Tokens', 'maxTokens', 'number', 256, 16000)}{field('最大文件数', 'maxAiFiles', 'number', 1, 50)}{field('最大 Diff 字符数', 'maxAiDiffSize', 'number', 1000, 200000)}{field('最大代码字符数', 'maxAiCodeSize', 'number', 1000, 500000)}</section>
      <section className="surface setting-card"><div className="setting-head"><RefreshCw /><div><h2>同步与进度</h2><p>外部系统为事实来源</p></div></div><label className="checkbox-field"><input type="checkbox" checked={values.autoSync} onChange={e => change('autoSync', e.target.checked)} />自动同步</label>{field('同步间隔 / 秒', 'syncInterval', 'number', 60, 86400)}{field('P0 权重', 'weightP0', 'number', 1, 20)}{field('P1 权重', 'weightP1', 'number', 1, 20)}{field('P2 权重', 'weightP2', 'number', 1, 20)}</section>
    </div><section className="surface sync-logs"><div className="surface-head"><h2>最近同步记录</h2></div>{logs.map(l => <div key={l.id}><time>{time(l.createdAt)}</time><strong>{l.source}</strong><span className={l.status === 'FAILED' ? 'danger-text' : 'success-text'}>{l.status === 'FAILED' ? '失败' : '完成'}</span><span>{l.message}</span></div>)}{!logs.length && <Empty text="暂无同步记录" />}</section>
  </>
}

function Workspace({ user, logout }: { user: User; logout: () => Promise<void> }) {
  const [view, setView] = useState<View>('projects'), [detailId, setDetailId] = useState<string | null>(null)
  const [projects, setProjects] = useState<ProjectSummary[]>([]), [projectId, setProjectId] = useState<number | null>(null)
  const [data, setData] = useState<Snapshot | null>(null), [loading, setLoading] = useState(true), [error, setError] = useState('')
  const [busy, setBusy] = useState(false), [sidebar, setSidebar] = useState(false), [dark, setDark] = useState(() => localStorage.getItem('pmo-theme') === 'dark')
  const [menuOpen, setMenuOpen] = useState(false), [createSignal, setCreateSignal] = useState(0)
  const version = useRef(0)
  const switcherRef = useRef<HTMLDivElement>(null)
  const admin = user.role === 'admin'
  const current = projects.find(p => p.id === projectId)
  useEffect(() => {
    if (!menuOpen) return
    const close = (event: MouseEvent) => { if (!switcherRef.current?.contains(event.target as Node)) setMenuOpen(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenuOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', escape) }
  }, [menuOpen])
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('pmo-theme', dark ? 'dark' : 'light') }, [dark])
  const listProjects = useCallback(async () => {
    const result = await api<{ items: ProjectSummary[] }>('/projects')
    setProjects(result.items)
    setProjectId(previous => result.items.some(p => p.id === previous) ? previous : result.items[0]?.id ?? null)
    if (!result.items.length) { setView('projects'); setLoading(false) }
  }, [])
  useEffect(() => { listProjects().catch(e => { setError(errorMessage(e)); setLoading(false) }) }, [listProjects])
  const load = useCallback(async (signal?: AbortSignal) => {
    if (!projectId) return
    const current = ++version.current
    try {
      const result = await api<Snapshot>(`/bootstrap?project=${projectId}`, 'GET', undefined, signal)
      if (version.current === current && !signal?.aborted) { setData(result); setError('') }
    } catch (err) { if (version.current === current && !signal?.aborted) setError(errorMessage(err)) }
    finally { if (version.current === current && !signal?.aborted) setLoading(false) }
  }, [projectId])
  useEffect(() => {
    const controller = new AbortController()
    setData(null); setDetailId(null); setLoading(true)
    if (projectId) void load(controller.signal)
    return () => { controller.abort(); ++version.current }
  }, [projectId, load])
  const navigate = (next: View) => { setView(next); setDetailId(null); setSidebar(false) }
  const open = (id: string) => { setView('requirements'); setDetailId(id); setSidebar(false) }
  const openProject = (id: number) => { setProjectId(id); setView('dashboard'); setDetailId(null); setSidebar(false) }
  async function createProject(body: unknown) {
    if (busy) return false
    setBusy(true); setError('')
    try {
      const created = await api<ProjectSummary>('/projects', 'POST', body)
      await listProjects(); setProjectId(created.id); setView('dashboard')
      return true
    } catch (err) { setError(errorMessage(err)); return false }
    finally { setBusy(false) }
  }
  async function mutate(path: string, body?: unknown, method = 'POST') {
    if (busy) return false
    setBusy(true); setError('')
    try { await api(`${path}?project=${projectId}`, method, body); await load(); return true }
    catch (err) {
      if (err instanceof ApiError && err.partial) {
        await load()
        setError(errorMessage(err))
        return true
      }
      setError(errorMessage(err)); return false
    }
    finally { setBusy(false) }
  }
  const actions = { open, navigate, sync: () => { void mutate('/sync') }, summary: () => { void mutate('/summary') }, mutate, admin, busy }
  const selected = data?.requirements.find(r => r.id === detailId)
  const icons = { projects: <FolderKanban />, dashboard: <LayoutDashboard />, requirements: <ListChecks />, weekly: <Clock3 />, modules: <LayoutGrid />, members: <UsersRound />, risks: <AlertTriangle />, settings: <Settings /> }
  return <div className="workspace-root workspace-enter">{sidebar && <button className="sidebar-backdrop" aria-label="关闭导航" onClick={() => setSidebar(false)} />}
    <aside className={`sidebar ${sidebar ? 'open' : ''}`}>
      <button className="workspace-switcher" onClick={() => navigate('projects')}><BrandMark small /><span><strong>NOMI</strong><small>研发控制台</small></span></button>
      <div className="project-switcher-wrap" ref={switcherRef}>
        <button className="project-switcher" aria-label="切换项目" aria-haspopup="listbox" aria-expanded={menuOpen} onClick={() => setMenuOpen(v => !v)}>
          <span className="switcher-avatar">{current?.name[0] ?? 'P'}</span>
          <span className="switcher-label"><strong>{current?.name ?? '暂无项目'}</strong><small>{current ? `${modeLabels[current.mode]} · 进度 ${current.progress}%` : '选择或新建项目'}</small></span>
          <ChevronDown className={menuOpen ? 'flip' : ''} />
        </button>
        {menuOpen && <div className="switcher-menu" role="listbox" aria-label="项目列表">
          {projects.map(p => <button className={`switcher-option ${p.id === projectId ? 'active' : ''}`} role="option" aria-selected={p.id === projectId} key={p.id}
            onClick={() => { setProjectId(p.id); setMenuOpen(false); setSidebar(false) }}>
            <span className="switcher-avatar">{p.name[0]}</span>
            <span className="switcher-label"><strong>{p.name}</strong><small>{modeLabels[p.mode]} · 进度 {p.progress}%</small></span>
            {p.id === projectId && <Check />}
          </button>)}
          {!projects.length && <p className="switcher-empty">暂无项目，去项目中心创建</p>}
          <div className="switcher-actions">
            <button onClick={() => { navigate('projects'); setMenuOpen(false); setSidebar(false) }}><FolderKanban />项目中心</button>
            {admin && <button onClick={() => { navigate('projects'); setCreateSignal(v => v + 1); setMenuOpen(false); setSidebar(false) }}><Plus />新建项目</button>}
          </div>
        </div>}
      </div>
      <nav aria-label="主导航"><span className="nav-label">项目控制</span>{Object.entries(labels).map(([key, label]) => <button className={`nav-item ${view === key ? 'active' : ''}`} key={key} onClick={() => navigate(key as View)}>{icons[key as View]}<span>{label}</span>{key === 'risks' && data && <b className="nav-badge">{data.risks.filter(r => r.status === 'OPEN').length}</b>}</button>)}</nav>
      <div className="sidebar-foot"><div className="runtime-mini"><span className={error ? 'dot-muted' : 'live-dot'} /><div><strong>{data?.dashboard.project.mode === 'demo' ? 'Demo Mode' : '研发工作区'}</strong><small>{error ? '连接异常' : data ? '数据已加载' : '等待数据'}</small></div></div><div className="sidebar-user"><span className="avatar">{user.username[0]}</span><span><strong>{user.username}</strong><small>{admin ? '管理员' : '项目成员'}</small></span><button className="header-icon" title="退出登录" onClick={() => void logout().catch(e => setError(errorMessage(e)))}><LogOut /></button></div></div>
    </aside>
    <div className="workspace-frame"><header className="workspace-header"><button className="mobile-menu" title="展开导航" onClick={() => setSidebar(v => !v)}><Menu /></button><div className="breadcrumbs"><span>NOMI</span><b>/</b><span>{selected?.id || labels[view]}</span></div><div className="header-spacer" />
      <button className="header-icon" title={dark ? '浅色模式' : '深色模式'} onClick={() => setDark(v => !v)}>{dark ? <Sun /> : <Moon />}</button></header>
      <main className="workspace-content">
        {error && <div className="notice error" role="alert"><AlertTriangle /><span>{error}{data && '。正在显示上次成功读取的快照，数据可能不是最新。'}</span><button className="btn secondary" onClick={() => void (projectId ? load() : listProjects().catch(e => setError(errorMessage(e))))}><RefreshCw />重试</button></div>}
        {data && <div className="data-stamp"><span>{data.dashboard.project.mode === 'demo' ? '演示数据 · 非真实研发证据' : data.dashboard.project.mode === 'local' ? '本地管理 · 控制台内维护' : '外部系统缓存'}</span><span>最后成功同步：{time(data.dashboard.project.lastSync)}</span></div>}
        {view === 'projects' ? <ProjectsPage items={projects} currentId={projectId} admin={admin} busy={busy} onOpen={openProject} onCreate={createProject} createSignal={createSignal} />
          : view === 'settings' ? <SettingsPage projectId={projectId} admin={admin} logs={data?.logs || []} onConnected={async () => { await listProjects(); await load() }} />
          : loading ? <Loading /> : !data ? <Empty text="尚无项目数据" /> : selected ? <Detail key={selected.id} item={selected} data={data} back={() => setDetailId(null)} mutate={mutate} admin={admin} busy={busy} />
          : view === 'dashboard' ? <Overview data={data} actions={actions} />
          : view === 'requirements' ? <RequirementsPage data={data} actions={actions} />
          : view === 'weekly' ? <Weekly key={projectId} data={data} open={open} />
          : view === 'modules' ? <ModulesPage key={projectId} data={data} open={open} />
          : view === 'members' ? <MembersPage key={projectId} data={data} open={open} />
          : <RisksPage data={data} actions={actions} scan={() => void mutate('/risks/scan')} acknowledge={(id, status) => void mutate(`/risks/${id}`, { status }, 'PATCH')} add={body => mutate('/risks', body)} />}
      </main></div></div>
}

export default function App() {
  const [user, setUser] = useState<User | null>(null), [checking, setChecking] = useState(true)
  const [transition, setTransition] = useState(false), [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    api<User>('/auth/me', 'GET', undefined, controller.signal).then(setUser).catch(e => {
      if (!controller.signal.aborted && (!(e instanceof ApiError) || e.status !== 401)) setError(errorMessage(e))
    }).finally(() => { if (!controller.signal.aborted) setChecking(false) })
    const expired = () => { setUser(null); setError('登录已过期，请重新登录') }
    window.addEventListener('pmo:session-expired', expired)
    return () => { controller.abort(); window.removeEventListener('pmo:session-expired', expired) }
  }, [])
  const finish = useCallback(() => setTransition(false), [])
  if (checking) return <Loading text="正在连接工作区" />
  if (transition) return <Transition onDone={finish} />
  if (!user) return <>{error && <div className="connection-error" role="alert">{error}</div>}<Login onLogin={u => { setError(''); setUser(u); setTransition(true) }} /></>
  return <Workspace user={user} logout={async () => { await api('/auth/logout', 'POST'); setUser(null) }} />
}
