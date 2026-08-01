(function () {
  'use strict';

  let filesList = [];

  const fileList = document.getElementById('file-list');
  const statusBanner = document.getElementById('status-banner');
  const btnSyncAll = document.getElementById('btn-sync-all');
  const btnCheckUpdate = document.getElementById('btn-check-update');
  const btnRefresh = document.getElementById('btn-refresh');
  const searchInput = document.getElementById('search-input');

  const btnSettings = document.getElementById('btn-settings');
  const settingsModal = document.getElementById('settings-modal');
  const settingsClose = document.getElementById('settings-close');
  const settingsCancel = document.getElementById('settings-cancel');
  const settingsSave = document.getElementById('settings-save');
  const settingsError = document.getElementById('settings-error');
  const inputOriginalDir = document.getElementById('input-original-dir');
  const inputServerDir = document.getElementById('input-server-dir');
  const btnPickOriginal = document.getElementById('btn-pick-original');
  const btnPickServer = document.getElementById('btn-pick-server');

  const STATUS_LABELS = {
    synced: { text: 'Sincronizado', cls: 'badge-ok' },
    outdated: { text: 'Desatualizado', cls: 'badge-warn' },
    new: { text: 'Novo', cls: 'badge-new' },
  };

  // Relative paths (the full "Subpasta/Ficheiro.xlsx" form, so two files with the
  // same base name in different subfolders are tracked separately) with a copy
  // currently in flight. Kept independent of any single button element so a
  // re-render triggered by another action still renders this row as disabled —
  // otherwise the user could click the fresh button and fire a second concurrent
  // copy of the same file.
  const syncingNames = new Set();
  let syncingAll = false;
  let savingSettings = false;
  let checkingUpdate = false;
  let refreshing = false;
  let searchQuery = '';

  async function init() {
    btnSyncAll.addEventListener('click', syncAll);
    btnCheckUpdate.addEventListener('click', checkForUpdate);
    btnRefresh.addEventListener('click', refreshFiles);
    searchInput.addEventListener('input', function () {
      searchQuery = searchInput.value;
      renderFileList();
    });

    btnSettings.addEventListener('click', openSettings);
    settingsClose.addEventListener('click', closeSettings);
    settingsCancel.addEventListener('click', closeSettings);
    settingsSave.addEventListener('click', saveSettings);
    btnPickOriginal.addEventListener('click', function () { pickFolder(inputOriginalDir); });
    btnPickServer.addEventListener('click', function () { pickFolder(inputServerDir); });

    // Clicking the dimmed backdrop closes; clicking inside the dialog must not.
    settingsModal.addEventListener('click', function (e) {
      if (e.target === settingsModal) closeSettings();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !settingsModal.hidden) closeSettings();
    });

    await loadFiles();
  }

  /* ---------------- files ---------------- */

  async function loadFiles() {
    let ok = true;
    try {
      const resp = await fetch('/api/files');
      const data = await resp.json();
      filesList = Array.isArray(data) ? data : [];
    } catch (e) {
      console.error('Failed to load files:', e);
      filesList = [];
      ok = false;
      showBanner('Não foi possível ler a pasta dos ficheiros.', false);
    }
    renderFileList();
    return ok;
  }

  async function refreshFiles() {
    if (refreshing) return;

    refreshing = true;
    btnRefresh.disabled = true;
    const originalLabel = btnRefresh.textContent;
    btnRefresh.textContent = 'A atualizar...';

    const ok = await loadFiles();
    if (ok) showBanner('Lista de ficheiros atualizada.', true);

    refreshing = false;
    btnRefresh.disabled = false;
    btnRefresh.textContent = originalLabel;
  }

  function renderFileList() {
    fileList.innerHTML = '';

    const query = searchQuery.trim().toLowerCase();
    const visible = query
      ? filesList.filter(function (f) { return f.name.toLowerCase().indexOf(query) !== -1; })
      : filesList;

    if (visible.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'file-empty';
      empty.textContent = filesList.length === 0
        ? 'Ainda não há ficheiros Excel na pasta original.'
        : 'Nenhum ficheiro encontrado para "' + searchInput.value.trim() + '".';
      fileList.appendChild(empty);
      return;
    }

    visible.forEach(function (file) {
      const isSyncing = syncingNames.has(file.name);

      const row = document.createElement('div');
      row.className = 'file-row';

      // entry.name may include subfolders ("Subpasta/Relatorio.xlsx"): show the
      // folder part muted and the file name in the normal style.
      const label = document.createElement('span');
      label.className = 'file-label';
      label.title = file.name;

      const cut = file.name.lastIndexOf('/');
      if (cut !== -1) {
        const folder = document.createElement('span');
        folder.className = 'file-folder';
        folder.textContent = file.name.slice(0, cut + 1);
        label.appendChild(folder);
      }

      const name = document.createElement('span');
      name.className = 'file-name';
      name.textContent = file.name.slice(cut + 1);
      label.appendChild(name);

      const info = STATUS_LABELS[file.status] || STATUS_LABELS.new;
      const badge = document.createElement('span');
      badge.className = 'file-badge ' + info.cls;
      badge.textContent = info.text;

      const btn = document.createElement('button');
      btn.className = 'file-btn';
      btn.type = 'button';
      btn.textContent = isSyncing ? 'A copiar...' : 'Copiar para o servidor';
      btn.disabled = isSyncing || syncingAll;
      btn.addEventListener('click', function () { syncFile(file.name, btn); });

      row.appendChild(label);
      row.appendChild(badge);
      row.appendChild(btn);
      fileList.appendChild(row);
    });
  }

  async function syncFile(name, rowButton) {
    if (!name || syncingNames.has(name)) return;

    syncingNames.add(name);
    rowButton.disabled = true;
    rowButton.textContent = 'A copiar...';

    try {
      const resp = await fetch('/api/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name }),
      });
      const data = await resp.json().catch(function () { return {}; });

      if (!resp.ok) {
        showBanner('Erro ao copiar "' + name + '": ' + (data.error || 'falha desconhecida'), false);
      } else {
        showBanner('Copiado para o servidor: ' + name, true);
      }
    } catch (e) {
      showBanner('Erro de ligação ao servidor', false);
    } finally {
      syncingNames.delete(name);
      await loadFiles();
    }
  }

  async function syncAll() {
    if (syncingAll) return;

    syncingAll = true;
    btnSyncAll.disabled = true;
    const originalLabel = btnSyncAll.textContent;
    btnSyncAll.textContent = 'A copiar...';
    renderFileList();

    try {
      const resp = await fetch('/api/sync-all', { method: 'POST' });
      const data = await resp.json().catch(function () { return {}; });

      if (!resp.ok) {
        showBanner('Erro ao copiar os ficheiros: ' + (data.error || 'falha desconhecida'), false);
      } else {
        const results = Array.isArray(data.results) ? data.results : [];
        const ok = results.filter(function (r) { return r.ok; }).length;
        const failed = results.length - ok;

        if (results.length === 0) {
          showBanner('Não há ficheiros para copiar.', true);
        } else if (failed === 0) {
          showBanner(ok + ' ficheiro(s) copiado(s) para o servidor.', true);
        } else {
          showBanner(ok + ' copiado(s), ' + failed + ' com erro.', false);
        }
      }
    } catch (e) {
      showBanner('Erro de ligação ao servidor', false);
    } finally {
      syncingAll = false;
      btnSyncAll.disabled = false;
      btnSyncAll.textContent = originalLabel;
      await loadFiles();
    }
  }

  /* ---------------- update ---------------- */

  async function checkForUpdate() {
    if (checkingUpdate) return;

    checkingUpdate = true;
    btnCheckUpdate.disabled = true;
    const originalLabel = btnCheckUpdate.textContent;
    btnCheckUpdate.textContent = 'A verificar...';

    let restarting = false;
    try {
      const resp = await fetch('/api/update', { method: 'POST' });
      const data = await resp.json().catch(function () { return {}; });

      if (!resp.ok || data.error) {
        showBanner(data.error || 'Não foi possível verificar as atualizações.', false);
      } else if (data.updated) {
        // The process is about to restart: leave the button disabled.
        restarting = true;
        showBanner('Atualização instalada. A aplicação vai reiniciar...', true);
        btnCheckUpdate.textContent = 'A reiniciar...';
      } else {
        showBanner('Já tem a versão mais recente.', true);
      }
    } catch (e) {
      showBanner('Erro de ligação ao servidor', false);
    } finally {
      if (!restarting) {
        checkingUpdate = false;
        btnCheckUpdate.disabled = false;
        btnCheckUpdate.textContent = originalLabel;
      }
    }
  }

  /* ---------------- settings ---------------- */

  async function openSettings() {
    setSettingsError('');
    inputOriginalDir.value = '';
    inputServerDir.value = '';

    try {
      const resp = await fetch('/api/settings');
      const data = await resp.json();
      inputOriginalDir.value = data.original_dir || '';
      inputServerDir.value = data.server_dir || '';
    } catch (e) {
      console.error('Failed to load settings:', e);
      showBanner('Não foi possível ler as definições.', false);
      return;
    }

    settingsModal.hidden = false;
    inputOriginalDir.focus();
  }

  function closeSettings() {
    if (savingSettings) return;
    settingsModal.hidden = true;
    setSettingsError('');
  }

  async function pickFolder(input) {
    try {
      const resp = await fetch('/api/pick-folder', { method: 'POST' });
      const data = await resp.json().catch(function () { return {}; });

      if (data.cancelled) return;

      if (data.error === 'unsupported') {
        setSettingsError('Não é possível abrir a janela de escolha de pastas. Escreva o caminho da pasta diretamente na caixa.');
        return;
      }
      if (!resp.ok || data.error) {
        setSettingsError('Erro ao escolher a pasta: ' + (data.error || 'falha desconhecida'));
        return;
      }
      if (data.path) {
        input.value = data.path;
        setSettingsError('');
      }
    } catch (e) {
      setSettingsError('Erro de ligação ao servidor');
    }
  }

  async function saveSettings() {
    if (savingSettings) return;

    const originalDir = inputOriginalDir.value.trim();
    const serverDir = inputServerDir.value.trim();

    savingSettings = true;
    settingsSave.disabled = true;
    const originalLabel = settingsSave.textContent;
    settingsSave.textContent = 'A guardar...';
    setSettingsError('');

    try {
      const resp = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original_dir: originalDir, server_dir: serverDir }),
      });
      const data = await resp.json().catch(function () { return {}; });

      if (!resp.ok) {
        setSettingsError(data.error || 'Não foi possível guardar as pastas.');
        return;
      }

      savingSettings = false;
      closeSettings();
      showBanner('Pastas atualizadas.', true);
      await loadFiles();
    } catch (e) {
      setSettingsError('Erro de ligação ao servidor');
    } finally {
      savingSettings = false;
      settingsSave.disabled = false;
      settingsSave.textContent = originalLabel;
    }
  }

  function setSettingsError(message) {
    settingsError.textContent = message || '';
    settingsError.hidden = !message;
  }

  function showBanner(message, success) {
    statusBanner.textContent = message;
    statusBanner.className = 'show ' + (success ? 'ok' : 'err');
    if (success) {
      setTimeout(function () {
        statusBanner.className = '';
      }, 5000);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
