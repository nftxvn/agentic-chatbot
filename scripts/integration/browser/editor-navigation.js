// Continue on page 1 after the failed-save scenario has removed its interception.
async (page) => {
  const documentPath = new URL(page.url()).pathname;
  const editor = page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' });
  const draft = await editor.inputValue();
  const saved = page.waitForResponse(response => response.request().method() === 'PUT'
    && new URL(response.url()).pathname === `/api${documentPath}/pages/1`);
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  if ((await saved).status() !== 200) throw new Error('Save retry failed');
  await page.waitForURL(url => url.searchParams.get('page') === '2');
  await page.getByRole('button', { name: 'Prev', exact: true }).click();
  await page.waitForURL(url => url.searchParams.get('page') === '1');
  if (await editor.inputValue() !== draft) throw new Error('Successful navigation did not restore the persisted draft');

  await page.evaluate(() => {
    history.pushState({}, '', '?page=2');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await page.getByRole('combobox', { name: 'Pilih Halaman' }).selectOption('2');
  const historyDraft = '  HISTORY-SAVE-FAILURE\n    Draft halaman kedua.\n';
  const pattern = `**/api${documentPath}/pages/2`;
  await page.route(pattern, route => route.request().method() === 'PUT'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"Synthetic history save failure"}' })
    : route.continue());
  try {
    const failed = page.waitForResponse(response => response.request().method() === 'PUT'
      && new URL(response.url()).pathname === `/api${documentPath}/pages/2`);
    await editor.fill(historyDraft);
    await page.goBack();
    await failed;
    await page.waitForTimeout(200);
    if (new URL(page.url()).searchParams.get('page') !== '2' || await editor.inputValue() !== historyDraft)
      throw new Error('Failed history save did not restore URL and retain draft');
  } finally {
    await page.unroute(pattern);
  }
  const retried = page.waitForResponse(response => response.request().method() === 'PUT'
    && new URL(response.url()).pathname === `/api${documentPath}/pages/2`);
  await editor.focus();
  await page.keyboard.press('Control+s');
  if ((await retried).status() !== 200) throw new Error('Keyboard save retry failed');
  return { check: 'successful_navigation_and_failed_browser_history_keep_correct_page_text', status: 'passed' };
}
