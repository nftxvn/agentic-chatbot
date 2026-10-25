// Ticket 1 is a synthetic web conversation, with no API key or external delivery.
async (page) => {
  await page.getByText('Riwayat panjang sintetis', { exact: true }).click();
  await page.getByText(/^Pesan sintetis 35:/).waitFor({ state: 'attached' });
  const stream = page.getByText(/^Pesan sintetis 35:/).locator('xpath=ancestor::div[contains(@class,"overflow-y-auto")][1]');
  if (!await stream.evaluate(element => element.scrollHeight > element.clientHeight + 100)) throw new Error('Scroll fixture is too short');
  await stream.evaluate(element => { element.scrollTo({ top: 0, behavior: 'instant' }); element.dispatchEvent(new Event('scroll')); });
  const pollingText = `Polling fixture browser ${Date.now()}`;
  const response = await page.evaluate(async message => {
    const csrf = document.cookie.split('; ').find(item => item.startsWith('XSRF-TOKEN='))?.slice('XSRF-TOKEN='.length);
    const result = await fetch('/api/tickets/1/messages', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-XSRF-TOKEN': decodeURIComponent(csrf || '') },
      body: JSON.stringify({ message }),
    });
    return result.status;
  }, pollingText);
  if (response !== 201) throw new Error(`Synthetic web message HTTP ${response}`);
  await page.getByText(pollingText, { exact: true }).waitFor({ state: 'attached', timeout: 15000 });
  if (await stream.evaluate(element => element.scrollTop) > 5) throw new Error('Polling pulled the reader away from old messages');
  const newest = page.getByTitle('Gulir ke pesan terbaru', { exact: true });
  await newest.waitFor();
  await page.screenshot({ path: 'live-chat-unread-scrolled.png' });
  await newest.click();
  await page.waitForFunction(() => {
    const element = [...document.querySelectorAll('div.overflow-y-auto')].find(item => item.textContent.includes('Polling fixture browser'));
    return element && element.scrollHeight - element.clientHeight - element.scrollTop < 100;
  });

  const input = page.getByRole('textbox', { name: 'Ketik balasan resmi petugas di sini...' });
  const draft = `Browser retry reply ${Date.now()}`;
  const pattern = '**/api/tickets/1/messages';
  await page.route(pattern, route => route.request().method() === 'POST'
    ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"Synthetic reply failure"}' })
    : route.continue());
  try {
    await input.fill(draft);
    await page.getByRole('button', { name: 'Kirim', exact: true }).click();
    await page.waitForFunction(value => {
      const input = document.querySelector('input[placeholder="Ketik balasan resmi petugas di sini..."]');
      return input && !input.disabled && input.value === value && document.activeElement === input;
    }, draft);
    await page.screenshot({ path: 'live-chat-reply-failure-focus.png' });
  } finally {
    await page.unroute(pattern);
  }
  const saved = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/tickets/1/messages');
  await page.getByRole('button', { name: 'Kirim', exact: true }).click();
  if ((await saved).status() !== 201) throw new Error('Real web reply retry failed');
  await page.waitForFunction(() => {
    const input = document.querySelector('input[placeholder="Ketik balasan resmi petugas di sini..."]');
    return input && !input.disabled && input.value === '' && document.activeElement === input;
  });
  await page.getByText(draft, { exact: true }).waitFor();
  return { check: 'real_polling_scroll_and_reply_error_retry_focus', status: 'passed' };
}
