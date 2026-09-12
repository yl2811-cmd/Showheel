(() => {
    'use strict';
    const mounted = new WeakMap();
    function mount(root, options = {}) {
        if (mounted.has(root)) return mounted.get(root);
        const key = 'showheel.character.language';
        const buttons = [...root.querySelectorAll('[data-character-lang]')];
        const toolbar = root.querySelector('[data-character-toolbar]');
        const scrolling = options.scrollContainer || window;
        function setLanguage(language, preservePosition = true) {
            if (language !== 'zh' && language !== 'en') return;
            const boundary = toolbar.getBoundingClientRect().bottom + 24;
            const bottom = options.scrollContainer?.getBoundingClientRect().bottom || innerHeight;
            const visible = [...root.querySelectorAll('[data-reading-anchor]')].filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.bottom > boundary && rect.top < bottom;
            });
            const anchor = preservePosition ? visible.sort((a, b) => Math.abs(a.getBoundingClientRect().top - boundary) - Math.abs(b.getBoundingClientRect().top - boundary))[0] : null;
            const before = anchor?.getBoundingClientRect().top;
            root.querySelectorAll('[data-copy]').forEach(el => { el.hidden = el.dataset.copy !== language; });
            root.querySelectorAll('[data-alt-zh]').forEach(el => { el.alt = language === 'zh' ? el.dataset.altZh : el.dataset.altEn; });
            buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.characterLang === language)));
            root.lang = language === 'zh' ? 'zh-Hans' : 'en';
            if (options.manageDocumentLanguage !== false) document.documentElement.lang = root.lang;
            if (anchor) scrolling.scrollBy({ top: anchor.getBoundingClientRect().top - before, behavior: 'instant' });
            if (!options.onLanguageChange) {
                try { localStorage.setItem(key, language); } catch { /* Reading works without storage. */ }
            }
        }
        let initial = options.locale || 'zh';
        if (!options.locale) {
            try { if (localStorage.getItem(key) === 'en') initial = 'en'; } catch { /* Default to Chinese. */ }
        }
        setLanguage(initial, false);
        root.querySelector('[data-language-controls]').hidden = false;
        buttons.forEach(button => button.addEventListener('click', () => {
            setLanguage(button.dataset.characterLang);
            options.onLanguageChange?.(button.dataset.characterLang);
        }));
        if (options.scrollContainer) {
            root.querySelectorAll('.character-jumps a').forEach(link => link.addEventListener('click', event => {
                const target = root.querySelector(link.getAttribute('href'));
                if (!target) return;
                event.preventDefault();
                scrolling.scrollTo({ top: target.getBoundingClientRect().top - scrolling.getBoundingClientRect().top + scrolling.scrollTop - toolbar.offsetHeight - 24, behavior: 'instant' });
            }));
        }
        const reader = { setLanguage };
        mounted.set(root, reader);
        return reader;
    }
    window.SHOWHEEL_CHARACTERS = { mount };
    const root = document.querySelector('[data-characters]');
    if (root) mount(root);
})();
