<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import riceFieldBg from './assets/rice.png'
import HistoryCharts from './components/HistoryCharts.vue'
import { fetchMonitoringState, fetchHdfsPointData, fetchStationRealtime, identifyLeafDamage, identifyPestDamage, saveMonitoringRecord } from './api/agriDiagnosis'

const stationPoints = ref([
  { x: 21, y: 16 }, { x: 32, y: 18 }, { x: 41, y: 16 },
  { x: 52, y: 19 }, { x: 61, y: 15 }, { x: 70, y: 15 },
  { x: 78, y: 18 },
  { x: 22, y: 38 }, { x: 32, y: 38 }, { x: 44, y: 40 },
  { x: 52, y: 41 }, { x: 65, y: 36 }, { x: 77, y: 37 },
  { x: 22, y: 58 }, { x: 33, y: 56 }, { x: 43, y: 61 },
  { x: 52, y: 57 }, { x: 64, y: 54 }, { x: 77, y: 62 },
  { x: 22, y: 79 }, { x: 33, y: 79 }, { x: 42, y: 81 },
  { x: 52, y: 80 }, { x: 64, y: 79 }, { x: 76, y: 82 }
])

const stationData = computed(() => stationPoints.value.map((point, idx) => {
  const id = idx + 1
  const states = ['正常', '预警', '关注']

  return {
    id,
    name: `站点 ${id}`,
    code: `ST-${String(id).padStart(3, '0')}`,
    x: point.x,
    y: point.y,
    state: states[id % states.length],
    temp: +(22 + (point.y / 100) * 7 + (point.x / 100) * 2.5).toFixed(1),
    humidity: +(50 + (point.x / 100) * 18).toFixed(1),
    ph: +(6.1 + (point.y / 100) * 0.35).toFixed(2),
    moisture: +(30 + (point.y / 100) * 22).toFixed(1),
    sunshineHours: +(2.8 + (point.x / 100) * 1.4).toFixed(1),
    avgWindSpeed: +(1.0 + (point.y / 100) * 0.9).toFixed(1),
    dailyRainfall: +(72 + (point.x / 100) * 30).toFixed(0),
    avgAirTemp: +(29 + (point.y / 100) * 5).toFixed(0),
    relativeHumidity: +(68 + (point.x / 100) * 12).toFixed(0),
    soilOrganicMatter: +(3.4 + (point.y / 100) * 1.6).toFixed(2),
    soilAcidity: +(6.0 + (point.x / 100) * 0.4).toFixed(1),
    soilPhosphorus: +(30 + (point.y / 100) * 14).toFixed(1),
    soilPotassium: +(172 + (point.x / 100) * 44).toFixed(2),
    soilConductivity: +(0.92 + (point.y / 100) * 0.5).toFixed(2)
  }
}))

function getBeijingDateParts() {
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })

  const parts = formatter.formatToParts(new Date())
  const map = Object.fromEntries(parts.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]))

  return {
    year: Number(map.year),
    month: Number(map.month),
    day: Number(map.day),
    time: `${map.hour}:${map.minute}:${map.second}`
  }
}

const beijingNow = ref(getBeijingDateParts())
const activeStationId = ref(8)
const showRecognitionView = ref(false)
const showHistoryCharts = ref(false)
const leafFileInput = ref(null)
const pestFileInput = ref(null)
const leafLoading = ref(false)
const pestLoading = ref(false)
const leafResult = ref(null)
const pestResult = ref(null)
const leafPreviewUrl = ref('')
const pestPreviewUrl = ref('')
const pestAnnotatedUrl = ref('')
const leafError = ref('')
const pestError = ref('')
const pestTypeLabels = ['二化螟', '稻纵卷叶螟', '褐飞虱']
const hdfsData = ref(null)
const hdfsAttempted = ref(false)
const hdfsLoading = ref(false)
const realtimeData = ref(null)
const realtimeLoading = ref(false)
const realtimeAttempted = ref(false)
let hdfsRequestId = 0
let realtimeRequestId = 0
const activeSuggestionType = ref('')
const expandedPlanPhases = ref([])
const INSPECT_DEFAULT_ITEMS = [
  { key: 'leaf_blight', name: '细菌性叶枯病', level: 'normal' },
  { key: 'leaf_brown_spot', name: '褐斑病', level: 'normal' },
  { key: 'leaf_tungro', name: '东格鲁病害', level: 'normal' },
  { key: 'pest_borer', name: '二化螟', level: 'normal' },
  { key: 'pest_planthopper', name: '褐飞虱', level: 'normal' },
  { key: 'pest_leafroller', name: '稻纵卷叶螟', level: 'normal' }
]
const LEAF_RISK_LEVEL_MAP = {
  细菌性叶枯病: 'warn',
  东格鲁病毒: 'warn',
  褐斑病: 'warn'
}
const INSPECT_STORAGE_KEY = 'smart-agri.station-inspect-map.v2'
const DATE_SELECTION_STORAGE_KEY = 'smart-agri.selected-date.v1'
const STATION_LEVEL_PRIORITY = { normal: 0, warn: 1, danger: 2 }
const stationInspectMapByDate = ref({})
const selectedDay = ref(beijingNow.value.day)
const selectedYear = ref(beijingNow.value.year)
const selectedMonth = ref(beijingNow.value.month)
const selectedDateKey = computed(() => formatDateValue(selectedYear.value, selectedMonth.value, selectedDay.value))
function createDefaultStationInspectMap() {
  return Object.fromEntries(
    stationData.value.map((station) => [station.code, INSPECT_DEFAULT_ITEMS.map((item) => ({ ...item }))])
  )
}
function getDateInspectMap(dateKey = selectedDateKey.value) {
  if (!stationInspectMapByDate.value[dateKey]) {
    stationInspectMapByDate.value[dateKey] = createDefaultStationInspectMap()
  }
  return stationInspectMapByDate.value[dateKey]
}
const inspectItems = computed(() => {
  return getDateInspectMap()[activeStation.value.code] ?? INSPECT_DEFAULT_ITEMS
})
const stationRiskLevelMap = computed(() => {
  const currentDateMap = getDateInspectMap()
  return Object.fromEntries(
    stationData.value.map((station) => {
      const items = currentDateMap[station.code] ?? INSPECT_DEFAULT_ITEMS
      let level = 'normal'
      for (const item of items) {
        if (STATION_LEVEL_PRIORITY[item.level] > STATION_LEVEL_PRIORITY[level]) {
          level = item.level
        }
      }
      return [station.code, level]
    })
  )
})
const STATION_STATUS_TEXT_MAP = {
  normal: '正常',
  warn: '预警',
  danger: '严重'
}
const activeStationStatusLevel = computed(() => {
  return stationRiskLevelMap.value[activeStation.value.code] || 'normal'
})
const activeStationStatusText = computed(() => {
  return STATION_STATUS_TEXT_MAP[activeStationStatusLevel.value] || '正常'
})
const activeDetailPopup = ref('')
const activePlanDialog = ref('')
let beijingTimer = null

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate()
}

const daysInCurrentMonth = computed(() => getDaysInMonth(selectedYear.value, selectedMonth.value))
const dayOptions = computed(() => Array.from({ length: daysInCurrentMonth.value }, (_, idx) => idx + 1))
const yearInput = ref(String(selectedYear.value))
const formattedYearMonth = computed(() => {
  return `${selectedYear.value}-${String(selectedMonth.value).padStart(2, '0')}`
})

const formattedBeijingDateTime = computed(() => {
  const { year, month, day, time } = beijingNow.value
  return `北京时间 ${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')} ${time}`
})

const fieldMapStyle = computed(() => {
  return {
    backgroundImage: `linear-gradient(rgba(5, 26, 54, 0.12), rgba(5, 26, 54, 0.12)), url(${riceFieldBg})`
  }
})

function scoreByRange(value, idealMin, idealMax, toleranceMin, toleranceMax) {
  if (!Number.isFinite(value)) return 0
  if (value < toleranceMin || value > toleranceMax) return 20
  if (value >= idealMin && value <= idealMax) return 100

  if (value < idealMin) {
    const ratio = (value - toleranceMin) / Math.max(idealMin - toleranceMin, 1e-6)
    return Math.round(20 + ratio * 80)
  }

  const ratio = (toleranceMax - value) / Math.max(toleranceMax - idealMax, 1e-6)
  return Math.round(20 + ratio * 80)
}

function weightedAverage(items) {
  let weightedSum = 0
  let totalWeight = 0
  for (const item of items) {
    weightedSum += item.score * item.weight
    totalWeight += item.weight
  }
  if (totalWeight <= 0) return 0
  return weightedSum / totalWeight
}

function getRiskPenalty(level) {
  if (level === 'danger') return 22
  if (level === 'warn') return 10
  return 0
}

function normalizeIndex(value) {
  return clamp((Number(value) || 0) / 100, 0, 1)
}

function getGrowthPeriodByCalendar(year, month, day, avgAirTemp) {
  const stageByMonth = [
    '育秧返青期',
    '育秧返青期',
    '分蘖期',
    '分蘖期',
    '拔节孕穗期',
    '拔节孕穗期',
    '抽穗扬花期',
    '灌浆结实期',
    '灌浆结实期',
    '成熟期',
    '成熟期',
    '育秧返青期'
  ]
  let stageIndex = month - 1
  if (Number(avgAirTemp) >= 31 && day >= 15) stageIndex += 1
  if (Number(avgAirTemp) <= 22 && day <= 15) stageIndex -= 1
  stageIndex = clamp(stageIndex, 0, stageByMonth.length - 1)
  return stageByMonth[stageIndex]
}

function getStageYieldFactor(stage) {
  if (stage === '育秧返青期') return 0.86
  if (stage === '分蘖期') return 0.92
  if (stage === '拔节孕穗期') return 0.97
  if (stage === '抽穗扬花期') return 1
  if (stage === '灌浆结实期') return 1.02
  if (stage === '成熟期') return 1.01
  return 0.95
}

// ── HDFS 数据辅助函数 ──

function stationCodeToHdfsPoint(code) {
  const num = parseInt(code.replace(/\D/g, ''), 10)
  return `point_${num}`
}

function severityToLevel(severity) {
  if (!severity) return 'normal'
  const s = String(severity)
  if (s.includes('严重') || s.includes('重度')) return 'danger'
  if (s.includes('中等') || s.includes('中度')) return 'warn'
  return 'normal'
}

function truncateText(text, maxLen) {
  if (!text || typeof text !== 'string') return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text
}

function mapHdfsInspectItems(diseaseOutput) {
  const items = diseaseOutput?.病害情况
  if (!items || typeof items !== 'object') return null

  const mapping = [
    { hdfsName: '白叶枯病', name: '细菌性叶枯病', field: '覆盖率', unit: '%', key: 'leaf_blight' },
    { hdfsName: '褐斑病', name: '褐斑病', field: '覆盖率', unit: '%', key: 'leaf_brown_spot' },
    { hdfsName: '东格鲁病毒病', name: '东格鲁病毒病', field: '覆盖率', unit: '%', key: 'leaf_tungro' },
    { hdfsName: '稻飞虱', name: '稻飞虱', field: '数量', unit: '头', key: 'pest_planthopper' },
    { hdfsName: '二化螟', name: '二化螟', field: '数量', unit: '头', key: 'pest_borer' },
    { hdfsName: '稻纵卷叶螟', name: '稻纵卷叶螟', field: '数量', unit: '头', key: 'pest_leafroller' },
  ]

  return mapping.map((m) => {
    const info = items[m.hdfsName]
    if (!info || typeof info !== 'object') {
      return { label: m.name, value: '无数据', level: 'normal', key: m.key }
    }
    const val = info[m.field] ?? ''
    const severity = info['严重程度'] ?? ''
    return {
      label: m.name,
      value: `${m.field} ${val}${m.unit}，${severity}`,
      level: severityToLevel(severity),
      key: m.key,
    }
  })
}

