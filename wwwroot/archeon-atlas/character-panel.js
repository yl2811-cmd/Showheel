(() => {
    'use strict';
    const stage = document.getElementById('character-stage');
    let pending = null, reader = null;
    const locale = () => window.ATLAS_I18N?.locale || 'zh';
    function status(message, retry) {
        const wrapper = document.createElement('div');
        wrapper.className = 'character-panel-status';
        const paragraph = document.createElement('p');
        paragraph.setAttribute('role', 'status');
        paragraph.textContent = message;
        wrapper.append(paragraph);
        if (retry) {
            const button = document.createElement('button');
            button.textContent = locale() === 'en' ? 'Try again' : '重新展开';
            button.onclick = () => window.ATLAS_APP.setTab('character');
            wrapper.append(button);
        }
        stage.replaceChildren(wrapper);
    }
    function open() {
        if (reader) { reader.setLanguage(locale(), false); return Promise.resolve(); }
        if (pending) return pending;
        stage.setAttribute('aria-busy', 'true');
        status(locale() === 'en' ? 'Opening the portraits…' : '正在展开人物…');
        pending = (async () => {
            const response = await fetch('/Character');
            if (!response.ok) throw Error('Character HTTP ' + response.status);
            const document = new DOMParser().parseFromString(await response.text(), 'text/html');
            const content = document.querySelector('[data-characters]');
            if (!content || !window.SHOWHEEL_CHARACTERS) throw Error('Character content is unavailable');
            content.dataset.noTranslate = '';
            stage.replaceChildren(content);
            reader = window.SHOWHEEL_CHARACTERS.mount(content, {
                locale: locale(), scrollContainer: stage, manageDocumentLanguage: false,
                onLanguageChange: value => window.ATLAS_I18N.setLocale(value)
            });
        })().catch(error => {
            pending = null;
            status(locale() === 'en' ? 'The portraits could not be opened. Please try again.' : '人物暂未展开，请重试。', true);
            throw error;
        }).finally(() => stage.setAttribute('aria-busy', 'false'));
        return pending;
    }
    addEventListener('atlas-language-changed', event => reader?.setLanguage(event.detail.locale));
    window.ATLAS_CHARACTERS = { open };
})();
