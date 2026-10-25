// Inspect real persisted text at dispatch; stop before launching an embedding job.
async (page) => {
  const path = new URL(page.url()).pathname;
  const number = Number(new URL(page.url()).searchParams.get('page'));
  const latest = `CORPUS-LATEST-BROWSER-${Date.now()}\n  Koreksi terakhir harus masuk korpus.\n`;
  let stored;
  const pattern = `**/api${path}/embed`;
  await page.route(pattern, async route => {
    const response = await page.request.get(new URL(`/api${path}/pages`, page.url()).href, {
      headers: { Origin: new URL(page.url()).origin, Referer: page.url(), Accept: 'application/json' },
    });
    stored = (await response.json()).data.halaman.find(item => item.page_number === number)?.text;
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{"message":"Synthetic stop after checking correction flush"}' });
  });
  await page.evaluate(() => { window.__browserOriginalAlert = window.alert; window.alert = () => {}; });
  try {
    await page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' }).fill(latest);
    await page.getByRole('button', { name: 'Simpan ke Korpus (ChromaDB)', exact: true }).click();
    const response = page.waitForResponse(response => new URL(response.url()).pathname === `/api${path}/embed`);
    await page.getByRole('button', { name: 'Ya, Simpan', exact: true }).click();
    await response;
    if (stored !== latest) throw new Error(`Corpus dispatch used stale correction: ${JSON.stringify({ stored, latest })}`);
    return { check: 'corpus_dispatch_flushes_latest_correction', status: 'passed' };
  } finally {
    await page.unroute(pattern);
    await page.evaluate(() => { window.alert = window.__browserOriginalAlert; delete window.__browserOriginalAlert; });
  }
}