function mapHdfsAnalysisItems(weatherOutput, soilOutput) {
  const result = []
  const wx = weatherOutput?.气象信息分析与水稻种植影响评估?.当日气象分析
  if (wx && typeof wx === 'object') {
    if (wx['温度条件']) result.push({ label: '温度条件', value: truncateText(wx['温度条件'], 80) })
    if (wx['湿度条件']) result.push({ label: '湿度条件', value: truncateText(wx['湿度条件'], 80) })
    if (wx['降水条件']) result.push({ label: '降水条件', value: truncateText(wx['降水条件'], 80) })
    if (wx['风速条件']) result.push({ label: '风速条件', value: truncateText(wx['风速条件'], 80) })
  }
  const sl = soilOutput?.土壤信息分析与水稻种植影响评估?.当前土壤分析
  if (sl && typeof sl === 'object') {
    if (sl['pH值状况']) result.push({ label: '土壤pH', value: truncateText(sl['pH值状况'], 80) })
    if (sl['养分状况']) result.push({ label: '土壤养分', value: truncateText(sl['养分状况'], 80) })
    if (sl['有机质含量']) result.push({ label: '有机质含量', value: truncateText(sl['有机质含量'], 80) })
    if (sl['土壤电导率']) result.push({ label: '土壤电导率', value: truncateText(sl['土壤电导率'], 80) })
  }
  return result.length > 0 ? result : null
}

function mapHdfsDecisionItems(output1) {
  const yi = output1?.产量影响分析
  if (!yi || typeof yi !== 'object') return null

  const result = []
  if (yi['当前农田预测产量']) {
    result.push({ label: '预计产量', value: yi['当前农田预测产量'] })
  }
  if (yi['预计减产']) {
    result.push({ label: '预计减产', value: yi['预计减产'] })
  }
  const factors = yi['各因素产量影响']
  if (factors && typeof factors === 'object') {
    if (factors['叶害影响']) result.push({ label: '叶害影响', value: truncateText(factors['叶害影响'], 80) })
    if (factors['虫害影响']) result.push({ label: '虫害影响', value: truncateText(factors['虫害影响'], 80) })
    if (factors['气象影响']) result.push({ label: '气象影响', value: truncateText(factors['气象影响'], 80) })
    if (factors['土壤影响']) result.push({ label: '土壤影响', value: truncateText(factors['土壤影响'], 80) })
  }
  return result.length > 0 ? result : null
}

function mapHdfsPlanPhases(planObj) {
  if (!planObj || typeof planObj !== 'object') return null

  const phases = []
  const phaseData = planObj['分阶段防控/预防措施']
  if (phaseData && typeof phaseData === 'object') {
    for (const [phaseName, phaseInfo] of Object.entries(phaseData)) {
      if (!phaseInfo || typeof phaseInfo !== 'object') continue
      const target = String(phaseInfo['阶段目标'] ?? '')
      const leafOps = {}
      const pestOps = {}

      // Collect leaf disease operations
      const leafSection = phaseInfo['叶害防控/预防'] || phaseInfo['叶害防控']
      if (leafSection && typeof leafSection === 'object') {
        for (const [pestName, ops] of Object.entries(leafSection)) {
          if (ops && typeof ops === 'object' && pestName !== '阶段目标') {
            leafOps[pestName] = ops
          }
        }
      }

      // Collect pest operations
      const pestSection = phaseInfo['虫害防控/预防'] || phaseInfo['虫害防控']
      if (pestSection && typeof pestSection === 'object') {
        for (const [pestName, ops] of Object.entries(pestSection)) {
          if (ops && typeof ops === 'object' && pestName !== '阶段目标') {
            pestOps[pestName] = ops
          }
        }
      }

      // For 方案B: try alternative key names
      if (Object.keys(leafOps).length === 0) {
        for (const [key, val] of Object.entries(phaseInfo)) {
          if (key.startsWith('叶害') && val && typeof val === 'object') {
            for (const [pestName, ops] of Object.entries(val)) {
              if (ops && typeof ops === 'object') leafOps[pestName] = ops
            }
          }
        }
      }
      if (Object.keys(pestOps).length === 0) {
        for (const [key, val] of Object.entries(phaseInfo)) {
          if (key.startsWith('虫害') && val && typeof val === 'object') {
            for (const [pestName, ops] of Object.entries(val)) {
              if (ops && typeof ops === 'object') pestOps[pestName] = ops
            }
          }
        }
      }

      phases.push({
        title: phaseName,
        target,
        leafOps: Object.keys(leafOps).length > 0 ? leafOps : null,
        pestOps: Object.keys(pestOps).length > 0 ? pestOps : null,
      })
    }
  }

  const notes = planObj['通用注意事项']
  return { phases, notes: notes && typeof notes === 'object' ? notes : null }
}

function formatOpsText(ops) {
  if (!ops || typeof ops !== 'object') return ''
  return Object.entries(ops)
    .filter(([, v]) => typeof v === 'string' && v && v !== '无操作')
    .map(([k, v]) => `${k}：${v}`)
    .join('\n')
}

function findPlanInOutput(outputData, planPrefix) {
  if (!outputData || typeof outputData !== 'object') return null
  for (const key of Object.keys(outputData)) {
    if (key.startsWith(planPrefix)) return outputData[key]
  }
  return null
}

async function loadHdfsData() {
  const code = activeStation.value?.code
  const dateKey = selectedDateKey.value
  const reqId = ++hdfsRequestId
  hdfsData.value = null
  hdfsLoading.value = true
  expandedPlanPhases.value = []
  if (!code || !dateKey) {
    hdfsLoading.value = false
    return
  }

  try {
    const point = stationCodeToHdfsPoint(code)
    const result = await fetchHdfsPointData(dateKey, point)
    if (reqId !== hdfsRequestId) return  // 过期请求，丢弃
    hdfsData.value = result
  } catch (e) {
    if (reqId !== hdfsRequestId) return
    console.warn('HDFS数据加载失败:', e.message)
    hdfsData.value = null
  } finally {
    if (reqId === hdfsRequestId) {
      hdfsAttempted.value = true
      hdfsLoading.value = false
    }
  }
}

async function loadRealtimeData() {
  const code = activeStation.value?.code
  const dateKey = selectedDateKey.value
  const reqId = ++realtimeRequestId
  realtimeData.value = null
  realtimeLoading.value = true
  if (!code || !dateKey) {
    realtimeLoading.value = false
    return
  }

  try {
    const result = await fetchStationRealtime(code, dateKey)
    if (reqId !== realtimeRequestId) return
    realtimeData.value = result
  } catch (e) {
    if (reqId !== realtimeRequestId) return
    console.warn('站点实时数据加载失败:', e.message)
    realtimeData.value = null
  } finally {
    if (reqId === realtimeRequestId) {
      realtimeAttempted.value = true
      realtimeLoading.value = false
    }
  }
}

function parseYieldNumber(text) {
  if (!text) return null
  const match = String(text).match(/([\d.]+)/)
  return match ? parseFloat(match[1]) : null
}

function openSuggestionDialog(type) {
  activeSuggestionType.value = type
}

function closeSuggestionDialog() {
  activeSuggestionType.value = ''
}

function togglePlanPhase(idx) {
  const pos = expandedPlanPhases.value.indexOf(idx)
  if (pos === -1) {
    expandedPlanPhases.value.push(idx)
  } else {
    expandedPlanPhases.value.splice(pos, 1)
  }
}

const hdfsExpectedYield = computed(() => {
  return parseYieldNumber(hdfsData.value?.main_output?.output1?.产量影响分析?.['当前农田预测产量'])
})

const hdfsRecoveryYield = computed(() => {
  const planA = findPlanInOutput(hdfsData.value?.main_output?.output2, '方案A')
  return parseYieldNumber(planA?.['方案核心参数']?.['预计恢复产量'])
})

const suggestionTitle = computed(() => {
  if (activeSuggestionType.value === 'inspect') return '病虫害防治建议'
  if (activeSuggestionType.value === 'analysis') return '环境与土壤管理建议'
  if (activeSuggestionType.value === 'decision') return '综合分析报告'
  return ''
})

function buildSuggestionHtml(type) {
  if (!hdfsData.value) return '<p class="suggestion-empty">暂无HDFS数据</p>'

  if (type === 'inspect') {
    const s = hdfsData.value?.disease_output
    if (!s) return '<p class="suggestion-empty">暂无病虫害数据</p>'
    let html = ''
    if (s['监测总结']) html += `<p class="suggestion-summary"><b>监测总结：</b>${s['监测总结']}</p>`
    const advice = s['综合防治建议']
    if (advice) {
      const leaf = advice['叶害防治策略']
      if (leaf && typeof leaf === 'object') {
        html += '<h4>叶害防治策略</h4>'
        for (const [key, val] of Object.entries(leaf)) {
          if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
        }
      }
      const pest = advice['虫害防治策略']
      if (pest && typeof pest === 'object') {
        html += '<h4>虫害防治策略</h4>'
        for (const [key, val] of Object.entries(pest)) {
          if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
        }
      }
      const general = advice['综合管理建议']
      if (general && typeof general === 'object') {
        html += '<h4>综合管理建议</h4>'
        for (const [key, val] of Object.entries(general)) {
          if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
        }
      }
    }
    return html || '<p class="suggestion-empty">暂无防治建议数据</p>'
  }

  if (type === 'analysis') {
    const wx = hdfsData.value?.weather_output
    const sl = hdfsData.value?.soil_output
    let html = ''

    if (wx?.气象信息分析与水稻种植影响评估) {
      const wxData = wx.气象信息分析与水稻种植影响评估
      if (wxData['综合评价']) html += `<p class="suggestion-summary"><b>气象综合评价：</b>${wxData['综合评价']}</p>`
    }
    if (wx?.农田措施) {
      html += '<h4>农田措施建议</h4>'
      for (const [key, val] of Object.entries(wx.农田措施)) {
        if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
      }
    }
    if (wx?.总结建议) {
      html += '<h4>气象总结建议</h4>'
      for (const [key, val] of Object.entries(wx.总结建议)) {
        if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
      }
    }
    if (sl?.土壤管理与农田措施) {
      html += '<h4>土壤管理措施</h4>'
      for (const [key, val] of Object.entries(sl.土壤管理与农田措施)) {
        if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
      }
    }
    if (sl?.总结建议) {
      html += '<h4>土壤总结建议</h4>'
      for (const [key, val] of Object.entries(sl.总结建议)) {
        if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
      }
    }
    return html || '<p class="suggestion-empty">暂无环境与土壤建议数据</p>'
  }

  if (type === 'decision') {
    const o1 = hdfsData.value?.main_output?.output1
    if (!o1 || typeof o1 !== 'object') return '<p class="suggestion-empty">暂无综合分析数据</p>'
    let html = ''
    const leaf = o1['叶害影响分析']
    if (leaf && typeof leaf === 'object') {
      html += '<h4>叶害影响分析</h4>'
      for (const [pestName, analysis] of Object.entries(leaf)) {
        if (analysis && typeof analysis === 'object') {
          html += `<h5>${pestName}</h5>`
          for (const [key, val] of Object.entries(analysis)) {
            if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
          }
        }
      }
    }
    const pest = o1['虫害影响分析']
    if (pest && typeof pest === 'object') {
      html += '<h4>虫害影响分析</h4>'
      for (const [pestName, analysis] of Object.entries(pest)) {
        if (analysis && typeof analysis === 'object') {
          html += `<h5>${pestName}</h5>`
          for (const [key, val] of Object.entries(analysis)) {
            if (typeof val === 'string') html += `<p><b>${key}：</b>${val}</p>`
          }
        }
      }
    }
    const yi = o1['产量影响分析']
    if (yi?.['总体影响']) html += `<p class="suggestion-summary"><b>总体影响：</b>${yi['总体影响']}</p>`
    return html || '<p class="suggestion-empty">暂无综合分析数据</p>'
  }

  return '<p class="suggestion-empty">暂无数据</p>'
}

