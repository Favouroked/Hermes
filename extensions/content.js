(function () {
    'use strict';
    const isGoogle = () => /google\./.test(location.hostname) && location.pathname === '/search';
    const captcha = () => Boolean(document.querySelector('iframe[src*="recaptcha"],.g-recaptcha,#captcha,form[action*="sorry"]')) || /unusual traffic|automated queries/i.test((document.body && document.body.innerText) || '');
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
        const extractedLinks = [...document.querySelectorAll('.yuRUbf a[href]')]
            .map(a => a.href);
        chrome.runtime.sendMessage({action: 'googlePage', links: extractedLinks, hasNext: Boolean(next)}, response => {
            if (response && response.continue && next) {
                sent = false;
                setTimeout(() => next.click(), 1200);
            }
        });
    }

    setTimeout(search, 500);
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
