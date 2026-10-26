import { reactive } from 'vue'
export type Business = 'domestic' | 'overseas'
export type AccountStatus = 'empty' | 'ready' | 'expired' | 'network'
export interface Audit { time: string; operator: string; action: string; result: string }
export interface Account { status: AccountStatus; email: string; workspace: string; checked: string; updated: string; audit: Audit[] }
export const businessNames: Record<Business, string> = { domestic: '国内业务', overseas: '海外业务' }
export const statusNames: Record<AccountStatus, string> = { empty: '未配置', ready: '可用', expired: '授权已失效', network: '连接异常' }
export const statusTypes = { empty: 'info', ready: 'success', expired: 'danger', network: 'warning' } as const
export const sampleEmails = { domestic: 'domestic@example.com', overseas: 'overseas@example.com' }
function initial(side: Business): Account {
  return { status: side === 'domestic' ? 'expired' : 'ready', email: sampleEmails[side], workspace: '个人工作区',
    checked: '2026-10-26 11:00:00', updated: '2026-10-24 14:30:00',
    audit: [{ time: '2026-10-24 14:30:00', operator: '管理员（示例）', action: '授权并启用', result: '成功' }] }
}
export const accounts = reactive<Record<Business, Account>>({ domestic: initial('domestic'), overseas: initial('overseas') })
export const now = () => new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' })
export function audit(side: Business, action: string, result: string) {
  accounts[side].audit.unshift({ time: now(), operator: '管理员（示例）', action, result })
}
export function scenario(side: Business, status: AccountStatus) {
  Object.assign(accounts[side], initial(side), { status })
  if (status === 'empty') Object.assign(accounts[side], { email: '', workspace: '', checked: '', updated: '', audit: [] })
}
export function activate(side: Business, email: string) {
  const account = accounts[side], changed = !!account.email && account.email !== email
  Object.assign(account, { status: 'ready', email, workspace: '个人工作区', checked: now(), updated: now() })
  audit(side, changed ? '更换账号并启用' : '授权并启用', '成功')
}
export function remove(side: Business) {
  Object.assign(accounts[side], { status: 'empty', email: '', workspace: '', checked: '', updated: '' })
  audit(side, '移除账号配置', '已移除')
}
