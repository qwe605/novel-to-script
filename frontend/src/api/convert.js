import axios from 'axios'

const client = axios.create({
  baseURL: '',
  timeout: 120000,
})

// ========== 转换 ==========

export async function convertFile(files, params) {
  const form = new FormData()

  // 支持单文件或多文件
  const fileList = Array.isArray(files) ? files : [files]
  for (const f of fileList) {
    form.append('files', f)
  }

  form.append('script_type', params.script_type)
  form.append('mode', params.mode)
  form.append('panel_mode', params.panel_mode)
  if (params.title) form.append('title', params.title)

  // 向后兼容：顶层 api_key
  if (params.api_key && !params.ai_config) {
    form.append('api_key', params.api_key)
  }

  // AI 配置（JSON 字符串）
  if (params.ai_config) {
    form.append('ai_config', JSON.stringify(params.ai_config))
  }

  // 分集配置（JSON 字符串）
  if (params.episode_config) {
    form.append('episode_config', JSON.stringify(params.episode_config))
  }

  const res = await client.post('/api/convert', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function getTaskStatus(taskId) {
  const res = await client.get(`/api/convert/${taskId}`)
  return res.data
}

export function getDownloadUrl(taskId) {
  return `/api/convert/${taskId}/download`
}

// ========== AI 提供商 ==========

/** 获取所有提供商信息 */
export async function getProviders() {
  const res = await client.get('/api/providers')
  return res.data
}

/** 获取示例小说文本（3 章 demo） */
export async function getDemoNovel() {
  const res = await client.get('/api/demo')
  return res.data
}

/** 生成封面图提示词 */
export async function generateCover(params) {
  const res = await client.post('/api/cover', params)
  return res.data
}

/** 测试提供商连通性 + 拉取可用模型 */
export async function testProvider(params) {
  const res = await client.post('/api/providers/test', params)
  return res.data
}

/** AI 辅助编辑（场景/节拍增强） */
export async function aiAssist(params) {
  const res = await client.post('/api/assist', params)
  return res.data
}
