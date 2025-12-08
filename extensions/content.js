// Content script for Hermes Job Search Extension
// Handles Google search page processing, captcha detection, and link extraction

(function () {
    'use strict';

    let captchaCheckInterval = null;
    let hasProcessedPage = false;

    // Check if this is a Google search page
    function isGoogleSearchPage() {
        const hostname = window.location.hostname;
        const pathname = window.location.pathname;

        return (hostname.includes('google.com') || hostname.includes('google.')) &&
            (pathname === '/search' || window.location.search.includes('q='));
    }

    // Check if captcha is present on the page
    function isCaptchaPresent() {
        // Google captcha indicators
        const captchaSelectors = [
            'iframe[src*="google.com/recaptcha"]',
            'iframe[src*="recaptcha"]',
            '#recaptcha',
            '.g-recaptcha',
            'form[action*="sorry"]',
            'div[id*="captcha"]',
            'div[class*="captcha"]'
        ];

        for (const selector of captchaSelectors) {
            if (document.querySelector(selector)) {
                return true;
            }
        }

        // Check if we're on the "sorry" page (unusual traffic detection)
        if (window.location.pathname.includes('/sorry/') ||
            document.body.textContent.includes('unusual traffic') ||
            document.body.textContent.includes('automated queries')) {
            return true;
        }

        return false;
    }

    // Extract all links from Google search results
    function extractSearchLinks() {
        const links = [];

        // Google search result link selectors
        // Main search results
        const resultLinks = document.querySelectorAll('a[href]');

        for (const link of resultLinks) {
            const href = link.href;

            // Filter out Google's own links, navigation, etc.
            if (href &&
                !href.includes('google.com/search') &&
                !href.includes('google.com/url') &&
                !href.includes('webcache.googleusercontent.com') &&
                !href.includes('support.google.com') &&
                !href.includes('policies.google.com') &&
                !href.includes('accounts.google.com') &&
                !href.startsWith('javascript:') &&
                !href.startsWith('#') &&
                (href.startsWith('http://') || href.startsWith('https://'))) {

                // Check if this link is in a search result (has certain parent elements)
                const parent = link.closest('div[data-sokoban-container]') ||
                    link.closest('div.g') ||
                    link.closest('div[class*="result"]') ||
                    link.closest('div[jsname]');

                if (parent && !links.includes(href)) {
                    links.push(href);
                }
            }
        }

        // Also try to get links from cite elements (visible URLs)
        const cites = document.querySelectorAll('cite');
        for (const cite of cites) {
            const text = cite.textContent.trim();
            if (text && !text.includes('...')) {
                // Try to find the actual link near this cite
                let element = cite;
                while (element && element !== document.body) {
                    const nearbyLink = element.querySelector('a[href]');
                    if (nearbyLink && nearbyLink.href.startsWith('http')) {
                        const href = nearbyLink.href;
                        if (!href.includes('google.com') && !links.includes(href)) {
                            links.push(href);
                        }
                        break;
                    }
                    element = element.parentElement;
                }
            }
        }

        return links;
    }

    // Wait for page to be fully loaded
    function waitForPageLoad() {
        return new Promise((resolve) => {
            if (document.readyState === 'complete') {
                setTimeout(resolve, 1000); // Extra delay for dynamic content
            } else {
                window.addEventListener('load', () => {
                    setTimeout(resolve, 1000);
                });
            }
        });
    }

    // Monitor for captcha resolution
    function startCaptchaMonitoring() {
        console.log('Starting captcha monitoring...');

        captchaCheckInterval = setInterval(() => {
            if (!isCaptchaPresent()) {
                console.log('Captcha resolved!');
                stopCaptchaMonitoring();

                // Notify background script
                chrome.runtime.sendMessage({
                    action: 'captchaResolved'
                });

                // Continue processing
                processPage();
            }
        }, 1000); // Check every second
    }

    // Stop captcha monitoring
    function stopCaptchaMonitoring() {
        if (captchaCheckInterval) {
            clearInterval(captchaCheckInterval);
            captchaCheckInterval = null;
        }
    }

    // Process the Google search page
    async function processPage() {
        // Prevent double processing
        if (hasProcessedPage) {
            return;
        }

        try {
            // Wait for page to load
            await waitForPageLoad();

            // Check if captcha is present
            if (isCaptchaPresent()) {
                console.log('Captcha detected! Waiting for user to solve...');

                // Notify background script about captcha
                chrome.runtime.sendMessage({
                    action: 'captchaDetected'
                });

                // Start monitoring for captcha resolution
                startCaptchaMonitoring();
                return;
            }

            // Mark as processed
            hasProcessedPage = true;

            // Extract all links from search results
            const links = extractSearchLinks();
            console.log(`Extracted ${links.length} links from search page`);

            if (links.length > 0) {
                // Send links to background script
                chrome.runtime.sendMessage({
                    action: 'linksExtracted',
                    links: links
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        console.error('Error sending links:', chrome.runtime.lastError);
                    } else {
                        console.log('Links sent to background script');
                    }
                });

            } else {
                console.warn('No links found on the page');
                // Still notify background that we're done (even with no links)
                chrome.runtime.sendMessage({
                    action: 'linksExtracted',
                    links: []
                });
            }


            // Get elements with class NKTSme and filter for YyVfkd
            const elements = document.querySelectorAll('td.NKTSme');
            const filteredElement = Array.from(elements).find(el => el.classList.contains('YyVfkd'));
            const currentPage = filteredElement ? filteredElement.textContent : '';

            // Limit to the first 5 pages
            if (currentPage === '' || currentPage === '5') {
                chrome.runtime.sendMessage({
                    action: 'linksExtracted',
                    links: [],
                    submitLinks: true
                });
            } else {
                // Click on next page link if present
                const nextButton = document.getElementById('pnnext');
                if (nextButton) {
                    nextButton.click();
                } else {
                    chrome.runtime.sendMessage({
                    action: 'linksExtracted',
                    links: [],
                    submitLinks: true
                });
                }
            }


        } catch (error) {
            console.error('Error processing page:', error);

            // Notify background of error (send empty links)
            chrome.runtime.sendMessage({
                action: 'linksExtracted',
                links: []
            });
        }
    }

    // ============ JOB APPLICATION PAGE HANDLING ============

    // Extract page HTML
    function getPageHTML() {
        return document.documentElement.outerHTML;
    }

    // Call /api/filler and execute actions
    async function processJobApplicationPage(installationId) {
        console.log('Processing job application page...');

        try {
            // Wait for page to fully load
            await waitForPageLoad();

            // Get page HTML and current URL
            const html = getPageHTML();
            const url = window.location.href;
            const timestamp = new Date().toISOString();

            console.log('Sending page data to /api/filler...');

            // Call /api/filler
            const response = await fetch('http://localhost:8080/api/filler', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    html: html,
                    timestamp: timestamp,
                    installation_id: installationId
                })
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const actions = await response.json();
            console.log(`Received ${actions.length} actions from /api/filler`);

            // Execute actions if any
            if (actions.length > 0) {
                await executeActions(actions);
            } else {
                console.log('No actions to execute');
            }

        } catch (error) {
            console.error('Error processing job application page:', error);
        }
    }

    // Execute actions sequentially
    async function executeActions(actions) {
        console.log('Executing actions...');

        for (let i = 0; i < actions.length; i++) {
            const action = actions[i];
            console.log(`Executing action ${i + 1}/${actions.length}:`, action.action);

            try {
                let success = false;

                switch (action.action) {
                    case 'type':
                        if (action.query_selector && action.value !== undefined) {
                            success = doType(action.query_selector, action.value);
                        }
                        break;

                    case 'click':
                        if (action.query_selector) {
                            success = doClick(action.query_selector);
                        }
                        break;

                    case 'select':
                        if (action.query_selector && action.value !== undefined) {
                            success = doSelect(action.query_selector, action.value);
                        }
                        break;

                    case 'alert':
                        // Show alert to user
                        if (action.value) {
                            alert(action.value);
                            success = true;
                        }
                        break;

                    default:
                        console.warn(`Unknown action type: ${action.action}`);
                }

                if (success) {
                    console.log(`Action ${i + 1} executed successfully`);
                } else {
                    console.warn(`Action ${i + 1} failed to execute`);
                }
            } catch (error) {
                console.log(`Error executing action ${i + 1}:`, error);
            } finally {
                // Add small delay between actions
                // await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        console.log('All actions executed');
    }

    // Listen for messages from background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'processJobPage') {
            console.log('Received processJobPage message with installation_id:', message.installationId);
            executeActions(message.jobActions);
            sendResponse({status: 'processing'});
        }
        return true; // Keep message channel open for async response
    });

    // ============ END JOB APPLICATION PAGE HANDLING ============

    // Main initialization
    async function init() {
        console.log('Hermes content script loaded');
        console.log('Current URL:', window.location.href);

        // Only process if this is a Google search page
        if (isGoogleSearchPage()) {
            console.log('Google search page detected');
            await processPage();
        } else {
            console.log('Not a Google search page, skipping processing');
        }
    }

    // Start processing
    init();

})();
