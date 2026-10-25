// Identity tab open with the assistant name edited in the synthetic database.
async (page) => {
  const input = page.getByRole('textbox', { name: 'Asisten Virtual Diskominfotik' });
  const expected = await input.inputValue();
  const pattern = '**/api/settings/chatbot';
  await page.route(pattern, route => route.request().method() === 'POST'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"Synthetic settings save failure"}' })
    : route.continue());
  try {
    await page.getByRole('button', { name: 'Simpan Perubahan', exact: true }).click();
    await page.getByText('Synthetic settings save failure', { exact: true }).waitFor();
    if (await input.inputValue() !== expected) throw new Error('Failed settings save cleared edited form');
    await page.screenshot({ path: 'settings-save-failure.png' });
  } finally {
    await page.unroute(pattern);
  }
  const saved = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/settings/chatbot');
  await page.getByRole('button', { name: 'Simpan Perubahan', exact: true }).click();
  if ((await saved).status() !== 200) throw new Error('Real settings retry failed');
  const response = await page.request.get(new URL('/api/settings/chatbot', page.url()).href, {
    headers: { Origin: new URL(page.url()).origin, Referer: page.url(), Accept: 'application/json' },
  });
  const body = await response.json();
  if (body.chatbot_name !== expected) throw new Error('Settings not persisted on real backend');
  await page.getByRole('button', { name: 'Simpan Perubahan', exact: true }).waitFor({ state: 'hidden' });
  return { check: 'settings_failure_retains_form_and_real_retry_persists', status: 'passed' };
}
