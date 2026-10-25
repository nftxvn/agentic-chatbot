// Complete the real logout and revisit a private route.
async (page) => {
  await page.getByTitle('Menu Akun Admin', { exact: true }).click();
  await page.getByRole('button', { name: 'Keluar / Logout', exact: true }).click();
  const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/logout');
  await page.getByRole('button', { name: 'Keluar', exact: true }).click();
  if (!(await response).ok()) throw new Error('Real logout failed');
  await page.waitForURL('**/login');
  await page.goto(new URL('/dashboard', page.url()).href);
  await page.waitForURL('**/login');
  await page.getByRole('button', { name: 'Masuk Ke Dashboard', exact: true }).waitFor();
  await page.screenshot({ path: 'logged-out-private-route.png' });
  return { check: 'real_browser_logout_blocks_private_route_after_reload', status: 'passed' };
}
