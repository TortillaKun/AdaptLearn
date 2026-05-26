// AdaptLearn Theme Manager
(function() {
  var tema = localStorage.getItem('adaptlearn_tema');
  if (tema) {
    try {
      var t = JSON.parse(tema);
      document.documentElement.style.setProperty('--accent',  t.accent);
      document.documentElement.style.setProperty('--accent2', t.accent2);
    } catch(e) {}
  }
  var modo = localStorage.getItem('adaptlearn_modo');
  if (modo === 'claro') {
    document.body.classList.add('modo-claro');
  }
})();