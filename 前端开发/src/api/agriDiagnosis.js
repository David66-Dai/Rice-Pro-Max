const HDFS_BASE = 'http://192.168.157.130:8000'

function fixUnquotedUnits(jsonStr) {
  // Dify LLM 有时输出 "预计减产": 35公斤/亩 而非 "35公斤/亩"，修复为合法 JSON
  return jsonStr.replace(
    /:\s*(\d+\.?\d*)([^\d\s,}\]"'][^\s,}\]]*)/g,
    (_, num, unit) => `: "${num}${unit}"`
  )
}

function parseJsonLike(value) {
  if (typeof value !== 'string') return value
  const s = value.trim()

  // 0) 预处理：修复 LLM 输出的未加引号的值（如 35公斤/亩 → "35公斤/亩"）
  const tryParse = (str) => {
    try { return JSON.parse(str) } catch (_) {
      try { return JSON.parse(fixUnquotedUnits(str)) } catch (_) { return null }
    }
  }

  // 1) plain JSON
  if (s.startsWith('{') || s.startsWith('[')) {
    const r = tryParse(s)
    if (r) return r
  }

  // 2) markdown code fence: ```json ... ``` or ``` ... ```
  const fence = s.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fence) {
    const r = tryParse(fence[1])
    if (r) return r
  }

  // 3) extract from first { to last }
  const objStart = s.indexOf('{')
  const objEnd = s.lastIndexOf('}')
  if (objStart !== -1 && objEnd > objStart) {
    const r = tryParse(s.slice(objStart, objEnd + 1))
    if (r) return r
  }

  return value
}

async function requestDiagnosis(endpoint, file, stationCode) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('stationCode', stationCode)

  const response = await fetch(endpoint, {
    method: 'POST',
    body: formData
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = payload?.message || payload?.detail || '识别服务请求失败'
    throw new Error(message)
  }

  return {
    label: payload?.label || payload?.diseaseName || payload?.name || '未识别',
    confidence: Number(payload?.confidence ?? payload?.score ?? 0),
    annotatedImageBase64: payload?.annotatedImageBase64 || '',
    pestCounts: payload?.pestCounts || {},
    totalPestCount: Number(payload?.totalPestCount ?? 0),
    raw: payload
  }
}

export function identifyLeafDamage(file, stationCode) {
  return requestDiagnosis('/api/diagnosis/leaf', file, stationCode)
}

export function identifyPestDamage(file, stationCode) {
  return requestDiagnosis('/api/diagnosis/pest', file, stationCode)
}

export async function saveMonitoringRecord(record) {
  const response = await fetch('/api/monitoring/record', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(record)
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = payload?.message || payload?.detail || '监测数据保存失败'
    throw new Error(message)
  }
  return payload
}

export async function fetchMonitoringState(date) {
  const response = await fetch(`/api/monitoring/state?date=${encodeURIComponent(date)}`)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = payload?.message || payload?.detail || '监测状态读取失败'
    throw new Error(message)
  }
  return payload
}

export async function fetchHdfsPointData(date, point) {
  const response = await fetch(`${HDFS_BASE}/api/${encodeURIComponent(date)}/${encodeURIComponent(point)}/all.json`)
  if (!response.ok) {
    throw new Error(`HDFS数据读取失败: ${response.status}`)
  }
  const raw = await response.json()

  // Parse nested JSON strings inside main_output (output1/output2/output3 are strings)
  if (raw.main_output && typeof raw.main_output === 'object') {
    const mo = raw.main_output
    if (typeof mo.output1 === 'string') {
      mo.output1 = parseJsonLike(mo.output1)
    }
    if (typeof mo.output2 === 'string') {
      mo.output2 = parseJsonLike(mo.output2)
    }
    if (typeof mo.output3 === 'string') {
      mo.output3 = parseJsonLike(mo.output3)
    }
  }
  return raw
}
