// Real browser confirmation -> Laravel -> Celery/Ollama -> shared Chroma server.
async (page) => {
  const path = new URL(page.url()).pathname;
  const marker = `BROWSER-KORPUS-${Date.now()}`;
  const value = `  ${marker}\n\n    Petugas memeriksa kelengkapan berkas registrasi dan menyimpan hasil koreksi terakhir sebelum embedding.\n`;
  await page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' }).fill(value);
  await page.getByRole('button', { name: 'Simpan ke Korpus (ChromaDB)', exact: true }).click();
  const dispatched = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === `/api${path}/embed`);
  await page.getByRole('button', { name: 'Ya, Simpan', exact: true }).click();
  if ((await dispatched).status() !== 202) throw new Error('Real corpus dispatch failed');
  const headers = { Origin: new URL(page.url()).origin, Referer: page.url(), Accept: 'application/json' };
  let document;
  for (let attempt = 0; attempt < 25; attempt++) {
    const response = await page.request.get(new URL(`/api${path}`, page.url()).href, { headers });
    document = (await response.json()).data.document;
    if (document.status === 'completed') break;
    if (document.status === 'failed') throw new Error('Embedding worker reported failure');
    await page.waitForTimeout(2000);
  }
  if (document.status !== 'completed' || document.total_chunks < 1) throw new Error('Real embedding did not finish within the browser check');
  const response = await page.request.get(new URL(`/api${path}/chunks`, page.url()).href, { headers });
  const chunks = (await response.json()).chunks;
  if (!chunks?.length || !JSON.stringify(chunks).includes(marker)) throw new Error('Latest browser correction missing from Chroma');
  await page.getByRole('button', { name: 'Selesai & Lihat Status Dokumen', exact: true }).waitFor({ timeout: 15000 });
  await page.screenshot({ path: 'editor-real-corpus-completed.png' });
  await page.getByRole('button', { name: 'Selesai & Lihat Status Dokumen', exact: true }).click();
  return { check: 'browser_latest_correction_reaches_real_chroma', status: 'passed', chunks: document.total_chunks, marker };
}
