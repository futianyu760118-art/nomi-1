export type Status = 'TODO' | 'IN_PROGRESS' | 'REVIEW' | 'TESTING' | 'DONE' | 'BLOCKED'
export type View = 'projects' | 'dashboard' | 'requirements' | 'weekly' | 'modules' | 'members' | 'risks' | 'settings'
export type ProjectMode = 'demo' | 'live' | 'local'
export type User = { username: string; role: 'admin' | 'member' }
export type ProjectOption = { id: number; name: string; mode: ProjectMode }
export type ProjectSummary = ProjectOption & {
  progress: number; week: number; weeks: number; startDate: string; endDate: string
  remainingDays: number; lastSync: string | null; requirements: Counts
  riskSummary: { HIGH: number; MEDIUM: number; LOW: number }; members: number; modules: number
}
export type GitLink = {
  repository: string; branch: string; mr: number | null; mrState: string | null
  pipeline: 'PASSED' | 'FAILED' | 'RUNNING' | 'UNKNOWN'; sha: string; author: string
  updatedAt: string; url: string | null; manual: boolean; source: string
  commits: { sha: string; message: string; author: string }[]
}
export type Inspection = {
  implementation_score: number; status: 'IMPLEMENTED' | 'PARTIAL' | 'MISSING' | 'UNKNOWN'
  acceptance_criteria: { criterion: string; status: string; evidence: string[] }[]
  risks: { level: string; description: string }[]
  tests: { status: string; summary: string }; summary: string; createdAt: string
  stale: boolean; source: string; context_truncated?: boolean
}
export type Requirement = {
  id: string; title: string; module: string; owner: string; priority: 'P0' | 'P1' | 'P2'
  status: Status; week: number; start: string | null; due: string | null
  delayed: boolean; description: string; criteria: string[]; planeUrl: string | null
  progress: number; git: GitLink | null; inspection: Inspection | null
}
export type Risk = {
  id: number; requirementId: string; title: string; level: 'HIGH' | 'MEDIUM' | 'LOW'
  owner: string; source: string; action: string; status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'; createdAt: string
}
export type Counts = { total: number; done: number; inProgress: number; todo: number; blocked: number; delayed: number }
export type Week = Counts & { week: number; progress: number; start: string; end: string }
export type Dashboard = {
  project: ProjectOption & { stage: string; week: number; weeks: number; progress: number; startDate: string; endDate: string; remainingDays: number; lastSync: string | null }
  requirements: Counts; currentWeek: Counts
  modules: (Counts & { name: string; progress: number })[]
  weeks: Week[]; members: (Counts & { name: string })[]
  riskSummary: { HIGH: number; MEDIUM: number; LOW: number }
}
export type Snapshot = {
  dashboard: Dashboard; requirements: Requirement[]; risks: Risk[]
  management?: { owners: string[]; modules: string[]; weeks: { week: number; name: string }[]; statuses: Status[] }
  catalog?: { cycles: (Counts & { week: number; name: string; start: string; end: string; progress: number; active: boolean })[]; modules: (Counts & { name: string; description: string; progress: number })[]; members: (Counts & { name: string; role: string; progress: number })[] }
  aiSummary?: { summary: string; priorities: string[]; source: string; createdAt: string; stale: boolean } | null
  logs: { id: number; source: string; status: string; message: string; createdAt: string }[]
}
export type SettingsData = {
  planeUrl: string; workspace: string; planeProject: string; planeTokenConfigured: boolean
  gitUrl: string; gitProvider: string; repository: string; gitTokenConfigured: boolean
  llmUrl: string; model: string; llmKeyConfigured: boolean
  temperature: number; maxTokens: number; maxAiFiles: number; maxAiCodeSize: number; maxAiDiffSize: number
  autoSync: boolean; syncInterval: number; weightP0: number; weightP1: number; weightP2: number
}
