// Capture existing layouts; no CSS, markup or application data is changed here.
async (page) => {
  const routes = [
    ['Dashboard', 'DASHBOARD DOKUMEN', 'dashboard'],
    ['Konfigurasi AI', 'KONFIGURASI AI', 'settings'],
    ['Integrasi', 'INTEGRASI', 'integrations'],
    ['Monitoring', 'MONITORING', 'monitoring'],
    ['Live Chat & Tiket', 'LIVE CHAT & TIKET', 'live-chat'],
  ];
  const sizes = [[1440, 1000], [1024, 768], [390, 844]];
  const captured = [];
  for (const [link, _heading, slug] of routes) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('link', { name: link, exact: link !== 'Live Chat & Tiket' }).click();
    await page.waitForFunction(() => !document.querySelector('.skeleton'));
    for (const theme of ['dark', 'light']) {
      const current = await page.locator('html').getAttribute('data-theme');
      if (current !== theme) await page.getByRole('button', { name: theme === 'dark' ? 'Mode Gelap' : 'Mode Terang', exact: true }).click();
      await page.waitForFunction(theme => document.documentElement.dataset.theme === theme, theme);
      for (const [width, height] of sizes) {
        await page.setViewportSize({ width, height });
        await page.waitForTimeout(350);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
        if (overflow > 1) throw new Error(`${slug} ${theme} ${width}: horizontal page overflow ${overflow}px`);
        const file = `${slug}-${theme}-${width}.png`;
        await page.screenshot({ path: file });
        captured.push({ page: slug, theme, width, height, horizontalOverflow: overflow, screenshot: file });
      }
    }
  }
  await page.getByRole('button', { name: 'Buka Navigasi', exact: true }).click();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await page.waitForURL('**/dashboard');
  return { check: 'five_real_pages_two_themes_three_viewports_and_mobile_navigation', status: 'passed', captured };
}
