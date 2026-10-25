// Both fixture tickets must be visible. Responses remain real; the first is delayed.
async (page) => {
  const pattern = '**/api/tickets/1/messages';
  await page.route(pattern, async route => {
    const response = await route.fetch();
    await new Promise(resolve => setTimeout(resolve, 1400));
    await route.fulfill({ response });
  });
  try {
    const delayed = page.waitForResponse(response => new URL(response.url()).pathname === '/api/tickets/1/messages');
    await page.getByText('Riwayat panjang sintetis', { exact: true }).click();
    const selected = page.waitForResponse(response => new URL(response.url()).pathname === '/api/tickets/2/messages');
    await page.getByText('Percakapan kedua sintetis', { exact: true }).click();
    await selected;
    await delayed;
    await page.waitForTimeout(200);
    await page.screenshot({ path: 'live-chat-stale-response.png' });
    if (await page.getByText(/^Pesan sintetis 35:/).count()) throw new Error('Late ticket 1 response replaced the selected ticket 2 conversation');
    return { check: 'late_response_cannot_replace_selected_ticket_conversation', status: 'passed' };
  } finally {
    await page.unroute(pattern);
  }
}
