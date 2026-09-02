(() => {
  const form = document.querySelector('.price-update-form');
  if (!form) return;
  const button = form.querySelector('button');
  const status = document.querySelector('#price-job-status');
  const last = document.querySelector('#last-price-update');
  const notification = document.querySelector('#async-notification');
  let previous = null;
  const formatDate = value => value ? new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'medium'}).format(new Date(value)) : 'Nunca';
  const show = message => { notification.textContent=message; notification.hidden=false; window.setTimeout(()=>notification.hidden=true,8000); };
  async function poll() {
    try {
      const response=await fetch(form.dataset.statusUrl,{headers:{Accept:'application/json'},cache:'no-store'});
      if (!response.ok) throw new Error();
      const job=await response.json();
      status.textContent=job.message || 'Sistema pronto';
      last.textContent=formatDate(job.last_price_update);
      const active=job.status==='queued'||job.status==='running';
      button.disabled=active;button.textContent=active?'◌':'⟳';
      button.title=active?'Atualização de preços em andamento':'Atualizar preços';
      button.setAttribute('aria-label',button.title);
      if (previous && active===false && (job.status==='completed'||job.status==='failed') && previous!==job.status) show(job.message);
      previous=job.status;
      window.setTimeout(poll,active?2000:15000);
    } catch { status.textContent='Estado da atualização indisponível'; button.disabled=false; window.setTimeout(poll,15000); }
  }
  form.addEventListener('submit',async event => {
    event.preventDefault();button.disabled=true;button.textContent='◌';button.title='Iniciando atualização de preços';button.setAttribute('aria-label',button.title);status.textContent='Solicitando atualização';
    try {
      const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error();
      previous='queued';window.setTimeout(poll,300);
    } catch { show('Não foi possível iniciar a atualização de preços.');button.disabled=false;button.textContent='⟳';button.title='Atualizar preços';button.setAttribute('aria-label',button.title); }
  });
  poll();
})();
