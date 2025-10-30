// Background service worker for Hermes Job Search Extension

const API_BASE_URL = 'http://localhost:8080';

// Job search state
let jobSearchState = {
  isActive: false,
  urls: [],
  currentIndex: 0,
  installationId: null,
  completedUrls: []
};

// Listen for messages from popup and content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'startJobSearch') {
    handleStartJobSearch(request.urls, request.installationId);
  } else if (request.action === 'linksExtracted') {
    handleLinksExtracted(request.links, sender.tab.id);
  } else if (request.action === 'captchaDetected') {
    handleCaptchaDetected(sender.tab.id);
  } else if (request.action === 'captchaResolved') {
    handleCaptchaResolved(sender.tab.id);
  }
  return true; // Keep message channel open for async responses
});

// Start the job search process
async function handleStartJobSearch(urls, installationId) {
  console.log('Starting job search with', urls.length, 'URLs');
  
  jobSearchState = {
    isActive: true,
    urls: urls,
    currentIndex: 0,
    installationId: installationId,
    completedUrls: []
  };

  // Process URLs sequentially
  await processNextUrl();
}

// Process the next URL in the queue
async function processNextUrl() {
  if (jobSearchState.currentIndex >= jobSearchState.urls.length) {
    // All URLs processed
    await handleSearchComplete();
    return;
  }

  const currentUrl = jobSearchState.urls[jobSearchState.currentIndex];
  console.log(`Processing URL ${jobSearchState.currentIndex + 1}/${jobSearchState.urls.length}: ${currentUrl}`);

  // Notify popup of progress
  chrome.runtime.sendMessage({
    action: 'searchProgress',
    current: jobSearchState.currentIndex + 1,
    total: jobSearchState.urls.length
  });

  try {
    // Open URL in a new tab
    const tab = await chrome.tabs.create({
      url: currentUrl,
      active: true
    });

    // Store tab info for this URL
    jobSearchState.completedUrls[jobSearchState.currentIndex] = {
      url: currentUrl,
      tabId: tab.id,
      status: 'loading'
    };

  } catch (error) {
    console.error('Error opening tab:', error);
    // Continue with next URL even if this one failed
    jobSearchState.currentIndex++;
    await processNextUrl();
  }
}

// Handle links extracted from a Google search page
async function handleLinksExtracted(links, tabId) {
  console.log(`Received ${links.length} links from tab ${tabId}`);

  try {
    // Send links to /api/listings
    const response = await fetch(`${API_BASE_URL}/api/listings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        installation_id: jobSearchState.installationId,
        links: links
      })
    });

    if (!response.ok) {
      throw new Error(`Server responded with status: ${response.status}`);
    }

    const result = await response.json();
    console.log('Links sent to server:', result);

    // Close the tab after processing
    await chrome.tabs.remove(tabId);

    // Move to next URL
    jobSearchState.currentIndex++;
    await processNextUrl();

  } catch (error) {
    console.error('Error sending links to server:', error);
    
    // Close tab and continue with next URL
    try {
      await chrome.tabs.remove(tabId);
    } catch (e) {
      console.error('Error closing tab:', e);
    }
    
    jobSearchState.currentIndex++;
    await processNextUrl();
  }
}

// Handle captcha detection
function handleCaptchaDetected(tabId) {
  console.log(`Captcha detected on tab ${tabId}. Waiting for user to solve...`);
  
  // Show notification to user
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon48.png',
    title: 'Hermes: Captcha Detected',
    message: 'Please solve the captcha in the open tab. The extension will continue automatically.',
    priority: 2
  });
}

// Handle captcha resolution
function handleCaptchaResolved(tabId) {
  console.log(`Captcha resolved on tab ${tabId}. Continuing...`);
  
  // Clear any captcha notifications
  chrome.notifications.clear('captcha_notification');
  
  // The content script will automatically continue extracting links
}

// Handle search completion
async function handleSearchComplete() {
  console.log('Job search complete!');
  
  jobSearchState.isActive = false;

  // Notify popup
  chrome.runtime.sendMessage({
    action: 'searchComplete'
  });

  // Show completion notification
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon48.png',
    title: 'Hermes: Search Complete',
    message: 'All job search URLs have been processed. Check back in 24 hours for results!',
    priority: 1
  });
}

// Listen for tab updates to detect when pages finish loading
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (jobSearchState.isActive && changeInfo.status === 'complete') {
    // Check if this is one of our search tabs
    const urlInfo = jobSearchState.completedUrls.find(u => u && u.tabId === tabId);
    if (urlInfo && urlInfo.status === 'loading') {
      urlInfo.status = 'loaded';
      console.log(`Tab ${tabId} finished loading: ${tab.url}`);
      // Content script will automatically start processing
    }
  }
});

// Handle extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('Hermes extension installed!');
    // Open popup automatically
    chrome.action.openPopup();
  }
});

console.log('Hermes background service worker initialized');
