import test from 'node:test'
import assert from 'node:assert/strict'
import { createExecutionManagement, isApiMonitor, isExecutionSettings } from '../src/api/execution-management'
const snapshot = () => ({checkedAt:'2026-10-10T08:00:00Z',incidents:[],incidentsTruncated:false,
  channels:['api','cli'].map(channel=>({channel,concurrencyLimit:5,imagesPerBatch:channel==='api'?10:null,state:'unknown',queueState:'available',enabled:true,paused:null,pauseReason:null,sharedActiveTurns:null,otherActiveTurns:null,workers:[],metrics:[{phase:'queued',tasks:0,images:0,turns:null}]}))})
test('heartbeat unknown remains distinct from available zero business queue',()=>{
  const value=snapshot();assert.ok(isApiMonitor(value))
  assert.equal(value.channels[0]?.state,'unknown');assert.equal(value.channels[0]?.metrics[0]?.images,0)
  assert.equal(isApiMonitor({...value,channels:[value.channels[0],value.channels[0]]}),false)
  assert.equal(isApiMonitor({...value,channels:[{...value.channels[0],metrics:[{phase:'queued',tasks:0,images:-1,turns:null}]},value.channels[1]]}),false)
})
test('actual HTTP endpoint returns unknown unchanged and failures never fabricate data',async()=>{
  let requested=''
  const api=createExecutionManagement('/api/v1',async input=>{requested=String(input);return new Response(JSON.stringify(snapshot()),{headers:{'content-type':'application/json'}})})
  assert.equal((await api.getApiMonitor()).channels[0]?.state,'unknown')
  assert.equal(requested,'/api/v1/management/api-monitor')
  await assert.rejects(createExecutionManagement('/api',async()=>new Response('{}',{status:503})).getApiMonitor(),{status:503})
  await assert.rejects(createExecutionManagement('/api',async()=>new Response('{}',{headers:{'content-type':'application/json'}})).getApiMonitor(),{code:'INVALID_RESPONSE'})
})
test('configuration contract rejects missing API or CLI fields',()=>{
  const data={api:{enabled:true,taskConcurrency:7,imagesPerBatch:9,requestTimeoutSeconds:190,downloadTimeoutSeconds:70,leaseSeconds:400,model:'image',quality:'xhigh',resolution:'1K',imagesPerRequest:1,sizePolicy:'跟随原图宽高'},cli:{enabled:true,concurrency:3,capacity:4,timeoutSeconds:600,timeoutCapacity:7200,model:'gpt-6-astra',reasoningEffort:'high',usesSkills:false},maxUploadBytes:1048576,retention:{enabled:false,cacheIdleDays:1,historyIdleDays:7}}
  assert.ok(isExecutionSettings(data));assert.equal(isExecutionSettings({...data,cli:{...data.cli,usesSkills:undefined}}),false)
})
