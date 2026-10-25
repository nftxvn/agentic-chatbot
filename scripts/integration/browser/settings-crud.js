// Playwright CLI run-code --filename. Use only start_browser_environment.py's account.
// Optional URL ?verifyPhase=before|after names comparison screenshots; default is current.
async (page) => {
  const origin = new URL(page.url()).origin;
  const phase = new URL(page.url()).searchParams.get('verifyPhase') || 'current';
  if (!['before', 'after', 'current'].includes(phase)) throw new Error('Unsupported verification phase');
  if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw new Error('Use the disposable local environment');
  await page.setViewportSize({ width: 1440, height: 1000 });
  if (!(await page.getByTitle('Menu Akun Admin', { exact: true }).innerText()).includes('browser@example.test'))
    throw new Error('Expected the synthetic browser account');

  const headers = { Origin: origin, Referer: page.url(), Accept: 'application/json' };
  const cases = [
    {
      slug: 'directories', tab: 'directories', endpoint: '/api/directories',
      heading: 'Direktori Unit Kerja, Bidang & Kontak Layanan',
      add: 'Tambah Unit / Bidang', loading: 'Memuat direktori bidang dari basis data...',
      title: 'Refactor Browser Directory', titleField: 'Contoh: Bidang Tata Kelola E-Government',
      keywordField: 'Contoh: egov, domain, hosting, vps, server, spbe',
      search: 'Cari nama bidang, email, kata kunci...', key: 'nama_bidang',
    },
    {
      slug: 'fastpaths', tab: 'fastpaths', endpoint: '/api/fast-paths',
      heading: 'Manajemen Fast-Path & FAQ Dinamis',
      add: 'Tambah Fast-Path', loading: 'Memuat data Fast-Path dari basis data...',
      title: 'Refactor Browser Fast Path', titleField: 'Contoh: Profil Kepala Dinas, Alamat Kantor, Magang Mahasiswa',
      keywordField: 'Contoh: kepala dinas, siapa kadis, pimpinan kominfo',
      search: 'Cari judul, kata kunci...', key: 'title',
    },
  ];
  const checks = [];
  const screenshots = [];
  const layouts = {};
  const capture = async (scope, file) => {
    await page.mouse.move(0, 0);
    await scope.screenshot({ path: file, animations: 'disabled', caret: 'hide' });
    layouts[file.replace(`${phase}-`, '')] = await scope.evaluate(element => {
      const base = element.getBoundingClientRect();
      const round = value => Math.round(value * 1000) / 1000;
      return Array.from(element.querySelectorAll('button,input,textarea,select')).map(control => {
        const box = control.getBoundingClientRect();
        return { tag: control.tagName, title: control.title, type: control.type,
          text: control.tagName === 'SELECT' ? undefined : control.textContent.trim(),
          value: control.value, disabled: control.disabled,
          checked: control.tagName === 'INPUT' && control.type === 'checkbox' ? control.checked : undefined,
          box: [box.x - base.x, box.y - base.y, box.width, box.height].map(round) };
      });
    });
  };
  const responseFor = (method, path) => page.waitForResponse(response => response.request().method() === method && new URL(response.url()).pathname === path);
  const readItem = async (path) => {
    const response = await page.request.get(origin + path, { headers });
    if (!response.ok()) throw new Error(`Read ${path}: HTTP ${response.status()}`);
    return (await response.json()).data;
  };
  for (const config of cases) {
    let id;
    const pattern = `**${config.endpoint}`;
    await page.route(pattern, async route => {
      if (route.request().method() === 'GET') await new Promise(resolve => setTimeout(resolve, 1000));
      await route.continue();
    });
    try {
      await page.goto(`${origin}/settings/chatbot?tab=${config.tab}`);
      await page.getByText(config.loading, { exact: true }).waitFor();
      await page.getByText(config.loading, { exact: true }).waitFor({ state: 'hidden' });
    } finally {
      await page.unroute(pattern);
    }
    checks.push(`${config.slug}: real delayed loading`);
    const root = page.getByRole('heading', { name: config.heading, exact: true })
      .locator('xpath=ancestor::div[contains(@class,"space-y-4")][1]');
    const form = page.locator('form').filter({ has: page.getByPlaceholder(config.titleField, { exact: true }) });
    const titleInput = page.getByPlaceholder(config.titleField, { exact: true });
    const edited = config.title + ' Updated';
    const card = () => page.getByRole('heading', { name: edited, exact: true })
      .locator('xpath=ancestor::div[contains(@class,"transition-all")][1]');
    try {
      let posts = 0;
      const countPost = request => { if (request.method() === 'POST' && new URL(request.url()).pathname === config.endpoint) posts++; };
      page.on('request', countPost);
      await page.getByRole('button', { name: config.add, exact: true }).click();
      await form.waitFor();
      if (!await form.evaluate(element => element.closest('.fixed')?.parentElement === document.body && document.body.style.overflow === 'hidden'))
        throw new Error(`${config.slug}: portal/scroll lock changed`);
      await form.getByRole('button', { name: 'Tambahkan', exact: true }).click();
      if (posts !== 0 || !await form.isVisible()) throw new Error(`${config.slug}: required-field validation changed`);
      page.off('request', countPost);
      checks.push(`${config.slug}: portal, scroll lock and local validation`);

      await titleInput.fill(config.title);
      await page.getByPlaceholder(config.keywordField, { exact: true }).fill('refactor browser synthetic');
      if (config.slug === 'directories') {
        await page.getByPlaceholder('Contoh: Helpdesk SPBE & Domain', { exact: true }).fill('Layanan sintetis untuk pengujian');
        await page.getByPlaceholder('egov@bandaacehkota.go.id', { exact: true }).fill('fixture@example.test');
        await page.getByPlaceholder('Pengelolaan domain dan hosting\nPengembangan aplikasi SPBE\nJaringan intra pemerintah', { exact: true })
          .fill('Tugas sintetis satu\nTugas sintetis dua');
      } else {
        await form.getByRole('combobox').selectOption('faq');
        await page.getByPlaceholder('Tuliskan teks jawaban resmi di sini (mendukung format Markdown tebal, miring, list poin)...', { exact: true })
          .fill('**Jawaban sintetis**\nBaris kedua untuk pengujian.');
      }
      await titleInput.focus();
      if (!await titleInput.evaluate(element => document.activeElement === element)) throw new Error('Input focus failed');
      await page.route(pattern, route => route.request().method() === 'POST'
        ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"Synthetic CRUD save failure"}' })
        : route.continue());
      try {
        const failed = responseFor('POST', config.endpoint);
        await form.getByRole('button', { name: 'Tambahkan', exact: true }).click();
        await failed;
        await form.getByRole('button', { name: 'Tambahkan', exact: true }).waitFor();
        if (await titleInput.inputValue() !== config.title) throw new Error('Failed create discarded draft');
      } finally { await page.unroute(pattern); }
      checks.push(`${config.slug}: failed create retains draft and permits retry`);
      const created = responseFor('POST', config.endpoint);
      await form.getByRole('button', { name: 'Tambahkan', exact: true }).click();
      const createdResponse = await created;
      if (createdResponse.status() !== 201) throw new Error(`Create HTTP ${createdResponse.status()}: ${await createdResponse.text()}`);
      id = (await createdResponse.json()).data.id;
      await form.waitFor({ state: 'hidden' });
      await page.getByRole('heading', { name: config.title, exact: true }).waitFor();
      await page.getByPlaceholder(config.search, { exact: true }).fill(config.title);
      const firstCard = page.getByRole('heading', { name: config.title, exact: true })
        .locator('xpath=ancestor::div[contains(@class,"transition-all")][1]');
      await firstCard.getByTitle('Edit', { exact: true }).click();
      if (config.slug === 'directories') {
        const tasks = await form.locator('textarea').inputValue();
        if (tasks !== 'Tugas sintetis satu\nTugas sintetis dua') throw new Error('Directory task array/text round trip changed');
      } else if (await form.getByRole('combobox').inputValue() !== 'faq') throw new Error('Fast path category changed');
      await titleInput.fill(edited);
      await form.getByRole('button', { name: 'Batal', exact: true }).click();
      if ((await readItem(`${config.endpoint}/${id}`))[config.key] !== config.title) throw new Error('Cancelled edit was saved');
      if (await page.evaluate(() => document.body.style.overflow) === 'hidden') throw new Error('Closing modal kept body locked');
      await firstCard.getByTitle('Edit', { exact: true }).click();
      await titleInput.fill(edited);
      const updated = responseFor('PUT', `${config.endpoint}/${id}`);
      await form.getByRole('button', { name: 'Simpan Perubahan', exact: true }).click();
      if (!(await updated).ok()) throw new Error('Edit failed');
      await form.waitFor({ state: 'hidden' });
      await page.getByRole('heading', { name: edited, exact: true }).waitFor();
      if ((await readItem(`${config.endpoint}/${id}`))[config.key] !== edited) throw new Error('Edit was not persisted');
      checks.push(`${config.slug}: real create, cancelled edit, update and formatted-field round trip`);

      for (const [label, active] of [['Nonaktifkan', false], ['Aktifkan', true]]) {
        const toggled = responseFor('PATCH', `${config.endpoint}/${id}/toggle`);
        await card().getByTitle(label, { exact: true }).click();
        if (!(await toggled).ok() || Boolean((await readItem(`${config.endpoint}/${id}`)).is_active) !== active)
          throw new Error('Toggle was not persisted');
      }
      checks.push(`${config.slug}: real active/inactive toggle`);

      // Close real transient toasts before visual comparison; do not change styles.
      while (await page.getByTitle('Tutup', { exact: true }).count())
        await page.getByTitle('Tutup', { exact: true }).first().click();
      await page.evaluate(() => document.fonts.ready.then(() => null));

      for (const theme of ['dark', 'light']) {
        if (await page.locator('html').getAttribute('data-theme') !== theme)
          await page.getByRole('button', { name: theme === 'dark' ? 'Mode Gelap' : 'Mode Terang', exact: true }).click();
        for (const [width, height] of [[1440, 1000], [1024, 768], [390, 844]]) {
          await page.setViewportSize({ width, height });
          await page.mouse.move(0, 0);
          await page.waitForTimeout(650);
          const listFile = `${phase}-${config.slug}-${theme}-${width}-list.png`;
          await capture(root, listFile);
          await card().getByTitle('Edit', { exact: true }).click();
          await form.evaluate(element => { element.scrollTop = 0; });
          const modalFile = `${phase}-${config.slug}-${theme}-${width}-modal.png`;
          await capture(form.locator('..'), modalFile);
          await form.getByRole('button', { name: 'Batal', exact: true }).click();
          screenshots.push(listFile, modalFile);
        }
      }
      checks.push(`${config.slug}: list/modal at two themes and three viewports`);
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.reload();
      await page.getByPlaceholder(config.search, { exact: true }).fill(edited);
      await page.getByRole('heading', { name: edited, exact: true }).waitFor();
      checks.push(`${config.slug}: update survives reload and search`);

      await card().getByTitle('Hapus', { exact: true }).click();
      await card().getByRole('button', { name: 'Batal', exact: true }).click();
      await card().getByTitle('Hapus', { exact: true }).waitFor();
      if (!(await readItem(`${config.endpoint}/${id}`))) throw new Error('Delete cancellation removed item');
      const itemPattern = `**${config.endpoint}/${id}`;
      await page.route(itemPattern, route => route.request().method() === 'DELETE'
        ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"message":"Synthetic CRUD delete failure"}' })
        : route.continue());
      await card().getByTitle('Hapus', { exact: true }).click();
      try {
        const failed = responseFor('DELETE', `${config.endpoint}/${id}`);
        await card().getByRole('button', { name: 'Hapus?', exact: true }).click();
        await failed;
        await card().waitFor();
      } finally { await page.unroute(itemPattern); }
      const removed = responseFor('DELETE', `${config.endpoint}/${id}`);
      await card().getByRole('button', { name: 'Hapus?', exact: true }).click();
      if (!(await removed).ok()) throw new Error('Delete retry failed');
      await page.getByRole('heading', { name: edited, exact: true }).waitFor({ state: 'hidden' });
      const gone = await page.request.get(`${origin}${config.endpoint}/${id}`, { headers });
      if (gone.status() !== 404) throw new Error('Deleted item still exists');
      id = null;
      checks.push(`${config.slug}: delete cancellation, failure retention and real retry`);
      await page.getByRole('button', { name: config.add, exact: true }).click();
      if (await titleInput.inputValue() !== '') throw new Error('New form retained previous item title');
      await form.getByRole('button', { name: 'Batal', exact: true }).click();
      checks.push(`${config.slug}: new form resets after editing/deletion`);
    } finally {
      if (id) {
        await page.evaluate(async path => {
          const token = document.cookie.split('; ').find(item => item.startsWith('XSRF-TOKEN='))?.slice(11);
          await fetch(path, { method: 'DELETE', credentials: 'include', headers: { Accept: 'application/json', 'X-XSRF-TOKEN': decodeURIComponent(token || '') } });
        }, `${config.endpoint}/${id}`);
      }
    }
  }
  let layoutComparison = 'not_requested';
  if (phase === 'before') {
    await page.evaluate(value => localStorage.setItem('refactor-settings-layout-before', value), JSON.stringify(layouts));
    await page.context().storageState({ path: 'settings-before-state.json' });
  }
  if (phase === 'after') {
    const previous = await page.evaluate(() => localStorage.getItem('refactor-settings-layout-before'));
    if (!previous) throw new Error('Run the before phase in this browser session before comparing layouts');
    if (previous !== JSON.stringify(layouts)) throw new Error('Control labels, values, disabled state or geometry changed');
    layoutComparison = 'passed';
    await page.context().storageState({ path: 'settings-after-state.json' });
  }
  return { check: 'settings_crud_real_backend', status: 'passed', phase, checks, screenshots, layoutComparison };
}
