async (page) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Perbesar (+)', exact: true }).click();
  if (await page.getByRole('button', { name: 'Auto', exact: true }).count()) throw new Error('Zoom did not leave auto mode');
  const number = Number(new URL(page.url()).searchParams.get('page'));
  await page.getByRole('button', { name: number === 1 ? 'Next' : 'Prev', exact: true }).click();
  await page.getByRole('button', { name: 'Auto', exact: true }).waitFor();
  const captured = [];
  for (const theme of ['dark', 'light']) {
    if (await page.locator('html').getAttribute('data-theme') !== theme)
      await page.getByRole('button', { name: theme === 'dark' ? 'Mode Gelap' : 'Mode Terang', exact: true }).click();
    for (const [width, height] of [[1440, 1000], [1024, 768], [390, 844]]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(350);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (overflow > 1) throw new Error(`Editor overflow ${overflow}px at ${width}/${theme}`);
      const screenshot = `editor-${theme}-${width}.png`;
      await page.screenshot({ path: screenshot });
      captured.push({ width, height, theme, screenshot, horizontalOverflow: overflow });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  const preview = page.waitForResponse(response => /\/chunks\/preview$/.test(new URL(response.url()).pathname));
  await page.getByRole('button', { name: 'Pratinjau Potongan', exact: true }).click();
  if ((await preview).status() !== 200) throw new Error('Real chunk preview failed');
  await page.getByRole('button', { name: 'Tutup', exact: true }).last().waitFor();
  await page.screenshot({ path: 'editor-real-preview.png' });
  await page.getByRole('button', { name: 'Tutup', exact: true }).last().click();
  return { check: 'editor_zoom_reset_preview_two_themes_three_viewports', status: 'passed', captured };
}
