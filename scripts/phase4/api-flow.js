async(page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));let rejectRead=false,forbidden=false,failSave=true,saves=0;
 let settings={version:1,concurrency:1,timeoutSeconds:600,maxUploadBytes:10485760,defaultSkillIds:{wallpaper:null,product:null,text:null},dingtalk:{corpId:'',appId:'',callbackDomain:'',state:'unconfigured'},audit:[]};
 const users=Array.from({length:25},(_,i)=>({id:'u'+i,name:i===0?'Alpha成员':i===1?'Beta成员':'成员'+i,department:'设计部',role:'designer',status:'active',lastLoginAt:null}));
 await page.route('**/api/v1/**',async route=>{
  const req=route.request(),url=req.url(),path=url.split('/api/v1')[1].split('?')[0];const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/auth/me')return json({id:'admin',name:'管理员',role:'super_admin',status:'active'});
  if(path==='/workspace')return json({templates:[],tasks:[],archives:[]});
  if(path==='/management/users'){
   if(forbidden)return json({code:'FORBIDDEN',message:'无权读取成员'},403);if(rejectRead){rejectRead=false;return json({code:'DOWN',message:'成员读取失败'},503);}
   const q=decodeURIComponent((url.match(/[?&]search=([^&]*)/)||[])[1]||'');if(q==='Alpha')await page.waitForTimeout(500);const p=Number((url.match(/[?&]page=(\d+)/)||[])[1]||1),items=users.filter(u=>u.name.includes(q));return json({items:items.slice((p-1)*12,p*12),total:items.length,page:p,pageSize:12});
  }
  if(path==='/management/skills')return json([]);
  if(path==='/management/settings'){
   if(req.method()==='PUT'){saves++;if(failSave){failSave=false;return json({code:'SAVE_FAILED',message:'配置保存失败，保留输入'},503)}const input=req.postDataJSON();settings={...input,version:2,dingtalk:{...input.dingtalk,state:'unconfigured'},audit:[{id:'audit1',operatorId:'admin',operatorName:'管理员',changedAt:new Date().toISOString(),version:2,fields:['concurrency']}]};return json(settings);}
   return json(settings);
  }
  return json({code:'NOT_FOUND',message:'测试未提供接口'},404);
 });
 await page.goto('http://127.0.0.1:3018/#/management/users');await page.reload();await page.getByRole('heading',{name:'用户与角色',exact:true}).waitFor();await page.getByText('Alpha成员',{exact:true}).waitFor();
 if(await page.getByRole('button',{name:'分配角色 / 状态'}).count()!==12)throw Error('分页不是12');await page.getByRole('listitem',{name:'第 2 页',exact:true}).click();await page.getByText('成员12',{exact:true}).waitFor();
 await page.getByRole('textbox',{name:'搜索成员'}).fill('Alpha');await page.waitForTimeout(100);await page.getByRole('textbox',{name:'搜索成员'}).fill('Beta');await page.getByText('Beta成员',{exact:true}).waitFor();await page.waitForTimeout(600);if(await page.getByText('Alpha成员',{exact:true}).count())throw Error('迟到覆盖新查询');
 rejectRead=true;await page.getByRole('button',{name:'刷新成员'}).click();await page.getByText('成员读取失败',{exact:true}).waitFor();await page.getByText('Beta成员',{exact:true}).waitFor();await page.getByRole('button',{name:'重试加载'}).click();await page.getByText('成员读取失败',{exact:true}).waitFor({state:'hidden'});
 forbidden=true;await page.getByRole('button',{name:'刷新成员'}).click();await page.getByText('无权读取成员',{exact:true}).waitFor();if(await page.getByText('Beta成员',{exact:true}).count())throw Error('403仍展示旧成员');
 await page.goto('http://127.0.0.1:3018/#/management/settings');await page.getByLabel('执行并发',{exact:true}).fill('4');await page.getByRole('button',{name:'保存配置'}).click();await page.getByText('配置保存失败，保留输入',{exact:true}).waitFor();if(await page.getByLabel('执行并发',{exact:true}).inputValue()!=='4')throw Error('写失败丢输入');await page.getByRole('button',{name:'保存配置'}).dblclick();await page.getByText('执行与上传 · 配置 v2').waitFor();if(saves!==2)throw Error('重复提交 '+saves);
 await page.unrouteAll();if(errors.length)throw Error(errors.join('\n'));return 'PASS HTTP分页、搜索竞态、503保留/重试、403清受限数据、保存失败保留和双击锁';
}