const suggestionContent = computed(() => {
  return buildSuggestionHtml(activeSuggestionType.value)
})

const activeStation = computed(() => {
  const base = stationData.value.find((station) => station.id === activeStationId.value) ?? stationData.value[0]
  const middleDay = Math.ceil(daysInCurrentMonth.value / 2)
  const dayShift = selectedDay.value - middleDay

  return {
    ...base,
    temp: +(base.temp + dayShift * 0.16).toFixed(1),
    humidity: +clamp(base.humidity + dayShift * 0.62, 38, 99).toFixed(1),
    ph: +clamp(base.ph + dayShift * 0.01, 5.2, 7.5).toFixed(2),
    moisture: +clamp(base.moisture + dayShift * 0.55, 20, 95).toFixed(1),
    sunshineHours: +clamp(base.sunshineHours + dayShift * 0.06, 0.5, 11).toFixed(1),
    avgWindSpeed: +clamp(base.avgWindSpeed + dayShift * 0.03, 0.2, 10).toFixed(1),
    dailyRainfall: +clamp(base.dailyRainfall + dayShift * 1.5, 0, 260).toFixed(0),
    avgAirTemp: +clamp(base.avgAirTemp + dayShift * 0.2, 10, 45).toFixed(0),
    relativeHumidity: +clamp(base.relativeHumidity + dayShift * 0.6, 30, 99).toFixed(0),
    soilOrganicMatter: +clamp(base.soilOrganicMatter + dayShift * 0.02, 1, 12).toFixed(2),
    soilAcidity: +clamp(base.soilAcidity + dayShift * 0.006, 4.5, 8.5).toFixed(1),
    soilPhosphorus: +clamp(base.soilPhosphorus + dayShift * 0.24, 5, 90).toFixed(1),
    soilPotassium: +clamp(base.soilPotassium + dayShift * 0.9, 80, 450).toFixed(2),
    soilConductivity: +clamp(base.soilConductivity + dayShift * 0.01, 0.2, 3).toFixed(2)
  }
})
const metricDisplay = computed(() => {
  const w = realtimeData.value?.weather
  const s = realtimeData.value?.soil

  function fmt(val, decimals, unit) {
    if (val == null || !Number.isFinite(Number(val))) return '--'
    return Number(val).toFixed(decimals)
  }

  return {
    sunshineHours:     { value: fmt(w?.sunshine_hours, 1),        unit: 'h' },
    avgWindSpeed:      { value: fmt(w?.wind_speed, 2),           unit: 'm/s' },
    dailyRainfall:     { value: fmt(w?.precipitation, 1),         unit: 'mm' },
    avgAirTemp:        { value: fmt(w?.temperature, 1),           unit: '℃' },
    relativeHumidity:  { value: fmt(w?.humidity, 1),              unit: '%' },
    soilOrganicMatter: { value: fmt(s?.organic_matter, 2),        unit: '%' },
    soilAcidity:       { value: fmt(s?.ph, 2),                   unit: 'ph' },
    soilPhosphorus:    { value: fmt(s?.phosphorus, 1),            unit: 'mg/kg' },
    soilPotassium:     { value: fmt(s?.potassium, 2),            unit: 'mg/kg' },
    soilConductivity:  { value: fmt(s?.conductivity, 2),          unit: 'dS/m' },
  }
})

const cropHealthIndex = computed(() => {
  const station = activeStation.value
  const climateScore = weightedAverage([
    { score: scoreByRange(realtimeData.value?.weather?.temperature ?? station.avgAirTemp, 24, 32, 18, 38), weight: 0.3 },
    { score: scoreByRange(realtimeData.value?.weather?.humidity ?? station.relativeHumidity, 65, 85, 45, 95), weight: 0.3 },
    { score: scoreByRange(realtimeData.value?.weather?.sunshine_hours ?? station.sunshineHours, 4, 8, 2, 11), weight: 0.2 },
    { score: scoreByRange(realtimeData.value?.weather?.wind_speed ?? station.avgWindSpeed, 0.8, 2.5, 0.2, 5), weight: 0.2 }
  ])
  const riskPenalty = getRiskPenalty(stationRiskLevelMap.value[station.code] || 'normal')
  return Math.max(0, Math.min(100, Math.round(climateScore - riskPenalty)))
})

const soilActivityIndex = computed(() => {
  const station = activeStation.value
  const soilScore = weightedAverage([
    { score: scoreByRange(station.moisture, 35, 70, 20, 90), weight: 0.35 },
    { score: scoreByRange(realtimeData.value?.soil?.ph ?? station.soilAcidity, 5.8, 6.8, 5.0, 7.8), weight: 0.25 },
    { score: scoreByRange(realtimeData.value?.soil?.organic_matter ?? station.soilOrganicMatter, 3.5, 6.0, 2.0, 8.5), weight: 0.2 },
    { score: scoreByRange(realtimeData.value?.soil?.conductivity ?? station.soilConductivity, 0.6, 1.4, 0.2, 2.4), weight: 0.2 }
  ])
  const riskPenalty = getRiskPenalty(stationRiskLevelMap.value[station.code] || 'normal') * 0.4
  return Math.max(0, Math.min(100, Math.round(soilScore - riskPenalty)))
})

const activeDecisionMetrics = computed(() => {
  const station = activeStation.value
  const riskLevel = stationRiskLevelMap.value[station.code] || 'normal'
  const avgTemp = realtimeData.value?.weather?.temperature ?? station.avgAirTemp
  const growthPeriod = getGrowthPeriodByCalendar(
    selectedYear.value,
    selectedMonth.value,
    selectedDay.value,
    avgTemp
  )
  const stageFactor = getStageYieldFactor(growthPeriod)

  const om = realtimeData.value?.soil?.organic_matter ?? station.soilOrganicMatter
  const sp = realtimeData.value?.soil?.phosphorus ?? station.soilPhosphorus
  const sk = realtimeData.value?.soil?.potassium ?? station.soilPotassium
  const potentialYield = clamp(
    450 + om * 18 + (sp - 30) * 1.2 + (sk - 180) * 0.18,
    420,
    680
  )

  const envFactor =
    normalizeIndex(cropHealthIndex.value) * 0.55 +
    normalizeIndex(soilActivityIndex.value) * 0.45

  const stationItems = inspectItems.value
  const diseaseStress = stationItems
    .filter((item) => item.key.startsWith('leaf_'))
    .reduce((sum, item) => sum + (item.level === 'danger' ? 0.22 : item.level === 'warn' ? 0.1 : 0), 0)
  const pestStress = stationItems
    .filter((item) => item.key.startsWith('pest_'))
    .reduce((sum, item) => sum + (item.level === 'danger' ? 0.24 : item.level === 'warn' ? 0.11 : 0), 0)

  const riskStress = riskLevel === 'danger' ? 0.12 : riskLevel === 'warn' ? 0.06 : 0
  const totalStress = clamp(diseaseStress * 0.55 + pestStress * 0.45 + riskStress, 0, 0.58)
  const currentProtectionFactor = 1 - totalStress

  const expectedYield = potentialYield * envFactor * stageFactor * currentProtectionFactor

  const improvedDiseaseStress = diseaseStress * 0.62
  const improvedPestStress = pestStress * 0.56
  const improvedTotalStress = clamp(improvedDiseaseStress * 0.55 + improvedPestStress * 0.45 + riskStress * 0.7, 0, 0.42)
  const improvedProtectionFactor = 1 - improvedTotalStress
  const recoveryYield = potentialYield * envFactor * stageFactor * improvedProtectionFactor

  const expectedRounded = hdfsExpectedYield.value != null
    ? hdfsExpectedYield.value
    : null
  const recoveryRounded = hdfsRecoveryYield.value != null
    ? hdfsRecoveryYield.value
    : null
  const recoveryProgress = recoveryRounded != null
    ? Number(clamp((recoveryRounded / Math.max(expectedRounded ?? potentialYield, 1)) * 100, 20, 98).toFixed(0))
    : 0

  return {
    growthPeriod,
    expectedYield: expectedRounded,
    recoveryYield: recoveryRounded,
    recoveryProgress
  }
})

function selectStation(id) {
  activeStationId.value = id
}

function toggleDetailPopup(type) {
  activeDetailPopup.value = activeDetailPopup.value === type ? '' : type
}

function openPlanDialog(planType) {
  activePlanDialog.value = planType
}

function closePlanDialog() {
  activePlanDialog.value = ''
}

function getPlanHdfsName(planType) {
  if (planType === 'A') {
    const keys = hdfsData.value?.main_output?.output2 ? Object.keys(hdfsData.value.main_output.output2) : []
    const fullKey = keys.find(k => k.startsWith('方案A'))
    if (fullKey) return fullKey
  }
  const keys = hdfsData.value?.main_output?.output3 ? Object.keys(hdfsData.value.main_output.output3) : []
  const fullKey = keys.find(k => k.startsWith('方案B'))
  if (fullKey) return fullKey
  return null
}

const planDialogTitle = computed(() => {
  const hdfsName = getPlanHdfsName(activePlanDialog.value)
  if (hdfsName) return hdfsName
  return activePlanDialog.value === 'A' ? '方案A（高效高成本快控型）' : '方案B（经济稳控强化农艺型）'
})

const planDialogPhases = computed(() => {
  const outputKey = activePlanDialog.value === 'A' ? 'output2' : 'output3'
  const planPrefix = activePlanDialog.value === 'A' ? '方案A' : '方案B'
  const planObj = findPlanInOutput(hdfsData.value?.main_output?.[outputKey], planPrefix)
  return mapHdfsPlanPhases(planObj)
})

const planDialogNotes = computed(() => {
  const outputKey = activePlanDialog.value === 'A' ? 'output2' : 'output3'
  const planPrefix = activePlanDialog.value === 'A' ? '方案A' : '方案B'
  const planObj = findPlanInOutput(hdfsData.value?.main_output?.[outputKey], planPrefix)
  return planObj?.['通用注意事项'] || null
})

const planDialogFallback = computed(() => {
  if (hdfsAttempted.value && !planDialogPhases.value) {
    return ['暂无HDFS数据，请确认该日期和站点的数据已上传。']
  }
  if (!planDialogPhases.value) {
    return activePlanDialog.value === 'A'
      ? [
          '24小时内完成虫口密度复核，重点排查稻飞虱与二化螟高发区。',
          '优先对高风险田块实施定点喷施，并保留10%的空白对照区进行效果评估。',
          '48小时后复测害虫数量，若下降低于30%，切换联合防控（生物+化学）。',
          '同步清理田埂杂草与积水，降低虫卵孳生环境。'
        ]
      : [
          '先完成病斑分布抽样，标注细菌性叶枯病与东格鲁高风险区块。',
          '分区施用抑菌剂并补充叶面营养，控制病斑扩展速度。',
          '加强水肥管理，避免连续高湿；必要时进行排水降湿。',
          '72小时后复拍并复判，若发病率仍上升，执行加强轮次防治。'
        ]
  }
  return null
})

const detailPopupTitle = computed(() => {
  if (activeDetailPopup.value === 'inspect') return '田间巡检详情'
  if (activeDetailPopup.value === 'analysis') return '环境分析详情'
  if (activeDetailPopup.value === 'decision') return '决策推演详情'
  return ''
})

