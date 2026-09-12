(() => {
    'use strict';
    const root = document.querySelector('[data-characters]');
    if (!root) return;
    const key = 'showheel.character.language';
    const buttons = [...root.querySelectorAll('[data-character-lang]')];
    const toolbar = root.querySelector('[data-character-toolbar]');
    function setLanguage(language, preservePosition) {
        if (language !== 'zh' && language !== 'en') return;
        const boundary = toolbar.getBoundingClientRect().bottom + 24;
        const anchors = [...root.querySelectorAll('[data-reading-anchor]')];
        const visible = anchors.filter(el => {
            const rect = el.getBoundingClientRect();
            return rect.bottom > boundary && rect.top < innerHeight;
        });
        const anchor = preservePosition ? visible.sort((a, b) =>
            Math.abs(a.getBoundingClientRect().top - boundary) - Math.abs(b.getBoundingClientRect().top - boundary)
        )[0] : null;
        const before = anchor?.getBoundingClientRect().top;
        root.querySelectorAll('[data-copy]').forEach(el => { el.hidden = el.dataset.copy !== language; });
        root.querySelectorAll('[data-alt-zh]').forEach(el => { el.alt = language === 'zh' ? el.dataset.altZh : el.dataset.altEn; });
        buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.characterLang === language)));
        document.documentElement.lang = root.lang = language === 'zh' ? 'zh-Hans' : 'en';
        if (anchor) window.scrollBy({ top: anchor.getBoundingClientRect().top - before, behavior: 'instant' });
        try { localStorage.setItem(key, language); } catch { /* Reading still works when storage is unavailable. */ }
    }
    let initial = 'zh';
    try { if (localStorage.getItem(key) === 'en') initial = 'en'; } catch { /* Default to Chinese. */ }
    setLanguage(initial, false);
    root.querySelector('[data-language-controls]').hidden = false;
    buttons.forEach(button => button.addEventListener('click', () => setLanguage(button.dataset.characterLang, true)));
})();
