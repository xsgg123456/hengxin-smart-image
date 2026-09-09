async(page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewportSize({width:1280,height:1000});
 for(const [path,title] of [['usage','调用统计'],['monitor','执行监控'],['users','用户与角色'],['skills','Skill 管理'],['settings','系统配置']]){
  await page.goto(`http://127.0.0.1:3008/?role=super_admin#/management/${path}`);await page.getByRole('heading',{name:title,exact:true}).waitFor();await page.waitForTimeout(1400);
  await page.locator('#app-main').evaluate(el=>el.scrollTop=0);
  if(await page.locator('#app-main').evaluate(el=>el.scrollWidth>el.clientWidth+2))throw Error(path+'横向溢出');
  await page.screenshot({path:`output/playwright/phase4-${path}-1280.png`,fullPage:true});
 }
 await page.goto('http://127.0.0.1:3008/?role=super_admin#/tasks/index');await page.getByRole('heading',{name:'任务中心',exact:true}).waitFor();await page.waitForTimeout(1400);await page.locator('#app-main').evaluate(el=>el.scrollTop=0);await page.screenshot({path:'output/playwright/phase4-neighbor-tasks.png',fullPage:true});
 for(const [scenario,text] of [['worker-lost','Worker 心跳失联'],['auth-rejected','CLI 认证被拒绝'],['rate-limited','执行服务被限流'],['timeout','最近执行超时']]){await page.goto(`http://127.0.0.1:3008/?role=super_admin&managementScenario=${scenario}#/management/monitor`);await page.getByText(text,{exact:false}).waitFor();}
 await page.screenshot({path:'output/playwright/phase4-monitor-timeout.png',fullPage:true});
 if(errors.length)throw Error(errors.join('\n'));return 'PASS 五管理页1280无横向溢出，邻居截图及失联/认证/限流/超时分别表达';
}
