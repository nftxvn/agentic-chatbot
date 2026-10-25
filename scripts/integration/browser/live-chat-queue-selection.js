// Start on ticket 2; a delayed queue refresh must preserve a later selection.
async (page) => {
  await page.getByText('Percakapan kedua sintetis', { exact: true }).click();
  const pattern = '**/api/tickets';
  await page.route(pattern, async route => {
    const response = await route.fetch();
    await new Promise(resolve => setTimeout(resolve, 1200));
    await route.fulfill({ response });
  });
  try {
    const refreshed = page.waitForResponse(response => new URL(response.url()).pathname === '/api/tickets');
    await page.getByRole('button', { name: 'Segarkan Data' }).click();
    await page.getByText('Riwayat panjang sintetis', { exact: true }).click();
    await refreshed;
    await page.waitForTimeout(200);
    if (!await page.getByText(/^Pesan sintetis 35:/).count()) throw new Error('Queue response changed the later ticket selection');
    return { check: 'queue_refresh_preserves_latest_ticket_selection', status: 'passed' };
  } finally {
    await page.unroute(pattern);
  }
}
