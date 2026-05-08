<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  stationCode: { type: String, default: '' },
  stationName: { type: String, default: '' }
})

const emit = defineEmits(['back'])

// ==================== 数据 ====================

// chart1: 总产量趋势与同比变化
const yieldData = [
  { year: 2020, total_yield: 26937.75 },
  { year: 2021, total_yield: 26860.43 },
  { year: 2022, total_yield: 26704.54 },
  { year: 2023, total_yield: 27257.67 },
  { year: 2024, total_yield: 27231.81 },
  { year: 2025, total_yield: 27076.24 },
]

// chart2: 各站点平均产量 (25站点)
const stationYield = [
  { station: 'ST-001', yield: 946.43 }, { station: 'ST-002', yield: 1015.44 }, { station: 'ST-003', yield: 1056.21 },
  { station: 'ST-004', yield: 757.40 }, { station: 'ST-005', yield: 956.76 }, { station: 'ST-006', yield: 952.58 },
  { station: 'ST-007', yield: 1034.01 }, { station: 'ST-008', yield: 944.53 }, { station: 'ST-009', yield: 979.42 },
  { station: 'ST-010', yield: 944.76 }, { station: 'ST-011', yield: 887.91 }, { station: 'ST-012', yield: 937.78 },
  { station: 'ST-013', yield: 920.99 }, { station: 'ST-014', yield: 915.75 }, { station: 'ST-015', yield: 840.20 },
  { station: 'ST-016', yield: 682.52 }, { station: 'ST-017', yield: 873.79 }, { station: 'ST-018', yield: 871.82 },
  { station: 'ST-019', yield: 824.72 }, { station: 'ST-020', yield: 772.23 }, { station: 'ST-021', yield: 903.43 },
  { station: 'ST-022', yield: 931.50 }, { station: 'ST-023', yield: 1015.33 }, { station: 'ST-024', yield: 855.91 },
  { station: 'ST-025', yield: 877.19 },
]

// chart3: 月均日照
const sunshineData = [
  { month: '7月', value: 5.30 }, { month: '8月', value: 5.56 },
  { month: '9月', value: 6.32 }, { month: '10月', value: 5.55 },
  { month: '11月', value: 2.37 }, { month: '12月', value: 3.36 },
]

// chart4: 月均降水量
const rainfallData = [
  { month: '7月', value: 10.5 }, { month: '8月', value: 9.8 },
  { month: '9月', value: 4.2 }, { month: '10月', value: 3.0 },
  { month: '11月', value: 2.2 }, { month: '12月', value: 1.2 },
]

// chart5: 月均气温
const tempData = [
  { month: '7月', value: 27.7 }, { month: '8月', value: 28.0 },
  { month: '9月', value: 27.9 }, { month: '10月', value: 23.1 },
  { month: '11月', value: 18.0 }, { month: '12月', value: 13.4 },
]

// ==================== 图表 refs ====================
const c1Ref = ref(null)
const c2Ref = ref(null)
const c3Ref = ref(null)
const c4Ref = ref(null)
const c5Ref = ref(null)

let charts = []

// ==================== 图表初始化 ====================

function initChart1() {
  if (!c1Ref.value) return
  const chart = echarts.init(c1Ref.value)
  const years = yieldData.map(d => d.year + '')
  const yields = yieldData.map(d => +d.total_yield.toFixed(1))
  const yoy = years.map((_, i) => {
    if (i === 0) return null
    return +(((yields[i] - yields[i - 1]) / yields[i - 1]) * 100).toFixed(1)
  })

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['总产量', '同比变化'], bottom: 0, textStyle: { color: '#8ca8cc' } },
    grid: { left: '10%', right: '10%', top: 20, bottom: 36 },
    xAxis: {
      type: 'category', data: years,
      axisLine: { lineStyle: { color: '#2a4a6e' } },
      axisLabel: { color: '#7a9ab8' }
    },
    yAxis: [
      {
        type: 'value', name: '总产量 (吨)', nameTextStyle: { color: '#7a9ab8', fontSize: 10 },
        axisLabel: { color: '#7a9ab8' }, splitLine: { lineStyle: { color: '#1a3350', type: 'dashed' } }
      },
      {
        type: 'value', name: '同比 (%)', nameTextStyle: { color: '#7a9ab8', fontSize: 10 },
        axisLabel: { color: '#7a9ab8', formatter: '{value}%' }, splitLine: { show: false }
      }
    ],
    series: [
      { name: '总产量', type: 'bar', data: yields, barWidth: '40%', itemStyle: { color: '#4dc9ff' } },
      {
        name: '同比变化', type: 'line', yAxisIndex: 1, data: yoy,
        lineStyle: { color: '#ffd93d', width: 2 }, itemStyle: { color: '#ffd93d' },
        symbol: 'circle', symbolSize: 8,
        label: { show: true, formatter: '{c}%', color: '#ffd93d', fontSize: 11 }
      }
    ]
  })
  charts.push(chart)
}

