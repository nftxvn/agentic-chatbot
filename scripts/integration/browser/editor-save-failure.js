// Open page 1. Only the correction PUT is failed; all other traffic stays real.
async (page) => {
  const documentPath = new URL(page.url()).pathname;
  const pattern = `**/api${documentPath}/pages/1`;
  const editor = page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' });
  const draft = '  DRAFT-BROWSER-SAVE-FAILURE\n    Isi ini tidak boleh hilang.\n';
  await page.route(pattern, route => route.request().method() === 'PUT'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ success: false, message: 'Synthetic save failure' }) })
    : route.continue());
  try {
    const failed = page.waitForResponse(response => response.request().method() === 'PUT'
      && new URL(response.url()).pathname === `/api${documentPath}/pages/1`);
    await editor.fill(draft);
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await failed;
    await page.waitForTimeout(200);
    const state = { page: new URL(page.url()).searchParams.get('page'), text: await editor.inputValue() };
    await page.screenshot({ path: 'editor-save-failure.png' });
    if (state.page !== '1' || state.text !== draft) throw new Error('Failed save lost the current draft: ' + JSON.stringify(state));
    return { check: 'failed_save_keeps_current_page_and_draft', status: 'passed' };
  } finally {
    await page.unroute(pattern);
  }
}
