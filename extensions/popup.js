// Popup script for Hermes Job Search Extension

(function () {
    'use strict';

    const API_BASE_URL = 'http://localhost:8080';
    let installationId = null;

    // Initialize popup
    async function init() {
        try {
            // Get or generate installation ID
            installationId = await getOrCreateInstallationId();
            await chrome.storage.local.set({"installationId": installationId})
            document.getElementById('installationIdDisplay').textContent = installationId;

            // Check if already processing
            const state = await chrome.storage.local.get(['isProcessing', 'isApplying', 'backendProcessing']);
            if (state.isProcessing) {
                showStatus('info', 'Job search is in progress...', 'Please wait while we process the search results.');
                disableForm();
            } else if (state.isApplying) {
                showStatus('info', 'Application in progress...', 'Close the current tab to open the next job application.');
                disableForm();
            } else if (state.backendProcessing) {
                // Check status from backend
                await checkJobStatus();
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
        await chrome.storage.local.set({installationId: newId});
        return newId;
    }

    // Check job status from backend
    async function checkJobStatus() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    installation_id: installationId
                })
            });

            if (response.status === 200) {
                // Jobs are ready
                const result = await response.json();
                await chrome.storage.local.set({jobsReady: true});
                showJobsReadyUI(result.job_count);
                await chrome.storage.local.remove(['isProcessing']);
            } else if (response.status === 202) {
                // Still processing
                showCompletionMessage(1);
                disableForm();
                await chrome.storage.local.set({jobsReady: false});
            }
        } catch (error) {
            console.error('Error checking job status:', error);
            // Don't show error to user, just log it
        }
    }

    // Show UI when jobs are ready
    function showJobsReadyUI(jobCount) {
        const state = chrome.storage.local.get(['isProcessing', 'isApplying']);
        state.then(s => {
            if (!s.isProcessing && !s.isApplying) {
                // Create and show "Start Applying" button
                const applyBtn = document.getElementById('applyBtn');
                if (applyBtn) {
                    applyBtn.style.display = 'block';
                    applyBtn.addEventListener('click', handleStartApplying);
                }
                disableForm();
                showStatus('success', 'Jobs Ready!', `${jobCount} job applications are ready. Click "Start Applying" to begin.`);
            }
        });
    }

    // Handle start applying button click
    async function handleStartApplying() {
        try {
            showStatus('info', 'Loading jobs...', 'Fetching job URLs from server...');

            // Get URLs from backend
            const response = await fetch(`${API_BASE_URL}/api/urls`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    installation_id: installationId
                })
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const result = await response.json();

            if (!result.urls || result.urls.length === 0) {
                throw new Error('No job URLs received from server');
            }

            showStatus('success', 'Starting Applications!', `Opening ${result.urls.length} job applications sequentially...`);

            // Mark as applying
            await chrome.storage.local.set({isApplying: true});

            // Send URLs to background script for sequential processing
            chrome.runtime.sendMessage({
                action: 'startApplying',
                urls: result.urls,
                installationId: installationId
            });

            // Hide apply button
            const applyBtn = document.getElementById('applyBtn');
            if (applyBtn) {
                applyBtn.style.display = 'none';
            }

        } catch (error) {
            console.error('Error starting application process:', error);
            showStatus('error', 'Error', `Failed to start applications: ${error.message}`);
        }
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
            await chrome.storage.local.set({isProcessing: true});

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
        } else if (message.action === 'applicationProgress') {
            updateApplicationProgress(message.current, message.total);
        } else if (message.action === 'applicationComplete') {
            handleApplicationComplete();
        }
    }

    // Update progress information
    function updateProgress(current, total) {
        const progressInfo = document.getElementById('progressInfo');
        progressInfo.textContent = `Processing search ${current} of ${total}...`;
    }

    // Update application progress information
    function updateApplicationProgress(current, total) {
        const progressInfo = document.getElementById('progressInfo');
        progressInfo.textContent = `Visiting application ${current} of ${total}. Close the tab when done to continue.`;
    }

    // Handle search completion
    async function handleSearchComplete() {
        await chrome.storage.local.set({
            isProcessing: false,
            backendProcessing: true,
        });

        showCompletionMessage(12);
    }

    // Handle application completion
    async function handleApplicationComplete() {
        await chrome.storage.local.remove(['isApplying']);

        showStatus('success', 'Applications Complete!', 'You have visited all job application URLs. You can now close this popup.');
        document.getElementById('progressInfo').textContent = '';

        // Re-enable form for new searches
        enableForm();
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
