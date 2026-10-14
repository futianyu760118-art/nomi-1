export class ApiError extends Error {
  constructor(message: string, public status: number, public source?: string, public partial = false) {
    super(message)
  }
}

export async function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort)
  if (signal?.aborted) controller.abort()
  const timeout = window.setTimeout(abort, method === 'GET' ? 15000 : 180000)
  try {
    const response = await fetch(`/api${path}`, {
      method, credentials: 'same-origin', signal: controller.signal,
      headers: method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-PMO-Request': '1' },
      body: method === 'GET' ? undefined : JSON.stringify(body ?? {}),
    })
    const data = await response.json().catch(() => { throw new ApiError('服务返回格式无效', response.status) })
    if (!response.ok) {
      if (response.status === 401 && path !== '/auth/me' && path !== '/auth/login') {
        window.dispatchEvent(new Event('pmo:session-expired'))
      }
      throw new ApiError(data.error || `HTTP ${response.status}`, response.status, data.source, data.partial === true)
    }
    return data as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(controller.signal.aborted ? '请求超时或已取消，请检查同步日志后重试' : '无法连接 API，请确认后端服务已启动', 0, 'Flask API')
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}

export function errorMessage(error: unknown) {
  return error instanceof ApiError && error.source ? `${error.source}：${error.message}` : error instanceof Error ? error.message : '请求失败'
}
