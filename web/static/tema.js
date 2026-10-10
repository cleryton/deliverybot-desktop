'use strict';
(() => {
  const root = document.documentElement;
  const choices = new Set(['sistema', 'claro', 'escuro']);
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let choice = choices.has(root.dataset.themeChoice) ? root.dataset.themeChoice : 'sistema';

  function apply(value) {
    choice = value;
    root.dataset.themeChoice = value;
    root.dataset.theme = value === 'escuro' || value === 'sistema' && system.matches ? 'dark' : 'light';
    document.querySelectorAll('[data-theme-picker]').forEach(select => { select.value = value; });
  }

  // Executado no head, antes das folhas de estilo, para evitar um painel claro ao abrir.
  apply(choice);
  system.addEventListener('change', () => { if (choice === 'sistema') apply(choice); });
  document.addEventListener('DOMContentLoaded', () => {
    apply(choice);
    document.querySelectorAll('[data-theme-picker]').forEach(select => {
      select.addEventListener('change', async () => {
        const previous = choice;
        const value = select.value;
        const status = document.querySelector('#theme-status');
        if (!choices.has(value)) return;
        apply(value);
        select.disabled = true;
        if (status) status.hidden = true;
        try {
          const response = await fetch('/gestao/api/aparencia', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
            body: JSON.stringify({tema: value})
          });
          if (!response.ok) throw new Error('Falha ao salvar');
          const saved = await response.json();
          if (!choices.has(saved.tema)) throw new Error('Tema inválido');
          apply(saved.tema);
        } catch {
          apply(previous);
          if (status) {
            status.textContent = 'Não foi possível salvar o tema. Tente novamente.';
            status.hidden = false;
          }
        } finally { select.disabled = false; }
      });
    });
  });
})();
