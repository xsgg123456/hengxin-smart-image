import { test } from 'node:test'
import assert from 'node:assert/strict'
import { beijingFilterTime, formatBeijingTime } from '../src/utils/beijing-time'
import { formatExecutionTime } from '../src/api/hengxin/execution-data'
import { formatTaskTime } from '../src/views/overseas/requirements'

test('用户原始微秒 UTC 样例、显式偏移和跨日均显示北京时间', () => {
  const sample = '2026-10-14T00:59:59.091561+00:00'
  assert.equal(formatBeijingTime(sample), '2026-10-14 08:59:59')
  assert.equal(formatExecutionTime(sample), '2026-10-14 08:59:59')
  assert.equal(formatTaskTime(sample), '2026-10-14 08:59:59')
  assert.equal(formatBeijingTime('2026-10-14T08:59:59+08:00'), '2026-10-14 08:59:59')
  assert.equal(formatBeijingTime('2026-10-13T17:59:59-07:00'), '2026-10-14 08:59:59')
  assert.equal(formatBeijingTime('2026-12-31T16:00:00Z'), '2027-01-01 00:00:00')
})

test('旧无时区显示数据是北京墙上时间，不重复增加八小时', () => {
  for (const value of ['2026-10-14 08:59:59', '2026/10/14 08:59:59', '2026-10-14T08:59:59']) {
    assert.equal(formatBeijingTime(value), '2026-10-14 08:59:59')
  }
  assert.equal(formatBeijingTime('2026/1/2 3:04'), '2026-01-02 03:04:00')
})

test('空时间和无效时间保留语义占位', () => {
  for (const value of ['', null, undefined, 'not-a-date', '2026-13-14T00:00:00Z', new Date(NaN)]) {
    assert.equal(formatBeijingTime(value), '—')
  }
  assert.equal(formatBeijingTime(null, '尚未开始'), '尚未开始')
  assert.equal(formatExecutionTime(null), '未提供')
})

test('海外管理筛选传递北京时间偏移，不依赖浏览器本地时区', () => {
  assert.equal(beijingFilterTime('2026-10-14 08:59:59'), '2026-10-14T08:59:59+08:00')
  assert.equal(new Date(beijingFilterTime('2026-10-14 08:59:59')).toISOString(), '2026-10-14T00:59:59.000Z')
  assert.equal(beijingFilterTime(null), '')
})


test('拒绝不存在日期和越界时分秒，允许真实闰日', () => {
  for (const value of ['2026-02-30T00:00:00Z', '2026-02-30 08:00:00', '2025-02-29T00:00:00Z', '2026-04-31T00:00:00Z', '2026-10-14T24:00:00Z', '2026-10-14T00:60:00Z', '2026-10-14T00:00:60Z']) assert.equal(formatBeijingTime(value), '—')
  assert.equal(formatBeijingTime('2024-02-29T00:00:00Z'), '2024-02-29 08:00:00')
})
