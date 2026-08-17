(function () {
    'use strict';
    const API = 'http://localhost:8080';
    const state = {id: null, route: location.hash.slice(1) || 'home', run: null, links: [], currentLink: null};
    const $ = id => document.getElementById(id);

    async function getId() {
        const v = await chrome.storage.local.get('installationId');
        if (v.installationId) return v.installationId;
        const id = `hermes_${crypto.randomUUID()}`;
        await chrome.storage.local.set({installationId: id});
        return id;
    }

    async function api(path, options = {}) {
        const response = await fetch(API + path, {headers: {'Content-Type': 'application/json', ...(options.headers || {})}, ...options});
        if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
        return response.json();
    }

    function shell(title, body, back = true) {
        $('app').innerHTML = `${back ? '<div class="nav"><button class="secondary" id="back">← Back</button></div>' : ''}<h2>${title}</h2><div class="stack">${body}</div>`;
        if (back) $('back').onclick = () => go(({
            automaton: 'home',
            google: 'automaton',
            results: 'google',
            links: 'automaton',
            manual: 'home',
            settings: 'home'
        }[state.route] || 'home'));
    }

    function go(route) {
        state.route = route;
        chrome.storage.local.set({currentRoute: route});
        location.hash = route;
        render();
    }

    function status(text, error = false) {
        const el = $('status');
        if (el) {
            el.textContent = text;
            el.className = `status ${error ? 'error' : ''}`;
        }
    }

    function render() {
        if (state.route === 'home') return home();
        if (state.route === 'automaton') return automaton();
        if (state.route === 'google') return google();
        if (state.route === 'results') return results();
        if (state.route === 'links') return links();
        if (state.route === 'manual') return manual();
        if (state.route === 'settings') return settings();
        home();
    }

    function home() {
        shell('Hermes', '<p>Choose an automation workflow.</p><button class="link" id="automaton">Automaton</button><button class="link" id="manual">Manual Fill</button><button class="link" id="settings">Settings</button>', false);
        $('automaton').onclick = () => go('automaton');
        $('manual').onclick = () => go('manual');
        $('settings').onclick = () => go('settings');
    }

    function automaton() {
        shell('Automaton', '<button class="link" id="google">Google Search</button><button class="link" id="links">Links</button>');
        $('google').onclick = () => go('google');
        $('links').onclick = () => go('links');
    }

    function google() {
        shell('Google Search', '<label>Cutoff date<input id="cutoff" type="date" required></label><label class="row">Force generate new searches<input id="forceGenerate" type="checkbox" style="width:auto"></label><button id="start">Start</button><div id="status"></div>');
        $('start').onclick = async () => {
            try {
                const cutoff = $('cutoff').value;
                if (!cutoff) return status('Choose a cutoff date.', true);
                $('start').disabled = true;
                status('Requesting Google searches…');
                const result = await api('/api/automaton/google-search', {
                    method: 'POST',
                    body: JSON.stringify({
                        installation_id: state.id,
                        cutoff_date: cutoff,
                        force_generate: $('forceGenerate').checked
                    })
                });
                state.run = result;
                await chrome.storage.local.set({googleRun: result});
                chrome.runtime.sendMessage({action: 'startGoogleSearch', ...result, installationId: state.id});
                status(`Opening ${result.urls.length} search pages…`);
                setTimeout(() => go('results'), 500);
            } catch (e) {
                $('start').disabled = false;
                status(e.message, true);
            }
        };
    }

    async function results() {
        const stored = await chrome.storage.local.get(['googleState', 'googleRun']);
        if (!state.run) state.run = stored.googleRun || stored.googleState || null;
        if (stored.googleState && state.links.length === 0) state.links = stored.googleState.links || [];
        shell('Search Results', '<div id="status">Search is running…</div><div id="results"></div>');
        const draw = () => {
            $('results').innerHTML = state.links.map(x => `<div class="result">${escapeHtml(x)}</div>`).join('') || '<p>No links extracted yet.</p>';
        };
        draw();
        chrome.runtime.onMessage.addListener(m => {
            if (m.action === 'googleProgress') status(`Search ${m.current} of ${m.total}…`);
            if (m.action === 'googleLinks') {
                state.links = [...new Set([...state.links, ...m.links])];
                draw();
            }
            if (m.action === 'googleComplete') {
                status('Search complete. Sending results…');
                const runId = (state.run || {}).search_run_id || (state.run || {}).runId;
                api('/api/automaton/google-results', {
                    method: 'POST',
                    body: JSON.stringify({installation_id: state.id, search_run_id: runId, links: state.links})
                }).then(() => status(`Submitted ${state.links.length} links.`)).catch(e => status(e.message, true));
            }
        });
    }

    async function links() {
        const saved = await chrome.storage.local.get('linksRun');
        shell('Links', '<div class="grid"><label>Max links<input id="max" type="number" min="1" max="100" value="20"></label><label>With actions<input id="withActions" type="checkbox" style="width:auto;margin-top:10px"></label></div><button id="start">Start</button><button id="terminate" class="danger hidden">Terminate</button><div id="status"></div><div id="notesBox" class="hidden"><label>Notes<textarea id="notes"></textarea></label><button id="saveNotes">Save notes</button></div>');
        const activate = () => {
            $('start').classList.add('hidden');
            $('terminate').classList.remove('hidden');
            $('notesBox').classList.remove('hidden');
            $('terminate').onclick = () => {
                chrome.runtime.sendMessage({action: 'terminateLinks'});
                $('terminate').classList.add('hidden');
                status('Loop terminated.');
            };
            $('saveNotes').onclick = saveNotes;
            chrome.runtime.onMessage.addListener(m => {
                if (m.action === 'linkProgress') {
                    state.currentLink = m.current - 1;
                    $('notes').value = state.links[state.currentLink].notes || '';
                    status(`Link ${m.current} of ${m.total}. Close the tab when finished.`);
                }
                if (m.action === 'linksComplete' || m.action === 'linksTerminated') $('terminate').classList.add('hidden');
            });
        };
        if (saved.linksRun && saved.linksRun.active) {
            state.links = saved.linksRun.links;
            state.currentLink = saved.linksRun.index;
            activate();
            status('Link loop is running. Close the current tab when finished.');
        }
        $('start').onclick = async () => {
            try {
                const result = await api('/api/automaton/links', {
                    method: 'POST',
                    body: JSON.stringify({
                        installation_id: state.id,
                        max_links: Number($('max').value),
                        with_actions: $('withActions').checked
                    })
                });
                if (!result.links.length) return status('No matching links found.');
                state.links = result.links;
                state.currentLink = 0;
                activate();
                chrome.runtime.sendMessage({action: 'startLinks', links: result.links, installationId: state.id});
                status(`Opening ${result.links.length} links. Close each tab when finished.`);
            } catch (e) {
                status(e.message, true);
            }
        };
    }

    async function saveNotes() {
        if (state.currentLink === null) return;
        const item = state.links[state.currentLink];
        await api(`/api/automaton/links/${item.id}/notes`, {
            method: 'PUT',
            body: JSON.stringify({installation_id: state.id, notes: $('notes').value})
        });
        status('Notes saved.');
    }

    function manual() {
        shell('Manual Fill', '<label>Page URL<input id="url" type="url" placeholder="https://…" required></label><label>Context file (optional)<input id="context" type="file"></label><button id="submit">Submit</button><div id="status"></div>');
        $('submit').onclick = async () => {
            try {
                const url = $('url').value.trim();
                if (!url) return status('Enter a URL.', true);
                $('submit').disabled = true;
                const form = new FormData();
                form.append('installation_id', state.id);
                form.append('url', url);
                const file = $('context').files[0];
                if (file) form.append('context', file);
                const tab = await chrome.tabs.query({active: true, currentWindow: true});
                let sameTab = tab[0] && tab[0].url === url;
                if (sameTab) {
                    const page = await chrome.tabs.sendMessage(tab[0].id, {action: 'getPageHtml'});
                    if (page) form.append('html', page);
                }
                const result = await fetch(API + '/api/manual-fill', {method: 'POST', body: form});
                if (!result.ok) throw new Error(await result.text());
                const actions = await result.json();
                if (sameTab) chrome.tabs.sendMessage(tab[0].id, {
                    action: 'executeActions',
                    actions
                }); else chrome.runtime.sendMessage({action: 'openAndExecute', url, actions});
                status(`${actions.length} actions implemented.`);
            } catch (e) {
                status(e.message, true);
                $('submit').disabled = false;
            }
        };
    }

    async function settings() {
        shell('Settings', '<label>Resume<textarea id="resume" placeholder="Paste your resume text here…"></textarea></label><label>Preferences<textarea id="preferences" placeholder="Describe your job preferences…"></textarea></label><label>LLM Provider<select id="provider"><option value="ollama">Ollama</option><option value="openai">OpenAI</option></select></label><label>LLM API Key (optional)<input id="key" type="password" autocomplete="off"></label><label class="row">Auto-fill<input id="auto" type="checkbox" style="width:auto"></label><div class="muted">Extension ID: ' + state.id + '</div><button id="save">Save</button><div id="status"></div>');
        try {
            const s = await api('/api/settings?installation_id=' + encodeURIComponent(state.id));
            $('resume').value = s.resume || '';
            $('preferences').value = s.preferences || '';
            $('provider').value = s.llm_provider;
            $('auto').checked = s.auto_fill;
        } catch (e) {
            status(e.message, true);
        }
        $('save').onclick = async () => {
            try {
                await api('/api/settings', {
                    method: 'PATCH',
                    body: JSON.stringify({
                        installation_id: state.id,
                        resume: $('resume').value,
                        preferences: $('preferences').value,
                        llm_provider: $('provider').value,
                        openai_key: $('key').value || null,
                        auto_fill: $('auto').checked
                    })
                });
                status('Settings saved.');
            } catch (e) {
                status(e.message, true);
            }
        };
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[c]));
    }

    window.addEventListener('hashchange', () => {
        state.route = location.hash.slice(1) || 'home';
        render();
    });
    (async () => {
        state.id = await getId();
        const stored = await chrome.storage.local.get(['currentRoute', 'googleRun', 'googleState']);
        if (location.hash.slice(1) === '') state.route = stored.currentRoute || 'home';
        state.run = stored.googleRun || stored.googleState || null;
        render();
    })();
})();
