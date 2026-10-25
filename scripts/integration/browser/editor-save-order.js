// Delay the first real PUT before delivery, then request a newer save/navigation.
async (page) => {
  const path = new URL(page.url()).pathname;
  const number = Number(new URL(page.url()).searchParams.get('page'));
  const endpoint = `/api${path}/pages/${number}`;
  const pattern = `**${endpoint}`;
  const editor = page.getByRole('textbox', { name: 'Teks hasil ekstraksi halaman ini...' });
  const marker = Date.now();
  const first = `FIRST-OLD-BROWSER-SAVE-${marker}\n`;
  const latest = `LATEST-BROWSER-SAVE-${marker}\n`;
  let writes = 0;
  await page.route(pattern, async route => {
    if (route.request().method() === 'PUT' && ++writes === 1) await new Promise(resolve => setTimeout(resolve, 2800));
    await route.continue();
  });
  try {
    const requested = page.waitForRequest(request => request.method() === 'PUT' && new URL(request.url()).pathname === endpoint);
    const delivered = page.waitForResponse(response => response.request().method() === 'PUT' && new URL(response.url()).pathname === endpoint && response.request().postDataJSON().text === first);
    await editor.fill(first);
    await requested;
    await editor.fill(latest);
    await page.getByRole('button', { name: number === 1 ? 'Next' : 'Prev', exact: true }).click();
    await delivered;
    await page.waitForURL(url => Number(url.searchParams.get('page')) !== number);
    const response = await page.request.get(new URL(`/api${path}/pages`, page.url()).href, {
      headers: { Origin: new URL(page.url()).origin, Referer: page.url(), Accept: 'application/json' },
    });
    const stored = (await response.json()).data.halaman.find(item => item.page_number === number)?.text;
    if (stored !== latest) throw new Error(`Older autosave overwrote latest correction: ${JSON.stringify({ stored, latest, writes })}`);
    return { check: 'late_autosave_cannot_overwrite_newer_save', status: 'passed', writes };
  } finally {
    await page.unroute(pattern);
  }
}
