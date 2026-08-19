(function () {
    'use strict';
    const isGoogle = () => /google\./.test(location.hostname) && location.pathname === '/search';
    const captcha = () => Boolean(document.querySelector('iframe[src*="recaptcha"],.g-recaptcha,#captcha,form[action*="sorry"]')) || /unusual traffic|automated queries/i.test((document.body && document.body.innerText) || '');
    const extract = () => [...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => /^https?:/.test(h) && !/(google\.|gstatic\.|googleusercontent\.)/.test(new URL(h).hostname)).filter((h, i, a) => a.indexOf(h) === i);
    let sent = false;

    function search() {
        if (!isGoogle() || sent) return;
        if (captcha()) {
            chrome.runtime.sendMessage({action: 'captchaDetected'});
            setTimeout(search, 1500);
            return;
        }
        sent = true;
        const next = document.querySelector('#pnnext');
        chrome.runtime.sendMessage({action: 'googleLinks', links: extract(), done: !next});
        if (next) {
            sent = false;
            setTimeout(() => next.click(), 1200);
        }
    }

    setTimeout(search, 1000);
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'getPageHtml') sendResponse(document.documentElement.outerHTML);
        if (message.action === 'executeActions') {
            executeActions(message.actions || []);
            sendResponse({status: 'ok'});
        }
        return true;
    });

    function executeActions(actions) {
        for (const a of actions) {
            try {
                if (a.action === 'type') doType(a.query_selector, a.value); else if (a.action === 'click') doClick(a.query_selector); else if (a.action === 'select') doSelect(a.query_selector, a.value);
            } catch (e) {
                console.warn('Hermes action failed', e);
            }
        }
    }
})();
