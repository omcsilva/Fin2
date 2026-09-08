(() => {
  const form = document.querySelector('.price-update-form');
  if (!form) return;
  const button = form.querySelector('button');
  const status = document.querySelector('#price-job-status');
  const last = document.querySelector('#last-price-update');
  const notification = document.querySelector('#async-notification');
  let previous = null;
  let active = false;
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
    try {
      const response=await fetch(form.dataset.statusUrl,{headers:{Accept:'application/json'},cache:'no-store'});
      if (!response.ok) throw new Error();
      const job=await response.json();
      last.textContent=formatDate(job.last_price_update);
      active=job.status==='queued'||job.status==='running';
      status.textContent=job.message || '';
      button.disabled=false;button.textContent=active?'■':'⟳';
      button.title=active?'Cancelar atualização de preços':'Atualizar preços';
      button.setAttribute('aria-label',button.title);
      if (previous && active===false && (job.status==='completed'||job.status==='failed'||job.status==='cancelled') && previous!==job.status) show(job.message);
      previous=job.status;
      window.setTimeout(poll,active?1000:15000);
    } catch { button.disabled=false; window.setTimeout(poll,15000); }
  }
  form.addEventListener('submit',async event => {
    event.preventDefault();
    const cancelling=active;
    button.disabled=true;button.textContent=cancelling?'■':'◌';
    button.title=cancelling?'Cancelando atualização de preços':'Iniciando atualização de preços';button.setAttribute('aria-label',button.title);
    if (!cancelling) status.textContent='Verificando ativos a serem atualizados...';
    try {
      const response=await fetch(cancelling?form.dataset.cancelUrl:form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error();
      previous=cancelling?'running':'queued';window.setTimeout(poll,100);
    } catch { show(cancelling?'Não foi possível cancelar a atualização de preços.':'Não foi possível iniciar a atualização de preços.');button.disabled=false;window.setTimeout(poll,300); }
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
