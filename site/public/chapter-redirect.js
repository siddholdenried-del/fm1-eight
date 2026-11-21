'use strict';
(() => {
  const chapters = new Set(["platform", "loops", "sequencer", "drums", "synth", "deeper", "acid", "modulation", "recording", "live", "fx", "master", "screen", "storage", "building", "story", "words"]);
  const forward = () => {
    const chapter = location.hash.slice(1);
    if (chapters.has(chapter)) location.replace('/technical/' + location.search + location.hash);
  };
  forward();
  addEventListener('hashchange', forward);
})();
