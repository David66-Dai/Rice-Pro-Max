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
