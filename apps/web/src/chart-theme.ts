export const chartBase = {
  backgroundColor: 'transparent',
  textStyle: { color: '#8590a3', fontFamily: 'ui-monospace, monospace', fontSize: 11 },
  grid: { left: 45, right: 20, top: 25, bottom: 30 },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#171b24',
    borderColor: '#303641',
    textStyle: { color: '#dce0e8' },
  },
  xAxis: {
    type: 'category',
    axisLine: { lineStyle: { color: '#252b36' } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: '#202630' } },
    axisLabel: { color: '#8590a3' },
  },
};
