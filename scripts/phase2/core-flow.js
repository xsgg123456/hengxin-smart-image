async (page) => {
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto('http://127.0.0.1:3008/#/image-processing/wallpaper');
  await page.reload();
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.getByRole('button', {name:'提交生成任务'}).click();
  await page.getByRole('alert').filter({hasText:'请先上传素材'}).first().waitFor();
  await page.getByRole('button', {name:'使用示例素材'}).click();
  await page.getByRole('textbox', {name:'任务名称',exact:true}).fill('Phase2 壁纸验收');
  await page.getByRole('textbox', {name:'SKU',exact:true}).fill('SKU-2026');
  await page.screenshot({path:'output/playwright/phase2-create.png', fullPage:true});
  await page.getByRole('button', {name:'提交生成任务'}).click();
  const drawer = page.getByRole('dialog',{name:'Phase2 壁纸验收',exact:true});
  await drawer.waitFor();
  await drawer.getByRole('button',{name:'修改这张',exact:true}).nth(1).click();
  const feedback = page.getByRole('dialog',{name:'修改第 2 张图片',exact:true});
  await feedback.getByRole('textbox').fill('只修改第二张');
  await feedback.getByRole('button',{name:'提交修改'}).click();
  await feedback.waitFor({state:'hidden'});
  await drawer.getByText('v2',{exact:true}).waitFor();
  if (await drawer.getByText('v1',{exact:true}).count() !== 7) throw new Error('其他图片版本变化');
  await drawer.getByRole('button',{name:'归档到成品库',exact:true}).click();
  await drawer.getByRole('button',{name:'已归档',exact:true}).waitFor();
  await drawer.getByRole('button',{name:'关闭此对话框',exact:true}).click();
  await page.getByRole('menuitem',{name:'成品库',exact:true}).click();
  await page.getByRole('heading',{name:'Phase2 壁纸验收',exact:true}).waitFor();
  for (const [mode,label] of [['product','商品'],['text','文字']]) {
    await page.goto('http://127.0.0.1:3008/#/image-processing/'+mode);
    await page.getByRole('heading',{name:'替换'+label,exact:true}).waitFor();
    await page.getByRole('button',{name:'使用示例素材'}).click();
    await page.getByRole('textbox',{name:'任务名称',exact:true}).fill('Phase2 '+label+'验收');
    if(mode==='text') {
      await page.getByRole('textbox',{name:'修改要求',exact:true}).fill('');
      await page.getByRole('button',{name:'提交生成任务'}).click();
      await page.getByRole('alert').filter({hasText:'请填写文字修改要求'}).first().waitFor();
      await page.getByRole('textbox',{name:'修改要求',exact:true}).fill('将新品改为秋日上新');
    }
    await page.getByRole('button',{name:'提交生成任务'}).click();
    const result=page.getByRole('dialog',{name:'Phase2 '+label+'验收',exact:true});
    await result.waitFor();
    await result.getByRole('button',{name:'归档到成品库',exact:true}).waitFor();
    if (mode==='text' && await result.getByText('v1',{exact:true}).count()!==2) throw new Error('文字输出数量错误');
    await result.getByRole('button',{name:'关闭此对话框',exact:true}).click();
  }
  return 'PASS 三类创建、文字必填、SKU输入、壁纸8张/文字2张输出、单图返工其余版本不变、归档回归';
}
