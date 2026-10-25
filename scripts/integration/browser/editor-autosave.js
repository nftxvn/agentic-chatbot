// Playwright CLI run-code --filename: open the real two-page editor on page 1.
async (page) => {
  const documentPath = new URL(page.url()).pathname;
  const editor = page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' });
  const base = '  # Koreksi browser sintetis\n\n    Teks berindentasi tetap utuh.\n';
  const value = await editor.inputValue() === base ? base + '  Uji simpan ulang.\n' : base;
  let writes = 0;
  const count = request => {
    if (request.method() === 'PUT' && new URL(request.url()).pathname === `/api${documentPath}/pages/1`) writes++;
  };
  page.on('request', count);
  try {
    const saved = page.waitForResponse(response => response.request().method() === 'PUT'
      && new URL(response.url()).pathname === `/api${documentPath}/pages/1`, { timeout: 15000 });
    await editor.fill(value);
    const response = await saved;
    if (response.status() !== 200) throw new Error(`Autosave HTTP ${response.status()}`);
    const stored = await page.request.get(new URL(`/api${documentPath}/pages`, page.url()).href, {
      headers: { Origin: new URL(page.url()).origin, Referer: page.url(), Accept: 'application/json' },
    });
    if (stored.status() !== 200) throw new Error(`Stored-page verification HTTP ${stored.status()}`);
    const pages = (await stored.json()).data.halaman;
    if (pages.find(item => item.page_number === 1)?.text !== value) throw new Error('Browser correction formatting changed before persistence');
    if (!await editor.evaluate(element => document.activeElement === element)) throw new Error('Autosave stole editor focus');
    if (writes !== 1) throw new Error(`Expected one debounced write, got ${writes}`);
    console.log(JSON.stringify({ check: 'real_browser_autosave_preserves_whitespace_and_focus', status: 'passed', writes }));
  } finally {
    page.off('request', count);
  }
}