const detailPopupRows = computed(() => {
  if (hdfsLoading.value) {
    const loadingLabels = {
      inspect: ['细菌性叶枯病', '褐斑病', '东格鲁病毒病', '稻飞虱', '二化螟', '稻纵卷叶螟'],
      analysis: ['温度条件', '湿度条件', '降水条件', '风速条件', '土壤pH', '土壤养分', '有机质含量', '土壤电导率'],
      decision: ['预计产量', '预计减产', '叶害影响', '虫害影响', '气象影响', '土壤影响'],
    }[activeDetailPopup.value] || []
    return loadingLabels.map((label) => ({ label, value: '', level: 'normal', loading: true }))
  }
  if (activeDetailPopup.value === 'inspect') {
    const hdfsItems = mapHdfsInspectItems(hdfsData.value?.disease_output)
    if (hdfsItems) return hdfsItems
    return [
      { label: '细菌性叶枯病', value: '--', level: 'normal' },
      { label: '褐斑病', value: '--', level: 'normal' },
      { label: '东格鲁病毒病', value: '--', level: 'normal' },
      { label: '稻飞虱', value: '--', level: 'normal' },
      { label: '二化螟', value: '--', level: 'normal' },
      { label: '稻纵卷叶螟', value: '--', level: 'normal' },
    ]
  }
  if (activeDetailPopup.value === 'analysis') {
    const hdfsItems = mapHdfsAnalysisItems(hdfsData.value?.weather_output, hdfsData.value?.soil_output)
    if (hdfsItems) return hdfsItems
    return [
      { label: '温度条件', value: '--' },
      { label: '湿度条件', value: '--' },
      { label: '降水条件', value: '--' },
      { label: '风速条件', value: '--' },
      { label: '土壤pH', value: '--' },
      { label: '土壤养分', value: '--' },
      { label: '有机质含量', value: '--' },
      { label: '土壤电导率', value: '--' },
    ]
  }
  if (activeDetailPopup.value === 'decision') {
    const hdfsItems = mapHdfsDecisionItems(hdfsData.value?.main_output?.output1)
    if (hdfsItems) return hdfsItems
    return [
      { label: '预计产量', value: '--' },
      { label: '预计减产', value: '--' },
      { label: '叶害影响', value: '--' },
      { label: '虫害影响', value: '--' },
      { label: '气象影响', value: '--' },
      { label: '土壤影响', value: '--' },
    ]
  }
  return []
})

function openRecognitionView() {
  clearRecognitionState()
  showRecognitionView.value = true
}

function closeRecognitionView() {
  showRecognitionView.value = false
  clearRecognitionState()
}

function openHistoryChartsView() {
  showHistoryCharts.value = true
}

function closeHistoryChartsView() {
  showHistoryCharts.value = false
}

function openFilePicker(type) {
  if (type === 'leaf') {
    leafFileInput.value?.click()
    return
  }
  pestFileInput.value?.click()
}

function formatConfidence(value) {
  if (!Number.isFinite(value) || value <= 0) return '--'
  return `${(value * 100).toFixed(1)}%`
}

function getPestCount(typeLabel) {
  return Number(pestResult.value?.pestCounts?.[typeLabel] ?? 0)
}

function formatDateValue(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function getCurrentGrowthPeriod() {
  return activeDecisionMetrics.value.growthPeriod
}

function getCurrentGrowthStatus() {
  const level = stationRiskLevelMap.value[activeStation.value.code] || 'normal'
  if (level === 'danger') return '较差'
  if (level === 'warn') return '一般'
  return '良好'
}

function buildMonitoringRecord() {
  // Model confidence is NOT disease coverage rate.
  // When a disease is detected in a spot-check image, use a moderate coverage
  // estimate (15%) to indicate "observed but severity unknown" → warn level.
  // The definitive coverage rate comes from pest_data field surveys (imported CSV).
  const leafClassName = String(leafResult.value?.raw?.className ?? '')
  const leafLabel = String(leafResult.value?.label ?? '')
  const hasDamage = leafResult.value?.raw?.hasLeafDamage

  let bacterialLeafBlightRate = 0
  let brownSpotRate = 0
  let tungroVirusRate = 0

  if (hasDamage) {
    const DETECTED_RATE = 15  // moderate estimate, backend maps 10–50 → warn
    if (leafClassName === 'Bacterial Leaf Blight' || leafLabel.includes('叶枯病')) {
      bacterialLeafBlightRate = DETECTED_RATE
    } else if (leafClassName === 'Brown Spot' || leafLabel.includes('褐斑病')) {
      brownSpotRate = DETECTED_RATE
    } else if (leafClassName === 'Tungro Virus' || leafLabel.includes('东格鲁')) {
      tungroVirusRate = DETECTED_RATE
    }
  }

  return {
    point: activeStation.value.code,
    Date: formatDateValue(selectedYear.value, selectedMonth.value, selectedDay.value),
    GrowthPeriod: getCurrentGrowthPeriod(),
    GrowthStatus: getCurrentGrowthStatus(),
    BacterialLeafBlightRate: bacterialLeafBlightRate,
    BrownSpotRate: brownSpotRate,
    TungroVirusRate: tungroVirusRate,
    PestRphNum: Number(pestResult.value?.pestCounts?.['褐飞虱'] ?? pestResult.value?.pestCounts?.['稻飞虱'] ?? 0),
    PestScsNum: Number(pestResult.value?.pestCounts?.['二化螟'] ?? 0),
    PestCmNum: Number(pestResult.value?.pestCounts?.['稻纵卷叶螟'] ?? 0)
  }
}

async function syncMonitoringRecord() {
  const record = buildMonitoringRecord()
  await saveMonitoringRecord(record)
}

function getStationInspectItems(stationCode) {
  const currentDateMap = getDateInspectMap()
  if (!currentDateMap[stationCode]) {
    currentDateMap[stationCode] = INSPECT_DEFAULT_ITEMS.map((item) => ({ ...item }))
  }
  return currentDateMap[stationCode]
}

function loadInspectMapFromStorage() {
  const raw = window.localStorage.getItem(INSPECT_STORAGE_KEY)
  if (!raw) {
    stationInspectMapByDate.value = { [selectedDateKey.value]: createDefaultStationInspectMap() }
    return
  }
  try {
    const parsed = JSON.parse(raw)
    const nextMapByDate = {}
    for (const [dateKey, stationMap] of Object.entries(parsed ?? {})) {
      if (typeof dateKey !== 'string' || !stationMap || typeof stationMap !== 'object') continue
      nextMapByDate[dateKey] = {}
      for (const station of stationData.value) {
        const rawItems = Array.isArray(stationMap?.[station.code]) ? stationMap[station.code] : []
        const itemLevelMap = Object.fromEntries(
          rawItems.map((item) => [item?.key, item?.level]).filter(([key]) => typeof key === 'string')
        )
        nextMapByDate[dateKey][station.code] = INSPECT_DEFAULT_ITEMS.map((item) => {
          const loadedLevel = itemLevelMap[item.key]
          const level = STATION_LEVEL_PRIORITY[loadedLevel] !== undefined ? loadedLevel : 'normal'
          return { ...item, level }
        })
      }
    }
    stationInspectMapByDate.value = nextMapByDate
    getDateInspectMap()
  } catch (error) {
    window.localStorage.removeItem(INSPECT_STORAGE_KEY)
    stationInspectMapByDate.value = { [selectedDateKey.value]: createDefaultStationInspectMap() }
  }
}

function persistInspectMapToStorage(value) {
  window.localStorage.setItem(INSPECT_STORAGE_KEY, JSON.stringify(value))
}

function persistSelectedDateToStorage() {
  window.localStorage.setItem(
    DATE_SELECTION_STORAGE_KEY,
    JSON.stringify({
      year: selectedYear.value,
      month: selectedMonth.value,
      day: selectedDay.value
    })
  )
}

function loadSelectedDateFromStorage() {
  const raw = window.localStorage.getItem(DATE_SELECTION_STORAGE_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    const year = Number(parsed?.year)
    const month = Number(parsed?.month)
    const day = Number(parsed?.day)
    if (Number.isFinite(year) && year >= 1900 && year <= 9999) {
      selectedYear.value = Math.round(year)
    }
    if (Number.isFinite(month) && month >= 1 && month <= 12) {
      selectedMonth.value = Math.round(month)
    }
    const maxDay = getDaysInMonth(selectedYear.value, selectedMonth.value)
    if (Number.isFinite(day)) {
      selectedDay.value = clamp(Math.round(day), 1, maxDay)
    } else {
      selectedDay.value = clamp(selectedDay.value, 1, maxDay)
    }
  } catch (_error) {
    window.localStorage.removeItem(DATE_SELECTION_STORAGE_KEY)
  }
}

function setInspectLevel(itemKey, level, stationCode = activeStation.value.code) {
  const stationItems = getStationInspectItems(stationCode)
  const item = stationItems.find((inspectItem) => inspectItem.key === itemKey)
  if (item) {
    item.level = level
    // 避免用户在识别后立即刷新，深层 watch 尚未落盘导致状态丢失。
    persistInspectMapToStorage(stationInspectMapByDate.value)
  }
}

function mergeInspectLevel(currentLevel, nextLevel) {
  const currentPriority = STATION_LEVEL_PRIORITY[currentLevel] ?? 0
  const nextPriority = STATION_LEVEL_PRIORITY[nextLevel] ?? 0
  return nextPriority > currentPriority ? nextLevel : currentLevel
}

async function loadInspectMapFromServer(dateKey = selectedDateKey.value) {
  try {
    const payload = await fetchMonitoringState(dateKey)
    const stations = payload?.stations ?? {}
    const dateMap = getDateInspectMap(dateKey)
    for (const station of stationData.value) {
      const serverItems = Array.isArray(stations?.[station.code]) ? stations[station.code] : []
      const levelMap = Object.fromEntries(
        serverItems.map((item) => [item?.key, item?.level]).filter(([key]) => typeof key === 'string')
      )
      const localItems = Array.isArray(dateMap[station.code]) ? dateMap[station.code] : INSPECT_DEFAULT_ITEMS
      const localLevelMap = Object.fromEntries(localItems.map((item) => [item.key, item.level]))
      dateMap[station.code] = INSPECT_DEFAULT_ITEMS.map((item) => {
        const localLevel = localLevelMap[item.key] ?? 'normal'
        const serverLevel = STATION_LEVEL_PRIORITY[levelMap[item.key]] !== undefined ? levelMap[item.key] : 'normal'
        return { ...item, level: mergeInspectLevel(localLevel, serverLevel) }
      })
    }
  } catch (_error) {
    // 网络或后端异常时保留本地状态，不中断页面使用。
  }
}

function getCountLevel(count) {
  if (count >= 2) return 'danger'
  if (count >= 1) return 'warn'
  return 'normal'
}

function applyLeafInspection(result) {
  const stationCode = activeStation.value.code
  if (!result?.raw?.hasLeafDamage) {
    return
  }

  const className = String(result?.raw?.className ?? '')
  const label = String(result?.label ?? '')
  const matchedLabel = LEAF_RISK_LEVEL_MAP[className] ? className : label
  const nextLevel = LEAF_RISK_LEVEL_MAP[matchedLabel] ?? 'warn'
  if (label.includes('叶枯病')) {
    const currentLevel = getStationInspectItems(stationCode).find((item) => item.key === 'leaf_blight')?.level ?? 'normal'
    setInspectLevel('leaf_blight', mergeInspectLevel(currentLevel, nextLevel), stationCode)
  } else if (label.includes('褐斑病')) {
    const currentLevel = getStationInspectItems(stationCode).find((item) => item.key === 'leaf_brown_spot')?.level ?? 'normal'
    setInspectLevel('leaf_brown_spot', mergeInspectLevel(currentLevel, nextLevel), stationCode)
  } else if (label.includes('东格鲁')) {
    const currentLevel = getStationInspectItems(stationCode).find((item) => item.key === 'leaf_tungro')?.level ?? 'normal'
    setInspectLevel('leaf_tungro', mergeInspectLevel(currentLevel, nextLevel), stationCode)
  }
}

function applyPestInspection(result) {
  const stationCode = activeStation.value.code
  const counts = result?.pestCounts ?? {}
  const pestUpdates = [
    { key: 'pest_borer', count: Number(counts['二化螟'] ?? 0) },
    { key: 'pest_leafroller', count: Number(counts['稻纵卷叶螟'] ?? 0) },
    { key: 'pest_planthopper', count: Number(counts['褐飞虱'] ?? counts['稻飞虱'] ?? 0) }
  ]

  for (const update of pestUpdates) {
    const nextLevel = getCountLevel(update.count)
    if (nextLevel === 'normal') continue
    const currentLevel = getStationInspectItems(stationCode).find((item) => item.key === update.key)?.level ?? 'normal'
    setInspectLevel(update.key, mergeInspectLevel(currentLevel, nextLevel), stationCode)
  }
}

function resetObjectUrl(urlRef) {
  if (urlRef.value) {
    URL.revokeObjectURL(urlRef.value)
    urlRef.value = ''
  }
}

function clearRecognitionState() {
  leafResult.value = null
  pestResult.value = null
  leafError.value = ''
  pestError.value = ''
  pestAnnotatedUrl.value = ''
  resetObjectUrl(leafPreviewUrl)
  resetObjectUrl(pestPreviewUrl)
}

async function handleLeafFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  resetObjectUrl(leafPreviewUrl)
  leafPreviewUrl.value = URL.createObjectURL(file)
  leafLoading.value = true
  leafError.value = ''
  try {
    leafResult.value = await identifyLeafDamage(file, activeStation.value.code)
    applyLeafInspection(leafResult.value)
    await syncMonitoringRecord()
  } catch (error) {
    if (!leafResult.value) {
      leafResult.value = null
      leafError.value = error instanceof Error ? error.message : '叶害识别失败'
    } else {
      leafError.value = error instanceof Error ? `识别成功，但监测数据保存失败：${error.message}` : '识别成功，但监测数据保存失败'
    }
  } finally {
    leafLoading.value = false
  }
}

