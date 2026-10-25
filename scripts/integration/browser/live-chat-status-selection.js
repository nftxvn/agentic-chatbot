// A real status response is delayed while the user selects another fixture ticket.
async (page) => {
  await page.getByText('Riwayat panjang sintetis', { exact: true }).click();
  await page.getByText(/^Pesan sintetis 35:/).waitFor({ state: 'attached' });
  const pattern = '**/api/tickets/1/status';
  await page.route(pattern, async route => {
    const response = await route.fetch();
    await new Promise(resolve => setTimeout(resolve, 1200));
    await route.fulfill({ response });
  });
  try {
    const saved = page.waitForResponse(response => response.request().method() === 'PATCH'
      && new URL(response.url()).pathname === '/api/tickets/1/status');
    await page.getByRole('button', { name: 'Tandai Selesai', exact: true }).click();
    await page.getByText('Percakapan kedua sintetis', { exact: true }).click();
    await saved;
    await page.waitForTimeout(200);
    const input = page.getByRole('textbox', { name: 'Ketik balasan resmi petugas di sini...' });
    if (!await input.isEnabled()) throw new Error('Status response for ticket 1 disabled ticket 2 input');
    if (await page.getByText(/^Pesan sintetis 35:/).count()) throw new Error('Status response switched the conversation');
    return { check: 'late_status_response_does_not_mutate_another_ticket', status: 'passed' };
  } finally {
    await page.unroute(pattern);
    await page.evaluate(async () => {
      const csrf = document.cookie.split('; ').find(item => item.startsWith('XSRF-TOKEN='))?.slice('XSRF-TOKEN='.length);
      const response = await fetch('/api/tickets/1/status', {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-XSRF-TOKEN': decodeURIComponent(csrf || '') },
        body: JSON.stringify({ status: 'in_progress' }),
      });
      if (response.status !== 200) throw new Error('Could not restore synthetic ticket status');
    });
  }
}
