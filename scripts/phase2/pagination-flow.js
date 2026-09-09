async (page) => {
  await page.goto('http://127.0.0.1:3008/?scenario=empty#/templates/index');
  await page.reload();
  await page.getByText('暂无匹配模板，可新建或清除筛选',{exact:true}).waitFor();
  for(let i=0;i<13;i++) {
    await page.getByRole('button',{name:'新建模板',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'新建套图模板',exact:true});
    await dialog.getByRole('textbox',{name:'*模板名称',exact:true}).fill('分页模板 '+String(i).padStart(2,'0'));
    await dialog.getByRole('button',{name:'使用示例套图',exact:true}).click();
    await dialog.getByRole('button',{name:'保存模板',exact:true}).click();
    await dialog.waitFor({state:'hidden'});
  }
  await page.getByRole('combobox',{name:'模板排序'}).focus();
  await page.getByRole('combobox',{name:'模板排序'}).press('ArrowDown');
  await page.getByRole('option',{name:'名称排序',exact:true}).click();
  await page.getByRole('heading',{name:'分页模板 00',exact:true}).waitFor();
  if(await page.locator('.hx-library-card').count()!==12) throw new Error('第一页不是12条');
  await page.getByRole('button',{name:'下一页',exact:true}).click();
  await page.getByRole('heading',{name:'分页模板 12',exact:true}).waitFor();
  if(await page.locator('.hx-library-card').count()!==1) throw new Error('第二页不是1条');
  await page.getByRole('textbox',{name:'搜索模板名称'}).fill('00');
  await page.getByRole('heading',{name:'分页模板 00',exact:true}).waitFor();
  if(await page.locator('.hx-library-card').count()!==1) throw new Error('搜索未重置页码');
  await page.getByRole('button',{name:'使用模板',exact:true}).click();
  await page.getByText('分页模板 00 · v1',{exact:true}).waitFor();
  if(await page.locator('.hx-template-option').count()!==4) throw new Error('创建页未分页');
  await page.getByRole('button',{name:'下一页',exact:true}).click();
  await page.waitForTimeout(250);
  if(await page.locator('.hx-template-option').count()!==4) throw new Error('创建页下一页错误');
  await page.getByRole('textbox',{name:'搜索可用模板'}).fill('00');
  await page.locator('.hx-template-option').filter({hasText:'分页模板 00'}).waitFor();
  return 'PASS 空工作区、UI创建13模板、12+1分页、名称排序、第二页搜索重置、跨页深链接、创建页4条分页搜索';
}
