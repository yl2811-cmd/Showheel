/* Shared Markdown reader for the Archeon page and standalone story URLs. */
(() => {
    'use strict';

    function prepareMarkdown(source) {
        const lines = source.replace(/^\uFEFF/, '').split(/\r\n|\n|\r/);
        const result = [];
        let fence = null;
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
            if (marker) {
                if (!fence) fence = marker[1];
                else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = null;
                result.push(line);
                continue;
            }
            if (!fence && /^={5,}\s*$/.test(line)) {
                const title = lines[i + 1];
                if (title?.trim() && !/^=+\s*$/.test(title) && /^={5,}\s*$/.test(lines[i + 2] || '')) {
                    result.push(/^#{1,6}\s/.test(title) ? title : '## ' + title);
                    i += 2;
                } else result.push('---');
            } else result.push(line);
        }
        return result.join('\n');
    }

    function renderMarkdown(source) {
        const html = marked.parse(prepareMarkdown(source), { gfm: true, breaks: true });
        return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
    }

    const sources = { zh: '/story.md', en: '/story-engl.md' };
    const copy = {
        zh: { title: '小说与世界设定', loading: '正在展开正文…', error: '正文暂时未能加载。', retry: '重新加载', label: '中文小说与世界设定' },
        en: { title: 'Story & worldbuilding', loading: 'Loading the manuscript…', error: 'The manuscript could not be loaded.', retry: 'Try again', label: 'English story and worldbuilding' }
    };

    document.querySelectorAll('[data-story-reader]').forEach(reader => {
        const scroller = reader.querySelector('[data-story-scroll]');
        const buttons = [...reader.querySelectorAll('[data-story-lang]')];
        const heading = reader.querySelector('[data-story-heading]');
        const status = reader.querySelector('[data-story-status]');
        const retry = reader.querySelector('[data-story-retry]');
        const cache = new Map();
        const positions = { zh: 0, en: 0 };
        let selected = reader.dataset.defaultLang === 'en' ? 'en' : 'zh';
        let displayed = null;
        let generation = 0;

        function fetchStory(lang) {
            if (!cache.has(lang)) {
                const request = fetch(sources[lang], { cache: 'no-cache' })
                    .then(response => {
                        if (!response.ok) throw new Error('Story HTTP ' + response.status);
                        return response.text();
                    })
                    .then(renderMarkdown)
                    .catch(error => { cache.delete(lang); throw error; });
                cache.set(lang, request);
            }
            return cache.get(lang);
        }

        async function selectLanguage(lang) {
            if (displayed) positions[displayed] = scroller.scrollTop;
            const current = ++generation;
            selected = lang;
            displayed = null;
            heading.textContent = copy[lang].title;
            scroller.lang = lang === 'zh' ? 'zh-CN' : 'en';
            scroller.setAttribute('aria-label', copy[lang].label);
            buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.storyLang === lang)));
            status.textContent = copy[lang].loading;
            retry.hidden = true;
            retry.textContent = copy[lang].retry;
            scroller.setAttribute('aria-busy', 'true');
            scroller.replaceChildren();
            try {
                const html = await fetchStory(lang);
                if (current !== generation) return;
                const article = document.createElement('article');
                article.className = 'story-prose';
                article.innerHTML = html;
                article.querySelectorAll('table, pre').forEach(element => {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'story-wide';
                    wrapper.tabIndex = 0;
                    wrapper.setAttribute('role', 'region');
                    wrapper.setAttribute('aria-label', lang === 'zh' ? '可横向滚动的内容' : 'Horizontally scrollable content');
                    element.replaceWith(wrapper);
                    wrapper.appendChild(element);
                });
                scroller.replaceChildren(article);
                scroller.scrollTop = positions[lang];
                displayed = lang;
                status.textContent = '';
            } catch {
                if (current !== generation) return;
                status.textContent = copy[lang].error;
                retry.hidden = false;
            } finally {
                if (current === generation) scroller.setAttribute('aria-busy', 'false');
            }
        }

        buttons.forEach(button => button.addEventListener('click', () => {
            if (selected !== button.dataset.storyLang) selectLanguage(button.dataset.storyLang);
        }));
        retry.addEventListener('click', () => selectLanguage(selected));
        selectLanguage(selected);
    });
})();