function initChart2() {
  if (!c2Ref.value) return
  const chart = echarts.init(c2Ref.value)
  const sorted = [...stationYield].sort((a, b) => a.yield - b.yield)

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '14%', right: '8%', top: 10, bottom: 20 },
    xAxis: {
      type: 'value', name: '平均产量 (kg/亩)', nameTextStyle: { color: '#7a9ab8', fontSize: 10 },
      axisLabel: { color: '#7a9ab8' }, splitLine: { lineStyle: { color: '#1a3350', type: 'dashed' } }
    },
    yAxis: {
      type: 'category', data: sorted.map(d => d.station), inverse: true,
      axisLabel: { color: '#7a9ab8', fontSize: 10 },
      axisLine: { lineStyle: { color: '#2a4a6e' } }
    },
    series: [{
      type: 'bar', data: sorted.map(d => +d.yield.toFixed(1)), barWidth: '60%',
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#6bcb77' }, { offset: 1, color: '#4dc9ff' }
        ])
      },
      label: { show: true, position: 'right', color: '#b8d6ff', fontSize: 10 }
    }]
  })
  charts.push(chart)
}

function initChart3() {
  if (!c3Ref.value) return
  const chart = echarts.init(c3Ref.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '12%', right: '6%', top: 20, bottom: 28 },
    xAxis: {
      type: 'category', data: sunshineData.map(d => d.month),
      axisLine: { lineStyle: { color: '#2a4a6e' } }, axisLabel: { color: '#7a9ab8' },
      name: '月份', nameTextStyle: { color: '#7a9ab8', fontSize: 10 }
    },
    yAxis: {
      type: 'value', name: '日照时长 (h)', nameTextStyle: { color: '#7a9ab8', fontSize: 10 },
      axisLabel: { color: '#7a9ab8' }, splitLine: { lineStyle: { color: '#1a3350', type: 'dashed' } }
    },
    series: [{
      type: 'bar', data: sunshineData.map(d => d.value), barWidth: '45%',
      itemStyle: { color: '#ffa502', borderRadius: [6, 6, 0, 0] },
      label: { show: true, position: 'top', color: '#ffa502', fontSize: 12, formatter: '{c}h' }
    }]
  })
  charts.push(chart)
}

function initChart4() {
  if (!c4Ref.value) return
  const chart = echarts.init(c4Ref.value)
  const months = rainfallData.map(d => d.month)
  const values = rainfallData.map(d => d.value)

  // 简单线性趋势
  const n = values.length
  const xMean = (n - 1) / 2
  const yMean = values.reduce((a, b) => a + b, 0) / n
  let num = 0, den = 0
  values.forEach((v, i) => { num += (i - xMean) * (v - yMean); den += (i - xMean) ** 2 })
  const slope = den === 0 ? 0 : num / den
  const intercept = yMean - slope * xMean
  const trend = values.map((_, i) => +(intercept + slope * i).toFixed(1))

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['降水量', '趋势线'], bottom: 0, textStyle: { color: '#8ca8cc' } },
    grid: { left: '12%', right: '6%', top: 20, bottom: 36 },
    xAxis: {
      type: 'category', data: months,
      axisLine: { lineStyle: { color: '#2a4a6e' } }, axisLabel: { color: '#7a9ab8' },
      name: '月份', nameTextStyle: { color: '#7a9ab8', fontSize: 10 }
    },
    yAxis: {
      type: 'value', name: '降水量 (mm)', nameTextStyle: { color: '#7a9ab8', fontSize: 10 },
      axisLabel: { color: '#7a9ab8' }, splitLine: { lineStyle: { color: '#1a3350', type: 'dashed' } }
    },
    series: [
      {
        name: '降水量', type: 'bar', data: values, barWidth: '40%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#5dade2' }, { offset: 1, color: '#2e86c1' }
          ])
        },
        label: { show: true, position: 'top', color: '#8fd4ff', fontSize: 11, formatter: '{c}mm' }
      },
      {
        name: '趋势线', type: 'line', data: trend,
        lineStyle: { color: '#ff6b6b', type: 'dashed', width: 2 },
        itemStyle: { color: '#ff6b6b' }, symbol: 'diamond', symbolSize: 8
      }
    ]
  })
  charts.push(chart)
}

