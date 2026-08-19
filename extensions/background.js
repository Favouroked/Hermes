const API_BASE_URL = 'http://localhost:8080';
let googleState = {active: false, urls: [], index: 0, runId: null, installationId: null, links: [], submitted: false};
const manualTasks = new Map();
const LINKS_KEY = 'linksRun';

async function saveLinks(state) {
    await chrome.storage.local.set({[LINKS_KEY]: state});
}

async function loadLinks() {
    const value = await chrome.storage.local.get(LINKS_KEY);
    return value[LINKS_KEY] || {active: false, links: [], index: 0, currentTabId: null, installationId: null};
}

async function post(path, body) {
    const response = await fetch(API_BASE_URL + path, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
}

async function loadGoogleState() {
    const stored = await chrome.storage.local.get('googleState');
    if (stored.googleState) googleState = stored.googleState;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'startGoogleSearch') startGoogleSearch(request).catch(console.error);
    if (request.action === 'stopGoogleSearch') stopGoogleSearch().catch(console.error);
    if (request.action === 'googleLinks') googleLinks(request.links || [], sender.tab && sender.tab.id, request.done);
    if (request.action === 'captchaDetected') chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon48.png',
        title: 'Hermes captcha',
        message: 'Solve the captcha in the open tab to continue.'
    });
    if (request.action === 'startLinks') startLinks(request.links, request.installationId).catch(console.error);
    if (request.action === 'terminateLinks') terminateLinks().catch(console.error);
    if (request.action === 'getCurrentLink') loadLinks().then(s => sendResponse({link: s.links[s.index] || null}));
    if (request.action === 'openAndExecute') chrome.tabs.create({
        url: request.url,
        active: true
    }).then(tab => manualTasks.set(tab.id, request.actions || []));
    return true;
});

async function startGoogleSearch(request) {
    googleState = {
        active: true,
        urls: request.urls,
        index: 0,
        runId: request.search_run_id,
        installationId: request.installationId,
        links: [],
        submitted: false
    };
    await chrome.storage.local.set({googleState, currentRoute: 'results'});
    await openGoogle();
}

async function openGoogle() {
    if (!googleState.active || googleState.index >= googleState.urls.length) {
        googleState.active = false;
        await chrome.storage.local.set({googleState});
        chrome.runtime.sendMessage({action: 'googleComplete'});
        await submitGoogleResults();
        return;
    }
    chrome.runtime.sendMessage({
        action: 'googleProgress',
        current: googleState.index + 1,
        total: googleState.urls.length
    });
    const tab = await chrome.tabs.create({url: googleState.urls[googleState.index], active: true});
    googleState.tabId = tab.id;
    await chrome.storage.local.set({googleState});
}

async function submitGoogleResults() {
    if (googleState.submitted) return;
    googleState.submitted = true;
    await chrome.storage.local.set({googleState});
    try {
        const result = await post('/api/automaton/google-results', {
            installation_id: googleState.installationId,
            search_run_id: googleState.runId,
            links: googleState.links
        });
        chrome.runtime.sendMessage({
            action: 'googleSubmitted',
            links: googleState.links.length,
            response: result
        });
    } catch (e) {
        googleState.submitted = false;
        await chrome.storage.local.set({googleState});
        chrome.runtime.sendMessage({action: 'googleSubmitError', error: e.message});
        throw e;
    }
}

async function stopGoogleSearch() {
    await loadGoogleState();
    if (!googleState.active) {
        if (!googleState.submitted) await submitGoogleResults();
        return;
    }
    const tabId = googleState.tabId;
    googleState.active = false;
    googleState.tabId = null;
    await chrome.storage.local.set({googleState});
    if (tabId !== undefined && tabId !== null) {
        try {
            await chrome.tabs.remove(tabId);
        } catch (e) {
        }
    }
    chrome.runtime.sendMessage({action: 'googleStopped'});
    await submitGoogleResults();
}

async function googleLinks(links, tabId, done) {
    await loadGoogleState();
    if (!googleState.active || tabId !== googleState.tabId) return;
    googleState.links = [...new Set([...googleState.links, ...links])];
    await chrome.storage.local.set({googleState});
    chrome.runtime.sendMessage({action: 'googleLinks', links});
    if (!done) return;
    try {
        await chrome.tabs.remove(tabId);
    } catch (e) {
    }
    googleState.index++;
    googleState.tabId = null;
    await chrome.storage.local.set({googleState});
    await openGoogle();
}

async function startLinks(links, installationId) {
    await saveLinks({active: true, links, index: 0, currentTabId: null, installationId});
    await openNextLink();
}

async function openNextLink() {
    const state = await loadLinks();
    if (!state.active || state.index >= state.links.length) {
        state.active = false;
        await saveLinks(state);
        chrome.runtime.sendMessage({action: 'linksComplete'});
        return;
    }
    const tab = await chrome.tabs.create({url: state.links[state.index].url, active: true});
    state.currentTabId = tab.id;
    await saveLinks(state);
    chrome.runtime.sendMessage({
        action: 'linkProgress',
        current: state.index + 1,
        total: state.links.length,
        link: state.links[state.index]
    });
}

async function terminateLinks() {
    const state = await loadLinks();
    state.active = false;
    await saveLinks(state);
    chrome.runtime.sendMessage({action: 'linksTerminated'});
}

async function markProcessed(state, item) {
    await fetch(`${API_BASE_URL}/api/automaton/links/${item.id}/processed`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({installation_id: state.installationId, notes: item.notes || ''})
    });
}

chrome.tabs.onRemoved.addListener(async tabId => {
    const state = await loadLinks();
    if (!state.active || state.currentTabId !== tabId) return;
    const item = state.links[state.index];
    try {
        await markProcessed(state, item);
    } catch (e) {
        console.error(e);
    }
    state.index++;
    state.currentTabId = null;
    await saveLinks(state);
    setTimeout(openNextLink, 300);
});

async function pageHtml(tabId) {
    try {
        const result = await chrome.tabs.sendMessage(tabId, {action: 'getPageHtml'});
        return result || '';
    } catch (e) {
        return '';
    }
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status !== 'complete') return;
    const state = await loadLinks();
    if (state.active && state.currentTabId === tabId) {
        try {
            const actions = await post('/api/auto-fill/check', {
                installation_id: state.installationId,
                url: tab.url,
                html: await pageHtml(tabId)
            });
            if (actions.length) chrome.tabs.sendMessage(tabId, {action: 'executeActions', actions});
        } catch (e) {
            console.error('link auto-fill', e);
        }
    }
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status !== 'complete' || !tab.url || /^chrome:|^chrome-extension:/.test(tab.url)) return;
    const state = await loadLinks();
    if (state.active && state.currentTabId === tabId) return;
    const stored = await chrome.storage.local.get('installationId');
    if (!stored.installationId) return;
    try {
        const settings = await fetch(`${API_BASE_URL}/api/settings?installation_id=${encodeURIComponent(stored.installationId)}`).then(r => r.json());
        if (!settings.auto_fill) return;
        const actions = await post('/api/auto-fill/check', {
            installation_id: stored.installationId,
            url: tab.url,
            html: await pageHtml(tabId)
        });
        if (actions.length) chrome.tabs.sendMessage(tabId, {action: 'executeActions', actions});
    } catch (e) {
        console.debug('Hermes auto-fill unavailable', e);
    }
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
    if (changeInfo.status !== 'complete' || !manualTasks.has(tabId)) return;
    const actions = manualTasks.get(tabId);
    manualTasks.delete(tabId);
    if (actions.length) chrome.tabs.sendMessage(tabId, {action: 'executeActions', actions});
});
