// Run from the app shell; delay only GET settings to observe its loading UI.
async (page) => {
  if (new URL(page.url()).pathname === '/settings/chatbot')
    await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  const pattern = '**/api/settings/chatbot';
  await page.route(pattern, async route => {
    if (route.request().method() === 'GET') await new Promise(resolve => setTimeout(resolve, 1800));
    await route.continue();
  });
  try {
    await page.getByRole('link', { name: 'Konfigurasi AI', exact: true }).click();
    await page.locator('.skeleton').first().waitFor({ state: 'visible', timeout: 5000 });
    await page.screenshot({ path: 'settings-loading.png' });
    await page.waitForFunction(() => document.querySelectorAll('.skeleton').length === 0, undefined, { timeout: 15000 });
    return { check: 'settings_real_response_with_delayed_loading_state', status: 'passed' };
  } finally {
    await page.unroute(pattern);
  }
}