function initChart5() {
  if (!c5Ref.value) return
  const chart = echarts.init(c5Ref.value)
  const months = tempData.map(d => d.month)
  const temps = tempData.map(d => d.value)
  const optimalMin = 24, optimalMax = 32

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '12%', right: '6%', top: 20, bottom: 28 },
    xAxis: {
      type: 'category', data: months,
      axisLine: { lineStyle: { color: '#2a4a6e' } }, axisLabel: { color: '#7a9ab8' },
      name: '月份', nameTextStyle: { color: '#7a9ab8', fontSize: 10 }
    },
    yAxis: {
      type: 'value', name: '温度 (℃)', nameTextStyle: { color: '#7a9ab8', fontSize: 10 },
      min: 0, max: 35,
      axisLabel: { color: '#7a9ab8' }, splitLine: { lineStyle: { color: '#1a3350', type: 'dashed' } }
    },
    series: [
      {
        type: 'line', data: temps, name: '月均气温',
        lineStyle: { color: '#ff6348', width: 2.5 }, itemStyle: { color: '#ff6348' },
        symbol: 'circle', symbolSize: 10,
        label: { show: true, color: '#ff6348', fontSize: 12, formatter: '{c}℃', distance: 10 },
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(77, 201, 255, 0.12)' },
          data: [
            [{ yAxis: optimalMin, itemStyle: { color: 'rgba(77, 201, 255, 0.15)' } },
             { yAxis: optimalMax }]
          ]
        }
      },
      // 适宜下限虚线
      {
        type: 'line', data: Array(months.length).fill(optimalMin), name: '适宜下限 (24℃)',
        lineStyle: { color: '#4dc9ff', type: 'dashed', width: 1.5 }, itemStyle: { color: '#4dc9ff' },
        symbol: 'none', showSymbol: false
      },
      // 适宜上限虚线
      {
        type: 'line', data: Array(months.length).fill(optimalMax), name: '适宜上限 (32℃)',
        lineStyle: { color: '#4dc9ff', type: 'dashed', width: 1.5 }, itemStyle: { color: '#4dc9ff' },
        symbol: 'none', showSymbol: false
      }
    ]
  })
  charts.push(chart)
}

function resizeAll() {
  charts.forEach(c => c?.resize())
}

onMounted(() => {
  initChart1()
  initChart2()
  initChart3()
  initChart4()
  initChart5()
  window.addEventListener('resize', resizeAll)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeAll)
  charts.forEach(c => c?.dispose())
  charts = []
})
</script>

