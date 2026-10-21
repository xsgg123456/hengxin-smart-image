export type Scenario = 'normal' | 'scanning' | 'error' | 'offline' | 'unknown' | 'empty' | 'loading'
export type Result = '缓存已清理' | '全部完成' | '文件回收中' | '失败待重试' | '暂缓清理' | '等待到期' | '已到期待处理'
export interface CleanupRow {
  id: string; task: string; image: number; kind: '缓存' | '会话历史'; result: Result
  time: string; activity: string; due: string; detail: string; turns: number; files: number; deleted?: boolean
}
export const scenarios: {value: Scenario; label: string}[] = [
  {value:'normal',label:'正常运行'}, {value:'scanning',label:'正在扫描'},
  {value:'error',label:'清理异常'}, {value:'offline',label:'心跳超时'},
  {value:'unknown',label:'数据读取失败'}, {value:'empty',label:'暂无记录'}, {value:'loading',label:'首次加载'}
]
export const records: CleanupRow[] = [
  {id:'CLI-0108',task:'秋季上新 · 星河蓝手机主图',image:2,kind:'会话历史',result:'全部完成',time:'2026-10-21 14:48:42',activity:'2026-10-18 13:20:00',due:'2026-10-21 13:20:00',detail:'已移除会话执行目录、6 轮对话及执行记录；2 个无引用候选文件已回收。',turns:6,files:2},
  {id:'CLI-0112',task:'轻薄旗舰 · 银色详情页',image:4,kind:'缓存',result:'缓存已清理',time:'2026-10-21 14:48:40',activity:'2026-10-20 14:10:00',due:'2026-10-21 14:10:00',detail:'会话私有缓存与插件目录已清理，聊天历史与图片保留。',turns:0,files:0},
  {id:'CLI-0096',task:'新品配色 · 珍珠白主图',image:1,kind:'会话历史',result:'文件回收中',time:'2026-10-21 14:48:38',activity:'2026-10-18 10:30:00',due:'2026-10-21 10:30:00',detail:'4 轮会话历史及执行目录已清理；2 个无引用文件等待存储删除，尚未全部完成。',turns:4,files:0},
  {id:'CLI-0083',task:'双十一预热 · 暖金系列',image:3,kind:'缓存',result:'缓存已清理',time:'2026-10-21 13:48:31',activity:'2026-10-20 12:05:00',due:'2026-10-21 12:05:00',detail:'会话私有缓存与插件目录已清理，聊天历史与图片保留。',turns:0,files:0},
  {id:'CLI-0071',task:'经典款 · 深空黑详情页',image:2,kind:'会话历史',result:'全部完成',time:'2026-10-20 16:48:25',activity:'2026-10-17 16:00:00',due:'2026-10-20 16:00:00',detail:'已移除会话执行目录、3 轮对话及执行记录；1 个无引用候选文件已回收。原任务后来已删除，保留清理摘要。',turns:3,files:1,deleted:true}
]
export const failure: CleanupRow = {id:'CLI-0094',task:'商务系列 · 石墨灰手机主图',image:5,kind:'会话历史',result:'失败待重试',time:'2026-10-21 14:48:36',activity:'2026-10-18 11:00:00',due:'2026-10-21 11:00:00',detail:'执行目录清理暂未完成，保留清理状态，预计 15:48 再试。当前不允许续接该会话。',turns:0,files:0}
export const pending: CleanupRow[] = [
  {id:'CLI-0120',task:'旗舰新品 · 冰川蓝主图',image:1,kind:'会话历史',result:'暂缓清理',time:'2026-10-21 14:48:41',activity:'2026-10-18 14:00:00',due:'2026-10-21 14:00:00',detail:'有执行结果待核实，保留现场；待确认执行结束后重新判断清理条件。',turns:0,files:0},
  {id:'CLI-0125',task:'轻量款 · 雾面白详情页',image:2,kind:'缓存',result:'等待到期',time:'—',activity:'2026-10-20 16:10:00',due:'2026-10-21 16:10:00',detail:'尚未到期。查看页面不续期；新的有效业务活动会重新计时。',turns:0,files:0},
  {id:'CLI-0128',task:'电商换图 · 新色组合',image:4,kind:'会话历史',result:'等待到期',time:'—',activity:'2026-10-18 17:30:00',due:'2026-10-21 17:30:00',detail:'闲置满 72 小时后进入扫描范围，正式版本及素材保留。',turns:0,files:0}
]
export const tagType = (result: Result) => result === '全部完成' || result === '缓存已清理' ? 'success' : result === '失败待重试' ? 'danger' : result === '等待到期' ? 'info' : 'warning'
