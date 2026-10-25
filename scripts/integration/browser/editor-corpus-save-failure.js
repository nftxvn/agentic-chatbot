// A correction failure must block corpus dispatch and keep the editable draft.
async (page) => {
  const path = new URL(page.url()).pathname;
  const number = new URL(page.url()).searchParams.get('page');
  const pattern = `**/api${path}/pages/${number}`;
  const editor = page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' });
  const draft = `CORPUS-BLOCKED-SAVE-${Date.now()}\n`;
  let embeds = 0;
  const listener = request => { if (new URL(request.url()).pathname === `/api${path}/embed`) embeds++; };
  page.on('request', listener);
  await page.route(pattern, route => route.request().method() === 'PUT'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"Synthetic correction failure before corpus"}' })
    : route.continue());
  try {
    await editor.fill(draft);
    await page.getByRole('button', { name: 'Simpan ke Korpus (ChromaDB)', exact: true }).click();
    const failed = page.waitForResponse(response => response.request().method() === 'PUT' && new URL(response.url()).pathname === `/api${path}/pages/${number}`);
    await page.getByRole('button', { name: 'Ya, Simpan', exact: true }).click();
    await failed;
    await page.waitForTimeout(250);
    if (embeds !== 0 || await editor.inputValue() !== draft) throw new Error('Corpus dispatched after failed correction, or draft was lost');
  } finally {
    await page.unroute(pattern);
    page.off('request', listener);
  }
  const saved = page.waitForResponse(response => response.request().method() === 'PUT' && new URL(response.url()).pathname === `/api${path}/pages/${number}`);
  await editor.focus();
  await page.keyboard.press('Control+s');
  if ((await saved).status() !== 200) throw new Error('Correction retry failed');
  return { check: 'failed_correction_blocks_corpus_and_retains_draft', status: 'passed', embeds };
}
