(() => {
  const form = document.querySelector('.price-update-form');
  if (!form) return;
  const button = form.querySelector('button');
  const status = document.querySelector('#price-job-status');
  const last = document.querySelector('#last-price-update');
  const notification = document.querySelector('#async-notification');
  let previous = null;
  let active = false;
  let pollTimer = null;
  let generation = 0;
  const schedulePoll = delay => {
    window.clearTimeout(pollTimer);
    pollTimer = window.setTimeout(poll, delay);
  };
  const formatDate = value => value ? new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'medium'}).format(new Date(value)) : 'Nunca';
  const show = message => { notification.textContent=message; notification.hidden=false; window.setTimeout(()=>notification.hidden=true,8000); };
  async function copyStatus() {
    const message=status.textContent.trim();
    if (!message) return;
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(message);
      else {
        const field=document.createElement('textarea');field.value=message;field.style.position='fixed';field.style.opacity='0';
        document.body.appendChild(field);field.select();
        if (!document.execCommand('copy')) throw new Error();
        field.remove();
      }
      show('Mensagem copiada para a área de transferência.');
    } catch { show('Não foi possível copiar a mensagem.'); }
  }
  status.addEventListener('click',copyStatus);
  status.addEventListener('keydown',event => {
    if (event.key==='Enter'||event.key===' ') { event.preventDefault();copyStatus(); }
  });
  async function poll() {
    const currentGeneration = generation;
    try {
      const response=await fetch(form.dataset.statusUrl,{headers:{Accept:'application/json'},cache:'no-store'});
      if (!response.ok) throw new Error();
      const job=await response.json();
      if (currentGeneration !== generation) return;
      last.textContent=formatDate(job.last_price_update);
      active=job.status==='queued'||job.status==='running';
      status.textContent=job.message || '';
      button.disabled=false;button.textContent=active?'■':'⟳';
      button.title=active?'Cancelar atualização de preços':'Atualizar preços';
      button.setAttribute('aria-label',button.title);
      if (previous && active===false && (job.status==='completed'||job.status==='failed'||job.status==='cancelled') && previous!==job.status) show(job.message);
      previous=job.status;
      if (active) schedulePoll(1000);
    } catch {
      if (currentGeneration !== generation) return;
      button.disabled=false;
      schedulePoll(15000);
    }
  }
  form.addEventListener('submit',async event => {
    event.preventDefault();
    if (button.disabled) return;
    window.clearTimeout(pollTimer);
    generation += 1;
    const cancelling=active;
    button.disabled=true;button.textContent=cancelling?'■':'◌';
    button.title=cancelling?'Cancelando atualização de preços':'Iniciando atualização de preços';button.setAttribute('aria-label',button.title);
    if (!cancelling) status.textContent='Verificando ativos a serem atualizados...';
    try {
      const response=await fetch(cancelling?form.dataset.cancelUrl:form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error();
      previous=cancelling?'running':'queued';schedulePoll(100);
    } catch { show(cancelling?'Não foi possível cancelar a atualização de preços.':'Não foi possível iniciar a atualização de preços.');button.disabled=false;schedulePoll(300); }
  });
  poll();
})();

// Make overflowing data panels reachable for keyboard scrolling as well.
document.querySelectorAll('.table-wrap').forEach(panel => {
  panel.tabIndex = 0;
  panel.setAttribute('role', 'region');
  panel.setAttribute('aria-label', 'Tabela com rolagem horizontal');
});

document.querySelectorAll('form[data-confirm-submit]').forEach(form => {
  form.addEventListener('submit',event => {
    if (!window.confirm(form.dataset.confirmSubmit)) event.preventDefault();
    else form.querySelectorAll('button[type="submit"]').forEach(button => button.disabled=true);
  });
});

(() => {
  const account=document.querySelector('[data-entry-account]');
  const application=document.querySelector('[data-entry-application]');
  const currency=document.querySelector('[data-entry-currency]');
  if (!account || !application || !currency) return;
  const refresh=() => {
    const selected=account.selectedOptions[0];
    [...application.options].forEach(option => {
      if (!option.value) return;
      option.hidden=account.value && option.dataset.account!==selected?.dataset.accountId;
      if (option.hidden && option.selected) application.value='';
    });
    const code=selected?.dataset.currency?.toUpperCase();
    if (code) currency.value=({REAL:'BRL',DOL:'USD',DOLAR:'USD'}[code]||code);
  };
  account.addEventListener('change',refresh);refresh();
})();

(() => {
  document.querySelectorAll('form[data-table-controls]').forEach(form => {
    const sort=form.querySelector('input[name="sort"]');
    const direction=form.querySelector('input[name="dir"]');
    const current=sort?.value;
    document.querySelectorAll('[data-table="'+form.dataset.tableControls+'"] [data-sort]').forEach(button => {
      if (button.dataset.sort===current) {
        button.dataset.direction=direction.value;
        button.setAttribute('aria-sort',direction.value==='desc'?'descending':'ascending');
      }
      button.addEventListener('click',() => {
        const same=sort.value===button.dataset.sort;
        sort.value=button.dataset.sort;
        direction.value=same&&direction.value==='asc'?'desc':'asc';
        form.submit();
      });
    });
  });
})();

