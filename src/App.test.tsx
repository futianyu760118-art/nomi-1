import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError, api } from './api'
import type { Snapshot } from './types'

vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: vi.fn() }))
const mocked = vi.mocked(api)
const counts = { total: 1, done: 0, inProgress: 1, todo: 0, delayed: 0, blocked: 0 }
const projectItems = [{ id: 1, name: '示例项目', mode: 'demo' as const, progress: 47, week: 3, weeks: 6, startDate: '2026-09-01', endDate: '2026-10-12', remainingDays: 21, lastSync: '2026-09-18T00:00:00Z', requirements: counts, riskSummary: { HIGH: 1, MEDIUM: 0, LOW: 0 }, members: 1, modules: 1 }]
const data: Snapshot = {
  dashboard: {
    project: { id: 1, name: '示例项目', mode: 'demo', stage: 'Phase 1', week: 3, weeks: 6, progress: 30, startDate: '2026-09-01', endDate: '2026-10-12', remainingDays: 24, lastSync: '2026-09-18T00:00:00Z' },
    requirements: counts, currentWeek: counts, modules: [{ ...counts, name: 'Skill 系统', progress: 30 }],
    weeks: Array.from({ length: 6 }, (_, i) => ({ ...counts, week: i + 1, start: '2026-09-01', end: '2026-09-07', progress: 30 })),
    members: [{ ...counts, name: '吴杨鹏' }], riskSummary: { HIGH: 1, MEDIUM: 0, LOW: 0 },
  },
  requirements: [{ id: 'REQ-012', title: '动态加载 Skill', module: 'Skill 系统', owner: '吴杨鹏', priority: 'P0', status: 'IN_PROGRESS', week: 3, due: '2026-09-19', start: null, delayed: false, description: '动态加载说明', criteria: ['动态加载成功'], planeUrl: null, progress: 30, git: null, inspection: null }],
  risks: [{ id: 1, requirementId: 'REQ-012', title: '测试缺失', level: 'HIGH', owner: '吴杨鹏', source: 'AI 核验', action: '补充测试', status: 'OPEN', createdAt: '2026-09-18T00:00:00Z' }],
  logs: [],
}

beforeEach(() => {
  mocked.mockImplementation(async (path) => {
    if (path === '/auth/me') return { username: 'demo', role: 'admin' }
    if (path === '/projects') return { items: structuredClone(projectItems) }
    if (path.startsWith('/bootstrap')) return structuredClone(data)
    throw new Error('Unexpected request ' + path)
  })
})

async function enterProject() {
  await userEvent.click(await screen.findByRole('button', { name: /示例项目/ }))
  await screen.findByRole('heading', { name: '示例项目' })
}

