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

        } catch (error) {
            console.error('Error processing page:', error);
            
            // Notify background of error (send empty links)
            chrome.runtime.sendMessage({
                action: 'linksExtracted',
                links: []
            });
        }
    }

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