async function handlePestFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  resetObjectUrl(pestPreviewUrl)
  pestPreviewUrl.value = URL.createObjectURL(file)
  pestAnnotatedUrl.value = ''
  pestLoading.value = true
  pestError.value = ''
  try {
    pestResult.value = await identifyPestDamage(file, activeStation.value.code)
    applyPestInspection(pestResult.value)
    if (pestResult.value?.annotatedImageBase64) {
      pestAnnotatedUrl.value = `data:image/jpeg;base64,${pestResult.value.annotatedImageBase64}`
    }
    await syncMonitoringRecord()
  } catch (error) {
    if (!pestResult.value) {
      pestResult.value = null
      pestError.value = error instanceof Error ? error.message : '虫害识别失败'
    } else {
      pestError.value = error instanceof Error ? `识别成功，但监测数据保存失败：${error.message}` : '识别成功，但监测数据保存失败'
    }
  } finally {
    pestLoading.value = false
  }
}

function selectDay(day) {
  selectedDay.value = day
}

function shiftMonth(step) {
  const next = selectedMonth.value + step
  if (next > 12) {
    selectedMonth.value = 1
    selectedYear.value += 1
    return
  }
  if (next < 1) {
    selectedMonth.value = 12
    selectedYear.value -= 1
    return
  }
  selectedMonth.value = next
}

function shiftYear(step) {
  selectedYear.value += step
}

function applyYearInput() {
  const parsedYear = Number.parseInt(yearInput.value.trim(), 10)

  if (Number.isNaN(parsedYear)) {
    yearInput.value = String(selectedYear.value)
    return
  }

  selectedYear.value = Math.min(9999, Math.max(1900, parsedYear))
  yearInput.value = String(selectedYear.value)
}

watch([selectedYear, selectedMonth], () => {
  if (selectedDay.value > daysInCurrentMonth.value) {
    selectedDay.value = daysInCurrentMonth.value
  }
})

watch(selectedYear, (year) => {
  yearInput.value = String(year)
})

watch(
  stationInspectMapByDate,
  (value) => {
    persistInspectMapToStorage(value)
  },
  { deep: true }
)

watch([selectedYear, selectedMonth, selectedDay], () => {
  persistSelectedDateToStorage()
})

onMounted(() => {
  loadSelectedDateFromStorage()
  loadInspectMapFromStorage()
  loadInspectMapFromServer()
  loadHdfsData()
  loadRealtimeData()
  beijingTimer = window.setInterval(() => {
    beijingNow.value = getBeijingDateParts()
  }, 1000)
})

watch(selectedDateKey, (dateKey) => {
  loadInspectMapFromServer(dateKey)
})

watch([selectedDateKey, () => activeStation.value?.code], () => {
  loadHdfsData()
  loadRealtimeData()
})

onBeforeUnmount(() => {
  if (beijingTimer !== null) {
    window.clearInterval(beijingTimer)
  }
  resetObjectUrl(leafPreviewUrl)
  resetObjectUrl(pestPreviewUrl)
})
</script>

