// Popup script for Hermes Job Search Extension

(function() {
  'use strict';

  const API_BASE_URL = 'http://localhost:8080';
  let installationId = null;

  // Initialize popup
  async function init() {
    try {
      // Get or generate installation ID
      installationId = await getOrCreateInstallationId();
      document.getElementById('installationIdDisplay').textContent = installationId;

      // Check if already processing
      const state = await chrome.storage.local.get(['isProcessing', 'completionTime']);
      if (state.isProcessing) {
        showStatus('info', 'Job search is in progress...', 'Please wait while we process the search results.');
        disableForm();
      } else if (state.completionTime) {
        const completionDate = new Date(state.completionTime);
        const hoursRemaining = 24 - (Date.now() - completionDate) / (1000 * 60 * 60);
        
        if (hoursRemaining > 0) {
          showCompletionMessage(Math.ceil(hoursRemaining));
          disableForm();
        } else {
          // 24 hours have passed, allow new search
          await chrome.storage.local.remove(['isProcessing', 'completionTime']);
        }
      }

      // Setup event listeners
      document.getElementById('submitBtn').addEventListener('click', handleSubmit);

      // Listen for messages from background script
      chrome.runtime.onMessage.addListener(handleBackgroundMessage);

    } catch (error) {
      console.error('Error initializing popup:', error);
      showStatus('error', 'Initialization Error', error.message);
    }
  }

  // Get or create a unique installation ID
  async function getOrCreateInstallationId() {
    const result = await chrome.storage.local.get(['installationId']);
    
    if (result.installationId) {
      return result.installationId;
    }

    // Generate new installation ID
    const newId = `hermes_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    await chrome.storage.local.set({ installationId: newId });
    return newId;
  }

  // Handle form submission
  async function handleSubmit() {
    const resumeText = document.getElementById('resumeText').value.trim();
    const preferencesText = document.getElementById('preferencesText').value.trim();

    // Validate inputs
    if (!resumeText) {
      showStatus('error', 'Validation Error', 'Please enter your resume text.');
      return;
    }

    if (!preferencesText) {
      showStatus('error', 'Validation Error', 'Please enter your job preferences.');
      return;
    }

    try {
      // Disable form during processing
      disableForm();
      showStatus('info', 'Processing...', 'Sending your information to the server...');

      // Send data to /api/install
      const response = await fetch(`${API_BASE_URL}/api/install`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          installation_id: installationId,
          resume: resumeText,
          preferences: preferencesText
        })
      });

      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }

      const result = await response.json();
      
      if (!result.urls || result.urls.length === 0) {
        throw new Error('No search URLs received from server');
      }

      showStatus('success', 'Success!', `Received ${result.urls.length} search queries. Opening tabs...`);

      // Mark as processing
      await chrome.storage.local.set({ isProcessing: true });

      // Send URLs to background script for processing
      chrome.runtime.sendMessage({
        action: 'startJobSearch',
        urls: result.urls,
        installationId: installationId
      });

    } catch (error) {
      console.error('Error submitting form:', error);
      showStatus('error', 'Error', `Failed to start job search: ${error.message}`);
      enableForm();
    }
  }

  // Handle messages from background script
  function handleBackgroundMessage(message, sender, sendResponse) {
    if (message.action === 'searchProgress') {
      updateProgress(message.current, message.total);
    } else if (message.action === 'searchComplete') {
      handleSearchComplete();
    } else if (message.action === 'searchError') {
      showStatus('error', 'Error', message.error);
      enableForm();
      chrome.storage.local.remove(['isProcessing']);
    }
  }

  // Update progress information
  function updateProgress(current, total) {
    const progressInfo = document.getElementById('progressInfo');
    progressInfo.textContent = `Processing search ${current} of ${total}...`;
  }

  // Handle search completion
  async function handleSearchComplete() {
    const completionTime = Date.now();
    await chrome.storage.local.set({ 
      isProcessing: false,
      completionTime: completionTime
    });
    
    showCompletionMessage(24);
  }

  // Show completion message
  function showCompletionMessage(hoursRemaining) {
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.className = 'status-message completion';
    statusMessage.innerHTML = `
      <strong>✓ Job Search Complete!</strong>
      <p>All search results have been processed and sent to the server.</p>
      <p style="margin-top: 10px;"><strong>Please check back in ${hoursRemaining} hours for results.</strong></p>
    `;
    document.getElementById('progressInfo').textContent = '';
    disableForm();
  }

  // Show status message
  function showStatus(type, title, message) {
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.className = `status-message ${type}`;
    statusMessage.innerHTML = `<strong>${title}</strong><p>${message}</p>`;
  }

  // Disable form
  function disableForm() {
    document.getElementById('resumeText').disabled = true;
    document.getElementById('preferencesText').disabled = true;
    document.getElementById('submitBtn').disabled = true;
  }

  // Enable form
  function enableForm() {
    document.getElementById('resumeText').disabled = false;
    document.getElementById('preferencesText').disabled = false;
    document.getElementById('submitBtn').disabled = false;
  }

  // Start initialization when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
