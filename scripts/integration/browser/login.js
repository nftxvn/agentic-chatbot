// Credentials belong only to start_browser_environment.py's disposable fixture.
async (page) => {
  await page.getByRole('textbox', { name: 'Alamat Email', exact: true }).fill('browser@example.test');
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill('Browser-Synthetic-Only-2026!');
  await page.getByRole('button', { name: 'Masuk Ke Dashboard', exact: true }).click();
  await page.waitForURL('**/dashboard');
  await page.getByTitle('Menu Akun Admin', { exact: true }).waitFor();
  return { check: 'real_browser_login', status: 'passed' };
}