<template>
  <main class="agri-board">
    <template v-if="!showHistoryCharts">
    <header class="top-header panel">
      <div class="top-main">
        <div class="top-side top-side-left">
          <div class="date-box">{{ formattedBeijingDateTime }}</div>
        </div>
        <div class="title-box">
          <span class="title-decor title-decor-left"></span>
          <div class="title-core">
            <h1>数智稻安</h1>
            <span class="title-glow"></span>
          </div>
          <span class="title-decor title-decor-right"></span>
        </div>
        <div class="top-side top-side-right">
          <div class="quick-data">
            <span>站点总数：25</span>
            <span>在线率：98%</span>
            <span>当前日期：{{ selectedMonth }}月{{ selectedDay }}日</span>
          </div>
        </div>
      </div>

      <div class="timeline-bar">
        <div class="timeline-year-nav">
          <button class="year-nav-btn" @click="shiftYear(-1)">‹</button>
          <input
            v-model="yearInput"
            class="year-nav-input"
            type="text"
            inputmode="numeric"
            maxlength="4"
            @blur="applyYearInput"
            @keyup.enter="applyYearInput"
          />
          <button class="year-nav-btn" @click="shiftYear(1)">›</button>
        </div>
        <div class="timeline-month">
          <button class="month-nav" @click="shiftMonth(-1)">‹</button>
          <span>{{ formattedYearMonth }}</span>
          <button class="month-nav" @click="shiftMonth(1)">›</button>
        </div>
        <div class="timeline-days" :style="{ gridTemplateColumns: `repeat(${dayOptions.length}, minmax(18px, 1fr))` }">
          <button
            v-for="day in dayOptions"
            :key="day"
            class="day-point"
            :class="{ active: day === selectedDay }"
            @click="selectDay(day)"
          >
            <i class="dot"></i>
            <span>{{ day }}</span>
          </button>
        </div>
      </div>
    </header>

    <section v-if="!showRecognitionView" class="content-grid">
      <article class="field-panel panel">
        <div class="panel-head">
          <h2>农田监测 · 区块站点图</h2>
          <span>当前站点：{{ activeStation.name }}</span>
        </div>

        <div class="field-map" :style="fieldMapStyle">
          <button
            v-for="(station, idx) in stationData"
            :key="station.id"
            class="station-dot"
            :class="[stationRiskLevelMap[station.code] || 'normal', { active: station.id === activeStationId }]"
            :style="{
              top: `${station.y}%`,
              left: `${station.x}%`
            }"
            @click="selectStation(station.id)"
          >
            <span>{{ station.id }}</span>
          </button>
          <div v-if="activeDetailPopup" class="map-detail-popup">
            <div class="map-detail-title">{{ detailPopupTitle }}</div>
            <div class="map-detail-body">
              <div
                v-for="row in detailPopupRows"
                :key="row.label"
                class="map-detail-row"
              >
                <span>{{ row.label }}</span>
                <b v-if="row.loading" class="loading-bar"></b>
                <b v-else :class="row.level ? `status-${row.level}` : ''">{{ row.value }}</b>
              </div>
            </div>
            <button
              v-if="hdfsData"
              class="map-suggestion-btn"
              @click="openSuggestionDialog(activeDetailPopup)"
            >查看防治建议</button>
          </div>
        </div>

        <div class="metrics-row">
          <div class="metric">
            <label>日照时长</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>h</small></strong>
            <strong v-else>{{ metricDisplay.sunshineHours.value }}<small>{{ metricDisplay.sunshineHours.value !== '--' ? metricDisplay.sunshineHours.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>日平均风速</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>m/s</small></strong>
            <strong v-else>{{ metricDisplay.avgWindSpeed.value }}<small>{{ metricDisplay.avgWindSpeed.value !== '--' ? metricDisplay.avgWindSpeed.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>日降水量</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>mm</small></strong>
            <strong v-else>{{ metricDisplay.dailyRainfall.value }}<small>{{ metricDisplay.dailyRainfall.value !== '--' ? metricDisplay.dailyRainfall.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>日平均温度</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>℃</small></strong>
            <strong v-else>{{ metricDisplay.avgAirTemp.value }}<small>{{ metricDisplay.avgAirTemp.value !== '--' ? metricDisplay.avgAirTemp.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>日相对湿度</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>%</small></strong>
            <strong v-else>{{ metricDisplay.relativeHumidity.value }}<small>{{ metricDisplay.relativeHumidity.value !== '--' ? metricDisplay.relativeHumidity.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>土壤有机质</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>%</small></strong>
            <strong v-else>{{ metricDisplay.soilOrganicMatter.value }}<small>{{ metricDisplay.soilOrganicMatter.value !== '--' ? metricDisplay.soilOrganicMatter.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>土壤酸碱度</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>ph</small></strong>
            <strong v-else>{{ metricDisplay.soilAcidity.value }}<small>{{ metricDisplay.soilAcidity.value !== '--' ? metricDisplay.soilAcidity.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>土壤磷含量</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>mg/kg</small></strong>
            <strong v-else>{{ metricDisplay.soilPhosphorus.value }}<small>{{ metricDisplay.soilPhosphorus.value !== '--' ? metricDisplay.soilPhosphorus.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>土壤钾含量</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>mg/kg</small></strong>
            <strong v-else>{{ metricDisplay.soilPotassium.value }}<small>{{ metricDisplay.soilPotassium.value !== '--' ? metricDisplay.soilPotassium.unit : '' }}</small></strong>
          </div>
          <div class="metric">
            <label>土壤电导率</label>
            <strong v-if="realtimeLoading && !realtimeAttempted" class="metric-loading">--<small>dS/m</small></strong>
            <strong v-else>{{ metricDisplay.soilConductivity.value }}<small>{{ metricDisplay.soilConductivity.value !== '--' ? metricDisplay.soilConductivity.unit : '' }}</small></strong>
          </div>
        </div>
      </article>

      <aside class="right-panels">
        <section class="panel detail-panel">
          <h3>站点详情</h3>
          <ul>
            <li><span>编号</span><b>{{ activeStation.code }}</b></li>
            <li>
              <span>运行状态</span>
              <b :class="`status-${activeStationStatusLevel}`">{{ activeStationStatusText }}</b>
            </li>
            <li><span>最后上报</span><b>30 秒前</b></li>
          </ul>
        </section>

        <section class="panel inspect-panel">
          <div class="inspect-head">
            <h3>田间巡检</h3>
            <button class="detail-trigger" @click="toggleDetailPopup('inspect')">详情</button>
          </div>
          <div class="inspect-list">
            <div
              v-for="item in inspectItems"
              :key="item.key"
              class="inspect-item"
            >
              <em class="level" :class="item.level">
                {{ item.level === 'danger' ? '严重' : item.level === 'warn' ? '预警' : '正常' }}
              </em>
              <b>{{ item.name }}</b>
            </div>
          </div>
          <div class="inspect-action-wrap">
            <button class="inspect-action-btn" @click="openRecognitionView">叶/虫害识别</button>
          </div>
        </section>

        <section class="panel analysis-panel">
          <div class="analysis-head">
            <h3>环境分析</h3>
            <button class="detail-trigger" @click="toggleDetailPopup('analysis')">详情</button>
          </div>
          <div class="progress">
            <label>
              作物健康指数
              <b>{{ cropHealthIndex }}%</b>
            </label>
            <div class="bar"><i :style="{ width: `${cropHealthIndex}%` }"></i></div>
          </div>
          <div class="progress">
            <label>
              土壤活性指数
              <b>{{ soilActivityIndex }}%</b>
            </label>
            <div class="bar"><i :style="{ width: `${soilActivityIndex}%` }"></i></div>
          </div>
          <div class="inspect-action-wrap">
            <button class="inspect-action-btn" @click="openHistoryChartsView">历史图表分析</button>
          </div>
        </section>

        <section class="panel suggest-panel">
          <div class="suggest-head">
            <h3>决策推演</h3>
            <button class="detail-trigger" @click="toggleDetailPopup('decision')">详情</button>
          </div>
          <div class="suggest-content">
            <p>
              预计产量：<b>{{ activeDecisionMetrics.expectedYield != null ? activeDecisionMetrics.expectedYield.toFixed(2) + '公斤/亩' : '--' }}</b>
              <span>生长阶段：{{ activeDecisionMetrics.growthPeriod }}</span>
            </p>
            <p>恢复产量：<b>{{ activeDecisionMetrics.recoveryYield != null ? activeDecisionMetrics.recoveryYield.toFixed(2) + '公斤/亩' : '--' }}</b></p>

            <div class="suggest-progress">
              <i :style="{ width: `${activeDecisionMetrics.recoveryProgress}%` }"></i>
              <em>{{ activeDecisionMetrics.recoveryYield != null ? activeDecisionMetrics.recoveryYield.toFixed(2) + '公斤/亩' : '--' }}</em>
            </div>
          </div>

          <div class="suggest-actions">
            <button class="suggest-btn" @click="openPlanDialog('A')">方案A</button>
            <button class="suggest-btn" @click="openPlanDialog('B')">方案B</button>
          </div>
          <div class="crop-mark">禾</div>
        </section>
      </aside>
    </section>

    <section v-else class="recognition-view panel">
      <div class="recognition-head">
        <div>
          <h2>叶/虫害识别</h2>
          <p>当前站点：{{ activeStation.name }}（{{ activeStation.code }}）</p>
        </div>
        <button class="back-btn" @click="closeRecognitionView">返回大屏</button>
      </div>

      <div class="recognition-grid">
        <article class="recognition-card">
          <h3>叶害识别</h3>
          <p>上传或拖拽叶片图像，识别叶斑病、细菌性叶枯病等病害类型。</p>
          <input
            ref="leafFileInput"
            class="file-input"
            type="file"
            accept="image/*"
            @change="handleLeafFileChange"
          />
          <button class="action-btn" :disabled="leafLoading" @click="openFilePicker('leaf')">
            {{ leafLoading ? '识别中...' : '上传叶片图片' }}
          </button>
          <img v-if="leafPreviewUrl" class="recognition-image" :src="leafPreviewUrl" alt="叶害上传图片" />
          <p v-if="leafError" class="recognition-error">{{ leafError }}</p>
          <div v-else-if="leafResult" class="recognition-result">
            <span>识别结果：{{ leafResult.label }}</span>
            <span>置信度：{{ formatConfidence(leafResult.confidence) }}</span>
          </div>
        </article>

        <article class="recognition-card">
          <h3>虫害识别</h3>
          <p>上传或拖拽虫害图像，识别稻飞虱、二化螟等虫害类型。</p>
          <input
            ref="pestFileInput"
            class="file-input"
            type="file"
            accept="image/*"
            @change="handlePestFileChange"
          />
          <button class="action-btn" :disabled="pestLoading" @click="openFilePicker('pest')">
            {{ pestLoading ? '识别中...' : '上传虫害图片' }}
          </button>
          <img
            v-if="pestAnnotatedUrl || pestPreviewUrl"
            class="recognition-image"
            :src="pestAnnotatedUrl || pestPreviewUrl"
            alt="虫害识别结果图片"
          />
          <p v-if="pestError" class="recognition-error">{{ pestError }}</p>
          <div v-else-if="pestResult" class="recognition-result">
            <span class="pest-total">虫害总数：{{ pestResult.totalPestCount }} 只</span>
            <div class="pest-count-grid">
              <span v-for="typeLabel in pestTypeLabels" :key="typeLabel">
                {{ typeLabel }}：{{ getPestCount(typeLabel) }} 只
              </span>
            </div>
          </div>
        </article>
      </div>
    </section>
    <div v-if="activePlanDialog" class="plan-dialog-mask" @click.self="closePlanDialog">
      <section class="plan-dialog panel">
        <div class="plan-dialog-head">
          <h3>{{ planDialogTitle }}</h3>
          <button class="plan-close-btn" @click="closePlanDialog">关闭</button>
        </div>
        <!-- Fallback: simple text steps -->
        <ul v-if="planDialogFallback" class="plan-dialog-list">
          <li v-for="(step, idx) in planDialogFallback" :key="idx">
            <em>{{ idx + 1 }}</em>
            <span>{{ step }}</span>
          </li>
        </ul>
        <!-- HDFS: collapsible phases -->
        <div v-else-if="planDialogPhases" class="plan-phase-list">
          <div
            v-for="(phase, idx) in planDialogPhases.phases"
            :key="idx"
            class="plan-phase-item"
          >
            <div class="plan-phase-header" @click="togglePlanPhase(idx)">
              <em>{{ idx + 1 }}</em>
              <div class="plan-phase-header-text">
                <span class="plan-phase-name">{{ phase.title }}</span>
                <span class="plan-phase-target">{{ phase.target }}</span>
              </div>
              <span class="plan-phase-arrow">{{ expandedPlanPhases.includes(idx) ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedPlanPhases.includes(idx)" class="plan-phase-body">
              <div v-if="phase.leafOps" class="phase-ops-section">
                <h4>叶害防控/预防</h4>
                <div v-for="(ops, pestName) in phase.leafOps" :key="pestName" class="phase-pest-item">
                  <h5>{{ pestName }}</h5>
                  <p v-for="(value, key) in ops" :key="key" v-show="typeof value === 'string' && value !== '无操作' && value !== '无操作（未发生，无需用药）' && value !== '无操作（未发生，无需补防）'">
                    <b>{{ key }}：</b>{{ value }}
                  </p>
                </div>
              </div>
              <div v-if="phase.pestOps" class="phase-ops-section">
                <h4>虫害防控/预防</h4>
                <div v-for="(ops, pestName) in phase.pestOps" :key="pestName" class="phase-pest-item">
                  <h5>{{ pestName }}</h5>
                  <p v-for="(value, key) in ops" :key="key" v-show="typeof value === 'string' && value !== '无操作'">
                    <b>{{ key }}：</b>{{ value }}
                  </p>
                </div>
              </div>
            </div>
          </div>
          <!-- Notes section -->
          <div v-if="planDialogNotes" class="plan-phase-notes">
            <h4>通用注意事项</h4>
            <p v-for="(value, key) in planDialogNotes" :key="key" v-show="typeof value === 'string'">
              <b>{{ key }}：</b>{{ value }}
            </p>
            <p v-if="planDialogPhases.notes?.['兜底说明']"><b>兜底说明：</b>{{ planDialogPhases.notes['兜底说明'] }}</p>
          </div>
        </div>
      </section>
    </div>
    <!-- 防治建议弹窗 -->
    <div v-if="activeSuggestionType" class="plan-dialog-mask" @click.self="closeSuggestionDialog">
      <section class="plan-dialog panel suggestion-dialog">
        <div class="plan-dialog-head">
          <h3>{{ suggestionTitle }}</h3>
          <button class="plan-close-btn" @click="closeSuggestionDialog">关闭</button>
        </div>
        <div class="suggestion-body" v-html="suggestionContent"></div>
      </section>
    </div>
    </template>
    <HistoryCharts
      v-else
      :station-code="activeStation.code"
      :station-name="activeStation.name"
      :year="selectedYear"
      @back="closeHistoryChartsView"
    />
  </main>
</template>

<style scoped>
.agri-board {
  min-height: 100vh;
  height: 100%;
  padding: 20px;
  color: #dcf0ff;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 15% 12%, rgba(68, 166, 255, 0.2), transparent 40%),
    radial-gradient(circle at 90% 20%, rgba(6, 224, 255, 0.15), transparent 36%),
    #051437;
}

.panel {
  position: relative;
  border: 1px solid rgba(71, 161, 255, 0.35);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(15, 53, 115, 0.9), rgba(8, 29, 71, 0.88)),
    radial-gradient(circle at top, rgba(66, 184, 255, 0.12), transparent 42%);
  box-shadow:
    inset 0 0 28px rgba(18, 124, 255, 0.12),
    0 18px 36px rgba(3, 12, 34, 0.34);
  overflow: hidden;
}

.panel::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  border: 1px solid rgba(168, 229, 255, 0.08);
  pointer-events: none;
}

.panel::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  top: 0;
  height: 1px;
  background: linear-gradient(90deg, rgba(123, 216, 255, 0), rgba(123, 216, 255, 0.72), rgba(123, 216, 255, 0));
  opacity: 0.9;
  pointer-events: none;
}

.top-header {
  padding: 12px 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.top-main {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  min-height: 62px;
}

.top-side {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}

.top-side-left {
  justify-content: flex-start;
}

.top-side-right {
  justify-content: flex-end;
}

.title-box {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 18px;
  text-align: center;
  pointer-events: none;
}

.title-core {
  position: relative;
  min-width: 360px;
  padding: 2px 28px 8px;
}

.title-box h1 {
  margin: 4px 0 0;
  font-size: 38px;
  line-height: 1.05;
  letter-spacing: 6px;
  font-weight: 800;
  background: linear-gradient(180deg, #f8feff 12%, #bde9ff 52%, #70cfff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow:
    0 0 12px rgba(103, 211, 255, 0.36),
    0 0 26px rgba(39, 140, 255, 0.24);
}

.title-box h1::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: 120px;
  height: 10px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(95, 221, 255, 0.55), rgba(95, 221, 255, 0));
}

.sub-title {
  margin: 0;
  color: #79ddff;
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  text-shadow: 0 0 10px rgba(73, 192, 255, 0.28);
}

.title-decor {
  position: relative;
  width: 86px;
  height: 1px;
  background: linear-gradient(90deg, rgba(69, 203, 255, 0), rgba(69, 203, 255, 0.95));
  box-shadow: 0 0 10px rgba(69, 203, 255, 0.35);
}

.title-decor::before,
.title-decor::after {
  content: '';
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  border-radius: 999px;
}

.title-decor::before {
  right: -3px;
  width: 7px;
  height: 7px;
  background: #9be7ff;
  box-shadow: 0 0 12px rgba(127, 223, 255, 0.85);
}

.title-decor::after {
  right: 10px;
  width: 22px;
  height: 3px;
  background: rgba(129, 227, 255, 0.45);
}

.title-decor-left {
  transform: scaleX(-1);
}

.title-glow {
  position: absolute;
  left: 50%;
  bottom: -4px;
  transform: translateX(-50%);
  width: 74%;
  height: 22px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(68, 198, 255, 0.26), rgba(68, 198, 255, 0));
  filter: blur(8px);
}

.date-box {
  padding: 8px 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(14, 177, 255, 0.16), rgba(10, 80, 146, 0.16));
  border: 1px solid rgba(86, 180, 255, 0.42);
  box-shadow: inset 0 0 12px rgba(91, 197, 255, 0.08);
}

.quick-data {
  display: flex;
  gap: 16px;
  font-size: 14px;
  color: #b7e4ff;
  justify-content: flex-end;
}

.timeline-bar {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
}

.timeline-year-nav {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 180px;
  height: 34px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid rgba(86, 180, 255, 0.45);
  background: rgba(9, 38, 88, 0.62);
  box-shadow: inset 0 0 10px rgba(55, 145, 255, 0.12);
}

.year-nav-btn {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1px solid rgba(121, 214, 255, 0.45);
  background: rgba(5, 27, 70, 0.55);
  color: #d6f3ff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.year-nav-btn:hover {
  color: #e8faff;
  border-color: rgba(122, 208, 255, 0.72);
  background: rgba(17, 68, 138, 0.65);
}

.year-nav-input {
  min-width: 0;
  flex: 1;
  height: 24px;
  padding: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #f3fbff;
  font-size: 16px;
  letter-spacing: 1px;
  text-align: center;
}

.year-nav-input::selection {
  background: rgba(114, 198, 255, 0.35);
}

.timeline-month {
  flex: 0 0 auto;
  width: 180px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(86, 180, 255, 0.45);
  background: rgba(9, 38, 88, 0.62);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 10px;
  color: #f3fbff;
  font-size: 16px;
  box-shadow: inset 0 0 10px rgba(55, 145, 255, 0.12);
}

.timeline-month span {
  min-width: 0;
  flex: 1;
  text-align: center;
  letter-spacing: 1px;
}

.month-nav {
  width: 20px;
  height: 20px;
  border: 1px solid rgba(121, 214, 255, 0.45);
  border-radius: 6px;
  background: rgba(5, 27, 70, 0.55);
  color: #d6f3ff;
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.month-nav:hover {
  color: #e8faff;
  border-color: rgba(122, 208, 255, 0.72);
  background: rgba(17, 68, 138, 0.65);
}

.timeline-days {
  position: relative;
  display: grid;
  grid-template-columns: repeat(31, minmax(18px, 1fr));
  gap: 6px;
  width: 100%;
  padding-top: 2px;
}

.timeline-days::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 8px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1ea9de, #37d4ff, #1ea9de);
}

.day-point {
  position: relative;
  z-index: 1;
  border: none;
  background: transparent;
  color: #a6ddff;
  font-size: 11px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 0;
}

.day-point .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #bcefff;
  box-shadow: 0 0 0 2px rgba(61, 176, 226, 0.4);
}

.day-point:hover {
  color: #ddf7ff;
}

.day-point.active {
  color: #e8faff;
  font-weight: 700;
}

.day-point.active .dot {
  width: 12px;
  height: 12px;
  background: #ecffff;
  box-shadow:
    0 0 0 2px rgba(74, 184, 255, 0.65),
    0 0 8px rgba(130, 228, 255, 0.8);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(700px, 1fr) 340px;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.field-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 10px 14px;
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(22, 113, 197, 0.4), rgba(16, 65, 129, 0.16) 55%, rgba(16, 65, 129, 0));
  border: 1px solid rgba(102, 192, 255, 0.18);
  box-shadow: inset 0 0 14px rgba(39, 151, 255, 0.08);
}

.panel-head h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: 1px;
}

.panel-head span {
  color: #8fe4ff;
  font-size: 14px;
}

.field-map {
  flex: 1;
  width: 100%;
  aspect-ratio: 2508 / 1672;
  min-height: 520px;
  max-height: calc(100vh - 290px);
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(98, 180, 255, 0.42);
  background-position: center;
  background-size: 100% 100%;
  background-repeat: no-repeat;
  box-shadow:
    inset 0 0 0 1px rgba(224, 250, 255, 0.06),
    inset 0 -60px 120px rgba(2, 18, 44, 0.18);
}

.station-dot {
  position: absolute;
  width: 24px;
  height: 24px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: 2px solid rgba(228, 250, 255, 0.96);
  background: radial-gradient(circle, #93ff5a, #2e9408);
  color: #0d2b42;
  font-size: 0;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  isolation: isolate;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.station-dot::before,
.station-dot::after {
  content: '';
  position: absolute;
  inset: -5px;
  border-radius: 50%;
  border: 2px solid rgba(140, 255, 120, 0.45);
  opacity: 0;
  transform: scale(0.7);
  pointer-events: none;
  z-index: -1;
  animation: stationPulse 2.4s ease-out infinite;
}

.station-dot::after {
  animation-delay: 1.2s;
}

.station-dot:hover {
  transform: translate(-50%, -50%) scale(1.1);
}

.station-dot.normal {
  background: radial-gradient(circle, #93ff5a, #2e9408);
}

.station-dot.warn {
  background: radial-gradient(circle, #ffe08d, #d5961f);
}

.station-dot.warn::before,
.station-dot.warn::after {
  border-color: rgba(255, 205, 102, 0.52);
}

.station-dot.danger {
  background: radial-gradient(circle, #ff998a, #d03a20);
}

.station-dot.danger::before,
.station-dot.danger::after {
  border-color: rgba(255, 138, 120, 0.55);
}

.station-dot.active {
  box-shadow: 0 0 0 4px rgba(161, 221, 255, 0.3);
  transform: translate(-50%, -50%) scale(1.12);
}

.station-dot.active::before,
.station-dot.active::after {
  border-width: 3px;
}

@keyframes stationPulse {
  0% {
    opacity: 0.7;
    transform: scale(0.85);
  }

  70% {
    opacity: 0.18;
  }

  100% {
    opacity: 0;
    transform: scale(2.8);
  }
}

.metrics-row {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.metric {
  position: relative;
  border-radius: 14px;
  border: 1px solid rgba(93, 176, 255, 0.24);
  padding: 12px 12px 10px;
  background:
    linear-gradient(180deg, rgba(8, 32, 72, 0.76), rgba(8, 26, 59, 0.6)),
    radial-gradient(circle at top left, rgba(67, 194, 255, 0.14), transparent 40%);
  box-shadow:
    inset 0 0 14px rgba(72, 175, 255, 0.08),
    0 10px 20px rgba(3, 12, 34, 0.18);
}

.metric::before {
  content: '';
  position: absolute;
  left: 12px;
  top: 0;
  width: 42px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(93, 220, 255, 0.95), rgba(93, 220, 255, 0));
}

.metric label {
  color: #8edcff;
  font-size: 12px;
}

.metric strong {
  display: block;
  margin-top: 7px;
  font-size: 30px;
  line-height: 1;
  color: #f4fbff;
  text-shadow: 0 0 12px rgba(104, 215, 255, 0.15);
}

.metric strong small {
  margin-left: 2px;
  font-size: 18px;
  color: #8fd9ff;
  font-weight: 600;
}

.metric-loading {
  opacity: 0.5;
}

.right-panels {
  display: grid;
  grid-template-rows: 1.15fr 1fr 1fr 1fr;
  gap: 12px;
  min-height: 0;
}

.right-panels section {
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.right-panels h3 {
  margin: 0 0 10px;
  color: #8eeaff;
  letter-spacing: 1px;
}

.inspect-panel {
  border-color: rgba(54, 196, 255, 0.48);
}

.inspect-head h3 {
  margin: 0;
}

.inspect-head,
.analysis-head,
.suggest-head {
  height: 34px;
  margin: -16px -16px 12px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background:
    linear-gradient(90deg, rgba(19, 145, 239, 0.42), rgba(19, 145, 239, 0.16) 62%, rgba(19, 145, 239, 0));
  border-bottom: 1px solid rgba(86, 198, 255, 0.34);
  box-shadow: inset 0 -8px 16px rgba(11, 76, 143, 0.08);
}

.inspect-head span,
.analysis-head span {
  color: #7fe3ff;
  font-size: 13px;
}

.detail-trigger {
  border: 1px solid rgba(112, 206, 255, 0.65);
  border-radius: 999px;
  background: rgba(12, 72, 138, 0.48);
  color: #7fe3ff;
  font-size: 12px;
  line-height: 1;
  padding: 4px 10px;
  cursor: pointer;
}

.detail-trigger:hover {
  color: #dff6ff;
  border-color: rgba(146, 224, 255, 0.85);
}

.map-detail-popup {
  position: absolute;
  right: 16px;
  top: 16px;
  width: 550px;
  max-height: 520px;
  overflow-y: auto;
  border-radius: 14px;
  border: 1px solid rgba(122, 206, 255, 0.62);
  background: linear-gradient(180deg, rgba(9, 44, 99, 0.92), rgba(7, 29, 69, 0.9));
  box-shadow:
    inset 0 0 14px rgba(77, 188, 255, 0.12),
    0 14px 28px rgba(3, 12, 34, 0.4);
  padding: 12px;
  z-index: 5;
}

.map-detail-title {
  font-size: 17px;
  color: #9ee9ff;
  font-weight: 700;
  margin-bottom: 10px;
}

.map-detail-body {
  display: grid;
  gap: 8px;
}

.map-detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid rgba(108, 193, 255, 0.24);
  border-radius: 8px;
  padding: 8px 10px;
  background: rgba(7, 31, 73, 0.45);
  font-size: 14px;
}

.map-detail-row span {
  color: #bcdfff;
  flex-shrink: 0;
  white-space: nowrap;
  margin-right: 10px;
}

.map-detail-row b {
  color: #eef9ff;
  font-weight: 600;
  text-align: right;
  flex: 1;
  min-width: 0;
  word-break: break-all;
}

.map-detail-row b.loading-bar {
  display: inline-block;
  width: 60%;
  height: 16px;
  border-radius: 4px;
  background: linear-gradient(90deg, rgba(86, 180, 255, 0.12), rgba(86, 180, 255, 0.3), rgba(86, 180, 255, 0.12));
  background-size: 200% 100%;
  animation: detailLoading 1.4s ease-in-out infinite;
}

@keyframes detailLoading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.map-detail-row b.status-normal {
  color: #72e38a;
}

.map-detail-row b.status-warn {
  color: #ffd56f;
}

.map-detail-row b.status-danger {
  color: #ff8f86;
}

.map-suggestion-btn {
  display: block;
  width: calc(100% - 24px);
  margin: 12px auto;
  height: 30px;
  border-radius: 8px;
  border: 1px solid rgba(121, 214, 255, 0.45);
  background: linear-gradient(90deg, rgba(23, 102, 196, 0.52), rgba(27, 153, 223, 0.42));
  color: #b8daff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.map-suggestion-btn:hover {
  border-color: rgba(121, 214, 255, 0.8);
  color: #e8faff;
  background: linear-gradient(90deg, rgba(23, 102, 196, 0.72), rgba(27, 153, 223, 0.62));
}

/* ── Suggestion dialog ── */
.suggestion-dialog {
  max-width: 680px;
  max-height: 76vh;
  overflow-y: auto;
}

.suggestion-body {
  padding: 8px 0;
  color: #c5e0f0;
  font-size: 13px;
  line-height: 1.8;
}

.suggestion-body h4 {
  margin: 14px 0 6px;
  color: #7fe3ff;
  font-size: 14px;
  border-bottom: 1px solid rgba(86, 198, 255, 0.2);
  padding-bottom: 4px;
}

.suggestion-body h5 {
  margin: 8px 0 4px;
  color: #a8dcff;
  font-size: 13px;
}

.suggestion-body p {
  margin: 2px 0;
  padding: 2px 0;
}

.suggestion-body p b {
  color: #90c8f0;
}

.suggestion-summary {
  background: rgba(12, 72, 138, 0.25);
  border-left: 3px solid rgba(121, 214, 255, 0.5);
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.suggestion-empty {
  color: #5c7e9e;
  text-align: center;
  padding: 20px 0;
}

/* ── Collapsible plan phases ── */
.plan-phase-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 62vh;
  overflow-y: auto;
  padding-right: 4px;
}

.plan-phase-item {
  border: 1px solid rgba(112, 206, 255, 0.18);
  border-radius: 12px;
  background: rgba(8, 35, 80, 0.4);
  overflow: hidden;
}

.plan-phase-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.18s ease;
  user-select: none;
}

.plan-phase-header:hover {
  background: rgba(12, 72, 138, 0.3);
}

.plan-phase-header em {
  min-width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-style: normal;
  font-weight: 700;
  font-size: 12px;
  color: #042340;
  background: #8fe4ff;
  flex-shrink: 0;
}

.plan-phase-header-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.plan-phase-name {
  color: #dcf0ff;
  font-size: 13px;
  font-weight: 600;
}

.plan-phase-target {
  color: #7a9ab8;
  font-size: 11px;
  line-height: 1.5;
}

.plan-phase-arrow {
  color: #7fe3ff;
  font-size: 12px;
  flex-shrink: 0;
}

.plan-phase-body {
  padding: 8px 12px 12px;
  border-top: 1px solid rgba(112, 206, 255, 0.12);
}

.phase-ops-section {
  margin-bottom: 10px;
}

.phase-ops-section h4 {
  color: #7fe3ff;
  font-size: 13px;
  margin: 0 0 6px;
  padding-bottom: 3px;
  border-bottom: 1px solid rgba(86, 198, 255, 0.16);
}

.phase-pest-item {
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 2px solid rgba(86, 198, 255, 0.18);
}

.phase-pest-item h5 {
  color: #a8dcff;
  font-size: 12px;
  margin: 0 0 3px;
}

.phase-pest-item p {
  margin: 1px 0;
  font-size: 11px;
  color: #99bcd0;
  line-height: 1.6;
}

.phase-pest-item p b {
  color: #8ab8d8;
}

.plan-phase-notes {
  border: 1px solid rgba(112, 206, 255, 0.18);
  border-radius: 12px;
  background: rgba(8, 35, 80, 0.35);
  padding: 12px;
}

.plan-phase-notes h4 {
  color: #7fe3ff;
  font-size: 13px;
  margin: 0 0 6px;
}

.plan-phase-notes p {
  margin: 2px 0;
  font-size: 11px;
  color: #99bcd0;
  line-height: 1.6;
}

.plan-phase-notes p b {
  color: #8ab8d8;
}

.analysis-panel .progress {
  margin-bottom: 12px;
}

.analysis-head h3,
.suggest-head h3 {
  margin: 0;
}

.inspect-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.inspect-item {
  min-height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid rgba(116, 193, 255, 0.16);
  background: linear-gradient(180deg, rgba(14, 34, 78, 0.62), rgba(10, 27, 59, 0.46));
  box-shadow: inset 0 0 12px rgba(68, 171, 255, 0.06);
}

.inspect-item b {
  font-size: 13px;
  color: #e5f6ff;
}

.level {
  min-width: 40px;
  height: 20px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-style: normal;
  font-weight: 700;
  color: #fff;
}

.level.danger {
  background: linear-gradient(90deg, #ff3b30, #d61233);
}

.level.warn {
  background: linear-gradient(90deg, #f0b84f, #c88a25);
}

.level.normal {
  background: linear-gradient(90deg, #37c871, #1b8f4b);
}

.inspect-action-wrap {
  margin-top: auto;
  padding-top: 12px;
}

.inspect-action-btn,
.action-btn,
.back-btn,
.suggest-btn {
  position: relative;
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.inspect-action-btn::before,
.action-btn::before,
.back-btn::before,
.suggest-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, rgba(255, 255, 255, 0) 20%, rgba(255, 255, 255, 0.16) 50%, rgba(255, 255, 255, 0) 80%);
  transform: translateX(-120%);
  transition: transform 0.5s ease;
}

.inspect-action-btn:hover::before,
.action-btn:hover::before,
.back-btn:hover::before,
.suggest-btn:hover::before {
  transform: translateX(120%);
}

.inspect-action-btn {
  width: 100%;
  height: 38px;
  border-radius: 10px;
  border: 1px solid rgba(121, 214, 255, 0.58);
  background: linear-gradient(90deg, #1b63dd, #1b92d2 55%, #24c2de);
  color: #f3fcff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  box-shadow:
    inset 0 0 12px rgba(255, 255, 255, 0.08),
    0 8px 18px rgba(12, 82, 188, 0.24);
}

.inspect-action-btn:hover,
.action-btn:hover,
.back-btn:hover,
.suggest-btn:hover {
  transform: translateY(-1px);
  box-shadow:
    inset 0 0 12px rgba(255, 255, 255, 0.08),
    0 10px 22px rgba(12, 82, 188, 0.32);
}

.recognition-view {
  flex: 1;
  min-height: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.recognition-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid rgba(84, 181, 255, 0.4);
  border-radius: 16px;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(12, 55, 112, 0.55), rgba(9, 34, 79, 0.46));
  box-shadow: inset 0 0 16px rgba(66, 183, 255, 0.08);
}

.recognition-head h2 {
  margin: 0;
  font-size: 24px;
}

.recognition-head p {
  margin: 6px 0 0;
  color: #a8dcff;
  font-size: 14px;
}

.back-btn {
  min-width: 110px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(121, 214, 255, 0.6);
  color: #dff6ff;
  background: linear-gradient(90deg, rgba(23, 102, 196, 0.72), rgba(27, 153, 223, 0.62));
  cursor: pointer;
}

.plan-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(3, 12, 34, 0.52);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.plan-dialog {
  width: min(680px, 92vw);
  max-height: 78vh;
  padding: 16px;
  overflow: auto;
}

.plan-dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.plan-dialog-head h3 {
  margin: 0;
  font-size: 20px;
  color: #93e8ff;
}

.plan-close-btn {
  border: 1px solid rgba(121, 214, 255, 0.6);
  background: rgba(15, 76, 146, 0.5);
  color: #dff6ff;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
}

.plan-dialog-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}

.plan-dialog-list li {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 10px;
  align-items: start;
  border: 1px solid rgba(112, 206, 255, 0.22);
  border-radius: 10px;
  background: rgba(8, 35, 80, 0.5);
  padding: 10px;
}

.plan-dialog-list em {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-style: normal;
  font-weight: 700;
  color: #042340;
  background: #8fe4ff;
}

.plan-dialog-list span {
  color: #d7eeff;
  line-height: 1.6;
}

.recognition-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.recognition-card {
  position: relative;
  border-radius: 16px;
  border: 1px solid rgba(84, 181, 255, 0.38);
  background:
    linear-gradient(180deg, rgba(14, 59, 127, 0.72), rgba(10, 37, 85, 0.62)),
    radial-gradient(circle at top right, rgba(92, 216, 255, 0.12), transparent 36%);
  padding: 18px;
  display: flex;
  flex-direction: column;
  box-shadow:
    inset 0 0 16px rgba(72, 181, 255, 0.08),
    0 16px 28px rgba(2, 10, 28, 0.18);
}

.recognition-card h3 {
  margin: 0 0 8px;
  color: #6fe6ff;
}

.recognition-card p {
  margin: 0;
  color: #c7e7ff;
  line-height: 1.6;
  flex: 1;
}

.detail-panel ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.detail-panel li {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #c5e7ff;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(103, 181, 255, 0.12);
  background: linear-gradient(180deg, rgba(10, 34, 73, 0.56), rgba(8, 27, 58, 0.34));
}

.detail-panel li b.status-normal {
  color: #72e38a;
}

.detail-panel li b.status-warn {
  color: #ffd56f;
}

.detail-panel li b.status-danger {
  color: #ff8f86;
}

.analysis-panel .progress + .progress {
  margin-top: 12px;
}

.progress label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: #b5ddff;
}

.progress label b {
  color: #7af0ff;
  font-size: 14px;
}

.bar {
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.08));
  box-shadow: inset 0 0 10px rgba(7, 21, 44, 0.35);
}

.bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #22ffd1, #5fd7ff 45%, #7ba3ff);
  box-shadow: 0 0 12px rgba(77, 223, 255, 0.38);
}

.suggest-panel p {
  margin: 0;
}

.suggest-panel {
  position: relative;
  overflow: hidden;
}

.suggest-head span {
  font-size: 13px;
  color: #7fe3ff;
}

.suggest-content {
  color: #d4edff;
  font-size: 14px;
  line-height: 1.8;
}

.suggest-content p + p {
  margin-top: 2px;
}

.suggest-content b {
  color: #ffffff;
  font-weight: 700;
}

.suggest-content span {
  margin-left: 10px;
}

.suggest-progress {
  margin-top: 8px;
  height: 24px;
  border-radius: 999px;
  overflow: hidden;
  position: relative;
  background: rgba(236, 244, 246, 0.18);
  border: 1px solid rgba(166, 231, 255, 0.18);
}

.suggest-progress i {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, #63cc46, #7fe167);
  box-shadow: 0 0 12px rgba(141, 232, 114, 0.28);
}

.suggest-progress em {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-style: normal;
  color: #f3fff8;
  font-size: 13px;
  font-weight: 700;
  z-index: 1;
}

.suggest-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}

.suggest-btn {
  flex: 1;
  height: 34px;
  border-radius: 999px;
  border: 1px solid rgba(112, 206, 255, 0.75);
  background: linear-gradient(180deg, rgba(15, 74, 145, 0.46), rgba(7, 38, 92, 0.36));
  color: #ebf8ff;
  cursor: pointer;
}

.crop-mark {
  position: absolute;
  right: 12px;
  bottom: 8px;
  font-size: 46px;
  line-height: 1;
  color: rgba(158, 230, 87, 0.85);
  transform: rotate(8deg);
}

.action-btn {
  margin-top: 12px;
  width: 100%;
  height: 38px;
  border-radius: 10px;
  border: 1px solid rgba(128, 213, 255, 0.5);
  background: linear-gradient(90deg, #1765d8, #1f89da 55%, #22b9df);
  color: #f4fdff;
  cursor: pointer;
}

.action-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.file-input {
  display: none;
}

.recognition-image {
  width: 100%;
  max-height: 260px;
  object-fit: contain;
  margin-top: 10px;
  border-radius: 10px;
  border: 1px solid rgba(105, 204, 255, 0.34);
  background: rgba(4, 20, 46, 0.62);
}

.recognition-result,
.recognition-error {
  margin: 10px 0 0;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.6;
}

.recognition-result {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #dff6ff;
  border: 1px solid rgba(105, 204, 255, 0.34);
  background: rgba(8, 35, 80, 0.5);
}

.pest-total {
  margin-top: 2px;
  font-weight: 600;
}

.pest-count-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 12px;
}

.recognition-error {
  color: #ffd7d7;
  border: 1px solid rgba(255, 119, 119, 0.4);
  background: rgba(89, 16, 28, 0.45);
}

@media (max-width: 1240px) {
  .agri-board {
    height: auto;
  }

  .content-grid {
    grid-template-columns: 1fr;
    flex: none;
  }

  .right-panels {
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: none;
  }

  .field-map {
    flex: none;
    min-height: 0;
    max-height: none;
  }

  .recognition-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .top-main {
    min-height: auto;
    flex-direction: column;
    gap: 10px;
    align-items: stretch;
  }

  .title-box {
    position: static;
    transform: none;
    order: -1;
    width: 100%;
    justify-content: center;
    gap: 10px;
  }

  .title-core {
    min-width: 0;
    padding: 2px 12px 8px;
  }

  .title-box h1 {
    font-size: 30px;
    letter-spacing: 3px;
  }

  .title-decor {
    width: 42px;
  }

  .top-side,
  .top-side-left,
  .top-side-right {
    justify-content: center;
  }

  .quick-data {
    display: none;
  }

  .timeline-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .timeline-year-nav {
    width: 100%;
    max-width: 180px;
  }

  .timeline-days {
    width: 100%;
    overflow-x: auto;
    padding-bottom: 6px;
  }

  .field-map {
    min-height: 0;
  }

  .metrics-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .right-panels {
    grid-template-columns: 1fr;
  }

  .inspect-list {
    grid-template-columns: 1fr;
  }
}
</style>
