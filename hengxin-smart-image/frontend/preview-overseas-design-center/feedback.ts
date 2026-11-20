export const statuses = ['待处理', '处理中', '已处理'] as const
export type Status = typeof statuses[number]
export const previewReporter = { id: 'preview-designer-zhang', name: '张帅' } as const
export interface Submission {
  reporterId?: string
  description: string
  source: string
  reporter?: string
  picture?: File
  createdAt: string
}
interface StoredFeedback extends Submission {
  status?: Status
  reply?: string
  note?: string
  revision?: number
  updatedAt?: string
  sample?: boolean
}
export interface Feedback extends StoredFeedback { id: number; status: Status }

let connection: Promise<IDBDatabase> | undefined
function database() {
  if (!connection) {
    connection = new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open('hx-design-center-feedback-preview', 3)
      request.onerror = () => reject(request.error)
      request.onupgradeneeded = event => {
        const store = event.oldVersion === 0
          ? request.result.createObjectStore('feedback', {autoIncrement: true})
          : request.transaction!.objectStore('feedback')
        const now = Date.now()
        store.createIndex('reporterId','reporterId')
        // Version 2 used a fixed local profile and stored only its display name.
        const legacy = store.openCursor()
        legacy.onsuccess = () => {
          const row = legacy.result
          if (!row) return
          if (!row.value.reporterId && row.value.reporter === previewReporter.name)
            row.update({...row.value, reporterId:previewReporter.id})
          row.continue()
        }
        const samples = [
          {source:'设计任务中心', description:'输入 SKU 后商品信息未带入，重新打开表单后仍然如此。', reporter:'林悦', status:'待处理'},
          {source:'AI 设计工作台', description:'上传参考图后缩略图一直在加载。', reporter:'张帅', status:'处理中', note:'已复现，正在检查图片加载过程。'},
        ]
        if(event.oldVersion < 2) samples.forEach((item,i) => store.add({...item, ...(item.reporter===previewReporter.name ? {reporterId:previewReporter.id} : {}), sample:true, createdAt:new Date(now-(i+1)*3600000).toISOString()}))
        store.add({source:'设计任务中心',description:'切换到继续任务后，没有看到刚提交的图需。',reporter:previewReporter.name,
          reporterId:previewReporter.id,status:'已处理',sample:true,reply:'任务列表已恢复更新。请重新打开「继续任务」，就能看到刚提交的图需。',
          updatedAt:new Date(now-3*3600000).toISOString(),createdAt:new Date(now-5*3600000).toISOString()})

      }
      request.onsuccess = () => {
        const db=request.result
        db.onversionchange=()=>{db.close();connection=undefined}
        resolve(db)
      }
    }).catch(error=>{connection=undefined;throw error})
  }
  return connection
}

export async function addFeedback(data: Submission) {
  const db=await database()
  await new Promise<void>((resolve,reject)=>{
    const tx=db.transaction('feedback','readwrite')
    tx.oncomplete=()=>resolve()
    tx.onabort=()=>reject(tx.error)
    tx.objectStore('feedback').add({...data,reporterId:previewReporter.id,reporter:previewReporter.name,status:'待处理'})
  })
}
export async function listFeedback() {
  const db=await database()
  return new Promise<Feedback[]>((resolve,reject)=>{
    const items:Feedback[]=[]
    const cursor=db.transaction('feedback').objectStore('feedback').openCursor()
    cursor.onerror=()=>reject(cursor.error)
    cursor.onsuccess=()=>{
      const row=cursor.result
      if(!row){resolve(items.sort((a,b)=>Number(!!a.sample)-Number(!!b.sample)||b.createdAt.localeCompare(a.createdAt)||b.id-a.id));return}
      items.push({...row.value,id:Number(row.key),status:row.value.status || '待处理'})
      row.continue()
    }
  })
}
export type PersonalFeedback = Pick<Feedback,'id'|'description'|'source'|'createdAt'|'status'|'reply'|'sample'>
export async function listMyFeedback():Promise<PersonalFeedback[]> {
  const db=await database()
  return new Promise((resolve,reject)=>{
    const rows:PersonalFeedback[]=[]
    const cursor=db.transaction('feedback').objectStore('feedback').index('reporterId').openCursor(previewReporter.id)
    cursor.onerror=()=>reject(cursor.error)
    cursor.onsuccess=()=>{
      const row=cursor.result
      if(!row){resolve(rows.sort((a,b)=>Number(!!a.sample)-Number(!!b.sample)||b.createdAt.localeCompare(a.createdAt)||b.id-a.id));return}
      const {description,source,createdAt,status='待处理',reply,sample}=row.value
      rows.push({id:Number(row.primaryKey),description,source,createdAt,status,reply,sample})
      row.continue()
    }
  })
}
export async function processFeedback(item: Feedback, status: Status, note: string, reply: string) {
  const db=await database()
  await new Promise<void>((resolve,reject)=>{
    const tx=db.transaction('feedback','readwrite'),store=tx.objectStore('feedback')
    const get=store.get(item.id)
    tx.onabort=()=>reject(tx.error || Error('这条反馈已更新，请重新打开后处理。'))
    tx.oncomplete=()=>resolve()
    get.onsuccess=()=>{
      const current:StoredFeedback=get.result
      if(!current || (current.revision || 0)!==(item.revision || 0)){tx.abort();return}
      store.put({...current,status,note,reply,revision:(current.revision || 0)+1,updatedAt:new Date().toISOString()},item.id)
    }
  })
}
