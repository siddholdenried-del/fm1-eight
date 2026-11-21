'use strict';
(() => {
  const topics = Array.from(document.querySelectorAll('a[data-guide-topic]'));
  const drawer = document.querySelector('.gm-toc-mobile');
  const mark = () => {
    for (const link of topics) {
      if (link.hash === location.hash) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
  };
  mark();
  window.addEventListener('hashchange', mark);
  if (drawer) drawer.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !drawer.open) return;
    event.preventDefault();
    drawer.open = false;
    drawer.querySelector('summary').focus({preventScroll: true});
  });
  for (const link of topics) {
    link.addEventListener('click', (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      const target = document.getElementById(link.hash.slice(1));
      if (drawer && drawer.contains(link)) drawer.open = false;
      if (target) requestAnimationFrame(() => target.focus({preventScroll: true}));
    });
  }
})();
