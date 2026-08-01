(function () {
  'use strict';

  let currentFileId = null;
  let filesList = [];
  let defaultFolder = '';
  let selectedResult = null;

  const sidebar = document.getElementById('file-list');
  const viewer = document.getElementById('viewer');
  const placeholder = document.getElementById('placeholder');
  const fileTitle = document.getElementById('file-title');
  const btnSave = document.getElementById('btn-save');
  const statusBanner = document.getElementById('status-banner');
  const authBanner = document.getElementById('auth-banner');

  // Add-file modal
  const btnAddFile = document.getElementById('btn-add-file');
  const modal = document.getElementById('add-file-modal');
  const modalClose = document.getElementById('modal-close');
  const stepSearch = document.getElementById('step-search');
  const stepDetails = document.getElementById('step-details');
  const searchInput = document.getElementById('search-input');
  const btnSearch = document.getElementById('btn-search');
  const searchStatus = document.getElementById('search-status');
  const searchResults = document.getElementById('search-results');
  const chosenName = document.getElementById('chosen-name');
  const inputLabel = document.getElementById('input-label');
  const inputPath = document.getElementById('input-path');
  const btnPickFolder = document.getElementById('btn-pick-folder');
  const detailsError = document.getElementById('details-error');
  const btnBack = document.getElementById('btn-back');
  const btnCancel = document.getElementById('btn-cancel');
  const btnConfirm = document.getElementById('btn-confirm');

  async function init() {
    await checkAuth();
    await loadFiles();
    loadDefaultFolder();

    btnSave.addEventListener('click', saveFile);

    btnAddFile.addEventListener('click', openModal);
    modalClose.addEventListener('click', closeModal);
    btnCancel.addEventListener('click', closeModal);
    btnBack.addEventListener('click', function () { showStep('search'); });
    btnSearch.addEventListener('click', runSearch);
    btnPickFolder.addEventListener('click', pickFolder);
    btnConfirm.addEventListener('click', confirmAdd);

    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        runSearch();
      }
    });

    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !modal.hidden) closeModal();
    });
  }

  async function checkAuth() {
    try {
      const resp = await fetch('/api/auth/status');
      const data = await resp.json();
      if (!data.authenticated) {
        authBanner.classList.add('show');
      } else {
        authBanner.classList.remove('show');
      }
    } catch (e) {
      console.error('Auth check failed:', e);
    }
  }

  async function loadDefaultFolder() {
    try {
      const resp = await fetch('/api/default-folder');
      const data = await resp.json();
      defaultFolder = data.path || '';
    } catch (e) {
      console.error('Failed to load default folder:', e);
    }
  }

  async function loadFiles(preferredId) {
    try {
      const resp = await fetch('/api/files');
      filesList = await resp.json();
      renderSidebar();

      if (filesList.length > 0) {
        const target = findFile(preferredId) || findFile(currentFileId) || filesList[0];
        selectFile(target);
      } else {
        showEmptyState('Nenhum ficheiro configurado');
      }
    } catch (e) {
      console.error('Failed to load files:', e);
      showBanner('Erro ao carregar ficheiros', false);
    }
  }

  function findFile(fileId) {
    if (!fileId) return null;
    return filesList.filter(function (f) { return f.id === fileId; })[0] || null;
  }

  function renderSidebar() {
    sidebar.innerHTML = '';
    filesList.forEach(function (file) {
      const row = document.createElement('div');
      row.className = 'file-row';

      const btn = document.createElement('button');
      btn.className = 'file-btn';
      btn.type = 'button';
      btn.dataset.fileId = file.id;
      btn.textContent = file.label || file.id;
      btn.addEventListener('click', function () { selectFile(file); });

      const remove = document.createElement('button');
      remove.className = 'file-remove';
      remove.type = 'button';
      remove.textContent = '×';
      remove.title = 'Remover da lista';
      remove.setAttribute('aria-label', 'Remover ' + (file.label || file.id));
      remove.addEventListener('click', function (e) {
        e.stopPropagation();
        removeFile(file);
      });

      row.appendChild(btn);
      row.appendChild(remove);
      sidebar.appendChild(row);
    });
  }

  function showEmptyState(message) {
    currentFileId = null;
    fileTitle.textContent = message;
    btnSave.disabled = true;
    viewer.style.display = 'none';
    viewer.removeAttribute('src');
    placeholder.style.display = 'flex';
    placeholder.textContent = message;
  }

  function selectFile(file) {
    currentFileId = file.id;
    fileTitle.textContent = file.label || file.id;
    btnSave.disabled = false;

    // Update active state
    document.querySelectorAll('.file-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.fileId === file.id);
    });

    // Show iframe. Only assign src when it actually changed — reassigning the
    // same URL reloads the embedded viewer and discards its state.
    if (file.onedrive_embed_url) {
      if (viewer.getAttribute('src') !== file.onedrive_embed_url) {
        viewer.src = file.onedrive_embed_url;
      }
      viewer.style.display = 'block';
      placeholder.style.display = 'none';
    } else {
      viewer.style.display = 'none';
      placeholder.style.display = 'flex';
      placeholder.textContent = 'URL de visualização não configurada';
    }
  }

  async function saveFile() {
    if (!currentFileId) return;

    btnSave.disabled = true;
    btnSave.textContent = 'A guardar...';

    try {
      const resp = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: currentFileId }),
      });
      const data = await resp.json();

      if (resp.status === 401 && data.error === 'not_authenticated') {
        showBanner('Conta Microsoft não ligada. Faça login primeiro.', false);
        authBanner.classList.add('show');
      } else if (!resp.ok) {
        showBanner('Erro: ' + (data.error || 'Falha desconhecida'), false);
      } else {
        showBanner('Guardado com sucesso em: ' + data.path, true);
      }
    } catch (e) {
      showBanner('Erro de ligação ao servidor', false);
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = 'Guardar no computador';
    }
  }

  // ---------- Add-file modal ----------

  function openModal() {
    selectedResult = null;
    searchInput.value = '';
    searchResults.innerHTML = '';
    setSearchStatus('');
    setDetailsError('');
    showStep('search');
    modal.hidden = false;
    searchInput.focus();
  }

  function closeModal() {
    modal.hidden = true;
    selectedResult = null;
  }

  function showStep(step) {
    const isSearch = step === 'search';
    stepSearch.hidden = !isSearch;
    stepDetails.hidden = isSearch;
  }

  function setSearchStatus(message) {
    searchStatus.textContent = message || '';
    searchStatus.hidden = !message;
  }

  function setDetailsError(message) {
    detailsError.textContent = message || '';
    detailsError.hidden = !message;
  }

  async function runSearch() {
    // Guard against a second Enter press while a search is already in flight,
    // which could render stale results out of order.
    if (btnSearch.disabled) return;

    const term = searchInput.value.trim();
    if (!term) {
      setSearchStatus('Escreva parte do nome do ficheiro.');
      return;
    }

    searchResults.innerHTML = '';
    setSearchStatus('A procurar...');
    btnSearch.disabled = true;

    try {
      const resp = await fetch('/api/onedrive/search?q=' + encodeURIComponent(term));
      const data = await resp.json();

      if (resp.status === 401) {
        setSearchStatus('Conta Microsoft não ligada. Faça login primeiro.');
        authBanner.classList.add('show');
        showBanner('Conta Microsoft não ligada. Faça login primeiro.', false);
        return;
      }
      if (!resp.ok) {
        const message = 'Erro na procura: ' + (data.error || 'Falha desconhecida');
        setSearchStatus(message);
        showBanner(message, false);
        return;
      }
      if (!Array.isArray(data) || data.length === 0) {
        setSearchStatus('Nenhum ficheiro Excel encontrado com esse nome.');
        return;
      }

      setSearchStatus(data.length + ' ficheiro(s) encontrado(s). Escolha um.');
      renderResults(data);
    } catch (e) {
      setSearchStatus('Erro de ligação ao servidor.');
      showBanner('Erro de ligação ao servidor', false);
    } finally {
      btnSearch.disabled = false;
    }
  }

  function renderResults(results) {
    searchResults.innerHTML = '';
    results.forEach(function (item) {
      const row = document.createElement('button');
      row.className = 'result-row';
      row.type = 'button';

      const name = document.createElement('span');
      name.className = 'result-name';
      name.textContent = item.name;

      const path = document.createElement('span');
      path.className = 'result-path';
      path.textContent = item.path || '/';

      row.appendChild(name);
      row.appendChild(path);
      row.addEventListener('click', function () { chooseResult(item); });
      searchResults.appendChild(row);
    });
  }

  function chooseResult(item) {
    selectedResult = item;
    chosenName.textContent = item.name;
    inputLabel.value = stripExtension(item.name);
    inputPath.value = suggestLocalPath(item.name);
    setDetailsError('');
    showStep('details');
    inputLabel.focus();
  }

  function stripExtension(name) {
    const dot = name.lastIndexOf('.');
    return dot > 0 ? name.substring(0, dot) : name;
  }

  function joinPath(folder, name) {
    if (!folder) return name;
    const sep = folder.indexOf('\\') !== -1 ? '\\' : '/';
    const trimmed = folder.replace(/[\\/]+$/, '');
    return trimmed + sep + name;
  }

  function suggestLocalPath(name) {
    return joinPath(defaultFolder, name);
  }

  async function pickFolder() {
    // The native dialog can stay open a long time; if the user meanwhile closed
    // the modal or picked another file, this response must not overwrite it.
    const openedFor = selectedResult;

    btnPickFolder.disabled = true;
    try {
      const resp = await fetch('/api/pick-folder', { method: 'POST' });
      const data = await resp.json();

      if (modal.hidden || selectedResult !== openedFor) {
        return;
      }

      if (data.error === 'unsupported') {
        setDetailsError('Escreva o caminho da pasta no campo acima (a janela de escolha só está disponível na aplicação).');
        inputPath.focus();
        return;
      }
      if (!resp.ok || data.error) {
        setDetailsError('Não foi possível abrir a janela de pastas: ' + (data.error || 'falha desconhecida'));
        return;
      }
      if (data.cancelled || !data.path) {
        return;
      }

      setDetailsError('');
      inputPath.value = joinPath(data.path, selectedResult ? selectedResult.name : '');
    } catch (e) {
      setDetailsError('Erro de ligação ao servidor.');
    } finally {
      btnPickFolder.disabled = false;
    }
  }

  async function confirmAdd() {
    if (!selectedResult) {
      setDetailsError('Escolha primeiro um ficheiro.');
      showStep('search');
      return;
    }

    const localPath = inputPath.value.trim();
    if (!localPath) {
      setDetailsError('Indique onde guardar o ficheiro no computador.');
      inputPath.focus();
      return;
    }

    setDetailsError('');
    btnConfirm.disabled = true;
    btnConfirm.textContent = 'A adicionar...';

    try {
      const resp = await fetch('/api/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          onedrive_item_id: selectedResult.id,
          name: selectedResult.name,
          label: inputLabel.value.trim(),
          local_path: localPath,
        }),
      });
      const data = await resp.json().catch(function () { return {}; });

      if (resp.status === 401) {
        setDetailsError('Conta Microsoft não ligada. Faça login primeiro.');
        authBanner.classList.add('show');
        showBanner('Conta Microsoft não ligada. Faça login primeiro.', false);
        return;
      }
      if (!resp.ok) {
        const message = data.error || 'Falha desconhecida ao adicionar o ficheiro.';
        setDetailsError(message);
        showBanner('Erro: ' + message, false);
        return;
      }

      closeModal();
      await loadFiles(data.id);
      showBanner('Ficheiro adicionado: ' + (data.label || data.name || data.id), true);
    } catch (e) {
      setDetailsError('Erro de ligação ao servidor.');
      showBanner('Erro de ligação ao servidor', false);
    } finally {
      btnConfirm.disabled = false;
      btnConfirm.textContent = 'Confirmar';
    }
  }

  async function removeFile(file) {
    const name = file.label || file.id;
    if (!window.confirm('Remover "' + name + '" da lista?\n\nO ficheiro no OneDrive não é apagado.')) {
      return;
    }

    try {
      const resp = await fetch('/api/files/' + encodeURIComponent(file.id), { method: 'DELETE' });

      if (!resp.ok && resp.status !== 204) {
        let message = 'Falha desconhecida';
        try {
          const data = await resp.json();
          message = data.error || message;
        } catch (e) { /* no JSON body */ }
        showBanner('Erro ao remover: ' + message, false);
        return;
      }

      if (currentFileId === file.id) {
        currentFileId = null;
      }
      await loadFiles();
      showBanner('Ficheiro removido: ' + name, true);
    } catch (e) {
      showBanner('Erro de ligação ao servidor', false);
    }
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