<template>
  <section class="history-view">
    <!-- 头部 -->
    <div class="history-head panel">
      <button class="back-btn" @click="$emit('back')">← 返回大屏</button>
      <div class="head-center">
        <div class="title-icon">
          <span class="icon-bar"></span>
          <span class="icon-dot"></span>
          <span class="icon-bar"></span>
        </div>
        <h2 class="main-title">历史图表分析</h2>
      </div>
    </div>

    <!-- 彩色分割线 -->
    <div class="divider-line">
      <span class="divider-segment" v-for="i in 5" :key="i"></span>
    </div>

    <!-- 图表网格 -->
    <div class="charts-grid">
      <!-- 图1: 总产量趋势与同比变化 -->
      <div class="chart-card panel">
        <h3>📈 总产量趋势与同比变化</h3>
        <p class="chart-desc">2020–2025 年度总产量及同比增长率</p>
        <div ref="c1Ref" class="chart-box"></div>
      </div>

      <!-- 图2: 各站点平均产量 -->
      <div class="chart-card panel">
        <h3>🌾 各站点平均产量</h3>
        <p class="chart-desc">25 个监测站点年均产量排名（kg/亩）</p>
        <div ref="c2Ref" class="chart-box"></div>
      </div>

      <!-- 图3: 月均日照对比 -->
      <div class="chart-card panel">
        <h3>☀️ 月均日照对比</h3>
        <p class="chart-desc">2025下半年各月平均日照时长</p>
        <div ref="c3Ref" class="chart-box"></div>
      </div>

      <!-- 图4: 月均降水量&趋势 -->
      <div class="chart-card panel">
        <h3>🌧️ 月均降水量 & 趋势</h3>
        <p class="chart-desc">2025下半年降水量及线性趋势线</p>
        <div ref="c4Ref" class="chart-box"></div>
      </div>

      <!-- 图5: 月均气温&适宜区间 -->
      <div class="chart-card panel">
        <h3>🌡️ 月均气温 & 适宜区间</h3>
        <p class="chart-desc">2025下半年气温变化与水稻最适温区 24~32℃</p>
        <div ref="c5Ref" class="chart-box"></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.history-view {
  width: 100%;
  height: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ===== 头部 ===== */
.history-head {
  padding: 28px 24px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}

.back-btn {
  position: absolute;
  right: 24px;
  top: 50%;
  transform: translateY(-50%);
  padding: 8px 22px;
  border: 1px solid rgba(71, 161, 255, 0.45);
  border-radius: 10px;
  background: rgba(15, 53, 115, 0.7);
  color: #b8daff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.25s;
  white-space: nowrap;
  z-index: 2;
}

.back-btn:hover {
  border-color: #4da3ff;
  background: rgba(30, 90, 180, 0.7);
  color: #fff;
  box-shadow: 0 0 18px rgba(77, 163, 255, 0.25);
}

/* ===== 居中标题区 ===== */
.head-center {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.title-icon {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 2px;
}

.icon-bar {
  display: block;
  width: 32px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, #00d2ff, #5fe0ff);
  box-shadow: 0 0 8px rgba(0, 210, 255, 0.5);
}

.icon-dot {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #5fe0ff;
  box-shadow:
    0 0 10px rgba(95, 224, 255, 0.8),
    0 0 24px rgba(0, 210, 255, 0.4);
}

.main-title {
  margin: 0;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: 6px;
  background: linear-gradient(180deg, #f8feff 10%, #a3e4ff 45%, #4dc9ff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: none;
  position: relative;
}

.main-title::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -6px;
  transform: translateX(-50%);
  width: 70%;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, rgba(95, 224, 255, 0.6), transparent);
}

/* ===== 彩色分割线 ===== */
.divider-line {
  display: flex;
  gap: 4px;
  padding: 0 24px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.divider-segment {
  flex: 1;
  height: 3px;
  border-radius: 2px;
}

.divider-segment:nth-child(1) {
  background: linear-gradient(90deg, transparent, #ff6b6b);
  box-shadow: 0 0 8px rgba(255, 107, 107, 0.5);
}

.divider-segment:nth-child(2) {
  background: linear-gradient(90deg, #ff6b6b, #ffd93d);
  box-shadow: 0 0 8px rgba(255, 217, 61, 0.5);
}

.divider-segment:nth-child(3) {
  background: linear-gradient(90deg, #ffd93d, #6bcb77);
  box-shadow: 0 0 8px rgba(107, 203, 119, 0.5);
}

.divider-segment:nth-child(4) {
  background: linear-gradient(90deg, #6bcb77, #4dc9ff);
  box-shadow: 0 0 8px rgba(77, 201, 255, 0.5);
}

.divider-segment:nth-child(5) {
  background: linear-gradient(90deg, #4dc9ff, #a855f7);
  box-shadow: 0 0 8px rgba(168, 85, 247, 0.5);
}

/* ===== 图表网格 ===== */
.charts-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: minmax(340px, auto);
  gap: 16px;
  padding: 0 24px 24px;
}

.chart-card {
  padding: 16px 18px 12px;
  display: flex;
  flex-direction: column;
}

.chart-card h3 {
  margin: 0 0 2px;
  font-size: 1rem;
  color: #dcf0ff;
}

.chart-desc {
  margin: 0 0 10px;
  font-size: 0.72rem;
  color: #5c7e9e;
}

.chart-box {
  flex: 1;
  min-height: 240px;
  width: 100%;
}

/* 第一张图跨两列 */
.chart-card:first-child {
  grid-column: span 2;
}

@media (max-width: 1200px) {
  .charts-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }

  .main-title {
    font-size: 1.5rem;
    letter-spacing: 4px;
  }
}
</style>