describe('data-backed console', () => {
  function liveProject() {
    const current = structuredClone(data)
    current.dashboard.project.mode = 'live'
    current.management = { owners: ['吴杨鹏', '尚无任务的成员'], modules: ['Skill 系统', '空模块'], weeks: [{ week: 3, name: 'Week 3' }], statuses: ['IN_PROGRESS', 'TESTING'] }
    const original = mocked.getMockImplementation()!
    mocked.mockImplementation(async (...args) => {
      const [path, method, body] = args
      if (path.startsWith('/bootstrap')) return structuredClone(current)
      if (path === '/requirements/REQ-012?project=1' && method === 'PATCH') {
        Object.assign(current.requirements[0], body)
        return current.requirements[0]
      }
      if (path === '/requirements?project=1' && method === 'POST') return { id: 'REQ-013' }
      return original(...args)
    })
    return current
  }

  it('edits a live requirement inside the console with only changed fields', async () => {
    liveProject()
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: /REQ-012 动态加载 Skill/ }))
    await userEvent.click(screen.getByRole('button', { name: '编辑需求' }))
    expect(screen.getByRole('option', { name: '尚无任务的成员' })).toBeInTheDocument()
    const title = screen.getByRole('textbox', { name: '标题' })
    await userEvent.clear(title)
    await userEvent.type(title, 'Updated title')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: '状态' }), 'TESTING')
    await userEvent.click(screen.getByRole('button', { name: '保存需求' }))
    expect(mocked).toHaveBeenCalledWith('/requirements/REQ-012?project=1', 'PATCH', { title: 'Updated title', status: 'TESTING' })
    expect(await screen.findByRole('heading', { name: 'Updated title' })).toBeVisible()
  })

  it('creates a requirement without requiring pre-existing modules or cycles', async () => {
    liveProject()
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: '新增需求' }))
    await userEvent.type(screen.getByRole('textbox', { name: '需求标题' }), 'New work')
    await userEvent.click(screen.getByRole('button', { name: '创建需求' }))
    expect(mocked).toHaveBeenCalledWith('/requirements?project=1', 'POST', expect.objectContaining({ title: 'New work', criteria: [] }))
    await waitFor(() => expect(screen.queryByRole('textbox', { name: '需求标题' })).not.toBeInTheDocument())
  })

  it('retains edits when the remote write fails', async () => {
    liveProject()
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: /REQ-012 动态加载 Skill/ }))
    await userEvent.click(screen.getByRole('button', { name: '编辑需求' }))
    await userEvent.type(screen.getByRole('textbox', { name: '标题' }), ' changed')
    mocked.mockRejectedValueOnce(new ApiError('Write denied', 502, 'Plane'))
    await userEvent.click(screen.getByRole('button', { name: '保存需求' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Write denied')
    expect(screen.getByRole('textbox', { name: '标题' })).toHaveValue('动态加载 Skill changed')
  })

  it('loads the dashboard and API-derived totals', async () => {
    render(<App />)
    await enterProject()
    expect(screen.getByText('项目完成度')).toBeVisible()
    expect(screen.getByText('演示数据 · 非真实研发证据')).toBeVisible()
  })

  it('opens requirement-specific details', async () => {
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: /REQ-012 动态加载 Skill/ }))
    expect(screen.getByRole('heading', { name: '动态加载 Skill' })).toBeVisible()
    expect(screen.getByText('动态加载成功')).toBeVisible()
    expect(screen.getByRole('button', { name: '重新核验' })).toBeDisabled()
  })

  it('filters requirements into an empty state', async () => {
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.type(screen.getByRole('textbox', { name: '搜索需求' }), 'nonexistent')
    expect(screen.getByText('没有匹配的需求')).toBeVisible()
  })

  it('renders the risk page from the API', async () => {
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '风险 1' }))
    expect(screen.getByRole('heading', { name: '风险' })).toBeVisible()
    expect(screen.getByText('补充测试')).toBeVisible()
    expect(screen.getByRole('button', { name: '确认' })).toBeVisible()
  })

  it('shows a loading state while the snapshot is pending', async () => {
    mocked.mockImplementation(async path => path === '/auth/me' ? { username: 'demo', role: 'admin' } : path === '/projects' ? { items: structuredClone(projectItems) } : new Promise(() => {}))
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /示例项目/ }))
    expect(await screen.findByText('正在读取项目数据')).toBeVisible()
  })

  it('shows an API error rather than fabricating fallback data', async () => {
    mocked.mockImplementation(async path => {
      if (path === '/auth/me') return { username: 'demo', role: 'admin' }
      if (path === '/projects') return { items: structuredClone(projectItems).map(p => ({ ...p, name: 'Offline Project' })) }
      throw new ApiError('Offline', 502, 'Plane')
    })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /Offline Project/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Plane')
    expect(screen.queryByText('项目完成度')).not.toBeInTheDocument()
  })

  it('retains the last snapshot on a refresh failure', async () => {
    render(<App />)
    await enterProject()
    mocked.mockRejectedValueOnce(new ApiError('Offline', 502, 'Plane'))
    await userEvent.click(screen.getByRole('button', { name: '刷新演示快照' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('上次成功读取')
    expect(screen.getByText('项目完成度')).toBeVisible()
  })

  it('creates a local project from the projects hub and lands on it', async () => {
    const localSnapshot = structuredClone(data)
    localSnapshot.dashboard.project = { ...localSnapshot.dashboard.project, id: 2, name: 'Nova 看板迁移', mode: 'local' }
    localSnapshot.management = { owners: [], modules: [], weeks: [{ week: 1, name: 'Week 1' }], statuses: [] }
    const original = mocked.getMockImplementation()!
    mocked.mockImplementation(async (...args) => {
      const [path, method, body] = args
      if (path === '/projects' && method === 'POST') {
        return { id: 2, name: 'Nova 看板迁移', mode: 'local', progress: 0, week: 1, weeks: 6, startDate: '2026-09-28', endDate: '2026-11-08', remainingDays: 48, lastSync: null, requirements: { total: 0, done: 0, inProgress: 0, todo: 0, delayed: 0, blocked: 0 }, riskSummary: { HIGH: 0, MEDIUM: 0, LOW: 0 }, members: 0, modules: 0 }
      }
      if (path === '/projects') return { items: [...structuredClone(projectItems), { id: 2, name: 'Nova 看板迁移', mode: 'local' as const, progress: 0, week: 1, weeks: 6, startDate: '2026-09-28', endDate: '2026-11-08', remainingDays: 48, lastSync: null, requirements: { total: 0, done: 0, inProgress: 0, todo: 0, delayed: 0, blocked: 0 }, riskSummary: { HIGH: 0, MEDIUM: 0, LOW: 0 }, members: 0, modules: 0 }] }
      if (path.startsWith('/bootstrap') && path.includes('project=2')) return structuredClone(localSnapshot)
      return original(...args)
    })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: '新建项目' }))
    await userEvent.type(screen.getByRole('textbox', { name: '项目名称' }), 'Nova 看板迁移')
    await userEvent.click(screen.getByRole('button', { name: '创建项目' }))
    expect(mocked).toHaveBeenCalledWith('/projects', 'POST', expect.objectContaining({ name: 'Nova 看板迁移', weeks: 6 }))
    expect(await screen.findByRole('heading', { name: 'Nova 看板迁移' })).toBeVisible()
    expect(screen.getByText('本地管理 · 控制台内维护')).toBeVisible()
  })

  it('drags a board card into another status column and patches only the status', async () => {
    liveProject()
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: /看板/ }))
    const card = screen.getByText('REQ-012').closest('article')!
    fireEvent.dragStart(card, { dataTransfer: { setData: vi.fn(), effectAllowed: 'move' } })
    const doneColumn = screen.getByLabelText('看板列 已完成')
    fireEvent.dragOver(doneColumn, { dataTransfer: { types: ['text/plain'] } })
    fireEvent.drop(doneColumn, { dataTransfer: {} })
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/requirements/REQ-012?project=1', 'PATCH', { status: 'DONE' }))
  })

  it('keeps the demo board read-only with guidance instead of drag handles', async () => {
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: /看板/ }))
    expect(screen.getByText(/演示项目为只读快照/)).toBeVisible()
    expect(screen.getByText('REQ-012').closest('article')).toHaveAttribute('draggable', 'false')
    expect(screen.queryByRole('button', { name: '新增需求' })).not.toBeInTheDocument()
  })

  it('switches the active project from the sidebar switcher', async () => {
    const second = structuredClone(data)
    second.dashboard.project = { ...second.dashboard.project, id: 2, name: 'Nova 看板迁移', mode: 'local' }
    const original = mocked.getMockImplementation()!
    mocked.mockImplementation(async (...args) => {
      const [path] = args
      if (path === '/projects') return { items: [...structuredClone(projectItems), { ...projectItems[0], id: 2, name: 'Nova 看板迁移', mode: 'local' as const, progress: 0 }] }
      if (path.startsWith('/bootstrap') && path.includes('project=2')) return structuredClone(second)
      return original(...args)
    })
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '切换项目' }))
    await userEvent.click(screen.getByRole('option', { name: /Nova 看板迁移/ }))
    expect(await screen.findByRole('heading', { name: 'Nova 看板迁移' })).toBeVisible()
  })

  it('quick-adds a requirement inline into a board column', async () => {
    liveProject()
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '需求' }))
    await userEvent.click(screen.getByRole('button', { name: /看板/ }))
    const todoColumn = screen.getByLabelText('看板列 未开始')
    await userEvent.click(await within(todoColumn).findByRole('button', { name: '新建' }))
    await userEvent.type(within(todoColumn).getByRole('textbox'), '快速卡片')
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/requirements?project=1', 'POST', expect.objectContaining({ title: '快速卡片', status: 'TODO' })))
  })

  it('renders Plane-style cycles, modules and members catalogs', async () => {
    const enriched = structuredClone(data)
    enriched.catalog = {
      cycles: [{ ...counts, week: 3, name: 'Cycle 3 · 引擎接入', start: '2026-09-14', end: '2026-09-20', progress: 40, active: true }],
      modules: [{ ...counts, name: 'Skill 系统', description: '技能加载与回滚', progress: 30 }],
      members: [{ ...counts, name: '吴杨鹏', role: '管理员', progress: 30 }],
    }
    const original = mocked.getMockImplementation()!
    mocked.mockImplementation(async (...args) => args[0].startsWith('/bootstrap') ? structuredClone(enriched) : original(...args))
    render(<App />)
    await enterProject()
    await userEvent.click(screen.getByRole('button', { name: '周期' }))
    expect(screen.getByText('Cycle 3 · 引擎接入')).toBeVisible()
    expect(screen.getByText('进行中')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '模块' }))
    expect(screen.getByText('技能加载与回滚')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '成员' }))
    const memberCard = screen.getByRole('heading', { name: '吴杨鹏' }).closest('article')!
    expect(within(memberCard).getByText('管理员')).toBeVisible()
  })

  it('requires server login after a 401 and transitions to the dashboard', async () => {
    const original = mocked.getMockImplementation()!
    mocked.mockImplementation(async (...args) => args[0] === '/auth/me' ? Promise.reject(new ApiError('请先登录', 401)) : args[0] === '/auth/login' ? { username: 'demo', role: 'admin' } : original(...args))
    render(<App />)
    await userEvent.type(await screen.findByRole('textbox', { name: '账号' }), 'demo')
    await userEvent.type(screen.getByLabelText('密码', { exact: true }), 'demo')
    await userEvent.click(screen.getByRole('button', { name: '继续进入工作区' }))
    await enterProject()
  })
})