(() => {
  const groups=[...document.querySelectorAll('.menu-group')];
  groups.forEach(group => group.addEventListener('toggle',() => {
    if (group.open) groups.forEach(other => { if (other!==group) other.open=false; });
  }));
  document.addEventListener('click',event => {
    if (!event.target.closest('.menu-group')) groups.forEach(group => group.open=false);
  });
  document.addEventListener('keydown',event => {
    if (event.key==='Escape') groups.forEach(group => group.open=false);
  });
})();

// Forms that reload the page as soon as one of their selects changes.
document.querySelectorAll('form[data-auto-submit] select').forEach(select => {
  select.addEventListener('change', () => select.form.submit());
});

// Individual XP statement review: load the dedicated review view and present it
// as a modal over the movements table. The full-page route stays as the
// no-JavaScript fallback, and a failed load navigates there directly.
(() => {
  const dialog = document.querySelector('[data-review-dialog]');
  if (!dialog || typeof dialog.showModal !== 'function' || typeof DOMParser === 'undefined') return;
  const body = dialog.querySelector('[data-review-body]');
  let trigger = null;
  const render = html => {
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    const content = parsed.querySelector('#individual-review');
    if (!content) return false;
    body.replaceChildren(document.importNode(content, true));
    // Replacing the body drops focus to the document; bring it back inside the
    // dialog so Escape and the keyboard navigation keep working.
    if (dialog.open) dialog.focus();
    return true;
  };
  // After a rejected submit the server re-renders from the stored decision, so
  // re-apply what the reviewer had typed before showing the error.
  const restore = data => {
    const form = body.querySelector('form');
    if (!form) return;
    for (const field of form.elements) {
      if (!field.name) continue;
      const values = data.getAll(field.name).map(String);
      if (field.type === 'checkbox' || field.type === 'radio') field.checked = values.includes(field.value) || values.includes('on');
      else if (field.tagName === 'SELECT' && field.multiple) for (const option of field.options) option.selected = values.includes(option.value);
      else if (values.length) field.value = values[0];
    }
  };
  const close = () => { if (dialog.open) dialog.close(); };
  document.addEventListener('click', async event => {
    const link = event.target.closest('a[data-review-modal]');
    const row = event.target.closest('tr[data-review-row]');
    if (!link && row && !event.target.closest('a,button,input,select,textarea,summary')) {
      row.querySelector('a[data-review-modal]')?.click();
      return;
    }
    if (link) {
      event.preventDefault();
      trigger = link;
      body.innerHTML = '<p class="muted">Carregando revisão…</p>';
      dialog.showModal();
      try {
        const response = await fetch(link.href, {headers:{Accept:'text/html'}});
        if (!response.ok || !render(await response.text())) throw new Error();
      } catch {
        close();
        window.location.assign(link.href);
      }
      return;
    }
    if (!dialog.open) return;
    const dismiss = event.target.closest('[data-review-close]');
    if (dismiss && dialog.contains(dismiss)) { event.preventDefault(); close(); }
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
  // Close on Escape from the document: some embedded browsers do not deliver the
  // native dialog cancel event, and focus can briefly leave the dialog after a
  // re-render.
  document.addEventListener('keydown', event => {
    if (!dialog.open || event.key !== 'Escape' || event.defaultPrevented) return;
    event.preventDefault();
    close();
  });
  dialog.addEventListener('close', () => {
    body.replaceChildren();
    if (trigger) { trigger.focus(); trigger = null; }
  });
  body.addEventListener('submit', async event => {
    const form = event.target.closest('form');
    if (!form) return;
    event.preventDefault();
    const submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;
    // Read the attribute: the form has a control named "action", which would
    // otherwise shadow the form.action property with that element.
    const action = form.getAttribute('action');
    // Include the clicked button: its name/value carries the "Excluir lançamento"
    // intent, which a plain FormData(form) would drop.
    const data = event.submitter ? new FormData(form, event.submitter) : new FormData(form);
    let response;
    try {
      response = await fetch(action, {method:'POST', body:data, headers:{Accept:'text/html'}});
    } catch {
      // The request never reached the server: fall back to a normal submit.
      if (submit) submit.disabled = false;
      form.submit();
      return;
    }
    const url = new URL(response.url, window.location.href);
    if (url.searchParams.has('review_line')) {
      // Validation failed server-side: swap in the re-rendered form with errors.
      if (render(await response.text())) { restore(data); if (submit) submit.disabled = false; }
      else window.location.assign(url.href);
      return;
    }
    if (!response.ok) { if (submit) submit.disabled = false; return; }
    if (response.redirected) window.location.assign(url.href);
    else window.location.reload();
  });
})();
