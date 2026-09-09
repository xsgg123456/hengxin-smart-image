async(page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewportSize({width:1440,height:1000});
 const login=()=>page.getByRole('heading',{name:'恒信 AI 换套图',exact:true});
 const select=async(label,value)=>{await page.locator('.el-select').filter({has:page.getByRole('combobox',{name:label,exact:true})}).click();await page.getByRole('option',{name:value,exact:true}).click();};
 const scenarios={authorizing:'正在等待钉钉授权结果',denied:'你已拒绝授权',expired:'会话已过期',pending:'等待超级管理员分配角色',disabled:'账号已禁用','enterprise-mismatch':'当前账号不属于目标企业',unavailable:'认证服务暂不可用'};
 for(const [state,message] of Object.entries(scenarios)){
   await page.goto('http://127.0.0.1:3008/?auth='+state+'#/tasks/index');await login().waitFor();
   await page.getByRole('alert').filter({hasText:message}).waitFor();
   if(await page.getByRole('menuitem',{name:'任务中心',exact:true}).count())throw new Error(state+'泄漏业务菜单');
   if(state!=='expired'){
     await page.getByRole('button',{name:'重新授权',exact:true}).click();
     await page.getByRole('button',{name:'重新授权',exact:true}).waitFor({state:'visible'});
     await page.waitForTimeout(500);await login().waitFor();
   }
 }
 await select('登录场景','正常登录');await page.getByRole('button',{name:'钉钉登录',exact:true}).click();
 await page.getByRole('heading',{name:'任务中心',exact:true}).waitFor();
 await page.goto('http://127.0.0.1:3008/#/auth/login?redirect=https://evil.test');await login().waitFor();
 await page.getByText('钉钉容器',{exact:true}).click();
 await page.getByText('钉钉电脑端 · 容器免登',{exact:true}).waitFor();
 await page.waitForTimeout(350);
 await page.screenshot({path:'output/playwright/phase4-login-container.png'});
 await page.getByRole('button',{name:'钉钉免登',exact:true}).click();
 await page.getByRole('menuitem',{name:'任务中心',exact:true}).waitFor();
 if(!page.url().includes('#/image-processing/wallpaper'))throw new Error('不安全回跳');
 for(const role of ['super_admin','design_manager','designer','operator']){
   await page.goto('http://127.0.0.1:3008/?role='+role+'#/management/usage');await page.getByRole('menuitem',{name:'管理中心',exact:true}).waitFor();
   await page.getByRole('menuitem',{name:'管理中心',exact:true}).click();
   const text=await page.locator('aside').count()?await page.locator('aside').innerText():await page.locator('body').innerText();
   if((await page.getByRole('menuitem',{name:'用户与角色',exact:true}).count()>0)!==(role==='super_admin'))throw new Error(role+'用户菜单隔离失败');
   if((await page.getByRole('menuitem',{name:'执行监控',exact:true}).count()>0)!==(['super_admin','design_manager'].includes(role)))throw new Error(role+'监控菜单隔离失败');
   if(!text.includes('调用统计'))throw new Error('缺失统计');
 }
 let status=401,expired=false,authRole='operator';
 await page.route('**/api/v1/**',async route=>{
   const url=route.request().url();
   if(url.endsWith('/auth/me'))return route.fulfill(status===200?{json:{id:'u1',name:'真实接口测试',role:authRole,status:'active'}}:{status,json:{message:status===401?'会话已过期':'认证连接暂不可用'}});
   if(expired)return route.fulfill({status:401,json:{message:'业务会话已过期'}});
   if(url.endsWith('/workspace'))return route.fulfill({json:{templates:[],tasks:[],archives:[]}});
   if(url.includes('/tasks?'))return route.fulfill({json:{items:[],page:1,pageSize:12,total:0,stats:{total:0,processing:0,ready:0,archived:0}}});
   return route.fulfill({json:{items:[],page:1,pageSize:12,total:0}});
 });
 await page.goto('http://127.0.0.1:3018/?role=super_admin#/tasks/index');await login().waitFor();
 if(await page.getByRole('combobox',{name:'预览角色',exact:true}).count())throw new Error('真实模式暴露角色工具');
 await page.getByRole('button',{name:'钉钉登录',exact:true}).click();await page.getByRole('alert').filter({hasText:'尚未接入'}).waitFor();
 status=503;await page.goto('http://127.0.0.1:3018/#/tasks/index');await page.reload();await page.getByRole('button',{name:'重新连接',exact:true}).waitFor();
 if(await page.getByRole('button',{name:'钉钉登录',exact:true}).count())throw new Error('503被误识别为401');
 status=200;await page.getByRole('button',{name:'重新连接',exact:true}).click();await page.getByRole('heading',{name:'任务中心',exact:true}).waitFor();
 authRole='super_admin';await page.evaluate(()=>window.dispatchEvent(new Event('hengxin:identity-changed')));
 await page.getByRole('menuitem',{name:'管理中心',exact:true}).waitFor();await page.getByRole('menuitem',{name:'管理中心',exact:true}).click();
 await page.getByRole('menuitem',{name:'用户与角色',exact:true}).waitFor();
 authRole='operator';await page.evaluate(()=>window.dispatchEvent(new Event('hengxin:identity-changed')));
 await page.getByRole('menuitem',{name:'用户与角色',exact:true}).waitFor({state:'hidden'});
 await page.getByRole('menuitem',{name:'任务中心',exact:true}).waitFor();
 await page.getByRole('menuitem',{name:'任务中心',exact:true}).click();await page.getByRole('heading',{name:'任务中心',exact:true}).waitFor();
 expired=true;
 await page.evaluate(async()=>{const {getService}=await import('/src/api/hengxin/client.ts');try{await(await getService()).getWorkspace();}catch{}});
 await login().waitFor();
 if(await page.getByRole('menuitem',{name:'任务中心',exact:true}).count())throw new Error('业务401后仍可操作');
 await page.waitForTimeout(1500);await page.screenshot({path:'output/playwright/phase4-login-expired-real.png'});
 await page.unroute('**/api/v1/**');
 if(errors.length)throw new Error(errors.join('\n'));
 return 'PASS 全部7种登录异常、模拟重试、容器入口、安全回跳、四角色菜单、身份变更重建路由、真实401/503分流、业务401锁定、真实模式无角色工具';
}
