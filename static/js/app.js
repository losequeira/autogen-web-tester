// AutoGen Web Tester - Frontend JavaScript

// Configure marked.js for safe, clean markdown rendering
if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

// ========== JWT TOKEN MANAGEMENT ==========
let authToken = localStorage.getItem('access_token') || null;
let refreshToken = localStorage.getItem('refresh_token') || null;

function storeTokens(access, refresh) {
    authToken = access;
    refreshToken = refresh;
    if (access) localStorage.setItem('access_token', access);
    else localStorage.removeItem('access_token');
    if (refresh) localStorage.setItem('refresh_token', refresh);
    else localStorage.removeItem('refresh_token');
}

function clearTokens() {
    authToken = null;
    refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
}

async function authFetch(url, options = {}) {
    if (!options.headers) options.headers = {};
    if (authToken) {
        options.headers['Authorization'] = `Bearer ${authToken}`;
    }
    let response = await fetch(url, options);
    if (response.status === 401 && refreshToken) {
        // Attempt token refresh
        const refreshResp = await fetch('/api/refresh-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (refreshResp.ok) {
            const data = await refreshResp.json();
            storeTokens(data.access_token, data.refresh_token);
            options.headers['Authorization'] = `Bearer ${data.access_token}`;
            response = await fetch(url, options);
        } else {
            clearTokens();
            showLoginModal();
        }
    }
    return response;
}
// ========== END JWT TOKEN MANAGEMENT ==========

function dismissLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    overlay.classList.add('fade-out');
    overlay.addEventListener('transitionend', () => overlay.remove());
}

function showAppOverlay(label = 'Loading workspace…') {
    const overlay = document.getElementById('workspace-switch-overlay');
    if (!overlay) return;
    const labelEl = overlay.querySelector('.workspace-switch-label');
    if (labelEl) labelEl.textContent = label;
    overlay.style.display = 'flex';
}

function hideAppOverlay() {
    const overlay = document.getElementById('workspace-switch-overlay');
    if (overlay) overlay.style.display = 'none';
}

// Initialize Socket.IO with auth token (passed as query param for Flask-SocketIO compat)
const socket = io({ query: { token: authToken || '' } });

// Authentication state
let currentUser = null;
let currentWorkspaceName = null;

// Cache of tests keyed by filename, populated when the file explorer loads
let testCache = {};

// ========== USER PREFERENCES SYNC ==========
function savePreferenceToDb(key, value) {
    try {
        localStorage.setItem('pref_' + key, JSON.stringify(value));
    } catch (err) {
        console.error('Failed to save preference:', err);
    }
}

async function loadPreferencesFromDb() {
    const prefs = {};
    for (const key of ['theme', 'editorTabsState', 'selectedWorkspaceName']) {
        const raw = localStorage.getItem('pref_' + key);
        if (raw !== null) {
            try { prefs[key] = JSON.parse(raw); } catch { prefs[key] = raw; }
        }
    }
    return prefs;
}

async function ensurePreferencesCached() {
    // no-op: localStorage reads are synchronous, no caching needed
}
// ========== END USER PREFERENCES SYNC ==========

// Authentication page elements
const authPage = document.getElementById('auth-page');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const loginError = document.getElementById('login-error');
const registerError = document.getElementById('register-error');
const authTabs = document.querySelectorAll('.auth-tab');
const authTabsContainer = document.querySelector('.auth-tabs');

// Workspace elements
const currentUsernameEl = document.getElementById('current-username');
const logoutBtn = document.getElementById('logout-btn');
const workspaceDropdown = document.getElementById('workspace-dropdown');
const newWorkspaceBtn = document.getElementById('new-workspace-btn');

const newWorkspaceModal = document.getElementById('new-workspace-modal');
const newWorkspaceForm = document.getElementById('new-workspace-form');
const closeNewWorkspaceBtns = document.querySelectorAll('.close-new-workspace');
const newWorkspaceError = document.getElementById('new-workspace-error');

let userWorkspaces = [];
let currentWorkspace = null;

// DOM Elements
const clearLogBtn = document.getElementById('clear-log');
const liveViewerIframe = document.getElementById('live-viewer-iframe');

/** Lazy-load live-viewer iframe on first use (faster startup). */
function ensureLiveViewerLoaded() {
    if (liveViewerIframe && !liveViewerIframe.src.includes('/live-viewer')) {
        liveViewerIframe.src = '/live-viewer/';
    }
}

const browserScreenshot = document.getElementById('browser-screenshot');
const browserStatus = document.getElementById('browser-status');
const browserTestName = document.getElementById('browser-test-name');
const browserLoading = document.getElementById('browser-loading');
const humanLogContainer = document.getElementById('human-log-container');
const technicalLogContainer = document.getElementById('technical-log-container');
const screenshotTimestamp = document.getElementById('screenshot-timestamp');
const logTabs = document.querySelectorAll('.log-tab');

// CodeMirror Editor
let codeMirrorEditor = null;

// Chat elements
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat');
const clearChatBtn = document.getElementById('clear-chat-btn');
const toggleChatBtn = document.getElementById('toggle-chat');
const closeChatSidebarBtn = document.getElementById('close-chat-sidebar');
const aiChatSidebar = document.getElementById('ai-chat-sidebar');
const chatResizer = document.getElementById('chat-resizer');
const contextMenu = document.getElementById('context-menu');
const codeEditorSection = document.querySelector('.code-editor-section');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const imagePreviewContainer = document.getElementById('image-preview-container');
const imagePreview = document.getElementById('image-preview');
const removeImageBtn = document.getElementById('remove-image');

let currentImage = null; // Store current image as base64

// Browser sidebar elements
const toggleBrowserBtn = document.getElementById('toggle-browser');
const closeBrowserSidebarBtn = document.getElementById('close-browser-sidebar');
const browserSidebar = document.getElementById('browser-sidebar');
const stopTestBtn = document.getElementById('stop-test-btn');
const stopRecordingBtn = document.getElementById('stop-recording-btn');
const recorderUrlBar = document.getElementById('recorder-url-bar');
const recorderUrlInput = document.getElementById('recorder-url-input');
const browserScreenshotContainer = document.querySelector('.browser-screenshot-container');

// Output panel elements
const outputPanel = document.getElementById('output-panel');
const toggleOutputBtn = document.getElementById('toggle-output');

// Code preview panel elements
const codePreviewPanel = document.getElementById('code-preview-panel');
const codePreviewExplanation = document.getElementById('code-preview-explanation');
const codePreviewCurrent = document.getElementById('code-preview-current');
const codePreviewSuggested = document.getElementById('code-preview-suggested');
const acceptCodeBtn = document.getElementById('accept-code-btn');
const rejectCodeBtn = document.getElementById('reject-code-btn');
const closePreviewBtn = document.getElementById('close-preview-btn');

// Editor tabs and file explorer (with null checks)
const fileExplorer = document.getElementById('file-explorer');
const fileList = document.getElementById('file-list');
const editorTabsContainer = document.querySelector('.editor-tabs-container');
const editorContent = document.querySelector('.editor-content');
const newTestBtn = document.getElementById('new-test-btn');
const closeAllTabsBtn = document.getElementById('close-all-tabs');
const explorerResizer = document.getElementById('explorer-resizer');

// AI Steps elements
const aiStepsList = document.getElementById('ai-steps-list');
const newAiStepBtn = document.getElementById('new-ai-step-btn');
const aiStepModal = document.getElementById('ai-step-modal');
const aiStepNameInput = document.getElementById('ai-step-name');
const aiStepStepsInput = document.getElementById('ai-step-steps');
const saveAiStepBtn = document.getElementById('save-ai-step-btn');
const cancelAiStepBtn = document.getElementById('cancel-ai-step-btn');
const closeAiStepModal = document.querySelector('.close-ai-step-modal');

let openTabs = []; // Array of {id, name, code, isDirty}
let activeTabId = null;
let pendingCodeSuggestion = null;

// Check if file explorer elements exist
const hasFileExplorer = fileExplorer && fileList && editorTabsContainer && newTestBtn && explorerResizer;

let currentEditingTest = null;  // Track if we're editing an existing test
let currentRecordingId = null;  // Track active recording
let recorderViewport = { width: 1280, height: 720 };  // Actual browser viewport for coordinate scaling
let pendingCodegenTest = null;  // Track test info from codegen
let pendingCodegenTabId = null;  // Tab (filename) to fill with recorded code when codegen_complete
let currentEditingAiStep = null;  // Track if we're editing an existing AI step
let currentRunningTestFilename = null;  // Track which saved test is currently running

let isTestRunning = false;
let isBatchRunning = false;
let runningTestsSet = new Set();
let batchRunStartTime = null;
let batchRunResults = [];
let isStopRequested = false;

// Helper function to update browser status
function updateBrowserStatus(status, text) {
    if (!browserStatus) return;

    // Remove all status classes
    browserStatus.className = 'status-badge';

    // Add new status class
    browserStatus.classList.add(`status-${status.toLowerCase()}`);
    browserStatus.textContent = text || status.toUpperCase();
}

// Helper function to update stop button visibility
function updateStopButtonVisibility() {
    if (!stopTestBtn) return;

    if (isTestRunning || isBatchRunning) {
        stopTestBtn.style.display = 'flex';
        stopTestBtn.disabled = false;
        stopTestBtn.textContent = '';
        const _stopIcon1 = document.createElement('i');
        _stopIcon1.className = 'lni lni-hand-stop';
        stopTestBtn.appendChild(_stopIcon1);
        stopTestBtn.title = 'Stop Test';
    } else {
        stopTestBtn.style.display = 'none';
        stopTestBtn.disabled = false;
        stopTestBtn.textContent = '';
        const _stopIcon2 = document.createElement('i');
        _stopIcon2.className = 'lni lni-hand-stop';
        stopTestBtn.appendChild(_stopIcon2);
        stopTestBtn.title = 'Stop Test';
    }
}

// Socket.IO Event Handlers
socket.on('connect', () => {
    addLogEntry('info', 'Connected to server');
});

socket.on('connect_error', () => {
    console.warn('Socket connection failed - session may be expired');
});

// Reconnect socket after login so it picks up the new session
socket.on('disconnect', () => {
    console.warn('Socket disconnected');
});

socket.on('playwright_code', (data) => {
    // Display generated Playwright code with syntax highlighting
    setPlaywrightCode(data.code);
    addLogEntry('success', '💻 Playwright code generated!', '💻 Code generated');

    // Open as new tab
    const tempId = 'generated_' + Date.now();
    const name = 'Generated Test';
    openTab(tempId, name, data.code);
    const tab = openTabs.find(t => t.id === tempId);
    if (tab) {
        tab.isDirty = true;
        lastSavedCode = '';
    }
    renderTabs();
});

socket.on('log', (data) => {
    // Simplify certain log messages for human view
    let humanMsg = data.message;
    if (data.message.includes('Initializing browser')) {
        humanMsg = '🚀 Starting browser...';
    } else if (data.message.includes('Browser initialized')) {
        humanMsg = '✅ Browser ready';
    } else if (data.message.includes('Initializing AI model')) {
        humanMsg = '🤖 Loading AI agent...';
    } else if (data.message.includes('Starting test execution')) {
        humanMsg = '▶️ Test started';
    } else if (data.message.includes('Test completed successfully')) {
        humanMsg = '✅ Test finished';
    } else if (data.type === 'agent_action') {
        // For agent action logs, don't show the technical details
        if (data.message.includes("source='user'")) {
            humanMsg = '📝 Test instructions received';
        } else if (data.message.includes("source='web_tester'")) {
            humanMsg = '🤖 Agent is analyzing...';
        } else {
            humanMsg = '🤖 Agent is working...';
        }
    }
    addLogEntry(data.type, data.message, humanMsg);
});

socket.on('screenshot', (data) => {
    // Hide loading state
    if (browserLoading) {
        browserLoading.classList.remove('active');
    }

    if (data.recorder_id) {
        // Recording mode: show CDP stream in live viewer iframe (same container as test runs); clicks/keys relayed from iframe
        if (liveViewerIframe) {
            ensureLiveViewerLoaded();
            liveViewerIframe.style.display = 'block';
            liveViewerIframe.contentWindow?.postMessage({ type: 'screenshot', image: data.image, url: data.url || '', recording: true, title: data.title || '' }, '*');
        }
        if (browserScreenshot) browserScreenshot.style.display = 'none';
        // Update recorder URL bar
        if (recorderUrlInput && document.activeElement !== recorderUrlInput) {
            recorderUrlInput.value = data.url || '';
        }
    } else {
        // Test streaming mode: show the live viewer iframe and forward the frame via postMessage
        if (liveViewerIframe) {
            ensureLiveViewerLoaded();
            liveViewerIframe.style.display = 'block';
            liveViewerIframe.contentWindow?.postMessage({ type: 'screenshot', image: data.image, url: data.url || '' }, '*');
        }
        if (browserScreenshot) browserScreenshot.style.display = 'none';
    }


    // Only log action screenshots, not continuous stream frames
    if (data.action !== 'stream') {
        // Human-friendly action descriptions
        const humanActions = {
            'navigate': '🌐 Opened webpage',
            'click_text': '👆 Clicked button',
            'fill_form': '✍️ Filled form field'
        };
        const humanMessage = humanActions[data.action] || `📸 ${data.action}`;

        addLogEntry('info', `📸 Screenshot captured: ${data.action}`, humanMessage);
    }
});

socket.on('agent_message', (data) => {
    // Display agent's reasoning and actions
    const content = data.content;

    // Check for test status messages
    if (content.includes('TEST PASSED:')) {
        const statusMsg = content.match(/TEST PASSED:.*$/)?.[0] || content;
        addLogEntry('success', `✅ ${content}`, `✅ ${statusMsg}`);
        updateBrowserStatus('passed', 'PASSED');
    } else if (content.includes('TEST FAILED:')) {
        const statusMsg = content.match(/TEST FAILED:.*$/)?.[0] || content;
        addLogEntry('error', `❌ ${content}`, `❌ ${statusMsg}`);
        updateBrowserStatus('failed', 'FAILED');
    } else if (content.includes('TEST ERROR:')) {
        const statusMsg = content.match(/TEST ERROR:.*$/)?.[0] || content;
        addLogEntry('error', `⚠️ ${content}`, `⚠️ ${statusMsg}`);
        updateBrowserStatus('error', 'ERROR');
    } else {
        // Extract meaningful info for human-readable view
        let humanMsg = '🤖 Agent is working...';

        // Check for tool calls/results
        if (content.includes('FunctionCall')) {
            const toolMatch = content.match(/name='([^']+)'/);
            if (toolMatch) {
                const toolName = toolMatch[1];
                humanMsg = `🔧 Calling tool: ${toolName}`;

                // Extract arguments for better context
                if (toolName === 'fill_form') {
                    const argsMatch = content.match(/arguments='({[^}]+})'/);
                    if (argsMatch) {
                        try {
                            const args = JSON.parse(argsMatch[1].replace(/'/g, '"'));
                            humanMsg = `✍️ Filling "${args.selector}" with: "${args.value}"`;
                        } catch {
                            humanMsg = `✍️ Filling form: ${argsMatch[1]}`;
                        }
                    }
                } else if (toolName === 'navigate') {
                    const argsMatch = content.match(/arguments='({[^}]+})'/);
                    if (argsMatch) {
                        try {
                            const args = JSON.parse(argsMatch[1].replace(/'/g, '"'));
                            humanMsg = `🌐 Navigating to: ${args.url}`;
                        } catch {
                            humanMsg = `🌐 Navigating to page`;
                        }
                    }
                } else if (toolName === 'click_text') {
                    const argsMatch = content.match(/arguments='({[^}]+})'/);
                    if (argsMatch) {
                        try {
                            const args = JSON.parse(argsMatch[1].replace(/'/g, '"'));
                            humanMsg = `👆 Clicking button: "${args.text}"`;
                        } catch {
                            humanMsg = `👆 Clicking button`;
                        }
                    }
                } else if (toolName === 'find_inputs') {
                    humanMsg = `🔍 Finding form inputs on page`;
                } else if (toolName === 'get_page_content') {
                    humanMsg = `📄 Reading page content`;
                } else if (toolName === 'get_current_url') {
                    humanMsg = `🔗 Checking current URL`;
                }
            }
        } else if (content.includes('FunctionExecutionResult')) {
            const resultMatch = content.match(/content='([^']+)'/);
            if (resultMatch) {
                const result = resultMatch[1];
                // Show more of the result for debugging
                humanMsg = `📥 ${result.substring(0, 200)}${result.length > 200 ? '...' : ''}`;
            }
        } else if (content.includes("source='web_tester'")) {
            // Extract actual reasoning text
            const reasoningMatch = content.match(/content='([^']+)'/);
            if (reasoningMatch) {
                const reasoning = reasoningMatch[1];
                humanMsg = `💭 ${reasoning.substring(0, 250)}${reasoning.length > 250 ? '...' : ''}`;
            }
        }

        addLogEntry('agent_action', content, humanMsg);
    }
});

socket.on('test_complete', (data) => {
    isTestRunning = false;
    isStopRequested = false;
    updateStopButtonVisibility();

    // Always dismiss the loading screen — it may still be showing if no screenshot was sent
    if (browserLoading) browserLoading.classList.remove('active');
    liveViewerIframe?.contentWindow?.postMessage({ type: 'test_complete' }, '*');

    if (data.status === 'success') {
        updateBrowserStatus('passed', 'PASSED');
        addLogEntry('success', '✅ Test completed successfully!', '🎉 Test completed!');
    } else if (data.status === 'stopped') {
        updateBrowserStatus('stopped', 'STOPPED');
        addLogEntry('error', '⏹ Test stopped by user', '⏹ Test stopped');
    } else {
        updateBrowserStatus('failed', 'FAILED');
        const errorMsg = data.message || 'Unknown error';
        addLogEntry('error', `❌ Test failed: ${errorMsg}`, `❌ Test failed`);
    }

    // Restore AI step tab content if an AI step just finished
    if (runningAiStepTabId) {
        const aiTab = openTabs.find(t => t.id === runningAiStepTabId);
        if (aiTab && activeTabId === runningAiStepTabId) {
            // Reload fresh from DB to make sure we have the latest
            authFetch(`/api/ai-steps/${runningAiStepTabId}/markdown?workspaceName=${currentWorkspaceName}`)
                .then(res => res.json())
                .then(aiData => {
                    if (aiData.markdown) {
                        aiTab.code = aiData.markdown;
                        setPlaywrightCode(aiData.markdown);
                        lastSavedCode = aiData.markdown;
                    }
                })
                .catch(err => console.error('Error restoring AI step content:', err));
        }
        runningAiStepTabId = null;
    }

    if (currentRunningTestFilename) {
        authFetch(`/api/saved-tests/${currentRunningTestFilename}/status?workspaceName=${currentWorkspaceName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: data.status })
        }).catch(() => {}).finally(() => {
            if (hasFileExplorer) loadFileExplorer();
            currentRunningTestFilename = null;
        });
    }
});

socket.on('artifacts_updated', (data) => {
    console.log('Artifacts updated for:', data.filename);
    // Refresh file explorer to show video icon
    if (hasFileExplorer) {
        loadFileExplorer();
    }
});

socket.on('batch_test_progress', (data) => {
    const { filename, name, status } = data;
    runningTestsSet.delete(filename);

    // Update UI: remove spinner, set status border (no icon), remove batch-running-active so border shows passed/failed
    const fileItem = document.querySelector(`.file-item[data-filename="${filename}"]`);
    if (fileItem) {
        const spinner = fileItem.querySelector('.test-loading-spinner');
        if (spinner) spinner.remove();

        fileItem.classList.remove('batch-running-active');
        fileItem.classList.remove('file-item-status-passed', 'file-item-status-failed', 'file-item-status-unknown', 'file-item-status-running');
        fileItem.classList.add(status === 'success' ? 'file-item-status-passed' : 'file-item-status-failed');
    }

    // Store result
    batchRunResults.push({ filename, name, status });

    // Log progress
    const emoji = status === 'success' ? '✅' : '❌';
    addLogEntry(status === 'success' ? 'success' : 'error', `${emoji} ${name}: ${status}`);
});

socket.on('batch_run_complete', (data) => {
    const { total, passed, failed, duration } = data;

    // Reset state
    isBatchRunning = false;
    isStopRequested = false;
    runningTestsSet.clear();
    updateStopButtonVisibility();

    // Remove batch classes
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('batch-running', 'batch-running-active');
    });

    // Re-enable button
    const runAllBtn = document.getElementById('run-all-tests-btn');
    if (runAllBtn) {
        runAllBtn.disabled = false;
        runAllBtn.style.opacity = '1';
    }

    // Log summary
    addLogEntry('info', `📊 Batch complete: ${passed}/${total} passed in ${duration.toFixed(1)}s`);

    // Reload file explorer
    if (hasFileExplorer) loadFileExplorer();

    // Show modal
    showTestResultsModal(total, passed, failed, duration);
});

socket.on('ai_step_complete_with_code', (data) => {
    // AI step completed successfully - prompt user to save generated code
    isTestRunning = false;
    isStopRequested = false;
    updateStopButtonVisibility();
    if (browserLoading) browserLoading.classList.remove('active');
    updateBrowserStatus('passed', 'PASSED');
    addLogEntry('success', '✅ AI Step completed successfully!', '🎉 AI Step completed!');

    // Reload the AI step content to restore it (it may have been cleared during execution)
    const aiStepFilename = data.ai_step_filename;
    authFetch(`/api/ai-steps/${aiStepFilename}/markdown?workspaceName=${currentWorkspaceName}`)
        .then(res => res.json())
        .then(aiStepData => {
            // Find and restore the AI step tab if it's open
            const aiStepTab = openTabs.find(t => t.id === aiStepFilename);
            if (aiStepTab) {
                aiStepTab.code = aiStepData.markdown;
                aiStepTab.isDirty = false;
                // If it's the active tab, update the editor
                if (activeTabId === aiStepFilename) {
                    setPlaywrightCode(aiStepData.markdown);
                    lastSavedCode = aiStepData.markdown;
                }
            }

            // Show confirmation dialog
            const aiStepName = data.ai_step_name;
            const suggestedTestName = `${aiStepName} - Generated Test`;

            if (confirm(`✅ AI Step "${aiStepName}" completed successfully!\n\nWould you like to save the generated Playwright code as a new test?`)) {
                // User wants to save - prompt for test name
                const testName = prompt('Enter a name for the generated test:', suggestedTestName);

                if (testName && testName.trim()) {
                    // Save the generated code as a new test
                    const trimmedName = testName.trim();
                    const generatedFilename = trimmedName.replace(/\s+/g, '_') + '.py';
                    authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(generatedFilename)}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: trimmedName,
                            code: data.code,
                        })
                    })
                    .then(res => res.json())
                    .then(result => {
                        if (result.filename) {
                            addLogEntry('success', `💾 Saved generated test: ${trimmedName}`);
                            if (hasFileExplorer) loadFileExplorer();
                            openTab(result.filename, trimmedName, data.code, 'test');
                        } else {
                            alert('Error saving test: ' + (result.error || 'Unknown error'));
                        }
                    })
                    .catch(err => {
                        alert('Failed to save test: ' + err);
                    });
                }
            } else {
                // User declined - just show info message
                addLogEntry('info', 'Generated code not saved');
            }
        })
        .catch(err => {
            console.error('Error reloading AI step content:', err);
            addLogEntry('error', 'Failed to reload AI step content');
        });
});

socket.on('codegen_status', (data) => {
    if (data.status === 'recording') {
        currentRecordingId = data.recording_id;
        if (data.viewport) recorderViewport = data.viewport;

        browserStatus.textContent = 'Recording';
        browserStatus.classList.add('recording');
        browserStatus.style.background = 'var(--ctp-red)';
        addLogEntry('info', data.message, '🎥 Recording in progress...');

        const isBrowserMode = data.mode === 'browser';
        if (isBrowserMode) {
            // Real Playwright Chromium window: no in-app recorder UI
            addLogEntry('info', 'A Chromium window has opened. Interact with the page, then close the window when done.', '🖥️ Record in browser window');
            if (browserSidebar) browserSidebar.classList.add('active');
        } else {
            // Embedded recorder: show URL bar and click relay
            if (browserSidebar) browserSidebar.classList.add('active');
            if (stopRecordingBtn) stopRecordingBtn.style.display = 'inline-flex';
            if (recorderUrlBar) recorderUrlBar.style.display = 'flex';
            if (browserScreenshotContainer) browserScreenshotContainer.classList.add('recording-mode');
            if (recorderUrlInput && data.url) recorderUrlInput.value = data.url || '';
        }
    }
});

socket.on('codegen_complete', (data) => {
    currentRecordingId = null;
    browserStatus.textContent = 'Recording Complete';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = 'var(--ctp-green)';

    // Exit recording mode
    if (stopRecordingBtn) stopRecordingBtn.style.display = 'none';
    if (recorderUrlBar) recorderUrlBar.style.display = 'none';
    if (browserScreenshotContainer) browserScreenshotContainer.classList.remove('recording-mode');
    if (liveViewerIframe?.contentWindow) liveViewerIframe.contentWindow.postMessage({ type: 'recording_ended' }, '*');

    if (pendingCodegenTabId) {
        const tab = openTabs.find(t => t.id === pendingCodegenTabId);
        if (tab) {
            tab.code = data.code;
            tab.isDirty = true;
            switchToTab(pendingCodegenTabId);
        }
        pendingCodegenTabId = null;
    } else {
        setPlaywrightCode(data.code);
        pendingCodegenTest = { name: data.name, source: 'codegen' };
    }

    addLogEntry('success', '✅ Recording complete! Code generated.', '✅ Recording complete!');

    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        editorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
});

socket.on('codegen_error', (data) => {
    currentRecordingId = null;
    pendingCodegenTabId = null;
    browserStatus.textContent = 'Recording Error';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = 'var(--ctp-surface2)';

    if (stopRecordingBtn) stopRecordingBtn.style.display = 'none';
    if (recorderUrlBar) recorderUrlBar.style.display = 'none';
    if (browserScreenshotContainer) browserScreenshotContainer.classList.remove('recording-mode');
    if (liveViewerIframe?.contentWindow) liveViewerIframe.contentWindow.postMessage({ type: 'recording_ended' }, '*');

    addLogEntry('error', `❌ Recording failed: ${data.message}`, '❌ Recording failed');
});

// UI Event Handlers
// Record, Run Test, Load Example, and Refresh buttons removed - use AI Steps section and file explorer instead

// Run Test and Stop Test buttons removed - use AI Steps section instead

// Load Example button removed - use AI Steps section instead

clearLogBtn.addEventListener('click', () => {
    humanLogContainer.replaceChildren();
    technicalLogContainer.replaceChildren();
    addLogEntry('info', 'Log cleared');
});

const copyLogBtn = document.getElementById('copy-log');
copyLogBtn.addEventListener('click', () => {
    const activeContainer = humanLogContainer.classList.contains('active')
        ? humanLogContainer
        : technicalLogContainer;
    const lines = [...activeContainer.querySelectorAll('.log-entry')].map(entry => {
        const ts = entry.querySelector('.timestamp')?.textContent?.trim() || '';
        const msg = entry.querySelector('.message')?.textContent?.trim() || '';
        return ts ? `[${ts}] ${msg}` : msg;
    });
    navigator.clipboard.writeText(lines.join('\n')).then(() => {
        const orig = copyLogBtn.innerHTML;
        copyLogBtn.textContent = '';
        const _checkIcon = document.createElement('i');
        _checkIcon.className = 'lni lni-check';
        copyLogBtn.appendChild(_checkIcon);
        setTimeout(() => { copyLogBtn.innerHTML = orig; }, 1500);
    });
});

// Stop test button handler
if (stopTestBtn) {
    stopTestBtn.addEventListener('click', () => {
        if (isStopRequested) {
            return; // Prevent double-click
        }

        // Confirm stop action
        if (!confirm('Are you sure you want to stop the running test?')) {
            return;
        }

        isStopRequested = true;
        stopTestBtn.disabled = true;
        stopTestBtn.textContent = 'STOPPING...';
        stopTestBtn.title = 'Stopping test...';

        // Emit stop event to backend
        socket.emit('stop_test');
        addLogEntry('info', '⏹ Stop request sent to server');
    });
}

// Save current test - used by Cmd+S keyboard shortcut and context menu
function saveCurrentTest() {
    const code = getPlaywrightCode();
    if (!code) {
        alert('No code to save!');
        return;
    }

    // Check if we're editing an existing tab
    // Temporary tabs start with: 'new_', 'generated_', or 'chat_'
    if (activeTabId && !activeTabId.startsWith('new_') && !activeTabId.startsWith('generated_') && !activeTabId.startsWith('chat_')) {
        // Updating existing saved test
        const tab = openTabs.find(t => t.id === activeTabId);
        if (!tab) return;

        if (tab.fileType === 'ai-step') {
            const path = encodeURIComponent(activeTabId);
            authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${path}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: tab.name, steps: code })
            })
            .then(res => res.json())
            .then(data => {
                if (data.path || data.filename) {
                    addLogEntry('success', `Saved: ${tab.name}`);
                    tab.isDirty = false;
                    tab.code = code;
                    lastSavedCode = code;
                    renderTabs();
                    loadAiSteps();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(err => alert('Error saving: ' + err));
            return;
        }

        const path = encodeURIComponent(activeTabId);
        authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${path}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: tab.name, code })
        })
        .then(res => res.json())
        .then(data => {
            if (data.path || data.filename || data.success) {
                tab.isDirty = false;
                tab.code = code;
                lastSavedCode = code;
                renderTabs();
                addLogEntry('success', `Saved: ${tab.name}`);
            } else {
                alert('Error: ' + (data.error || 'Unknown'));
            }
        })
        .catch(err => alert('Failed to save: ' + err));
    } else {
        // Saving as new test
        let defaultName = '';
        if (activeTabId) {
            const tab = openTabs.find(t => t.id === activeTabId);
            if (tab) defaultName = tab.name;
        }

        const name = prompt('Save as:', defaultName);
        if (!name) return;

        authFetch('/api/save-test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, code, source: 'ai' })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                addLogEntry('success', `💾 Saved: ${name}`);

                // Close old tab if it was a temporary tab (new, generated, or chat)
                if (activeTabId && (activeTabId.startsWith('new_') || activeTabId.startsWith('generated_') || activeTabId.startsWith('chat_'))) {
                    const oldTabIndex = openTabs.findIndex(t => t.id === activeTabId);
                    if (oldTabIndex !== -1) {
                        openTabs.splice(oldTabIndex, 1);
                    }
                }

                // Reload file explorer
                loadFileExplorer();

                // Open as new tab
                openTab(data.filename, name, code);
                lastSavedCode = code;
            } else {
                alert('Error saving: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(err => {
            alert('Failed to save: ' + err);
        });
    }
}

// Refresh and load saved tests functions removed - file explorer handles this now

function runSavedTest(filename, name) {
    if (isBatchRunning) {
        alert('Batch test execution in progress. Please wait for it to finish.');
        return;
    }

    if (isTestRunning) {
        alert('A test is already running. Please wait for it to finish.');
        return;
    }

    // Track the running test for status update
    currentRunningTestFilename = filename;

    // Reload file explorer to show stop button
    if (hasFileExplorer) {
        loadFileExplorer();
    }

    // Clear previous results
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';

    addLogEntry('info', `🚀 Running: ${name} (no AI tokens used!)`, `🚀 Running: ${name}`);
    isTestRunning = true;
    isStopRequested = false;

    // Update browser header with test name and status
    if (browserTestName) {
        browserTestName.textContent = name;
    }
    updateBrowserStatus('running', 'RUNNING');
    updateStopButtonVisibility();

    // Show loading state in browser preview
    if (browserLoading) {
        browserLoading.classList.add('active');
        browserLoading.querySelector('.loading-text').textContent = 'Starting browser...';
        browserLoading.querySelector('.loading-subtext').textContent = 'Initializing Playwright session';
    }
    if (liveViewerIframe) {
        liveViewerIframe.style.display = 'none';
        liveViewerIframe.contentWindow?.postMessage({ type: 'test_reset' }, '*');
    }

    // Automatically open browser sidebar
    if (!browserSidebar.classList.contains('open')) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.add('open');
        codeEditorContainer.classList.add('browser-open');
        if (toggleBrowserBtn) {
            toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
            toggleBrowserBtn.classList.add('active');
        }
    }

    socket.emit('run_saved_test', {
        filename,
        workspaceName: currentWorkspaceName
    });
}

function collectTreeFilePaths(nodes) {
    const paths = [];
    nodes.forEach(n => {
        if (n.type === 'file' && n.path) paths.push(n.path);
        if (n.children) paths.push(...collectTreeFilePaths(n.children));
    });
    return paths;
}

async function runAllTests() {
    if (isBatchRunning || isTestRunning) {
        alert('A test is already running.');
        return;
    }

    const treeRes = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests`);
    const treeData = await treeRes.json();
    const filePaths = collectTreeFilePaths(treeData.tree || []);

    if (filePaths.length === 0) {
        alert('No tests available to run.');
        return;
    }

    // Initialize batch state
    isBatchRunning = true;
    isStopRequested = false;
    batchRunStartTime = Date.now();
    batchRunResults = [];
    runningTestsSet.clear();

    // Clear logs
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';
    addLogEntry('info', `🚀 Running ${filePaths.length} tests in parallel...`);

    // Show stop button
    updateStopButtonVisibility();

    document.querySelectorAll('.file-item:not(.file-item--folder)').forEach(item => {
        item.classList.add('batch-running');
    });

    const runAllBtn = document.getElementById('run-all-tests-btn');
    if (runAllBtn) {
        runAllBtn.disabled = true;
        runAllBtn.style.opacity = '0.5';
    }

    filePaths.forEach(path => {
        runningTestsSet.add(path);
        const fileItem = document.querySelector(`.file-item[data-filename="${path}"]`);
        if (fileItem) {
            fileItem.classList.remove('file-item-status-passed', 'file-item-status-failed', 'file-item-status-unknown', 'file-item-status-running');
            fileItem.classList.add('batch-running-active');

            const spinner = document.createElement('span');
            spinner.className = 'test-loading-spinner';
            spinner.dataset.filename = path;
            const actions = fileItem.querySelector('.file-item-actions');
            if (actions) fileItem.insertBefore(spinner, actions);
        }
    });

    socket.emit('run_all_tests', {
        filenames: filePaths,
        workspaceName: currentWorkspaceName
    });
}

// Tab Management Functions
function openTab(filename, name, code, fileType = 'test', meta = null) {
    // Check if tab is already open
    const existingTab = openTabs.find(tab => tab.id === filename);
    if (existingTab) {
        switchToTab(filename);
        return;
    }

    // Add new tab
    openTabs.push({
        id: filename,
        name: name,
        code: code,
        isDirty: false,
        fileType: fileType,  // 'test', 'ai-step', 'recording', or 'trace'
        meta: meta           // { videoUrl, info } for recording; { viewerUrl } for trace
    });

    // Hide welcome page before switching to tab
    hideWelcomePage();

    renderTabs();
    switchToTab(filename);
    saveTabsState();  // Save state when opening a new tab
}

function closeTab(filename) {
    const tabIndex = openTabs.findIndex(tab => tab.id === filename);
    if (tabIndex === -1) return;

    const tab = openTabs[tabIndex];

    // Check if dirty (unsaved changes) — skip for media tabs
    if (tab.isDirty && tab.fileType !== 'recording' && tab.fileType !== 'trace') {
        if (!confirm(`Close ${tab.name}?\nYou have unsaved changes.`)) {
            return;
        }
    }

    // Clear media resources when closing media tabs to stop playback
    if (tab.fileType === 'recording') {
        const vid = document.getElementById('media-panel-video');
        if (vid) { vid.pause(); vid.src = ''; }
    } else if (tab.fileType === 'trace') {
        const iframeEl = document.getElementById('media-panel-trace-iframe');
        if (iframeEl) iframeEl.src = '';
    }

    // Remove tab
    openTabs.splice(tabIndex, 1);

    // Switch to another tab if this was active
    if (activeTabId === filename) {
        if (openTabs.length > 0) {
            // Switch to previous tab or first tab
            const newActiveTab = openTabs[Math.max(0, tabIndex - 1)];
            switchToTab(newActiveTab.id);
        } else {
            activeTabId = null;
            setPlaywrightCode('');
            if (editorContent) editorContent.classList.add('empty');
            // Hide dashboard and media panel
            hideDashboardContent();
            const mediaPanel = document.getElementById('media-panel');
            if (mediaPanel) mediaPanel.style.display = 'none';
        }
    }

    renderTabs();
    saveTabsState();  // Save state when closing a tab
}

function switchToTab(filename) {
    const tab = openTabs.find(t => t.id === filename);
    if (!tab) return;

    activeTabId = filename;

    const mediaPanel = document.getElementById('media-panel');
    const mediaPanelRecording = document.getElementById('media-panel-recording');
    const mediaPanelTrace = document.getElementById('media-panel-trace');

    if (tab.fileType === 'dashboard') {
        if (mediaPanel) mediaPanel.style.display = 'none';
        showDashboardContent();
    } else if (tab.fileType === 'recording') {
        hideDashboardContent();
        if (codemirrorEditor) codemirrorEditor.style.display = 'none';
        if (mediaPanel) mediaPanel.style.display = 'flex';
        if (mediaPanelRecording) mediaPanelRecording.style.display = 'flex';
        if (mediaPanelTrace) mediaPanelTrace.style.display = 'none';
        const vid = document.getElementById('media-panel-video');
        if (vid) {
            vid.src = tab.meta?.videoUrl || '';
            vid.oncanplay = () => { vid.play().catch(() => {}); };
        }
        const infoEl = document.getElementById('media-panel-video-info');
        if (infoEl) infoEl.textContent = tab.meta?.info || '';
        if (editorContent) editorContent.classList.remove('empty');
    } else if (tab.fileType === 'trace') {
        hideDashboardContent();
        if (codemirrorEditor) codemirrorEditor.style.display = 'none';
        if (mediaPanel) mediaPanel.style.display = 'block';
        if (mediaPanelRecording) mediaPanelRecording.style.display = 'none';
        if (mediaPanelTrace) mediaPanelTrace.style.display = 'block';
        const iframeEl = document.getElementById('media-panel-trace-iframe');
        if (iframeEl) iframeEl.src = tab.meta?.viewerUrl || '';
        if (editorContent) editorContent.classList.remove('empty');
    } else {
        // Hide media panel when switching to code/ai-step/dashboard tabs
        if (mediaPanel) mediaPanel.style.display = 'none';
        // Hide dashboard content if switching away from it
        hideDashboardContent();

        lastSavedCode = tab.code;  // Set lastSavedCode to prevent false dirty flag
        setPlaywrightCode(tab.code);

        // Set CodeMirror mode based on file type
        // AI Steps use markdown, Tests use Python
        if (codeMirrorEditor) {
            const mode = tab.fileType === 'ai-step' ? 'markdown' : 'python';
            codeMirrorEditor.setOption('mode', mode);
        }

        if (editorContent) editorContent.classList.remove('empty');
    }

    hideWelcomePage();
    renderTabs();
    updateFileListActiveState();
    saveTabsState();  // Save state when switching tabs
}

// Tab State Persistence Functions
function saveTabsState() {
    try {
        const tabsState = {
            // Filter out temporary tabs (new_, generated_, chat_) but KEEP dashboard
            openTabs: openTabs
                .filter(tab => {
                    // Exclude temporary and media tabs
                    if (tab.id.startsWith('new_')) return false;
                    if (tab.id.startsWith('generated_')) return false;
                    if (tab.id.startsWith('chat_')) return false;
                    if (tab.id.startsWith('__recording__:')) return false;
                    if (tab.id.startsWith('__trace__:')) return false;
                    return true;
                })
                .map(tab => ({
                    id: tab.id,
                    name: tab.name,
                    fileType: tab.fileType  // Save file type (including 'dashboard')
                    // Don't save code or isDirty, we'll reload fresh from files
                })),
            activeTabId: activeTabId  // Keep dashboard as activeTabId if it was active
        };
        const json = JSON.stringify(tabsState);
        localStorage.setItem('editorTabsState', json);
        savePreferenceToDb('editorTabsState', json);
    } catch (err) {
        console.error('Error saving tabs state:', err);
    }
}

async function restoreTabsState() {
    try {
        let savedState = localStorage.getItem('editorTabsState');

        // Fall back to DB if localStorage is empty
        if (!savedState) {
            const dbPrefs = await loadPreferencesFromDb();
            if (dbPrefs && dbPrefs.editorTabsState) {
                savedState = dbPrefs.editorTabsState;
                localStorage.setItem('editorTabsState', savedState);
            }
        }

        if (!savedState) return;

        const tabsState = JSON.parse(savedState);
        if (!tabsState.openTabs || tabsState.openTabs.length === 0) return;

        const tabsToRestore = tabsState.openTabs.filter(tabInfo =>
            !tabInfo.id.startsWith('new_') &&
            !tabInfo.id.startsWith('generated_') &&
            !tabInfo.id.startsWith('chat_')
        );

        const fetchPromises = tabsToRestore
            .filter(tabInfo => tabInfo.fileType === 'ai-step' || tabInfo.fileType === 'test')
            .map(async (tabInfo) => {
                try {
                    if (tabInfo.fileType === 'ai-step') {
                        let res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${encodeURIComponent(tabInfo.id)}`);
                        if (res.ok) {
                            const data = await res.json();
                            return { tabInfo, type: 'ai-step', data: { markdown: data.steps } };
                        }
                        res = await authFetch(`/api/ai-steps/${tabInfo.id}/markdown?workspaceName=${currentWorkspaceName}`);
                        if (res.ok) {
                            const data = await res.json();
                            return { tabInfo, type: 'ai-step', data };
                        }
                    } else {
                        let res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(tabInfo.id)}`);
                        if (res.ok) {
                            const data = await res.json();
                            return { tabInfo, type: 'test', data };
                        }
                        res = await authFetch(`/api/saved-tests/${tabInfo.id}?workspaceName=${currentWorkspaceName}`);
                        if (res.ok) {
                            const data = await res.json();
                            return { tabInfo, type: 'test', data };
                        }
                    }
                } catch (err) {
                    console.error(`Error restoring tab ${tabInfo.id}:`, err);
                }
                return null;
            });

        const fetchResults = await Promise.all(fetchPromises);
        const resultById = new Map();
        fetchResults.forEach(r => { if (r) resultById.set(r.tabInfo.id, r); });

        // Restore tabs in original order
        for (const tabInfo of tabsToRestore) {
            if (tabInfo.fileType === 'dashboard') {
                if (!openTabs.find(t => t.id === '__dashboard__')) {
                    openTabs.push({
                        id: '__dashboard__',
                        name: 'Dashboard',
                        code: '',
                        isDirty: false,
                        fileType: 'dashboard'
                    });
                }
            } else {
                const result = resultById.get(tabInfo.id);
                if (!result || openTabs.find(t => t.id === tabInfo.id)) continue;
                if (result.type === 'ai-step') {
                    openTabs.push({
                        id: tabInfo.id,
                        name: tabInfo.name,
                        code: result.data.markdown,
                        isDirty: false,
                        fileType: 'ai-step'
                    });
                } else {
                    openTabs.push({
                        id: tabInfo.id,
                        name: tabInfo.name,
                        code: result.data.code,
                        isDirty: false,
                        fileType: 'test'
                    });
                }
            }
        }

        // Render all tabs
        if (openTabs.length > 0) {
            hideWelcomePage();
            renderTabs();

            // Switch to the previously active tab
            const activeTab = tabsState.activeTabId && openTabs.find(t => t.id === tabsState.activeTabId);
            if (activeTab) {
                switchToTab(tabsState.activeTabId);
            } else {
                // If active tab no longer exists, switch to first tab
                switchToTab(openTabs[0].id);
            }
        }
    } catch (err) {
        console.error('Error restoring tabs state:', err);
    }
}

// Welcome Page Functions
async function showWelcomePage() {
    if (!codeMirrorEditor) return;

    // Fetch statistics
    const stats = await fetchTestStatistics();

    // Create welcome page HTML
    const welcomeHTML = `
        <div class="welcome-page">
            <div class="welcome-header">
                <h1><i class="lni lni-android"></i> AutoGen Web Tester</h1>
                <p class="welcome-subtitle">AI-powered browser automation and testing</p>
            </div>

            <div class="welcome-stats">
                <div class="stat-card">
                    <div class="stat-icon"><i class="lni lni-pencil-1"></i></div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.totalTests}</div>
                        <div class="stat-label">Saved Tests</div>
                    </div>
                </div>

                <div class="stat-card stat-success">
                    <div class="stat-icon"><i class="lni lni-check"></i></div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.passedTests}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                </div>

                <div class="stat-card stat-error">
                    <div class="stat-icon"><i class="lni lni-xmark-circle"></i></div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.failedTests}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon"><i class="lni lni-android"></i></div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.aiSteps}</div>
                        <div class="stat-label">AI Steps</div>
                    </div>
                </div>
            </div>

            <div class="welcome-actions">
                <h3>Get Started</h3>
                <div class="action-buttons">
                    <button class="action-btn" onclick="document.getElementById('new-test-btn').click()">
                        <span class="action-icon"><i class="lni lni-file-plus-circle"></i></span>
                        <div>
                            <div class="action-title">New Test</div>
                            <div class="action-desc">Create a new Playwright test</div>
                        </div>
                    </button>
                    <button class="action-btn" onclick="document.getElementById('new-ai-step-btn').click()">
                        <span class="action-icon"><i class="lni lni-file-plus-circle"></i></span>
                        <div>
                            <div class="action-title">New AI Step</div>
                            <div class="action-desc">Write tests in natural language</div>
                        </div>
                    </button>
                </div>
            </div>
        </div>
    `;

    // Hide CodeMirror and show welcome page
    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        const cmWrapper = editorElement.querySelector('.CodeMirror');
        if (cmWrapper) cmWrapper.style.display = 'none';

        // Remove existing welcome page if any
        const existingWelcome = editorElement.querySelector('.welcome-page');
        if (existingWelcome) existingWelcome.remove();

        // Insert welcome page
        editorElement.insertAdjacentHTML('beforeend', welcomeHTML);
    }
}

function hideWelcomePage() {
    if (!codeMirrorEditor) return;

    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        const cmWrapper = editorElement.querySelector('.CodeMirror');
        if (cmWrapper) cmWrapper.style.display = '';

        const welcomePage = editorElement.querySelector('.welcome-page');
        if (welcomePage) welcomePage.remove();
    }
}

async function fetchTestStatistics() {
    // Stats are loaded from tree data in loadDashboardStats; this function is a no-op stub.
    return { totalTests: 0, passedTests: 0, failedTests: 0, aiSteps: 0 };
}

function updateFormatBtnVisibility() {
    if (!formatCodeBtn) return;
    const activeTab = openTabs.find(t => t.id === activeTabId);
    const hasFile = activeTab && !['dashboard', 'recording', 'trace'].includes(activeTab.fileType);
    formatCodeBtn.style.display = hasFile ? '' : 'none';
}

function renderTabs() {
    if (!editorTabsContainer) return;

    editorTabsContainer.innerHTML = '';

    updateFormatBtnVisibility();

    // Show welcome page if no tabs are open
    if (openTabs.length === 0) {
        showWelcomePage();
        return;
    }

    openTabs.forEach(tab => {
        const tabEl = document.createElement('div');
        tabEl.className = 'editor-tab' + (tab.id === activeTabId ? ' active' : '') + (tab.isDirty ? ' dirty' : '');
        tabEl.dataset.fileType = tab.fileType || 'test';

        const icon = tab.fileType === 'dashboard'
            ? '<i class="lni lni-bar-chart-4 tab-icon-colored"></i>'
            : tab.fileType === 'ai-step' ? '<i class="lni lni-pencil-1"></i>'
            : tab.fileType === 'recording' ? '<i class="lni lni-camera-movie-1"></i>'
            : tab.fileType === 'trace' ? '<i class="lni lni-layers-1"></i>'
            : '<i class="lni lni-python"></i>';
        const iconHtml = `<span class="editor-tab-icon">${icon}</span>`;

        const displayName = getDisplayName(tab.name, tab.fileType);
        let nameHtml;
        if (tab.fileType === 'recording' && displayName.endsWith(' — Recording')) {
            const testNamePart = displayName.slice(0, -(' — Recording').length);
            nameHtml = `<span class="editor-tab-name">${escapeHtml(testNamePart)}</span><span class="editor-tab-suffix"> — Recording</span>`;
        } else if (tab.fileType === 'trace' && displayName.endsWith(' — Trace')) {
            const testNamePart = displayName.slice(0, -(' — Trace').length);
            nameHtml = `<span class="editor-tab-name">${escapeHtml(testNamePart)}</span><span class="editor-tab-suffix"> — Trace</span>`;
        } else {
            nameHtml = `<span class="editor-tab-name">${escapeHtml(displayName)}</span>`;
        }
        tabEl.innerHTML = `
            ${iconHtml}
            ${nameHtml}
            <button class="editor-tab-close" data-tab-id="${tab.id}">×</button>
        `;

        // Click tab to switch
        tabEl.addEventListener('click', (e) => {
            if (!e.target.classList.contains('editor-tab-close')) {
                switchToTab(tab.id);
            }
        });

        // Close button
        const closeBtn = tabEl.querySelector('.editor-tab-close');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeTab(tab.id);
        });

        editorTabsContainer.appendChild(tabEl);
    });
}

function updateFileListActiveState() {
    document.querySelectorAll('.file-item').forEach(item => {
        const filename = item.dataset.filename;
        if (filename === activeTabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Highlight active child item (recording/trace tab)
    document.querySelectorAll('.file-tree-child').forEach(item => {
        const action = item.dataset.childAction;
        const filename = item.dataset.filename;
        const tabId = action === 'recording' ? `__recording__:${filename}` : `__trace__:${filename}`;
        if (tabId === activeTabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Also highlight active AI step in sidebar
    if (aiStepsList) {
        const aiStepItems = aiStepsList.querySelectorAll('.file-item');
        aiStepItems.forEach(item => {
            const filename = item.dataset.filename;
            if (filename === activeTabId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }
}

// Root drop zones for "move to root" (attach once to list containers)
function setupTreeRootDropZones() {
    if (fileList && !fileList.dataset.dropZoneSetup) {
        fileList.dataset.dropZoneSetup = '1';
        fileList.addEventListener('dragover', (e) => {
            if (!e.dataTransfer.types.includes('application/json')) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });
        fileList.addEventListener('drop', (e) => {
            e.preventDefault();
            if (e.target.closest('.file-item--folder')) return;
            let data;
            try { data = JSON.parse(e.dataTransfer.getData('application/json') || '{}'); } catch (_) { return; }
            if (data.treeType !== 'saved_tests' || !data.path) return;
            const fromPath = data.path;
            const toPath = fromPath.split('/').pop();
            if (toPath === fromPath) return;
            moveTreeItem(currentWorkspaceName, 'saved_tests', fromPath, toPath).catch(err => alert(err.message || err));
        });
    }
    if (aiStepsList && !aiStepsList.dataset.dropZoneSetup) {
        aiStepsList.dataset.dropZoneSetup = '1';
        aiStepsList.addEventListener('dragover', (e) => {
            if (!e.dataTransfer.types.includes('application/json')) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });
        aiStepsList.addEventListener('drop', (e) => {
            e.preventDefault();
            if (e.target.closest('.file-item--folder')) return;
            let data;
            try { data = JSON.parse(e.dataTransfer.getData('application/json') || '{}'); } catch (_) { return; }
            if (data.treeType !== 'ai_steps' || !data.path) return;
            const fromPath = data.path;
            const toPath = fromPath.split('/').pop();
            if (toPath === fromPath) return;
            moveTreeItem(currentWorkspaceName, 'ai_steps', fromPath, toPath).catch(err => alert(err.message || err));
        });
    }
}

// Drag-and-drop: move tree item (file or folder) via API, then reload tree and fix open tab id
async function moveTreeItem(workspaceName, treeType, fromPath, toPath) {
    const res = await authFetch(`/api/workspaces/${workspaceName}/tree/${treeType}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: fromPath, to: toPath })
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || res.statusText);
    }
    if (treeType === 'saved_tests') loadFileExplorer();
    else loadAiSteps();
    // If the moved path is the active tab, update tab id to new path so save goes to new location
    if (activeTabId === fromPath) {
        const tab = openTabs.find(t => t.id === fromPath);
        if (tab) {
            tab.id = toPath;
            if (activeTabId === fromPath) activeTabId = toPath;
            renderEditorTabs();
        }
    }
}

// File Explorer Functions (tree: Saved Tests from ~/.autogen)
function loadFileExplorer() {
    if (!hasFileExplorer || !fileList) {
        console.warn('File explorer elements not found, skipping load');
        return;
    }
    setupTreeRootDropZones();

    if (!currentWorkspaceName) {
        fileList.innerHTML = '<div class="file-list-empty">Select a workspace</div>';
        return;
    }

    fileList.innerHTML = '<div class="file-list-loading"><span class="file-list-spinner"></span>Loading tests…</div>';

    authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests`)
        .then(res => res.json())
        .then(data => {
            const children = data.tree || [];
            testCache = {};
            fileList.innerHTML = '';

            if (children.length === 0) {
                fileList.innerHTML = '<div class="file-list-empty">No saved tests. Add a folder or new test.</div>';
                updateFileListActiveState();
                return;
            }

            renderSavedTestsTree(children, fileList, 0, '');
            updateFileListActiveState();
        })
        .catch(err => {
            console.error('Failed to load file explorer:', err);
            fileList.innerHTML = '<div class="file-list-empty">Error loading tests</div>';
        });
}

function renderSavedTestsTree(nodes, container, depth, parentPath) {
    nodes.forEach(node => {
        if (node.type === 'folder') {
            const nodeEl = document.createElement('div');
            nodeEl.className = 'file-tree-node file-tree-node--folder';
            nodeEl.dataset.path = node.path;
            nodeEl.dataset.type = 'folder';
            const hasChildren = (node.children && node.children.length > 0);
            const expandArrow = '<span class="file-tree-expand"><i class="lni lni-chevron-down"></i></span>';
            const row = document.createElement('div');
            row.className = 'file-item file-item--folder';
            row.style.paddingLeft = (10 + depth * 10) + 'px';
            row.innerHTML = `
                ${expandArrow}
                <span class="file-item-icon file-item-icon--folder"><i class="lni lni-folder"></i></span>
                <span class="file-item-name">${escapeHtml(node.name)}</span>
            `;
            const childrenEl = document.createElement('div');
            childrenEl.className = 'file-tree-children';
            if (hasChildren) {
                renderSavedTestsTree(node.children, childrenEl, depth + 1, node.path);
            }
            row.addEventListener('click', (e) => {
                if (e.target.closest('.file-tree-expand')) {
                    nodeEl.classList.toggle('expanded');
                } else if (!e.target.closest('.file-item-actions')) {
                    nodeEl.classList.toggle('expanded');
                }
            });
            row.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e.clientX, e.clientY, { path: node.path, name: node.name, type: 'folder', treeType: 'saved_tests' });
            });
            row.draggable = true;
            row.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({ path: node.path, type: 'folder', treeType: 'saved_tests' }));
                e.dataTransfer.effectAllowed = 'move';
            });
            row.addEventListener('dragover', (e) => {
                if (!e.dataTransfer.types.includes('application/json')) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                row.classList.add('file-tree-drop-target');
            });
            row.addEventListener('dragleave', () => row.classList.remove('file-tree-drop-target'));
            row.addEventListener('drop', (e) => {
                e.preventDefault();
                row.classList.remove('file-tree-drop-target');
                let data;
                try { data = JSON.parse(e.dataTransfer.getData('application/json') || '{}'); } catch (_) { return; }
                if (data.treeType !== 'saved_tests' || !data.path) return;
                const fromPath = data.path;
                const basename = fromPath.split('/').pop();
                const toPath = node.path ? node.path + '/' + basename : basename;
                if (toPath === fromPath || (data.type === 'folder' && (toPath === fromPath || toPath.startsWith(fromPath + '/')))) return;
                moveTreeItem(currentWorkspaceName, 'saved_tests', fromPath, toPath).catch(err => alert(err.message || err));
            });
            nodeEl.appendChild(row);
            nodeEl.appendChild(childrenEl);
            container.appendChild(nodeEl);
            return;
        }

        // file node
        const path = node.path;
        const name = node.display_name || node.name || path.replace(/\.py$/, '').replace(/_/g, ' ');
        testCache[path] = { path, filename: path, name, artifacts: node.artifacts || [], last_run_status: node.last_run_status };

        const hasRecording = (node.artifacts || []).some(a => a.video_path && a.video_path !== 'null');
        const hasTrace = (node.artifacts || []).some(a => a.trace_path);
        const hasChildren = hasRecording || hasTrace;

        const nodeEl = document.createElement('div');
        nodeEl.className = 'file-tree-node';
        nodeEl.dataset.path = path;
        nodeEl.dataset.type = 'file';

        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.dataset.filename = path;
        fileItem.dataset.path = path;

        if (currentRunningTestFilename === path) fileItem.classList.add('file-item-status-running');
        else if (node.last_run_status === 'success') fileItem.classList.add('file-item-status-passed');
        else if (node.last_run_status === 'error' || node.last_run_status === 'stopped') fileItem.classList.add('file-item-status-failed');
        else fileItem.classList.add('file-item-status-unknown');

        const expandArrow = hasChildren
            ? '<span class="file-tree-expand"><i class="lni lni-chevron-down"></i></span>'
            : '<span class="file-tree-expand" style="visibility:hidden;"><i class="lni lni-chevron-down"></i></span>';

        let runOrStopBtn = currentRunningTestFilename === path
            ? `<button class="file-item-action" data-action="stop" title="Stop Test" style="color: var(--ctp-red);"><i class="lni lni-hand-stop"></i></button>`
            : `<button class="file-item-action file-item-action--run" data-action="run" title="Run Test"><i class="lni lni-play"></i></button>`;

        const itemPadding = (10 + depth * 10);
        fileItem.style.paddingLeft = itemPadding + 'px';
        fileItem.innerHTML = `
            ${expandArrow}
            <span class="file-item-icon"><i class="lni lni-python"></i></span>
            <span class="file-item-name">${escapeHtml(name)}</span>
            <div class="file-item-actions">${runOrStopBtn}</div>
        `;

        // Append git status badge via DOM (avoids XSS concerns with innerHTML)
        if (node.git_status) {
            const nameEl = fileItem.querySelector('.file-item-name');
            if (nameEl) {
                const badge = document.createElement('span');
                badge.className = `git-status-badge ${node.git_status}`;
                badge.textContent = node.git_status;
                nameEl.appendChild(badge);
            }
        }

        // Artifact container: JS-toggled, each child gets explicit depth-based padding
        const childrenEl = document.createElement('div');
        childrenEl.className = 'file-tree-artifacts';
        childrenEl.style.display = 'none';
        const artifactPadding = (itemPadding + 22) + 'px';
        if (hasRecording) {
            const c = document.createElement('div');
            c.className = 'file-tree-child';
            c.style.paddingLeft = artifactPadding;
            c.dataset.filename = path;
            c.innerHTML = '<i class="lni lni-camera-movie-1"></i> Recording';
            c.addEventListener('click', (e) => { e.stopPropagation(); openRecordingTab(path, name); });
            childrenEl.appendChild(c);
        }
        if (hasTrace) {
            const c = document.createElement('div');
            c.className = 'file-tree-child';
            c.style.paddingLeft = artifactPadding;
            c.dataset.filename = path;
            c.innerHTML = '<i class="lni lni-layers-1"></i> Trace';
            c.addEventListener('click', (e) => { e.stopPropagation(); openTraceTab(path, name); });
            childrenEl.appendChild(c);
        }

        fileItem.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]')?.dataset.action;
            if (action === 'run') {
                e.stopPropagation();
                runSavedTest(path, name);
            } else if (action === 'stop') {
                e.stopPropagation();
                if (isStopRequested) return;
                if (confirm('Stop the running test?')) {
                    isStopRequested = true;
                    socket.emit('stop_test');
                    addLogEntry('info', '⏹ Stop request sent');
                    if (stopTestBtn) { stopTestBtn.disabled = true; stopTestBtn.textContent = 'STOPPING...'; }
                }
            } else if (e.target.closest('.file-tree-expand') && hasChildren) {
                const expanded = nodeEl.classList.toggle('expanded');
                childrenEl.style.display = expanded ? 'block' : 'none';
            } else if (!e.target.closest('.file-item-actions') && !e.target.closest('.file-tree-expand')) {
                openFileFromExplorer(path, name);
            }
        });
        fileItem.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu(e.clientX, e.clientY, { filename: path, path, name, type: 'test', treeType: 'saved_tests' });
        });
        fileItem.draggable = true;
        fileItem.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('application/json', JSON.stringify({ path, type: 'file', treeType: 'saved_tests' }));
            e.dataTransfer.effectAllowed = 'move';
        });

        nodeEl.appendChild(fileItem);
        nodeEl.appendChild(childrenEl);
        container.appendChild(nodeEl);
    });
}

function openFileFromExplorer(filename, name) {
    const path = filename;
    const cached = testCache[path];
    if (cached && cached.code) {
        openTab(path, name, cached.code, 'test');
        return;
    }

    // Open the tab immediately so the UI feels instant
    openTab(path, name, '# Loading…', 'test');

    authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(path)}`)
        .then(res => res.json())
        .then(data => {
            if (data && data.code !== undefined) {
                testCache[path] = { ...(testCache[path] || {}), ...data };
                const tab = openTabs.find(t => t.id === path);
                if (tab) {
                    tab.code = data.code;
                    if (activeTabId === path) {
                        lastSavedCode = data.code;
                        setPlaywrightCode(data.code);
                    }
                }
            }
        })
        .catch(err => {
            alert('Failed to load test: ' + err);
        });
}

function openRecordingTab(filename, testName) {
    const tabId = `__recording__:${filename}`;
    if (openTabs.find(t => t.id === tabId)) { switchToTab(tabId); return; }
    const artifacts = testCache[filename]?.artifacts || [];
    const latest = artifacts.find(a => a.video_path && a.video_path !== 'null');
    if (!latest) return;
    const videoUrl = `/api/video/${latest.video_path}`;
    const info = [latest.video_size_mb ? `${latest.video_size_mb} MB` : '', latest.status || ''].filter(Boolean).join(' · ');
    openTab(tabId, `${testName} — Recording`, null, 'recording', { videoUrl, info });
}

function openTraceTab(filename, testName) {
    const tabId = `__trace__:${filename}`;
    if (openTabs.find(t => t.id === tabId)) { switchToTab(tabId); return; }
    const artifacts = testCache[filename]?.artifacts || [];
    const latest = artifacts.find(a => a.trace_path);
    if (!latest) return;
    const traceUrl = `${window.location.origin}/api/trace/${latest.trace_path}`;
    const viewerUrl = `/trace-viewer/?trace=${encodeURIComponent(traceUrl)}`;
    openTab(tabId, `${testName} — Trace`, null, 'trace', { viewerUrl });
}

function deleteFileFromExplorer(filename, name) {
    if (!confirm(`Delete "${name}"?`)) return;
    const path = filename;

    authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(path)}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                closeTab(path);
                loadFileExplorer();
                addLogEntry('info', `Deleted: ${name}`);
            }
        })
        .catch(err => {
            alert('Failed to delete: ' + err);
        });
}

// Explorer Resizer
if (hasFileExplorer && explorerResizer) {
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    // Restore saved width on load (clamp to match resize bounds)
    const savedWidth = localStorage.getItem('fileExplorerWidth');
    if (savedWidth) {
        const clampedWidth = Math.max(150, Math.min(400, parseInt(savedWidth, 10)));
        fileExplorer.style.width = clampedWidth + 'px';
    }

    explorerResizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = fileExplorer.offsetWidth;
        explorerResizer.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const diff = e.clientX - startX;
        const newWidth = Math.max(150, Math.min(400, startWidth + diff));
        fileExplorer.style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            explorerResizer.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';

            // Save the new width to localStorage
            const currentWidth = fileExplorer.offsetWidth;
            localStorage.setItem('fileExplorerWidth', currentWidth);
        }
    });
}

// Chat Resizer
if (chatResizer) {
    let isChatResizing = false;
    let chatResizeStartX = 0;
    let chatResizeStartWidth = 0;

    chatResizer.addEventListener('mousedown', (e) => {
        isChatResizing = true;
        chatResizeStartX = e.clientX;
        chatResizeStartWidth = aiChatSidebar.offsetWidth;
        chatResizer.classList.add('resizing');
        aiChatSidebar.style.transition = 'none';
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
        if (!isChatResizing) return;
        const diff = chatResizeStartX - e.clientX;
        const newWidth = Math.max(MIN_CHAT_WIDTH, Math.min(700, chatResizeStartWidth + diff));
        aiChatSidebar.style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', () => {
        if (isChatResizing) {
            isChatResizing = false;
            chatResizer.classList.remove('resizing');
            aiChatSidebar.style.transition = '';
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            localStorage.setItem('aiChatWidth', aiChatSidebar.offsetWidth);
        }
    });
}

// New Test Button (creates .py file in tree)
function sanitizeTestFilename(name) {
    const base = (name || '').replace(/[^a-zA-Z0-9 _-]/g, '').trim().replace(/\s+/g, '_');
    return (base || 'New_Test') + '.py';
}
if (newTestBtn) {
    newTestBtn.addEventListener('click', async () => {
        const name = prompt('Enter test name:');
        if (!name) return;
        const filename = sanitizeTestFilename(name);
        const code = `from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Your code here

        await browser.close()

asyncio.run(run())`;

        try {
            const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(filename)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name.trim(), code })
            });
            const data = await res.json();
            if (data.path || data.filename) {
                const path = data.path || data.filename;
                openTab(path, name.trim(), code, 'test');
                lastSavedCode = code;
                loadFileExplorer();
                addLogEntry('success', `Created test: ${name}`);
            } else {
                alert('Error creating test: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            alert('Failed to create test: ' + err);
        }
    });
}

// New Folder (Saved Tests)
const newFolderTestsBtn = document.getElementById('new-folder-tests-btn');
if (newFolderTestsBtn) {
    newFolderTestsBtn.addEventListener('click', async () => {
        const name = prompt('Folder name:');
        if (!name || !name.trim()) return;
        const path = name.trim().replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_') || 'NewFolder';
        try {
            const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, type: 'folder' })
            });
            const data = await res.json();
            if (data.success) {
                loadFileExplorer();
                addLogEntry('info', `Created folder: ${path}`);
            } else {
                alert('Error: ' + (data.error || 'Unknown'));
            }
        } catch (err) {
            alert('Failed to create folder: ' + err);
        }
    });
}

// Run All Tests Button
const runAllTestsBtn = document.getElementById('run-all-tests-btn');
if (runAllTestsBtn) {
    runAllTestsBtn.addEventListener('click', () => {
        if (confirm('Run all saved tests in parallel?')) {
            runAllTests();
        }
    });
}

// Record Test Button — name first, create empty test tab, then URL and open Playwright codegen (works logged in or not)
const recordTestBtn = document.getElementById('record-test-btn');
if (recordTestBtn) {
    recordTestBtn.addEventListener('click', async () => {
        if (currentRecordingId) {
            alert('A recording is already in progress.');
            return;
        }
        const name = prompt('Enter a name for this test:');
        if (!name) return;

        const emptyCode = '# Record your actions in the Playwright window; close it when done to generate code here.';
        let tabIdForRecording = null;

        try {
            if (currentUser && currentWorkspaceName) {
                const filename = sanitizeTestFilename(name);
                const saveRes = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(filename)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name.trim(), code: emptyCode }),
                });
                const saveData = await saveRes.json();
                if (!saveData.path && !saveData.filename) {
                    alert('Error creating test: ' + (saveData.error || 'Unknown error'));
                    return;
                }
                tabIdForRecording = saveData.path || saveData.filename;
                openTab(tabIdForRecording, name, emptyCode);
                loadFileExplorer();
                addLogEntry('success', `Created test: ${name}`);
            } else {
                tabIdForRecording = `record_${Date.now()}.py`;
                openTab(tabIdForRecording, name, emptyCode);
                addLogEntry('info', `Recording into "${name}". Log in to save tests to a workspace.`);
            }

            const url = prompt('Enter the URL to record (e.g. https://example.com):');
            if (!url) return;

            pendingCodegenTabId = tabIdForRecording;

            const res = await fetch('/api/start-codegen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, name }),
            });
            const data = await res.json();
            if (data.error) {
                pendingCodegenTabId = null;
                alert('Failed to start recording: ' + data.error);
                return;
            }
            currentRecordingId = data.recording_id;
            addLogEntry('info', `Starting recording for ${url}...`, '🎥 Starting recording...');
            // Show recording state immediately so recording is "on" from the beginning
            if (browserStatus) {
                browserStatus.textContent = 'Recording';
                browserStatus.classList.add('recording');
                browserStatus.style.background = 'var(--ctp-red)';
            }
            if (browserSidebar) browserSidebar.classList.add('active');
        } catch (err) {
            pendingCodegenTabId = null;
            alert('Failed to start recording: ' + err);
        }
    });
}

// Stop Recording Button
if (stopRecordingBtn) {
    stopRecordingBtn.addEventListener('click', () => {
        if (currentRecordingId) {
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'stop' });
        }
    });
}

// Recorder URL bar — navigate on Enter
if (recorderUrlInput) {
    recorderUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && currentRecordingId) {
            let url = recorderUrlInput.value.trim();
            if (url && !url.startsWith('http')) url = 'https://' + url;
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'navigate', url });
        }
    });
}

// Recorder "Wait X seconds" — add explicit wait step
const recorderWaitSeconds = document.getElementById('recorder-wait-seconds');
const recorderWaitAddBtn = document.getElementById('recorder-wait-add-btn');
if (recorderWaitAddBtn && recorderWaitSeconds) {
    recorderWaitAddBtn.addEventListener('click', () => {
        if (!currentRecordingId) return;
        const sec = parseInt(recorderWaitSeconds.value, 10) || 1;
        const clamped = Math.max(1, Math.min(300, sec));
        if (clamped !== sec) recorderWaitSeconds.value = clamped;
        socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'wait', duration_ms: clamped * 1000 });
    });
}

// Click on browser screenshot during recording — relay as mouse click to the recorder
if (browserScreenshot) {
    browserScreenshot.addEventListener('click', (e) => {
        if (!currentRecordingId || !browserScreenshotContainer?.classList.contains('recording-mode')) return;
        browserScreenshot.focus();
        const rect = browserScreenshot.getBoundingClientRect();
        const xRatio = (e.clientX - rect.left) / rect.width;
        const yRatio = (e.clientY - rect.top) / rect.height;
        const x = Math.round(xRatio * recorderViewport.width);
        const y = Math.round(yRatio * recorderViewport.height);
        socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'click', x, y });
    });

    // Type into the recorder via keyboard while browser screenshot is focused in recording mode
    browserScreenshot.addEventListener('keydown', (e) => {
        if (!currentRecordingId || !browserScreenshotContainer?.classList.contains('recording-mode')) return;
        if (e.key.length === 1) {
            e.preventDefault();
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'type', text: e.key });
        } else if (e.key === 'Enter') {
            e.preventDefault();
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'type', text: '\n' });
        } else if (e.key === 'Backspace') {
            e.preventDefault();
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'key', key: 'Backspace' });
        }
    });
}

// Live viewer iframe: relay recorder click/key from iframe to socket (when recording stream is shown in live viewer)
window.addEventListener('message', (e) => {
    if (e.source !== liveViewerIframe?.contentWindow || !e.data || !e.data.type) return;
    if (!currentRecordingId || !browserScreenshotContainer?.classList.contains('recording-mode')) return;
    const d = e.data;
    if (d.type === 'recorder_click') {
        const x = Math.round((d.xRatio ?? 0) * recorderViewport.width);
        const y = Math.round((d.yRatio ?? 0) * recorderViewport.height);
        socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'click', x, y });
    } else if (d.type === 'recorder_key') {
        if (d.text != null) {
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'type', text: d.text });
        } else if (d.key) {
            socket.emit('recorder_interact', { recording_id: currentRecordingId, action: 'key', key: d.key });
        }
    }
});

// Dashboard Button
const dashboardBtn = document.getElementById('dashboard-btn');
const dashboardView = document.getElementById('dashboard-view');
const codemirrorEditor = document.getElementById('codemirror-editor');

if (dashboardBtn) {
    dashboardBtn.addEventListener('click', () => {
        openDashboardTab();
    });
}

// Get Started Cards in Dashboard
const newTestCard = document.getElementById('new-test-card');
const newAiStepCard = document.getElementById('new-ai-step-card');

if (newTestCard) {
    newTestCard.addEventListener('click', () => {
        if (newTestBtn) newTestBtn.click();
    });
}

if (newAiStepCard) {
    newAiStepCard.addEventListener('click', () => {
        if (newAiStepBtn) newAiStepBtn.click();
    });
}

function openDashboardTab() {
    const dashboardTabId = '__dashboard__';

    // Check if dashboard tab already exists
    const existingDashboard = openTabs.find(tab => tab.id === dashboardTabId);
    if (existingDashboard) {
        // Just switch to it
        switchToTab(dashboardTabId);
        return;
    }

    // Create dashboard tab and insert at the beginning
    const dashboardTab = {
        id: dashboardTabId,
        name: 'Dashboard',
        code: '', // Dashboard doesn't use code
        isDirty: false,
        fileType: 'dashboard'
    };

    // Insert at the beginning
    openTabs.unshift(dashboardTab);
    activeTabId = dashboardTabId;

    // Show dashboard view
    showDashboardContent();
    renderTabs();
    updateFileListActiveState();
    saveTabsState();
}

function showDashboardContent() {
    // Hide the entire editor content area so its ::before placeholder can't bleed through
    if (editorContent) {
        editorContent.style.display = 'none';
        editorContent.classList.remove('empty');
    }
    if (dashboardView) dashboardView.style.display = 'block';

    // Load dashboard statistics
    loadDashboardStats();
}

function hideDashboardContent() {
    // Restore editor content area and hide dashboard
    if (editorContent) editorContent.style.display = '';
    if (codemirrorEditor) codemirrorEditor.style.display = 'block';
    if (dashboardView) dashboardView.style.display = 'none';
}

function _setStatValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

async function loadDashboardStats() {
    if (!currentWorkspaceName) return;

    // Show skeletons
    ['dashboard-saved-tests', 'dashboard-passed', 'dashboard-failed', 'dashboard-ai-steps'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<span class="stat-skeleton"></span>';
    });

    try {
        const [testsTreeRes, aiStepsTreeRes] = await Promise.all([
            authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests`),
            authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps`),
        ]);
        const testsTree = (await testsTreeRes.json()).tree || [];
        const aiStepsTree = (await aiStepsTreeRes.json()).tree || [];

        function countFiles(nodes) {
            let n = 0;
            nodes.forEach(node => {
                if (node.type === 'file') n++;
                if (node.children) n += countFiles(node.children);
            });
            return n;
        }
        function countByStatus(nodes, status) {
            let n = 0;
            nodes.forEach(node => {
                if (node.type === 'file' && node.last_run_status === status) n++;
                if (node.children) n += countByStatus(node.children, status);
            });
            return n;
        }

        const totalTests = countFiles(testsTree);
        const passedTests = countByStatus(testsTree, 'success');
        const failedTests = countByStatus(testsTree, 'error') + countByStatus(testsTree, 'stopped');
        const totalAiSteps = countFiles(aiStepsTree);

        _setStatValue('dashboard-saved-tests', totalTests);
        _setStatValue('dashboard-passed', passedTests);
        _setStatValue('dashboard-failed', failedTests);
        _setStatValue('dashboard-ai-steps', totalAiSteps);

        await loadRecordingsGallery();
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
        ['dashboard-saved-tests', 'dashboard-passed', 'dashboard-failed', 'dashboard-ai-steps'].forEach(id => {
            _setStatValue(id, '–');
        });
    }
}

async function loadRecordingsGallery() {
    const recordingsGallery = document.getElementById('recordings-gallery');
    const noRecordingsMessage = document.getElementById('no-recordings-message');

    if (!recordingsGallery) return;

    // Show skeleton cards while fetching
    recordingsGallery.style.display = 'grid';
    noRecordingsMessage.style.display = 'none';
    recordingsGallery.innerHTML = `
        <div class="recording-card skeleton-card"></div>
        <div class="recording-card skeleton-card"></div>
        <div class="recording-card skeleton-card"></div>
    `;

    try {
        const response = await authFetch(`/api/recent-recordings?workspaceName=${currentWorkspaceName}`);
        const recordings = await response.json();

        recordingsGallery.innerHTML = '';

        if (recordings.length === 0) {
            noRecordingsMessage.style.display = 'block';
            recordingsGallery.style.display = 'none';
            return;
        }

        noRecordingsMessage.style.display = 'none';
        recordingsGallery.style.display = 'grid';

        recordings.forEach(recording => {
            const card = createRecordingCard(recording);
            recordingsGallery.appendChild(card);
        });
    } catch (error) {
        console.error('Error loading recordings:', error);
        recordingsGallery.innerHTML = '';
    }
}

function createRecordingCard(recording) {
    const card = document.createElement('div');
    card.className = 'recording-card';

    const statusClass = recording.status === 'success' || recording.status === 'passed' ? 'passed' : 'failed';
    const statusText = recording.status === 'success' || recording.status === 'passed' ? 'PASSED' : 'FAILED';

    const timestamp = (() => {
        const raw = (recording.timestamp || '').replace(/_/g, 'T');
        const d = new Date(raw);
        if (isNaN(d.getTime())) return recording.timestamp || '';
        const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const day = String(d.getDate()).padStart(2, '0');
        return `${days[d.getDay()]} ${day} ${months[d.getMonth()]} - ${d.getFullYear()}`;
    })();

    // Thumbnail
    const thumbnail = document.createElement('div');
    thumbnail.className = 'recording-thumbnail';
    thumbnail.innerHTML = '<div class="recording-placeholder"><i class="lni lni-camera-movie-1"></i></div><div class="recording-play-overlay"><div class="recording-play-icon"><i class="lni lni-play"></i></div></div>';

    // Info
    const info = document.createElement('div');
    info.className = 'recording-info';
    const name = document.createElement('div');
    name.className = 'recording-name';
    name.title = recording.test_name;
    name.textContent = recording.test_name;
    const meta = document.createElement('div');
    meta.className = 'recording-meta';
    const statusSpan = document.createElement('span');
    statusSpan.className = `recording-status ${statusClass}`;
    statusSpan.textContent = statusText;
    const tsSpan = document.createElement('span');
    tsSpan.className = 'recording-timestamp';
    tsSpan.textContent = timestamp;
    meta.append(statusSpan, tsSpan);
    info.append(name, meta);

    // Delete button
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'recording-delete-btn';
    deleteBtn.title = 'Delete recording';
    deleteBtn.textContent = '✕';

    card.append(thumbnail, info, deleteBtn);

    card.addEventListener('click', () => {
        showVideoViewerModal(recording.test_filename, recording.test_name);
    });

    deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();

        // Optimistic: remove immediately
        const gallery = document.getElementById('recordings-gallery');
        const cardNextSibling = card.nextSibling;
        const cardParent = card.parentNode;
        card.remove();

        const galleryWasVisible = gallery && gallery.style.display !== 'none';
        const isEmpty = gallery && gallery.children.length === 0;
        if (isEmpty) {
            gallery.style.display = 'none';
            const msg = document.getElementById('no-recordings-message');
            if (msg) msg.style.display = '';
        }

        const fileItem = document.querySelector(`.file-item[data-filename="${recording.test_filename}"]`);
        const recordingBtn = fileItem ? fileItem.querySelector('[data-action="view-recording"]') : null;
        if (recordingBtn) recordingBtn.remove();

        try {
            await authFetch(`/api/workspaces/${currentWorkspaceName}/tests/${recording.test_filename}/artifacts`, { method: 'DELETE' });
        } catch (err) {
            // Rollback
            if (cardParent) cardParent.insertBefore(card, cardNextSibling);
            if (isEmpty && gallery) {
                gallery.style.display = galleryWasVisible ? '' : 'none';
                const msg = document.getElementById('no-recordings-message');
                if (msg) msg.style.display = 'none';
            }
            if (recordingBtn && fileItem) {
                const actions = fileItem.querySelector('.file-item-actions');
                if (actions) actions.insertBefore(recordingBtn, actions.firstChild);
            }
            showToast('Failed to delete recording. Please try again.');
        }
    });

    return card;
}

// Close All Tabs
if (closeAllTabsBtn) {
    closeAllTabsBtn.addEventListener('click', () => {
    if (openTabs.length === 0) return;

    const dirtyTabs = openTabs.filter(tab => tab.isDirty);
    if (dirtyTabs.length > 0) {
        if (!confirm(`Close all tabs?\nYou have ${dirtyTabs.length} unsaved change(s).`)) {
            return;
        }
    }

        openTabs = [];
        activeTabId = null;
        setPlaywrightCode('');
        if (editorContent) editorContent.classList.add('empty');
        renderTabs();
        updateFileListActiveState();
        saveTabsState();  // Save state when closing all tabs
    });
}

// Format Code Button
const formatCodeBtn = document.getElementById('format-code-btn');
if (formatCodeBtn) {
    formatCodeBtn.addEventListener('click', () => {
        formatCode();
    });
}

// Track code changes to mark tabs as dirty (handled in CodeMirror change event)
let lastSavedCode = '';

// Load file explorer on page load
window.addEventListener('load', () => {
    if (hasFileExplorer) {
        loadFileExplorer();
        loadAiSteps();
        if (editorContent) editorContent.classList.add('empty');

        // Dashboard opening is now handled by the main load handler after tab restoration
    }
    initUnifiedTree();
    initScmPanel();
    initGithubPanel();
});

// ========================================
// AI STEPS FUNCTIONALITY
// ========================================

async function loadAiSteps() {
    if (!aiStepsList) return;
    setupTreeRootDropZones();
    if (!currentWorkspaceName) {
        aiStepsList.innerHTML = '<div class="file-list-empty">Select a workspace</div>';
        return;
    }

    aiStepsList.innerHTML = '<div class="file-list-loading"><span class="file-list-spinner"></span>Loading…</div>';

    try {
        const response = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps`);
        const data = await response.json();
        const children = data.tree || [];

        aiStepsList.innerHTML = '';
        if (children.length === 0) {
            aiStepsList.innerHTML = '<div class="file-list-empty">No AI steps. Add a folder or new step.</div>';
            return;
        }
        renderAiStepsTree(children, aiStepsList, 0);
    } catch (err) {
        console.error('Failed to load AI steps:', err);
        aiStepsList.innerHTML = '<div class="file-list-empty">Error loading AI steps</div>';
    }
}

function renderAiStepsTree(nodes, container, depth) {
    nodes.forEach(node => {
        if (node.type === 'folder') {
            const nodeEl = document.createElement('div');
            nodeEl.className = 'file-tree-node file-tree-node--folder';
            nodeEl.dataset.path = node.path;
            nodeEl.dataset.type = 'folder';
            const hasChildren = (node.children && node.children.length > 0);
            const row = document.createElement('div');
            row.className = 'file-item file-item--folder';
            row.style.paddingLeft = (10 + depth * 10) + 'px';
            row.innerHTML = `
                <span class="file-tree-expand"><i class="lni lni-chevron-down"></i></span>
                <span class="file-item-icon file-item-icon--folder"><i class="lni lni-folder"></i></span>
                <span class="file-item-name">${escapeHtml(node.name)}</span>
            `;
            const childrenEl = document.createElement('div');
            childrenEl.className = 'file-tree-children';
            if (hasChildren) renderAiStepsTree(node.children, childrenEl, depth + 1);
            row.addEventListener('click', (e) => {
                if (e.target.closest('.file-tree-expand')) nodeEl.classList.toggle('expanded');
                else nodeEl.classList.toggle('expanded');
            });
            row.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e.clientX, e.clientY, { path: node.path, name: node.name, type: 'folder', treeType: 'ai_steps' });
            });
            row.draggable = true;
            row.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({ path: node.path, type: 'folder', treeType: 'ai_steps' }));
                e.dataTransfer.effectAllowed = 'move';
            });
            row.addEventListener('dragover', (e) => {
                if (!e.dataTransfer.types.includes('application/json')) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                row.classList.add('file-tree-drop-target');
            });
            row.addEventListener('dragleave', () => row.classList.remove('file-tree-drop-target'));
            row.addEventListener('drop', (e) => {
                e.preventDefault();
                row.classList.remove('file-tree-drop-target');
                let data;
                try { data = JSON.parse(e.dataTransfer.getData('application/json') || '{}'); } catch (_) { return; }
                if (data.treeType !== 'ai_steps' || !data.path) return;
                const fromPath = data.path;
                const basename = fromPath.split('/').pop();
                const toPath = node.path ? node.path + '/' + basename : basename;
                if (toPath === fromPath || (data.type === 'folder' && (toPath === fromPath || toPath.startsWith(fromPath + '/')))) return;
                moveTreeItem(currentWorkspaceName, 'ai_steps', fromPath, toPath).catch(err => alert(err.message || err));
            });
            nodeEl.appendChild(row);
            nodeEl.appendChild(childrenEl);
            container.appendChild(nodeEl);
            return;
        }

        const path = node.path;
        const name = node.display_name || node.name || path.replace(/\.md$/, '').replace(/_/g, ' ');
        const nodeEl = document.createElement('div');
        nodeEl.className = 'file-tree-node';
        nodeEl.dataset.path = path;
        const item = document.createElement('div');
        item.className = 'file-item';
        item.dataset.filename = path;
        item.dataset.path = path;
        item.style.paddingLeft = (10 + depth * 10) + 'px';
        item.innerHTML = `
            <span class="file-tree-expand" style="visibility:hidden;"><i class="lni lni-chevron-down"></i></span>
            <span class="file-item-icon"><i class="lni lni-pencil-1"></i></span>
            <span class="file-item-name">${escapeHtml(name)}</span>
            <div class="file-item-actions">
                <button class="file-item-action" data-action="run" title="Run"><i class="lni lni-play"></i></button>
                <button class="file-item-action" data-action="edit" title="Edit"><i class="lni lni-pencil-1"></i></button>
                <button class="file-item-action" data-action="delete" title="Delete"><i class="lni lni-trash-3"></i></button>
            </div>
        `;

        // Append git status badge via DOM
        if (node.git_status) {
            const nameEl = item.querySelector('.file-item-name');
            if (nameEl) {
                const badge = document.createElement('span');
                badge.className = `git-status-badge ${node.git_status}`;
                badge.textContent = node.git_status;
                nameEl.appendChild(badge);
            }
        }

        item.querySelector('[data-action="run"]').addEventListener('click', (e) => { e.stopPropagation(); runAiStep(null, path, name); });
        item.querySelector('[data-action="edit"]').addEventListener('click', (e) => { e.stopPropagation(); openAiStepInEditor(path, name); });
        item.querySelector('[data-action="delete"]').addEventListener('click', (e) => { e.stopPropagation(); deleteAiStep(path, name); });
        item.addEventListener('click', (e) => {
            if (!e.target.closest('.file-item-actions')) openAiStepInEditor(path, name);
        });
        item.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu(e.clientX, e.clientY, { filename: path, path, name, type: 'ai-step', treeType: 'ai_steps' });
        });
        item.draggable = true;
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('application/json', JSON.stringify({ path, type: 'file', treeType: 'ai_steps' }));
            e.dataTransfer.effectAllowed = 'move';
        });

        nodeEl.appendChild(item);
        container.appendChild(nodeEl);
    });
}

let runningAiStepTabId = null;  // Track which AI step tab is running

function runAiStep(stepId, filename, name) {
    if (isTestRunning) {
        alert('A test is already running');
        return;
    }

    // Warn if the AI step tab has unsaved changes
    const aiTab = openTabs.find(t => t.id === filename);
    if (aiTab && aiTab.isDirty) {
        if (!confirm('You have unsaved changes to this AI step. Run will use the last saved version.\n\nContinue anyway?')) {
            return;
        }
    }

    // Track the AI step tab so we can restore its content after test completes
    runningAiStepTabId = filename;

    // Clear previous log results
    while (humanLogContainer.firstChild) humanLogContainer.removeChild(humanLogContainer.firstChild);
    while (technicalLogContainer.firstChild) technicalLogContainer.removeChild(technicalLogContainer.firstChild);
    setPlaywrightCode('');

    // Update UI
    isTestRunning = true;
    isStopRequested = false;

    // Update browser header with test name and status
    if (browserTestName) {
        browserTestName.textContent = name;
    }
    updateBrowserStatus('running', 'RUNNING');
    updateStopButtonVisibility();

    // Show loading state in browser preview
    if (browserLoading) {
        browserLoading.classList.add('active');
        browserLoading.querySelector('.loading-text').textContent = 'Running AI steps...';
        browserLoading.querySelector('.loading-subtext').textContent = 'Agent is automating your test';
    }
    if (liveViewerIframe) {
        liveViewerIframe.style.display = 'none';
        liveViewerIframe.contentWindow?.postMessage({ type: 'test_reset' }, '*');
    }

    // Open browser sidebar and output panel
    if (!browserSidebar.classList.contains('open')) {
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.add('open');
        codeEditorContainer.classList.add('browser-open');
        if (toggleBrowserBtn) {
            toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
            toggleBrowserBtn.classList.add('active');
        }
    }

    // Emit run AI step event - use database ID for unambiguous lookup
    socket.emit('run_ai_step', {
        id: stepId,
        filename,
        workspaceName: currentWorkspaceName
    });

    addLogEntry('info', `🤖 Running AI steps: ${name}`);
}

function openAiStepInEditor(filename, name) {
    const path = filename;
    authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${encodeURIComponent(path)}`)
        .then(res => res.ok ? res.json() : Promise.reject(res))
        .then(data => {
            const content = data.steps != null ? data.steps : data.markdown;
            if (content != null) openTab(path, name, content, 'ai-step');
        })
        .catch(() => {
            authFetch(`/api/ai-steps/${path}/markdown?workspaceName=${currentWorkspaceName}`)
                .then(r => r.json())
                .then(data => { if (data.markdown) openTab(path, name, data.markdown, 'ai-step'); })
                .catch(err => { alert('Failed to load AI step: ' + err); });
        });
}

function showAiStepModal(filename = null, name = '', steps = '') {
    if (!aiStepModal) return;

    currentEditingAiStep = filename;
    aiStepNameInput.value = name;
    aiStepStepsInput.value = steps;
    aiStepModal.style.display = 'block';
}

function editAiStep(filename, name, steps) {
    showAiStepModal(filename, name, steps);
}

function showTestResultsModal(total, passed, failed, duration) {
    const modal = document.getElementById('test-results-modal');
    if (!modal) return;

    // Update stats
    document.getElementById('total-tests-run').textContent = total;
    document.getElementById('passed-tests-count').textContent = passed;
    document.getElementById('failed-tests-count').textContent = failed;
    document.getElementById('total-execution-time').textContent = `${duration.toFixed(1)}s`;

    // Build results list
    const resultsContainer = document.getElementById('individual-results-container');
    resultsContainer.innerHTML = '';

    batchRunResults.forEach(result => {
        const resultItem = document.createElement('div');
        resultItem.className = 'result-item';

        const icon = result.status === 'success' ? '✅' : '❌';
        const statusClass = result.status === 'success' ? 'passed' : 'failed';
        const statusText = result.status === 'success' ? 'Passed' : 'Failed';

        resultItem.innerHTML = `
            <span class="result-icon">${icon}</span>
            <span class="result-name">${escapeHtml(result.name)}</span>
            <span class="result-status ${statusClass}">${statusText}</span>
        `;

        resultsContainer.appendChild(resultItem);
    });

    // Load video if available from the last completed test
    const lastTest = batchRunResults[batchRunResults.length - 1];
    if (lastTest && lastTest.filename) {
        authFetch(`/api/saved-tests/${lastTest.filename}/artifacts?workspaceName=${currentWorkspaceName}`)
            .then(res => res.json())
            .then(artifacts => {
                if (artifacts.length > 0) {
                    const latestArtifact = artifacts[artifacts.length - 1];
                    if (latestArtifact.video_path) {
                        showVideoInModal(latestArtifact.video_path);
                    }
                }
            })
            .catch(err => console.error('Error loading artifacts:', err));
    }

    modal.style.display = 'block';
}

async function showVideoInModal(videoPath) {
    const videoContainer = document.getElementById('test-video-container');
    const videoSource = document.getElementById('test-video-source');
    const videoPlayer = document.getElementById('test-video-player');
    const noVideoMessage = document.getElementById('no-video-message');
    const downloadBtn = document.getElementById('download-video-btn');

    // Fetch signed URL from server
    try {
        const resp = await authFetch(`/api/artifacts/${videoPath}`);
        if (!resp.ok) {
            console.error('Failed to get signed URL');
            return;
        }
        const data = await resp.json();
        const signedUrl = data.url;

        videoPlayer.src = signedUrl;

        videoContainer.style.display = 'block';
        noVideoMessage.style.display = 'none';

        downloadBtn.onclick = () => {
            const a = document.createElement('a');
            a.href = signedUrl;
            a.download = videoPath.split('/').pop();
            a.click();
        };
    } catch (err) {
        console.error('Failed to load video:', err);
    }
}

async function showVideoViewerModal(filename, testName) {
    const modal = document.getElementById('video-viewer-modal');
    const title = document.getElementById('video-viewer-title');
    const loading = document.getElementById('video-viewer-loading');
    const videoContainer = document.getElementById('video-viewer-container');
    const noRecording = document.getElementById('video-viewer-no-recording');
    const videoPlayer = document.getElementById('video-viewer-player');
    const timestampElem = document.getElementById('video-viewer-timestamp');
    const sizeElem = document.getElementById('video-viewer-size');
    const downloadBtn = document.getElementById('video-viewer-download-btn');
    const traceBtn = document.getElementById('video-viewer-trace-btn');
    traceBtn.style.display = 'none';

    // Show modal immediately with loading state
    title.textContent = '';
    const _titleIcon = document.createElement('i');
    _titleIcon.className = 'lni lni-camera-movie-1';
    title.appendChild(_titleIcon);
    title.appendChild(document.createTextNode(` ${testName}`));
    loading.style.display = '';
    videoContainer.style.display = 'none';
    noRecording.style.display = 'none';
    videoPlayer.removeAttribute('src');
    modal.style.display = 'block';

    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tests/${filename}/artifacts`);
        const artifacts = await res.json();
        const validArtifacts = artifacts.filter(a => a.video_url);

        if (validArtifacts.length === 0) {
            loading.style.display = 'none';
            noRecording.style.display = 'block';
            return;
        }

        const latestArtifact = validArtifacts[0];
        const signedUrl = latestArtifact.video_url;

        // Set video source and wait for it to be playable
        videoPlayer.src = signedUrl;
        videoPlayer.oncanplay = () => {
            loading.style.display = 'none';
            videoContainer.style.display = 'block';
            videoPlayer.play().catch(() => {});
        };
        videoPlayer.onerror = () => {
            loading.style.display = 'none';
            noRecording.style.display = 'block';
        };

        // Show info and download button immediately (don't wait for video decode)
        timestampElem.textContent = (() => {
            const raw = (latestArtifact.timestamp || '').replace(/_/g, 'T');
            const d = new Date(raw);
            if (isNaN(d.getTime())) return `Recorded: ${latestArtifact.timestamp}`;
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const day = String(d.getDate()).padStart(2, '0');
            const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            return `Recorded: ${days[d.getDay()]} ${day} ${months[d.getMonth()]} - ${d.getFullYear()} at ${time}`;
        })();
        sizeElem.textContent = `Size: ${latestArtifact.video_size_mb} MB | Status: ${latestArtifact.status}`;
        downloadBtn.style.display = '';
        downloadBtn.onclick = () => {
            const a = document.createElement('a');
            a.href = signedUrl;
            a.download = latestArtifact.video_path.split('/').pop();
            a.click();
        };

        if (latestArtifact.trace_path) {
            traceBtn.style.display = 'inline-block';
            traceBtn.onclick = () => {
                const traceUrl = `${window.location.origin}/api/trace/${latestArtifact.trace_path}`;
                const viewerUrl = `/trace-viewer/?trace=${encodeURIComponent(traceUrl)}`;
                document.getElementById('trace-viewer-iframe').src = viewerUrl;
                document.getElementById('trace-viewer-modal').style.display = 'flex';
            };
        } else {
            traceBtn.style.display = 'none';
        }
    } catch (err) {
        console.error('Error loading artifacts:', err);
        loading.style.display = 'none';
        noRecording.style.display = 'block';
    }
}

function sanitizeAiStepFilename(name) {
    const base = (name || '').replace(/[^a-zA-Z0-9 _-]/g, '').trim().replace(/\s+/g, '_');
    return (base || 'New_Step') + '.md';
}

async function saveAiStep() {
    const name = aiStepNameInput.value.trim();
    const steps = aiStepStepsInput.value.trim();

    if (!name || !steps) {
        alert('Please enter both name and steps');
        return;
    }

    try {
        const path = currentEditingAiStep || sanitizeAiStepFilename(name);
        const url = `/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${encodeURIComponent(path)}`;
        const response = await authFetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, steps })
        });

        if (response.ok) {
            const data = await response.json();
            loadAiSteps();
            aiStepModal.style.display = 'none';
            addLogEntry('success', `Saved: ${name}`);
            if (!currentEditingAiStep && data.path) {
                currentEditingAiStep = data.path;
            }
        } else {
            const err = await response.json().catch(() => ({}));
            alert('Failed to save: ' + (err.error || response.status));
        }
    } catch (err) {
        alert('Failed to save: ' + err);
    }
}

async function deleteAiStep(filename, name) {
    if (!confirm(`Delete AI step "${name}"?`)) return;
    const path = filename;

    try {
        let res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${encodeURIComponent(path)}`, { method: 'DELETE' });
        const data = res.ok ? await res.json() : null;
        if (data && data.success) {
            loadAiSteps();
            addLogEntry('info', `Deleted: ${name}`);
            return;
        }
        res = await authFetch(`/api/ai-steps/${path}?workspaceName=${currentWorkspaceName}`, { method: 'DELETE' });
        if (res.ok) {
            loadAiSteps();
            addLogEntry('info', `Deleted: ${name}`);
        } else {
            alert('Failed to delete AI step');
        }
    } catch (err) {
        alert('Failed to delete: ' + err);
    }
}

// New Folder (AI Steps)
const newFolderAiStepsBtn = document.getElementById('new-folder-ai-steps-btn');
if (newFolderAiStepsBtn) {
    newFolderAiStepsBtn.addEventListener('click', async () => {
        const name = prompt('Folder name:');
        if (!name || !name.trim()) return;
        const path = name.trim().replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_') || 'NewFolder';
        try {
            const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/tree/ai_steps`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, type: 'folder' })
            });
            const data = await res.json();
            if (data.success) {
                loadAiSteps();
                addLogEntry('info', `Created folder: ${path}`);
            } else {
                alert('Error: ' + (data.error || 'Unknown'));
            }
        } catch (err) {
            alert('Failed to create folder: ' + err);
        }
    });
}

// Event Listeners for AI Steps
if (newAiStepBtn) {
    newAiStepBtn.addEventListener('click', () => {
        showAiStepModal();
    });
}

if (saveAiStepBtn) {
    saveAiStepBtn.addEventListener('click', saveAiStep);
}

if (cancelAiStepBtn) {
    cancelAiStepBtn.addEventListener('click', () => {
        aiStepModal.style.display = 'none';
    });
}

if (closeAiStepModal) {
    closeAiStepModal.addEventListener('click', () => {
        aiStepModal.style.display = 'none';
    });
}

// Test Results Modal Close Handlers
const closeTestResultsModal = document.querySelector('.close-test-results-modal');
const closeResultsBtn = document.getElementById('close-results-btn');
const testResultsModal = document.getElementById('test-results-modal');

if (closeTestResultsModal) {
    closeTestResultsModal.addEventListener('click', () => {
        testResultsModal.style.display = 'none';
    });
}

if (closeResultsBtn) {
    closeResultsBtn.addEventListener('click', () => {
        testResultsModal.style.display = 'none';
    });
}

// Video Viewer Modal Close Handlers
const videoViewerModal = document.getElementById('video-viewer-modal');
const closeVideoViewerBtn = document.querySelector('.close-video-viewer');

if (closeVideoViewerBtn) {
    closeVideoViewerBtn.addEventListener('click', () => {
        const videoPlayer = document.getElementById('video-viewer-player');
        if (videoPlayer) {
            videoPlayer.pause(); // Pause video when closing
        }
        videoViewerModal.style.display = 'none';
    });
}

// Trace Viewer Modal Close Handler
const traceViewerModal = document.getElementById('trace-viewer-modal');
const closeTraceViewerBtn = document.getElementById('close-trace-viewer');
if (closeTraceViewerBtn) {
    closeTraceViewerBtn.addEventListener('click', () => {
        traceViewerModal.style.display = 'none';
        document.getElementById('trace-viewer-iframe').src = '';
    });
}

// Modal click handlers
window.addEventListener('click', (event) => {
    if (event.target === aiStepModal) {
        aiStepModal.style.display = 'none';
    }
    if (event.target === testResultsModal) {
        testResultsModal.style.display = 'none';
    }
    if (event.target === videoViewerModal) {
        const videoPlayer = document.getElementById('video-viewer-player');
        if (videoPlayer) {
            videoPlayer.pause();
        }
        videoViewerModal.style.display = 'none';
    }
    if (event.target === traceViewerModal) {
        traceViewerModal.style.display = 'none';
        document.getElementById('trace-viewer-iframe').src = '';
    }
});

// Custom video player — controls auto-hide after 2 seconds of inactivity
(function initVideoViewerPlayer() {
    const wrapper = document.getElementById('video-wrapper');
    const video = document.getElementById('video-viewer-player');
    const controls = document.getElementById('vc-controls');
    const playBtn = document.getElementById('vc-play-btn');
    const seekBar = document.getElementById('vc-seek-bar');
    const currentTimeEl = document.getElementById('vc-current-time');
    const durationEl = document.getElementById('vc-duration-time');
    if (!wrapper || !video || !controls) return;

    let hideTimer = null;

    function formatTime(s) {
        const m = Math.floor((s || 0) / 60);
        const ss = Math.floor((s || 0) % 60).toString().padStart(2, '0');
        return `${m}:${ss}`;
    }

    function showControls() {
        controls.classList.remove('vc-hidden');
        clearTimeout(hideTimer);
        if (!video.paused && !video.ended) {
            hideTimer = setTimeout(() => controls.classList.add('vc-hidden'), 2000);
        }
    }

    wrapper.addEventListener('mousemove', showControls);
    wrapper.addEventListener('mouseenter', showControls);
    wrapper.addEventListener('mouseleave', () => {
        if (!video.paused && !video.ended) {
            clearTimeout(hideTimer);
            hideTimer = setTimeout(() => controls.classList.add('vc-hidden'), 500);
        }
    });

    // Click on video itself toggles play/pause
    video.addEventListener('click', (e) => {
        e.stopPropagation();
        if (video.paused) video.play().catch(() => {}); else video.pause();
    });

    playBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (video.paused) video.play().catch(() => {}); else video.pause();
    });

    video.addEventListener('play', () => {
        playBtn.textContent = '';
        const _pauseIcon = document.createElement('i');
        _pauseIcon.className = 'lni lni-pause';
        playBtn.appendChild(_pauseIcon);
        showControls();
    });

    video.addEventListener('pause', () => {
        playBtn.textContent = '';
        const _playIcon = document.createElement('i');
        _playIcon.className = 'lni lni-play';
        playBtn.appendChild(_playIcon);
        clearTimeout(hideTimer);
        controls.classList.remove('vc-hidden');
    });

    video.addEventListener('ended', () => {
        playBtn.textContent = '';
        const _playIcon2 = document.createElement('i');
        _playIcon2.className = 'lni lni-play';
        playBtn.appendChild(_playIcon2);
        clearTimeout(hideTimer);
        controls.classList.remove('vc-hidden');
    });

    video.addEventListener('timeupdate', () => {
        const dur = video.duration || 0;
        if (dur > 0) seekBar.value = (video.currentTime / dur) * 100;
        currentTimeEl.textContent = formatTime(video.currentTime);
    });

    video.addEventListener('loadedmetadata', () => {
        durationEl.textContent = formatTime(video.duration);
        seekBar.value = 0;
        currentTimeEl.textContent = '0:00';
        controls.classList.remove('vc-hidden');
    });

    seekBar.addEventListener('input', (e) => {
        e.stopPropagation();
        const dur = video.duration || 0;
        video.currentTime = (parseFloat(e.target.value) / 100) * dur;
        showControls();
    });

    // Reset player state when modal opens
    const modal = document.getElementById('video-viewer-modal');
    new MutationObserver(() => {
        if (modal.style.display === 'none') {
            clearTimeout(hideTimer);
            playBtn.textContent = '';
            const _resetIcon = document.createElement('i');
            _resetIcon.className = 'lni lni-play';
            playBtn.appendChild(_resetIcon);
            seekBar.value = 0;
            currentTimeEl.textContent = '0:00';
            durationEl.textContent = '0:00';
            controls.classList.remove('vc-hidden');
        }
    }).observe(modal, { attributes: true, attributeFilter: ['style'] });
})();

// Context Menu helpers
let contextMenuTarget = null; // { filename, name, type: 'test'|'ai-step', id? }

function showContextMenu(x, y, target) {
    contextMenuTarget = target;
    const isFolder = target.type === 'folder';
    contextMenu.querySelectorAll('[data-show="folder"]').forEach(el => { el.style.display = isFolder ? '' : 'none'; });
    contextMenu.querySelectorAll('[data-hide="folder"]').forEach(el => { el.style.display = isFolder ? 'none' : ''; });
    contextMenu.style.left = x + 'px';
    contextMenu.style.top = y + 'px';
    contextMenu.style.display = 'block';
    const rect = contextMenu.getBoundingClientRect();
    if (rect.right > window.innerWidth)  contextMenu.style.left = (x - rect.width) + 'px';
    if (rect.bottom > window.innerHeight) contextMenu.style.top = (y - rect.height) + 'px';
}

function hideContextMenu() {
    contextMenu.style.display = 'none';
    contextMenuTarget = null;
}

document.addEventListener('click', hideContextMenu);

contextMenu.addEventListener('click', (e) => {
    e.stopPropagation();
    const btn = e.target.closest('[data-action]');
    if (!btn || !contextMenuTarget) return;
    const { filename, name, type, id, path, treeType } = contextMenuTarget;
    const action = btn.dataset.action;
    hideContextMenu();

    const basePath = path || filename;
    const treeBase = treeType === 'ai_steps' ? 'ai_steps' : 'saved_tests';

    if (action === 'new-folder') {
        const folderName = prompt('Folder name:');
        if (!folderName || !folderName.trim()) return;
        const segment = folderName.trim().replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_') || 'NewFolder';
        const newPath = basePath ? `${basePath}/${segment}` : segment;
        authFetch(`/api/workspaces/${currentWorkspaceName}/tree/${treeBase}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: newPath, type: 'folder' })
        }).then(res => res.json()).then(data => {
            if (data.success) { if (treeBase === 'saved_tests') loadFileExplorer(); else loadAiSteps(); }
            else alert('Error: ' + (data.error || ''));
        }).catch(err => alert(err));
        return;
    }

    if (action === 'new-file') {
        if (treeBase === 'saved_tests') {
            const testName = prompt('Test name:');
            if (!testName) return;
            const filePath = (basePath ? basePath + '/' : '') + sanitizeTestFilename(testName);
            const code = 'from playwright.async_api import async_playwright\nimport asyncio\n\nasync def run():\n    async with async_playwright() as p:\n        browser = await p.chromium.launch(headless=False)\n        page = await browser.new_page()\n        await browser.close()\nasyncio.run(run())';
            authFetch(`/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(filePath)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: testName.trim(), code })
            }).then(() => { loadFileExplorer(); addLogEntry('info', 'Created: ' + testName); }).catch(err => alert(err));
        } else {
            showAiStepModal();
        }
        return;
    }

    if (action === 'rename') {
        const newName = prompt('New name:', name);
        if (!newName || newName.trim() === name) return;
        if (type === 'folder') {
            alert('Renaming folders is not supported in this prototype.');
            return;
        }
        const parent = basePath.includes('/') ? basePath.split('/').slice(0, -1).join('/') + '/' : '';
        const newPath = parent + (treeBase === 'saved_tests' ? sanitizeTestFilename(newName) : sanitizeAiStepFilename(newName));
        if (newPath === basePath) return;
        authFetch(`/api/workspaces/${currentWorkspaceName}/tree/${treeBase}/${encodeURIComponent(basePath)}`)
            .then(r => r.json())
            .then(data => {
                const body = treeBase === 'saved_tests' ? { name: newName.trim(), code: data.code || '' } : { name: newName.trim(), steps: data.steps || '' };
                return authFetch(`/api/workspaces/${currentWorkspaceName}/tree/${treeBase}/${encodeURIComponent(newPath)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            })
            .then(() => authFetch(`/api/workspaces/${currentWorkspaceName}/tree/${treeBase}/${encodeURIComponent(basePath)}`, { method: 'DELETE' }))
            .then(() => { if (treeBase === 'saved_tests') loadFileExplorer(); else loadAiSteps(); addLogEntry('info', 'Renamed'); })
            .catch(err => alert('Rename failed: ' + err));
        return;
    }

    if (action === 'run') {
        if (type === 'test') runSavedTest(basePath, name);
        else runAiStep(id, basePath, name);
        return;
    }

    if (action === 'delete') {
        if (type === 'folder') {
            if (!confirm(`Delete folder "${name}" and its contents?`)) return;
            authFetch(`/api/workspaces/${currentWorkspaceName}/tree/${treeBase}/${encodeURIComponent(basePath)}`, { method: 'DELETE' })
                .then(r => r.json()).then(data => {
                    if (data.success) { if (treeBase === 'saved_tests') loadFileExplorer(); else loadAiSteps(); }
                    else alert(data.error || 'Failed');
                }).catch(err => alert(err));
        } else {
            if (type === 'test') deleteFileFromExplorer(basePath, name);
            else deleteAiStep(basePath, name);
        }
        return;
    }

    if (action === 'ask-ai') {
        openFileFromExplorer(basePath, name);
        openChat();
        setTimeout(() => chatInput.focus(), 300);
    }
});

// AI Chat Sidebar helpers
const DEFAULT_CHAT_WIDTH = 450;
const MIN_CHAT_WIDTH = 280;

function openChat() {
    const savedWidth = parseInt(localStorage.getItem('aiChatWidth')) || DEFAULT_CHAT_WIDTH;
    aiChatSidebar.style.width = savedWidth + 'px';
    aiChatSidebar.classList.add('open');
    chatResizer.classList.add('visible');
    toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Chat';
    toggleChatBtn.classList.add('active');
}

function closeChat() {
    aiChatSidebar.classList.remove('open');
    aiChatSidebar.style.width = '';
    chatResizer.classList.remove('visible');
    toggleChatBtn.innerHTML = '<i class="lni lni-chat-bubble-2" style="margin-right: 4px;"></i> Chat';
    toggleChatBtn.classList.remove('active');
}

// AI Chat Sidebar Toggle
toggleChatBtn.addEventListener('click', () => {
    if (aiChatSidebar.classList.contains('open')) {
        closeChat();
    } else {
        openChat();
        setTimeout(() => chatInput.focus(), 300);
    }
});

closeChatSidebarBtn.addEventListener('click', () => {
    closeChat();
});

// Live Browser Sidebar Toggle (removed from UI - browser opens automatically during test runs)
if (toggleBrowserBtn) {
    toggleBrowserBtn.addEventListener('click', () => {
        const isOpen = browserSidebar.classList.toggle('open');
        const codeEditorContainer = document.querySelector('.code-editor-container');

        if (isOpen) {
            codeEditorContainer.classList.add('browser-open');
            toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
            toggleBrowserBtn.classList.add('active');
        } else {
            // Re-open sidebar if test is running — show confirm first, then modal
            if (isTestRunning || isBatchRunning) {
                browserSidebar.classList.add('open');
                codeEditorContainer.classList.add('browser-open');
                toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Browser';
                toggleBrowserBtn.classList.add('active');
                if (!confirm('Are you sure you want to stop the running test?')) {
                    return;
                }
                stopAndCloseModal.style.display = 'block';
                return;
            }
            codeEditorContainer.classList.remove('browser-open');
            toggleBrowserBtn.innerHTML = '<i class="lni lni-globe-1" style="margin-right: 4px;"></i> Browser';
            toggleBrowserBtn.classList.remove('active');
            closeOutputPanel();
        }
    });
}

// Stop-and-close modal
const stopAndCloseModal = document.getElementById('stop-and-close-modal');
const stopAndCloseConfirmBtn = document.getElementById('stop-and-close-confirm-btn');
const stopAndCloseCancelBtn = document.getElementById('stop-and-close-cancel-btn');

function _doCloseBrowserSidebar() {
    const codeEditorContainer = document.querySelector('.code-editor-container');
    browserSidebar.classList.remove('open');
    codeEditorContainer.classList.remove('browser-open');
    if (toggleBrowserBtn) {
        toggleBrowserBtn.innerHTML = '<i class="lni lni-globe-1" style="margin-right: 4px;"></i> Browser';
        toggleBrowserBtn.classList.remove('active');
    }
    closeOutputPanel();
}

function _requestCloseBrowserSidebar() {
    if (isTestRunning || isBatchRunning) {
        // Show native confirm first; only then show the "test is running" modal
        if (!confirm('Are you sure you want to stop the running test?')) {
            return;
        }
        stopAndCloseModal.style.display = 'block';
    } else {
        _doCloseBrowserSidebar();
    }
}

stopAndCloseConfirmBtn.addEventListener('click', () => {
    stopAndCloseModal.style.display = 'none';
    if (!isStopRequested) {
        isStopRequested = true;
        socket.emit('stop_test');
        addLogEntry('info', '⏹ Stop request sent to server');
    }
    _doCloseBrowserSidebar();
});

if (stopAndCloseCancelBtn) {
    stopAndCloseCancelBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (stopAndCloseModal) stopAndCloseModal.style.display = 'none';
    });
}

closeBrowserSidebarBtn.addEventListener('click', () => {
    _requestCloseBrowserSidebar();
});

// Close browser sidebar when clicking outside (but not on logs)
document.addEventListener('click', (e) => {
    // Only proceed if browser sidebar is open
    if (!browserSidebar.classList.contains('open')) return;

    // Check if click is inside browser sidebar or its toggle button
    const clickInsideBrowser = browserSidebar.contains(e.target);
    const clickOnToggleButton = toggleBrowserBtn && toggleBrowserBtn.contains(e.target);

    // Check if click is inside output panel (logs)
    const clickInsideLogs = outputPanel.contains(e.target);

    // Close if clicking outside browser AND not on logs
    if (!clickInsideBrowser && !clickOnToggleButton && !clickInsideLogs) {
        if (isTestRunning || isBatchRunning) {
            if (!confirm('Are you sure you want to stop the running test?')) {
                return;
            }
            stopAndCloseModal.style.display = 'block';
        } else {
            _doCloseBrowserSidebar();
        }
    }
});

// Output Panel — collapsed by default (only header visible)
const outputPreviewText = document.getElementById('output-preview-text');

// Toggle on the button or anywhere on the header
const outputPanelHeader = outputPanel.querySelector('.output-panel-header');
outputPanelHeader.addEventListener('click', (e) => {
    // Don't toggle when clicking log-tab buttons or clear button
    if (e.target.closest('.log-tabs') || e.target.closest('#clear-log') || e.target.closest('#copy-log')) return;
    outputPanel.classList.toggle('open');
});

function openOutputPanel() {
    outputPanel.classList.add('open');
}

function closeOutputPanel() {
    outputPanel.classList.remove('open');
}

function _updateOutputPreview(text) {
    if (outputPreviewText) outputPreviewText.textContent = text;
}

// Tab switching (log tabs)
logTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active class from all tabs and containers
        logTabs.forEach(t => t.classList.remove('active'));
        humanLogContainer.classList.remove('active');
        technicalLogContainer.classList.remove('active');

        // Add active class to clicked tab
        tab.classList.add('active');

        // Show corresponding container
        if (tab.dataset.tab === 'human') {
            humanLogContainer.classList.add('active');
        } else {
            technicalLogContainer.classList.add('active');
        }
    });
});

// Helper Functions
function addLogEntry(type, message, humanMessage = null) {
    const timestamp = new Date().toLocaleTimeString();

    // Add to technical log (full detail)
    const technicalEntry = document.createElement('div');
    technicalEntry.className = `log-entry ${type}`;
    technicalEntry.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="message">${escapeHtml(message)}</span>
    `;
    technicalLogContainer.appendChild(technicalEntry);
    technicalLogContainer.scrollTop = technicalLogContainer.scrollHeight;

    // Add to human log (simplified)
    const humanEntry = document.createElement('div');
    humanEntry.className = `log-entry ${type}`;
    const displayMessage = humanMessage || simplifyMessage(message);
    humanEntry.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="message">${escapeHtml(displayMessage)}</span>
    `;
    humanLogContainer.appendChild(humanEntry);
    humanLogContainer.scrollTop = humanLogContainer.scrollHeight;

    // Update the collapsed-state preview with the latest human-readable entry
    _updateOutputPreview(`${timestamp}  ${displayMessage}`);
}

function simplifyMessage(message) {
    // Simplify technical messages for human readability
    if (message.includes('source=')) {
        // Extract key info from agent messages
        if (message.includes('TEST PASSED:')) {
            return message.match(/TEST PASSED:.*$/)?.[0] || message;
        }
        if (message.includes('TEST FAILED:')) {
            return message.match(/TEST FAILED:.*$/)?.[0] || message;
        }
        if (message.includes('TEST ERROR:')) {
            return message.match(/TEST ERROR:.*$/)?.[0] || message;
        }

        // Extract content from structured messages
        const contentMatch = message.match(/content='([^']*)/);
        if (contentMatch) {
            const content = contentMatch[1];
            // Determine message type from source
            if (message.includes("source='user'")) {
                return '📝 Test instructions received';
            } else if (message.includes("source='web_tester'")) {
                return '🤖 Agent is thinking...';
            }
        }

        // For other agent actions, just return a generic message
        return '🤖 Agent is working...';
    }

    // Handle [agent_action] messages
    if (message.startsWith('[') && message.includes(']')) {
        return '🤖 Agent is working...';
    }

    return message;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper function to get display name with proper extension
function getDisplayName(name, fileType) {
    // Remove .json extension if present
    const baseName = name.replace(/\.json$/, '');

    // Add proper extension based on file type
    if (fileType === 'ai-step') {
        return baseName + '.md';
    } else if (fileType === 'test') {
        return baseName + '.py';
    }

    // Return as-is for other types (like dashboard)
    return name;
}

// Helper functions for Playwright code editor
// CodeMirror code editor functions
function setPlaywrightCode(code) {
    if (codeMirrorEditor) {
        codeMirrorEditor.setValue(code || '');
    }
}

function getPlaywrightCode() {
    return codeMirrorEditor ? codeMirrorEditor.getValue() : '';
}

// Format code using Black formatter
async function formatCode() {
    if (!codeMirrorEditor) return;

    const code = codeMirrorEditor.getValue();
    if (!code.trim()) return;

    try {
        const response = await authFetch('/api/format-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code })
        });

        const data = await response.json();

        if (response.ok && data.formatted_code) {
            // Save cursor position
            const cursor = codeMirrorEditor.getCursor();
            const scrollInfo = codeMirrorEditor.getScrollInfo();

            // Set formatted code
            codeMirrorEditor.setValue(data.formatted_code);

            // Restore cursor position (best effort)
            codeMirrorEditor.setCursor(cursor);
            codeMirrorEditor.scrollTo(scrollInfo.left, scrollInfo.top);

            addLogEntry('info', '✨ Code formatted successfully');
        } else {
            addLogEntry('error', `Formatting failed: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        addLogEntry('error', `Formatting error: ${error.message}`);
    }
}

// CodeMirror initialization and change tracking
function initializeCodeMirror() {
    if (typeof CodeMirror !== 'undefined') {
        const editorElement = document.getElementById('codemirror-editor');
        if (editorElement && !codeMirrorEditor) {
            codeMirrorEditor = CodeMirror(editorElement, {
                mode: 'python',
                theme: 'material-darker',
                lineNumbers: true,
                indentUnit: 4,
                tabSize: 4,
                indentWithTabs: false,
                lineWrapping: false,
                autofocus: false,
                styleActiveLine: true,
                matchBrackets: true,
                autoCloseBrackets: true,
                hintOptions: {
                    completeSingle: false,  // Don't auto-complete if only one option
                    alignWithWord: true,
                    closeCharacters: /[\s()\[\]{};:>,]/,
                    hint: CodeMirror.hint.anyword  // Use anyword-hint for context-aware completion
                },
                extraKeys: {
                    "Cmd-/": "toggleComment",
                    "Ctrl-/": "toggleComment",
                    "Shift-Alt-F": formatCode,  // Format keyboard shortcut
                    "Shift-Ctrl-F": formatCode,  // Alternative shortcut
                    "Ctrl-Space": "autocomplete"  // Trigger autocomplete
                }
            });

            // Listen for content changes
            codeMirrorEditor.on('change', function(cm) {
                if (activeTabId) {
                    const tab = openTabs.find(t => t.id === activeTabId);
                    if (tab) {
                        const currentCode = cm.getValue();
                        if (currentCode !== lastSavedCode) {
                            tab.isDirty = true;
                            tab.code = currentCode;
                            renderTabs();
                        }
                    }
                }
            });

            // Format on paste
            codeMirrorEditor.on('paste', function(cm, event) {
                // Delay formatting slightly to let paste complete
                setTimeout(() => {
                    formatCode();
                }, 100);
            });

            // Auto-trigger autocomplete as you type
            codeMirrorEditor.on('inputRead', function(cm, change) {
                // Don't trigger on deletion or paste
                if (change.origin === '+delete' || change.origin === 'paste') {
                    return;
                }

                // Trigger autocomplete after typing a letter or dot
                const text = change.text[0];
                if (text && (text.match(/[a-zA-Z_.]/) || text === '.')) {
                    // Small delay to avoid triggering too frequently
                    setTimeout(() => {
                        if (!cm.state.completionActive) {
                            CodeMirror.commands.autocomplete(cm, null, {completeSingle: false});
                        }
                    }, 150);
                }
            });

            // Set up hover documentation
            setupHoverDocumentation(codeMirrorEditor);
        }
    }
}

// Hover Documentation Database
const functionDocs = {
    // Python Built-ins
    'print': {
        signature: 'print(*objects, sep=" ", end="\\n", file=None, flush=False)',
        description: 'Print objects to the text stream file, separated by sep and followed by end.',
        params: [
            { name: 'objects', desc: 'Values to print' },
            { name: 'sep', desc: 'String inserted between values (default " ")' },
            { name: 'end', desc: 'String appended after the last value (default "\\n")' }
        ]
    },
    'len': {
        signature: 'len(object)',
        description: 'Return the length (the number of items) of an object.',
        params: [
            { name: 'object', desc: 'A sequence (string, bytes, tuple, list, or range) or collection (dict, set, or frozen set)' }
        ]
    },
    'range': {
        signature: 'range(start, stop, step=1)',
        description: 'Return an immutable sequence of numbers from start to stop by step.',
        params: [
            { name: 'start', desc: 'Starting number (inclusive)' },
            { name: 'stop', desc: 'Ending number (exclusive)' },
            { name: 'step', desc: 'Increment between numbers (default 1)' }
        ]
    },
    'str': {
        signature: 'str(object="")',
        description: 'Return a string version of object.',
        params: [
            { name: 'object', desc: 'Object to convert to string' }
        ]
    },
    'int': {
        signature: 'int(x, base=10)',
        description: 'Convert a number or string to an integer.',
        params: [
            { name: 'x', desc: 'Number or string to convert' },
            { name: 'base', desc: 'Number base for conversion (default 10)' }
        ]
    },
    'sleep': {
        signature: 'sleep(seconds)',
        description: 'Suspend execution for the given number of seconds.',
        params: [
            { name: 'seconds', desc: 'Number of seconds to sleep (can be a float)' }
        ]
    },
    // Playwright Page Methods
    'goto': {
        signature: 'page.goto(url, *, timeout=30000, wait_until="load")',
        description: 'Navigate to the specified URL.',
        params: [
            { name: 'url', desc: 'URL to navigate to' },
            { name: 'timeout', desc: 'Maximum navigation time in milliseconds (default 30000)' },
            { name: 'wait_until', desc: 'When to consider navigation succeeded: "load", "domcontentloaded", "networkidle"' }
        ]
    },
    'click': {
        signature: 'page.click(selector, *, timeout=30000, button="left")',
        description: 'Click an element matching the selector.',
        params: [
            { name: 'selector', desc: 'CSS selector or text selector to identify element' },
            { name: 'timeout', desc: 'Maximum time to wait for element (default 30000ms)' },
            { name: 'button', desc: 'Mouse button: "left", "right", or "middle"' }
        ]
    },
    'fill': {
        signature: 'page.fill(selector, value, *, timeout=30000)',
        description: 'Fill an input field with text.',
        params: [
            { name: 'selector', desc: 'CSS selector to identify input element' },
            { name: 'value', desc: 'Text value to fill' },
            { name: 'timeout', desc: 'Maximum time to wait for element (default 30000ms)' }
        ]
    },
    'type': {
        signature: 'page.type(selector, text, *, delay=0)',
        description: 'Type text into an input field character by character.',
        params: [
            { name: 'selector', desc: 'CSS selector to identify input element' },
            { name: 'text', desc: 'Text to type' },
            { name: 'delay', desc: 'Time to wait between key presses in milliseconds' }
        ]
    },
    'press': {
        signature: 'page.press(selector, key, *, delay=0)',
        description: 'Press a key on an element.',
        params: [
            { name: 'selector', desc: 'CSS selector to identify element' },
            { name: 'key', desc: 'Key name (e.g., "Enter", "Tab", "Escape")' },
            { name: 'delay', desc: 'Time to wait between keydown and keyup in milliseconds' }
        ]
    },
    'wait_for_selector': {
        signature: 'page.wait_for_selector(selector, *, timeout=30000, state="visible")',
        description: 'Wait for element matching selector to be in specified state.',
        params: [
            { name: 'selector', desc: 'CSS selector to wait for' },
            { name: 'timeout', desc: 'Maximum time to wait in milliseconds (default 30000)' },
            { name: 'state', desc: 'Element state: "attached", "detached", "visible", "hidden"' }
        ]
    },
    'screenshot': {
        signature: 'page.screenshot(*, path=None, full_page=False, type="png")',
        description: 'Take a screenshot of the page.',
        params: [
            { name: 'path', desc: 'File path to save screenshot' },
            { name: 'full_page', desc: 'Capture full scrollable page (default False)' },
            { name: 'type', desc: 'Image format: "png" or "jpeg"' }
        ]
    },
    'get_by_role': {
        signature: 'page.get_by_role(role, *, name=None)',
        description: 'Locate element by ARIA role.',
        params: [
            { name: 'role', desc: 'ARIA role (e.g., "button", "textbox", "link")' },
            { name: 'name', desc: 'Accessible name to filter by' }
        ]
    },
    'get_by_text': {
        signature: 'page.get_by_text(text, *, exact=False)',
        description: 'Locate element by text content.',
        params: [
            { name: 'text', desc: 'Text content to search for' },
            { name: 'exact', desc: 'Require exact match (default False)' }
        ]
    },
    'get_by_label': {
        signature: 'page.get_by_label(text, *, exact=False)',
        description: 'Locate form control by associated label text.',
        params: [
            { name: 'text', desc: 'Label text to search for' },
            { name: 'exact', desc: 'Require exact match (default False)' }
        ]
    },
    'get_by_placeholder': {
        signature: 'page.get_by_placeholder(text, *, exact=False)',
        description: 'Locate input by placeholder text.',
        params: [
            { name: 'text', desc: 'Placeholder text to search for' },
            { name: 'exact', desc: 'Require exact match (default False)' }
        ]
    },
    'expect': {
        signature: 'expect(locator)',
        description: 'Create an assertion for Playwright testing.',
        params: [
            { name: 'locator', desc: 'Element locator to assert on' }
        ]
    }
};

// Hover tooltip state
let hoverTooltip = null;
let hoverTimeout = null;
let currentHoverToken = null;

// Create and show hover tooltip
function showHoverTooltip(cm, token, coords) {
    // Remove existing tooltip
    removeHoverTooltip();

    const funcName = token.string;
    const docs = functionDocs[funcName];

    if (!docs) return;

    // Create tooltip element
    hoverTooltip = document.createElement('div');
    hoverTooltip.className = 'cm-hover-tooltip';

    // Build tooltip content
    let html = `
        <div class="cm-hover-tooltip-header">
            <i class="lni lni-book-1 cm-hover-tooltip-icon"></i>
            <code class="cm-hover-tooltip-signature">${docs.signature}</code>
        </div>
        <div class="cm-hover-tooltip-body">
            <div class="cm-hover-tooltip-description">${docs.description}</div>
    `;

    if (docs.params && docs.params.length > 0) {
        html += `
            <div class="cm-hover-tooltip-params">
                <div class="cm-hover-tooltip-param-title">Parameters</div>
        `;
        docs.params.forEach(param => {
            html += `
                <div class="cm-hover-tooltip-param">
                    <span class="cm-hover-tooltip-param-name">${param.name}</span>
                    <span class="cm-hover-tooltip-param-desc">— ${param.desc}</span>
                </div>
            `;
        });
        html += `</div>`;
    }

    html += `</div>`;
    hoverTooltip.innerHTML = html;

    // Position and add tooltip
    document.body.appendChild(hoverTooltip);

    // Calculate position
    const editorRect = cm.getWrapperElement().getBoundingClientRect();
    const tooltipRect = hoverTooltip.getBoundingClientRect();

    let left = editorRect.left + coords.left;
    let top = editorRect.top + coords.bottom + 5; // 5px below cursor

    // Keep tooltip within viewport
    if (left + tooltipRect.width > window.innerWidth) {
        left = window.innerWidth - tooltipRect.width - 10;
    }
    if (top + tooltipRect.height > window.innerHeight) {
        top = editorRect.top + coords.top - tooltipRect.height - 5; // Show above if no space below
    }

    hoverTooltip.style.left = left + 'px';
    hoverTooltip.style.top = top + 'px';
}

// Remove hover tooltip
function removeHoverTooltip() {
    if (hoverTooltip) {
        hoverTooltip.remove();
        hoverTooltip = null;
    }
    if (hoverTimeout) {
        clearTimeout(hoverTimeout);
        hoverTimeout = null;
    }
    currentHoverToken = null;
}

// Set up hover documentation for CodeMirror
function setupHoverDocumentation(cm) {
    cm.on('mouseover', (cm, event) => {
        const pos = cm.coordsChar({ left: event.clientX, top: event.clientY });
        const token = cm.getTokenAt(pos);

        // Only show tooltip for variable/property tokens
        if (!token || !token.string || token.type !== 'variable' && token.type !== 'property') {
            removeHoverTooltip();
            return;
        }

        // Check if we're hovering over the same token
        if (currentHoverToken === token.string) {
            return;
        }

        // Clear previous timeout
        if (hoverTimeout) {
            clearTimeout(hoverTimeout);
        }

        currentHoverToken = token.string;

        // Set 3-second delay before showing tooltip
        hoverTimeout = setTimeout(() => {
            const coords = cm.cursorCoords(pos);
            showHoverTooltip(cm, token, coords);
        }, 3000);
    });

    cm.on('mouseout', () => {
        removeHoverTooltip();
    });

    // Also remove tooltip when scrolling or typing
    cm.on('scroll', removeHoverTooltip);
    cm.on('change', removeHoverTooltip);
}

// Chat functionality
function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message && !currentImage) return;

    // Open chat sidebar if not already open
    if (!aiChatSidebar.classList.contains('open')) {
        openChat();
    }

    // Get existing code from bottom panel
    const existingCode = getPlaywrightCode();

    // Detect current file type
    let fileType = 'unknown';
    if (activeTabId) {
        const activeTab = openTabs.find(t => t.id === activeTabId);
        if (activeTab) {
            fileType = activeTab.fileType || 'test';  // Default to 'test' if not specified
        }
    }

    // Add user message to chat (with image if present)
    if (currentImage) {
        appendChatMessageWithImage('user', message || 'Analyze this image', currentImage);
    } else {
        appendChatMessage('user', message);
    }

    chatInput.value = '';

    // Send to backend
    socket.emit('chat_message', {
        message: message || 'Analyze this image and generate relevant Playwright code',
        existing_code: existingCode || null,
        image: currentImage,
        file_type: fileType,
        workspaceName: currentWorkspaceName,
        user_id: currentUser ? currentUser.id : null,
    });

    // Clear image after sending
    if (currentImage) {
        currentImage = null;
        imagePreviewContainer.style.display = 'none';
        imagePreview.src = '';
        fileInput.value = '';
    }

    // Show floating thinking indicator
    showChatThinking('Thinking…');
}

function enhanceCodeBlocks(container) {
    container.querySelectorAll('pre code').forEach((codeEl) => {
        const pre = codeEl.parentElement;
        if (pre.dataset.enhanced) return; // already enhanced
        pre.dataset.enhanced = '1';

        const codeContent = codeEl.textContent;
        const lang = [...codeEl.classList].find(c => c.startsWith('language-'))?.replace('language-', '') || '';

        // Header
        const header = document.createElement('div');
        header.className = 'chat-code-header';
        const langLabel = document.createElement('span');
        langLabel.className = 'chat-code-lang';
        langLabel.textContent = (lang || 'code').toUpperCase();
        header.appendChild(langLabel);

        const btnGroup = document.createElement('div');
        btnGroup.style.cssText = 'display:flex;gap:4px;';
        if (lang === 'python' || (!lang && codeContent.includes('async_playwright'))) {
            const applyBtn = document.createElement('button');
            applyBtn.className = 'chat-code-btn apply';
            applyBtn.textContent = '⚡ Apply';
            applyBtn.title = 'Apply code to active editor tab';
            applyBtn.onclick = () => {
                const currentCode = activeTabId ? getPlaywrightCode() : '';
                pendingCodeSuggestion = { code: codeContent, explanation: 'AI-suggested code from chat', currentCode, targetTabId: activeTabId, contentType: 'code' };
                showCodePreview();
            };
            btnGroup.appendChild(applyBtn);
        }
        const copyBtn = document.createElement('button');
        copyBtn.className = 'chat-code-btn';
        const _cpIcon1 = document.createElement('i');
        _cpIcon1.className = 'lni lni-clipboard';
        copyBtn.appendChild(_cpIcon1);
        copyBtn.title = 'Copy code';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(codeContent);
            copyBtn.textContent = '';
            const _ckIcon1 = document.createElement('i');
            _ckIcon1.className = 'lni lni-check';
            copyBtn.appendChild(_ckIcon1);
            setTimeout(() => {
                copyBtn.textContent = '';
                const _cpIcon2 = document.createElement('i');
                _cpIcon2.className = 'lni lni-clipboard';
                copyBtn.appendChild(_cpIcon2);
            }, 2000);
        };
        btnGroup.appendChild(copyBtn);
        header.appendChild(btnGroup);

        // CodeMirror container
        const cmContainer = document.createElement('div');
        cmContainer.className = 'chat-cm-editor';

        // Wrapper replaces <pre>
        const wrapper = document.createElement('div');
        wrapper.className = 'chat-code-block';
        wrapper.appendChild(header);
        wrapper.appendChild(cmContainer);
        pre.replaceWith(wrapper);

        if (typeof CodeMirror !== 'undefined') {
            CodeMirror(cmContainer, {
                value: codeContent,
                mode: lang || 'python',
                theme: 'material-darker',
                readOnly: true,
                lineNumbers: false,
                lineWrapping: false,
                scrollbarStyle: 'native',
            });
        }
    });
}

function appendChatMessage(type, content, isCode = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;

    if (isCode) {
        messageDiv.className = 'chat-message code';

        // Add code header
        const codeHeader = document.createElement('div');
        codeHeader.className = 'chat-code-header';
        const langLabel = document.createElement('span');
        langLabel.className = 'chat-code-lang';
        langLabel.textContent = 'Python';
        codeHeader.appendChild(langLabel);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'chat-code-btn';
        copyBtn.textContent = '';
        const _cpyIcon = document.createElement('i');
        _cpyIcon.className = 'lni lni-clipboard';
        copyBtn.appendChild(_cpyIcon);
        copyBtn.appendChild(document.createTextNode(' Copy'));
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(content);
            copyBtn.textContent = '';
            const _ckIcon2 = document.createElement('i');
            _ckIcon2.className = 'lni lni-check';
            copyBtn.appendChild(_ckIcon2);
            setTimeout(() => {
                copyBtn.textContent = '';
                const _cpyIcon2 = document.createElement('i');
                _cpyIcon2.className = 'lni lni-clipboard';
                copyBtn.appendChild(_cpyIcon2);
                copyBtn.appendChild(document.createTextNode(' Copy'));
            }, 2000);
        };
        codeHeader.appendChild(copyBtn);
        messageDiv.appendChild(codeHeader);

        const cmContainer = document.createElement('div');
        cmContainer.className = 'chat-cm-editor';
        messageDiv.appendChild(cmContainer);
        if (typeof CodeMirror !== 'undefined') {
            CodeMirror(cmContainer, {
                value: content,
                mode: 'python',
                theme: 'material-darker',
                readOnly: true,
                lineNumbers: false,
                lineWrapping: false,
                scrollbarStyle: 'native',
            });
        }

    } else if (type === 'ai' && typeof marked !== 'undefined') {
        // AI messages now go through the typewriter path; this branch is a fallback
        messageDiv.innerHTML = marked.parse(content);
        enhanceCodeBlocks(messageDiv);

    } else {
        const contentSpan = document.createElement('span');
        contentSpan.textContent = content;
        messageDiv.appendChild(contentSpan);
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
}

function appendChatMessageWithImage(type, content, imageSrc) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;

    // Wrap image + text in a content div so the ❯ prefix aligns correctly
    const contentDiv = document.createElement('div');
    contentDiv.className = 'chat-message-content';

    const img = document.createElement('img');
    img.src = imageSrc;
    img.alt = 'Attached image';
    img.className = 'chat-attached-image';
    contentDiv.appendChild(img);

    if (content) {
        const contentSpan = document.createElement('span');
        contentSpan.textContent = content;
        contentDiv.appendChild(contentSpan);
    }

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
}

// ── Floating thinking indicator helpers ──
function showChatThinking(label) {
    const el = document.getElementById('chat-thinking-indicator');
    const lbl = document.getElementById('chat-thinking-label');
    if (!el) return;
    if (lbl) lbl.textContent = label;
    el.style.display = 'flex';
}

function hideChatThinking() {
    const el = document.getElementById('chat-thinking-indicator');
    if (el) el.style.display = 'none';
}

// Typewriter reveal for AI messages
function typewriterAppend(messageDiv, fullText, onDone) {
    const CHARS_PER_TICK = 4; // speed: chars per ~16ms frame
    let pos = 0;
    const rawEl = document.createElement('span');
    messageDiv.classList.add('streaming');
    messageDiv.appendChild(rawEl);
    chatMessages.appendChild(messageDiv);

    function tick() {
        if (pos < fullText.length) {
            pos = Math.min(pos + CHARS_PER_TICK, fullText.length);
            rawEl.textContent = fullText.slice(0, pos);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            requestAnimationFrame(tick);
        } else {
            // Done streaming — render markdown
            messageDiv.classList.remove('streaming');
            if (typeof marked !== 'undefined') {
                messageDiv.innerHTML = marked.parse(fullText);
                enhanceCodeBlocks(messageDiv);
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
            if (onDone) onDone();
        }
    }
    requestAnimationFrame(tick);
}

// Socket.IO event handlers for chat
socket.on('chat_response', (data) => {
    hideChatThinking();
    chatMessages.querySelectorAll('.chat-message.tool-call').forEach(el => el.remove());

    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message ai';
    typewriterAppend(messageDiv, data.message || '');
});

socket.on('code_suggestion', (data) => {
    // Show code/steps in chat
    appendChatMessage('code', data.code, true);

    // Store suggestion and show preview
    const currentCode = activeTabId ? getPlaywrightCode() : '';
    const contentType = data.content_type || 'code';  // 'code' or 'steps'

    pendingCodeSuggestion = {
        code: data.code,
        explanation: data.explanation || (contentType === 'steps' ? 'AI-generated test steps' : 'AI-generated code suggestion'),
        currentCode: currentCode,
        targetTabId: activeTabId,
        contentType: contentType
    };

    showCodePreview();
});

socket.on('chat_error', (data) => {
    hideChatThinking();
    appendChatMessage('system', `Error: ${data.message}`);
});

// Agent tool call notification — shown as a subtle status line in chat
const TOOL_LABELS = {
    get_workspace_context: 'Analysing workspace…',
    list_tests:            'Listing tests…',
    list_ai_steps:         'Listing AI steps…',
    read_test:             'Reading test…',
    read_ai_step:          'Reading AI steps…',
    search_files:          'Searching files…',
    create_test:           'Creating test…',
    create_ai_step:        'Creating AI steps…',
    update_test:           'Updating test…',
    update_ai_step:        'Updating AI steps…',
    run_test:              'Running test…',
    get_test_results:      'Getting results…',
    get_test_trace:        'Reading trace…',
};

socket.on('agent_tool_call', (data) => {
    const label = TOOL_LABELS[data.tool] || `${data.tool}…`;
    showChatThinking(label);
});

socket.on('file_created', (data) => {
    // Remove any tool-call indicators now that the agent finished a create action
    chatMessages.querySelectorAll('.chat-message.tool-call').forEach(el => el.remove());
    // Refresh the file explorer so the new file appears immediately
    if (currentWorkspaceName) {
        loadFileExplorer();
    }
    // Auto-open the newly created file in a tab
    const { filename, name, type } = data;
    if (filename && name && currentWorkspaceName) {
        const fileType = type === 'ai_step' ? 'ai-step' : 'test';
        const apiPath = fileType === 'ai-step'
            ? `/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${encodeURIComponent(filename)}`
            : `/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(filename)}`;
        authFetch(apiPath)
            .then(res => res.json())
            .then(freshData => {
                const code = freshData.code !== undefined ? freshData.code : freshData.steps;
                if (code !== undefined) {
                    testCache[filename] = freshData;
                    openTab(filename, name, code, fileType);
                }
            })
            .catch(err => console.error('Failed to open new tab after file_created:', err));
    }
});

socket.on('file_updated', (data) => {
    chatMessages.querySelectorAll('.chat-message.tool-call').forEach(el => el.remove());
    // Immediately evict the stale cache entry so any open-from-explorer
    // while async fetches are in-flight will fall back to a fresh API call.
    const { filename, type } = data;
    if (filename) delete testCache[filename];
    if (currentWorkspaceName) {
        loadFileExplorer();
    }
    // If the updated file is open in a tab, refresh its content live
    if (filename && currentWorkspaceName) {
        const openTab = openTabs.find(t => t.id === filename);
        if (openTab) {
            const fileType = type === 'ai_step' ? 'ai-step' : 'test';
            const apiPath = fileType === 'ai-step'
                ? `/api/workspaces/${currentWorkspaceName}/tree/ai_steps/${encodeURIComponent(filename)}`
                : `/api/workspaces/${currentWorkspaceName}/tree/saved_tests/${encodeURIComponent(filename)}`;
            authFetch(apiPath)
                .then(res => res.json())
                .then(freshData => {
                    const code = freshData.code !== undefined ? freshData.code : freshData.steps;
                    if (code !== undefined) {
                        testCache[filename] = freshData;
                        openTab.code = code;
                        // Update CodeMirror immediately if this tab is active
                        if (activeTabId === filename) {
                            lastSavedCode = code;
                            setPlaywrightCode(code);
                        }
                    }
                })
                .catch(err => console.error('Failed to refresh tab after file_updated:', err));
        }
    }
});

socket.on('propose_change', (data) => {
    chatMessages.querySelectorAll('.chat-message.tool-call').forEach(el => el.remove());
    const { filename, type, old_content, new_content, workspaceName } = data;
    const isSteps = type === 'ai_step';
    pendingCodeSuggestion = {
        code: new_content,
        currentCode: old_content,
        explanation: `Review AI-proposed changes to ${filename}`,
        targetTabId: filename,
        contentType: isSteps ? 'steps' : 'code',
        agentPending: true,
        filename,
        fileType: type,
        workspaceName: workspaceName,
    };
    showCodePreview();
});

// ========================================
// CODE PREVIEW PANEL FUNCTIONALITY
// ========================================

function showCodePreview() {
    if (!pendingCodeSuggestion) return;

    const contentType = pendingCodeSuggestion.contentType || 'code';
    const isSteps = contentType === 'steps';

    // Update panel labels based on content type
    const previewLabel = document.querySelector('.code-preview-label');
    if (previewLabel) {
        previewLabel.textContent = isSteps ? 'TEST STEPS SUGGESTION' : 'CODE SUGGESTION';
    }

    // Update diff column headers
    const diffHeaders = document.querySelectorAll('.diff-column-header');
    if (diffHeaders.length >= 2) {
        diffHeaders[0].textContent = isSteps ? 'CURRENT STEPS' : 'CURRENT CODE';
        diffHeaders[1].textContent = isSteps ? 'SUGGESTED STEPS (AI)' : 'SUGGESTED CODE (AI)';
    }

    // Set explanation
    codePreviewExplanation.textContent = pendingCodeSuggestion.explanation;

    // Generate diff
    highlightCodeDiff();

    // Show panel
    codePreviewPanel.classList.add('open');

    addLogEntry('info', isSteps ? '📝 Test steps suggestion ready for review' : '📝 Code suggestion ready for review');
}

function highlightCodeDiff() {
    const currentLines = (pendingCodeSuggestion.currentCode || '').split('\n');
    const suggestedLines = pendingCodeSuggestion.code.split('\n');

    let currentHtml = '';
    let suggestedHtml = '';

    const maxLines = Math.max(currentLines.length, suggestedLines.length);

    for (let i = 0; i < maxLines; i++) {
        const currentLine = currentLines[i] || '';
        const suggestedLine = suggestedLines[i] || '';

        const escapedCurrent = escapeHtmlForDiff(currentLine);
        const escapedSuggested = escapeHtmlForDiff(suggestedLine);

        if (currentLine !== suggestedLine) {
            if (currentLine && !suggestedLine) {
                currentHtml += `<div class="diff-line-removed">${escapedCurrent}</div>`;
                suggestedHtml += `<div></div>`;
            } else if (!currentLine && suggestedLine) {
                currentHtml += `<div></div>`;
                suggestedHtml += `<div class="diff-line-added">${escapedSuggested}</div>`;
            } else {
                currentHtml += `<div class="diff-line-removed">${escapedCurrent}</div>`;
                suggestedHtml += `<div class="diff-line-added">${escapedSuggested}</div>`;
            }
        } else {
            currentHtml += `<div>${escapedCurrent}</div>`;
            suggestedHtml += `<div>${escapedSuggested}</div>`;
        }
    }

    // Handle empty current content
    if (!pendingCodeSuggestion.currentCode) {
        const contentType = pendingCodeSuggestion.contentType || 'code';
        const emptyMessage = contentType === 'steps' ? 'No existing steps in editor' : 'No existing code in editor';
        currentHtml = `<div style="color: var(--ctp-overlay1); font-style: italic;">${emptyMessage}</div>`;
    }

    codePreviewCurrent.innerHTML = currentHtml;
    codePreviewSuggested.innerHTML = suggestedHtml;
}

function escapeHtmlForDiff(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function closeCodePreview() {
    pendingCodeSuggestion = null;
    codePreviewPanel.classList.remove('open');
}

// Button Event Listeners for Code Preview
acceptCodeBtn.addEventListener('click', () => {
    if (!pendingCodeSuggestion) return;

    if (pendingCodeSuggestion.agentPending) {
        // Agent-proposed change: commit to DB via API, then apply to editor
        const { filename, fileType, workspaceName, code } = pendingCodeSuggestion;
        const isSteps = fileType === 'ai_step';
        const apiPath = isSteps
            ? `/api/workspaces/${workspaceName}/tree/ai_steps/${encodeURIComponent(filename)}`
            : `/api/workspaces/${workspaceName}/tree/saved_tests/${encodeURIComponent(filename)}`;
        const body = isSteps ? { steps: code } : { code };

        closeCodePreview();

        authFetch(apiPath, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                // Apply to editor if the tab is open
                setPlaywrightCode(code);
                const tab = openTabs.find(t => t.id === filename);
                if (tab) {
                    tab.code = code;
                    tab.isDirty = false;
                    if (activeTabId === filename) lastSavedCode = code;
                    renderTabs();
                }
                delete testCache[filename];
                if (currentWorkspaceName) loadFileExplorer();
                addLogEntry('success', `✓ Changes to ${filename} saved`);
                appendChatMessage('system', `✓ Changes accepted and saved to ${filename}`);
            })
            .catch(err => {
                addLogEntry('error', `Failed to save changes: ${err.message}`);
                appendChatMessage('system', `✗ Failed to save changes: ${err.message}`);
            });
        return;
    }

    // Non-agent flow: apply code to editor only
    setPlaywrightCode(pendingCodeSuggestion.code);

    if (pendingCodeSuggestion.targetTabId) {
        const tab = openTabs.find(t => t.id === pendingCodeSuggestion.targetTabId);
        if (tab) {
            tab.code = pendingCodeSuggestion.code;
            tab.isDirty = true;
            renderTabs();
        }
    } else {
        const tempId = 'chat_' + Date.now();
        openTab(tempId, 'AI Generated', pendingCodeSuggestion.code);
        const tab = openTabs.find(t => t.id === tempId);
        if (tab) {
            tab.isDirty = true;
            lastSavedCode = '';
        }
        renderTabs();
    }

    const contentType = pendingCodeSuggestion.contentType || 'code';
    const isSteps = contentType === 'steps';
    const acceptMessage = isSteps ? '✓ Test steps suggestion accepted and applied' : '✓ Code suggestion accepted and applied';
    const chatMessage = isSteps ? '✓ Steps applied to editor' : '✓ Code applied to editor';

    addLogEntry('success', acceptMessage);
    appendChatMessage('system', chatMessage);

    closeCodePreview();
});

rejectCodeBtn.addEventListener('click', () => {
    if (!pendingCodeSuggestion) return;

    const contentType = pendingCodeSuggestion.contentType || 'code';
    const isSteps = contentType === 'steps';
    const rejectMessage = isSteps ? '✗ Test steps suggestion rejected' : '✗ Code suggestion rejected';

    addLogEntry('info', rejectMessage);
    appendChatMessage('system', '✗ Suggestion rejected - editor unchanged');

    closeCodePreview();
});

closePreviewBtn.addEventListener('click', () => {
    closeCodePreview();
});

// Keyboard Shortcuts for Code Preview
document.addEventListener('keydown', (e) => {
    if (!codePreviewPanel.classList.contains('open')) return;

    // Cmd/Ctrl + Enter = Accept
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        acceptCodeBtn.click();
    }

    // Escape = Close (only if preview panel is open, not chat sidebar)
    if (e.key === 'Escape') {
        e.preventDefault();
        closePreviewBtn.click();
    }
});

// Event listeners for chat
sendChatBtn.addEventListener('click', sendChatMessage);

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        sendChatMessage();
    }
});

// ESC to close chat (code preview takes priority if open)
document.addEventListener('keydown', (e) => {
    // Code preview ESC handling is in the keyboard shortcuts section above
    // Only close chat if code preview is NOT open
    if (e.key === 'Escape' &&
        aiChatSidebar.classList.contains('open') &&
        !codePreviewPanel.classList.contains('open')) {
        closeChat();
    }
    if (e.key === 'Escape') hideContextMenu();
});

// Cmd+S (Mac) / Ctrl+S (Windows/Linux) to save file
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault(); // Prevent default browser save dialog
        saveCurrentTest(); // Save current test
    }
});

clearChatBtn.addEventListener('click', () => {
    if (confirm('Clear all chat messages?')) {
        chatMessages.innerHTML = '';
        hideChatThinking();
        socket.emit('clear_chat', { workspaceName: currentWorkspaceName });
        appendChatMessage('system', 'Chat history cleared');
    }
});

// Drag and Drop functionality
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleImageFile(files[0]);
    }
});

// File input functionality
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleImageFile(e.target.files[0]);
    }
});

// Remove image
removeImageBtn.addEventListener('click', () => {
    currentImage = null;
    imagePreviewContainer.style.display = 'none';
    imagePreview.src = '';
    fileInput.value = '';
});

// Handle image file
function handleImageFile(file) {
    // Check if it's an image
    if (!file.type.startsWith('image/')) {
        alert('Please select an image file');
        return;
    }

    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('Image size must be less than 10MB');
        return;
    }

    // Read file as base64
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        imagePreview.src = currentImage;
        imagePreviewContainer.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

// ========== AUTHENTICATION FUNCTIONS ==========

function showLoginModal() {
    authPage.classList.remove('hidden');
    document.querySelector('.vscode-layout').classList.add('auth-hidden');
    switchAuthTab('login');
}

function showRegisterModal() {
    authPage.classList.remove('hidden');
    document.querySelector('.vscode-layout').classList.add('auth-hidden');
    switchAuthTab('register');
}

function hideAuthModals() {
    authPage.classList.add('hidden');
    document.querySelector('.vscode-layout').classList.remove('auth-hidden');
}

function switchAuthTab(tab) {
    authTabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    authTabsContainer.dataset.active = tab;
    loginForm.classList.toggle('active', tab === 'login');
    registerForm.classList.toggle('active', tab === 'register');
    loginError.style.display = 'none';
    registerError.style.display = 'none';
}

async function checkAuthentication() {
    try {
        const response = await authFetch('/api/check-auth');
        const data = await response.json();

        if (data.authenticated) {
            currentUser = data.user;
            hideAuthModals();
            await loadUserWorkspaces();
            return true;
        }

        // Access token may be expired. Try refreshing silently before prompting login.
        if (refreshToken) {
            try {
                const refreshResp = await fetch('/api/refresh-token', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: refreshToken })
                });
                if (refreshResp.ok) {
                    const refreshData = await refreshResp.json();
                    storeTokens(refreshData.access_token, refreshData.refresh_token);
                    // Reconnect socket with the refreshed token
                    socket.io.opts.query = { token: refreshData.access_token };
                    socket.disconnect().connect();

                    // Retry with the new access token
                    const retryResp = await authFetch('/api/check-auth');
                    const retryData = await retryResp.json();
                    if (retryData.authenticated) {
                        currentUser = retryData.user;
                        hideAuthModals();
                        await loadUserWorkspaces();
                        return true;
                    }
                }
            } catch (refreshErr) {
                console.warn('Silent token refresh failed:', refreshErr);
            }
            // Refresh token is also expired or invalid — clear everything
            clearTokens();
        }

        // Try auto-login from server-side .env credentials before showing modal
        try {
            const autoResp = await fetch('/api/auto-login', { method: 'POST' });
            if (autoResp.ok) {
                const autoData = await autoResp.json();
                storeTokens(autoData.access_token, autoData.refresh_token);
                // The socket was initialized with the old/expired token.
                // Update its auth query and reconnect so handle_connect accepts it.
                socket.io.opts.query = { token: autoData.access_token };
                socket.disconnect().connect();
                currentUser = autoData.user;
                hideAuthModals();
                await loadUserWorkspaces();
                return true;
            }
        } catch (autoErr) {
            console.warn('Auto-login not available:', autoErr);
        }

        showLoginModal();
        return false;
    } catch (error) {
        console.error('Auth check failed:', error);
        showLoginModal();
        return false;
    }
}

async function loadUserWorkspaces() {
    try {
        await ensurePreferencesCached();
        const response = await authFetch('/api/current-user');
        if (!response.ok) {
            if (response.status === 401) {
                showLoginModal();
                return;
            }
            throw new Error('Failed to get user info');
        }

        const data = await response.json();
        currentUser = data.user;

        console.log('User authenticated:', currentUser.username);

        // Load workspaces from local filesystem
        await loadWorkspaces();
    } catch (error) {
        console.error('Failed to load user workspaces:', error);
    }
}

async function handleLogin(event) {
    event.preventDefault();

    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const remember = document.getElementById('login-remember').checked;

    const btn = document.getElementById('login-submit-btn');
    const btnText = btn.querySelector('.auth-submit-text');
    const btnSpinner = btn.querySelector('.auth-submit-spinner');
    btn.disabled = true;
    btnText.style.display = 'none';
    btnSpinner.style.display = '';

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, remember })
        });

        const data = await response.json();

        if (response.ok) {
            // Store JWT tokens
            storeTokens(data.access_token, data.refresh_token);

            currentUser = data.user;
            hideAuthModals();
            showAppOverlay('Loading workspace…');
            addLogEntry('info', `👋 Welcome back, ${currentUser.username}!`);

            // Reconnect socket with the new authenticated token
            socket.io.opts.query = { token: authToken };
            socket.disconnect();
            socket.connect();

            // Update username display
            if (currentUsernameEl) {
                currentUsernameEl.textContent = currentUser.username;
            }

            // Initialize CodeMirror editor (skipped on page load when not authenticated)
            initializeCodeMirror();

            // Load workspaces (will restore saved workspace from localStorage)
            await loadWorkspaces();

            // Restore theme from DB (overrides localStorage if user changed it elsewhere)
            await restoreThemeFromDb();

            // Reload file lists for the current workspace
            if (hasFileExplorer && currentWorkspaceName) {
                loadFileExplorer();
                loadAiSteps();
            }

            // Open dashboard tab if no tabs
            if (openTabs.length === 0) {
                openDashboardTab();
            }

            hideAppOverlay();
        } else {
            loginError.textContent = data.error || 'Login failed';
            loginError.style.display = 'block';
        }
    } catch (error) {
        console.error('Login error:', error);
        loginError.textContent = 'Login failed. Please try again.';
        loginError.style.display = 'block';
        hideAppOverlay();
    } finally {
        btn.disabled = false;
        btnText.style.display = '';
        btnSpinner.style.display = 'none';
    }
}

async function handleRegister(event) {
    event.preventDefault();

    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const passwordConfirm = document.getElementById('register-password-confirm').value;

    // Client-side validation (before showing loading state)
    if (password !== passwordConfirm) {
        registerError.textContent = 'Passwords do not match';
        registerError.style.display = 'block';
        return;
    }

    const btn = document.getElementById('register-submit-btn');
    const btnText = btn.querySelector('.auth-submit-text');
    const btnSpinner = btn.querySelector('.auth-submit-spinner');
    btn.disabled = true;
    btnText.style.display = 'none';
    btnSpinner.style.display = '';

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();

        if (response.ok) {
            // Store JWT tokens
            storeTokens(data.access_token, data.refresh_token);

            currentUser = data.user;
            hideAuthModals();
            showAppOverlay('Setting up workspace…');
            addLogEntry('info', `🎉 Welcome to AutoGen Web Tester, ${currentUser.username}!`);

            // Connect socket with the new authenticated token
            socket.io.opts.query = { token: authToken };
            socket.disconnect();
            socket.connect();

            // Update username display
            if (currentUsernameEl) {
                currentUsernameEl.textContent = currentUser.username;
            }

            // Initialize CodeMirror editor (skipped on page load when not authenticated)
            initializeCodeMirror();

            // Load workspaces (user's default workspace will be loaded)
            await loadWorkspaces();

            // Restore theme from DB
            await restoreThemeFromDb();

            // Reload file lists for the current workspace
            if (hasFileExplorer && currentWorkspaceName) {
                loadFileExplorer();
                loadAiSteps();
            }

            // Open dashboard tab
            if (openTabs.length === 0) {
                openDashboardTab();
            }

            hideAppOverlay();
        } else {
            registerError.textContent = data.error || 'Registration failed';
            registerError.style.display = 'block';
        }
    } catch (error) {
        console.error('Registration error:', error);
        registerError.textContent = 'Registration failed. Please try again.';
        registerError.style.display = 'block';
        hideAppOverlay();
    } finally {
        btn.disabled = false;
        btnText.style.display = '';
        btnSpinner.style.display = 'none';
    }
}

// Event listeners for auth page
if (loginForm) loginForm.addEventListener('submit', handleLogin);
if (registerForm) registerForm.addEventListener('submit', handleRegister);
authTabs.forEach(tab => {
    tab.addEventListener('click', () => switchAuthTab(tab.dataset.tab));
});

// ========== END AUTHENTICATION FUNCTIONS ==========

// ========== WORKSPACE MANAGEMENT FUNCTIONS ==========

async function loadWorkspaces() {
    try {
        const response = await authFetch('/api/workspaces');
        if (!response.ok) {
            throw new Error('Failed to load workspaces');
        }

        const data = await response.json();
        userWorkspaces = data.workspaces;

        // Show first-workspace modal if user has none
        if (!userWorkspaces || userWorkspaces.length === 0) {
            showFirstWorkspaceModal();
            return;
        }

        // Update dropdown - safe since option values come from server data
        while (workspaceDropdown.firstChild) workspaceDropdown.removeChild(workspaceDropdown.firstChild);
        userWorkspaces.forEach(workspace => {
            const option = document.createElement('option');
            option.value = workspace.name;
            option.textContent = workspace.name;
            workspaceDropdown.appendChild(option);
        });

        // Set current workspace - try localStorage, then default
        if (userWorkspaces.length > 0) {
            let savedWorkspaceName = localStorage.getItem('pref_selectedWorkspaceName');

            if (savedWorkspaceName) {
                const hasAccess = userWorkspaces.some(w => w.name === savedWorkspaceName);
                if (hasAccess) {
                    currentWorkspaceName = savedWorkspaceName;
                } else {
                    currentWorkspaceName = userWorkspaces[0].name;
                }
            } else if (!currentWorkspaceName) {
                currentWorkspaceName = userWorkspaces[0].name;
            }
            // Persist the selection so it survives page reloads and re-login
            localStorage.setItem('pref_selectedWorkspaceName', currentWorkspaceName);
        }

        // Select current workspace
        workspaceDropdown.value = currentWorkspaceName;

        // Load file explorer and AI steps
        if (hasFileExplorer) {
            loadFileExplorer();
            loadAiSteps();
        }

    } catch (error) {
        console.error('Failed to load workspaces:', error);
    }
}

function loadWorkspaceDetails() {
    // No-op: workspace details are no longer fetched from the DB
}

function displayWorkspaceMembers() {
    // No-op: member management removed
}

async function switchWorkspace(name) {
    const wsSwitchOverlay = document.getElementById('workspace-switch-overlay');
    if (wsSwitchOverlay) wsSwitchOverlay.style.display = 'flex';

    try {
        currentWorkspaceName = name;

        // Sync the dropdown immediately so it reflects the selection
        if (workspaceDropdown) workspaceDropdown.value = currentWorkspaceName;

        // Close all open tabs — tests belong to a specific workspace
        openTabs = [];
        activeTabId = null;
        lastSavedCode = '';
        setPlaywrightCode('');
        renderTabs();
        saveTabsState();

        // Save selected workspace to localStorage
        localStorage.setItem('pref_selectedWorkspaceName', currentWorkspaceName);

        // Reload file lists for new workspace
        if (hasFileExplorer) {
            loadFileExplorer();
            loadAiSteps();
        }

        // Re-open dashboard tab so the main area shows workspace stats (not "No file open")
        openDashboardTab();

        addLogEntry('info', `Switched to workspace: ${currentWorkspaceName}`);
    } finally {
        if (wsSwitchOverlay) wsSwitchOverlay.style.display = 'none';
    }
}

let _isFirstWorkspaceFlow = false;

function showFirstWorkspaceModal() {
    _isFirstWorkspaceFlow = true;
    // Pre-fill with a sensible default
    document.getElementById('workspace-name').value = `${currentUser.username}'s Workspace`;
    // Update modal header for first-time flow
    const header = newWorkspaceModal.querySelector('.modal-header h2');
    if (header) header.textContent = 'Welcome! Create your first workspace';
    // Hide cancel/close buttons so user must create one
    closeNewWorkspaceBtns.forEach(btn => btn.style.display = 'none');
    newWorkspaceError.style.display = 'none';
    newWorkspaceModal.style.display = 'block';
}

async function createWorkspace(event) {
    event.preventDefault();

    const name = document.getElementById('workspace-name').value.trim();
    const cloneUrlInput = document.getElementById('clone-url-input');
    const clone_url = cloneUrlInput ? cloneUrlInput.value.trim() : '';

    const submitBtn = document.getElementById('create-workspace-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = clone_url ? 'Cloning…' : 'Creating…';

    try {
        const response = await authFetch('/api/workspaces', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, ...(clone_url && { clone_url }) })
        });

        const data = await response.json();

        if (response.ok) {
            newWorkspaceModal.style.display = 'none';
            newWorkspaceForm.reset();

            // Restore cancel/close buttons and header for future use
            if (_isFirstWorkspaceFlow) {
                _isFirstWorkspaceFlow = false;
                closeNewWorkspaceBtns.forEach(btn => btn.style.display = '');
                const header = newWorkspaceModal.querySelector('.modal-header h2');
                if (header) header.textContent = 'Create New Workspace';
            }

            addLogEntry('info', `Created workspace: ${name}`);

            // Reload workspaces (updates dropdown), then switch to new one
            await loadWorkspaces();
            await switchWorkspace(data.workspace.name);
        } else {
            newWorkspaceError.textContent = data.error || 'Failed to create workspace';
            newWorkspaceError.style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to create workspace:', error);
        newWorkspaceError.textContent = 'Failed to create workspace';
        newWorkspaceError.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create';
    }
}

function inviteMember() {
    // No-op: invite member functionality removed
}

function removeMember() {
    // No-op: remove member functionality removed
}

async function handleLogout() {
    try {
        await authFetch('/api/logout', { method: 'POST' });
    } catch (error) {
        console.error('Logout error:', error);
    }
    // Always clear tokens and state regardless of server response
    clearTokens();
    currentUser = null;
    currentWorkspaceName = null;
    userWorkspaces = [];
    showLoginModal();
    addLogEntry('info', '👋 Logged out successfully');
}

// ========== WORKSPACE RENAME ==========
const renameWorkspaceBtn = document.getElementById('rename-workspace-btn');
const workspaceRenameRow = document.getElementById('workspace-rename-row');
const workspaceRenameInput = document.getElementById('workspace-rename-input');
const workspaceRenameConfirm = document.getElementById('workspace-rename-confirm');
const workspaceRenameCancel = document.getElementById('workspace-rename-cancel');

function showRenameRow() {
    workspaceRenameRow.style.display = 'flex';
    document.querySelector('.workspace-dropdown-row').style.display = 'none';
    workspaceRenameInput.value = currentWorkspaceName || '';
    workspaceRenameInput.focus();
    workspaceRenameInput.select();
}

function hideRenameRow() {
    workspaceRenameRow.style.display = 'none';
    document.querySelector('.workspace-dropdown-row').style.display = 'flex';
}

async function confirmRename() {
    const newName = workspaceRenameInput.value.trim();
    if (!newName || newName === currentWorkspaceName) {
        hideRenameRow();
        return;
    }

    try {
        const res = await authFetch(`/api/workspaces/${encodeURIComponent(currentWorkspaceName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName }),
        });
        const data = await res.json();
        if (!res.ok) {
            alert(data.error || 'Failed to rename workspace');
            return;
        }
        // Update local state and reload workspaces
        localStorage.setItem('pref_selectedWorkspaceName', newName);
        currentWorkspaceName = newName;
        hideRenameRow();
        await loadWorkspaces();
    } catch (err) {
        alert('Failed to rename workspace: ' + err);
    }
}

if (renameWorkspaceBtn) renameWorkspaceBtn.addEventListener('click', showRenameRow);
if (workspaceRenameConfirm) workspaceRenameConfirm.addEventListener('click', confirmRename);
if (workspaceRenameCancel) workspaceRenameCancel.addEventListener('click', hideRenameRow);
if (workspaceRenameInput) workspaceRenameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') confirmRename();
    if (e.key === 'Escape') hideRenameRow();
});

// Event listeners for workspace management
if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);
if (workspaceDropdown) workspaceDropdown.addEventListener('change', (e) => switchWorkspace(e.target.value));
if (newWorkspaceBtn) newWorkspaceBtn.addEventListener('click', () => {
    newWorkspaceModal.style.display = 'block';
    newWorkspaceError.style.display = 'none';
});

if (newWorkspaceForm) newWorkspaceForm.addEventListener('submit', createWorkspace);

// Close modal buttons
closeNewWorkspaceBtns.forEach(btn => {
    btn.addEventListener('click', () => newWorkspaceModal.style.display = 'none');
});

// ========== END WORKSPACE MANAGEMENT FUNCTIONS ==========

// ========== THEME MANAGEMENT ==========
const VALID_THEMES = ['mocha', 'macchiato', 'frappe', 'latte'];

// macOS title bar colors to match each Catppuccin theme's --ctp-base
const THEME_TITLEBAR = {
    mocha:     { hex: '#1e1e2e', dark: true  },
    macchiato: { hex: '#24273a', dark: true  },
    frappe:    { hex: '#303446', dark: true  },
    latte:     { hex: '#eff1f5', dark: false },
};

function applyTheme(themeName) {
    if (!VALID_THEMES.includes(themeName)) themeName = 'mocha';
    document.documentElement.setAttribute('data-theme', themeName);
    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === themeName);
    });
    // Persist in cookie so the server can inject it on next page load (login page etc.)
    document.cookie = `theme=${themeName}; path=/; max-age=31536000; SameSite=Lax`;
    try {
        if (liveViewerIframe && liveViewerIframe.contentWindow) liveViewerIframe.contentWindow.postMessage({ type: 'theme', theme: themeName }, '*');
    } catch (_) {}
    // Sync the native macOS title bar when running inside PyWebView
    const tb = THEME_TITLEBAR[themeName] || THEME_TITLEBAR.mocha;
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.set_title_bar_color(tb.hex, tb.dark);
    }
}

function initThemePicker() {
    // Read from both keys for backwards compatibility
    const savedTheme = localStorage.getItem('pref_theme')
        ? JSON.parse(localStorage.getItem('pref_theme'))
        : (localStorage.getItem('theme') || 'mocha');
    applyTheme(savedTheme);

    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.theme;
            applyTheme(theme);
            savePreferenceToDb('theme', theme);
        });
    });
}

async function restoreThemeFromDb() {
    const dbPrefs = await loadPreferencesFromDb();
    if (dbPrefs && dbPrefs.theme && VALID_THEMES.includes(dbPrefs.theme)) {
        applyTheme(dbPrefs.theme);
        localStorage.setItem('theme', dbPrefs.theme);
    }
}
// ========== END THEME MANAGEMENT ==========

// ========== TOAST ==========
function showToast(message, type = 'error') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-visible'));
    setTimeout(() => {
        toast.classList.remove('toast-visible');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, 3500);
}
// ========== END TOAST ==========

// Load default example on page load
window.addEventListener('load', async () => {
    // Initialize theme picker (apply saved theme from localStorage immediately)
    initThemePicker();

    // Check authentication first
    const isAuthenticated = await checkAuthentication();

    if (!isAuthenticated) {
        // Show app anyway so recording works without login (record since app loads)
        hideAuthModals();
        if (currentUsernameEl) currentUsernameEl.textContent = 'Not logged in';
        initializeCodeMirror();
        if (openTabs.length === 0) {
            openDashboardTab();
        }
        addLogEntry('info', '👋 Record a test anytime with the Record button. Log in to save tests to a workspace.');
        dismissLoadingOverlay();
        return;
    }

    // Restore theme from DB (may override localStorage if DB has a different value)
    restoreThemeFromDb();

    addLogEntry('info', '👋 Welcome to AutoGen Web Tester!');
    addLogEntry('info', '🤖 Create AI Steps in the file explorer to run natural language tests');
    addLogEntry('info', '💬 Use AI Chat to generate and modify Playwright code');

    // Update username display
    if (currentUsernameEl && currentUser) {
        currentUsernameEl.textContent = currentUser.username;
    }

    // Workspace dropdown and details already set by loadUserWorkspaces() from checkAuthentication

    // Initialize CodeMirror editor
    initializeCodeMirror();

    // Restore previously open tabs
    await restoreTabsState();

    // Open dashboard tab if no tabs were restored
    if (openTabs.length === 0) {
        openDashboardTab();
    }

    dismissLoadingOverlay();
});

// ========================================
// ACTIVITY BAR SWITCHING
// ========================================

function switchPanel(panelId) {
    document.querySelectorAll('.activity-bar-btn[data-panel]').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.panel === panelId));
    document.querySelectorAll('.sidebar-panel').forEach(p =>
        p.classList.toggle('sidebar-panel--hidden', p.id !== `panel-${panelId}`));
    if (panelId === 'scm') {
        refreshScmPanel();
        loadGithubConfig();
    }
}

document.querySelectorAll('.activity-bar-btn[data-panel]').forEach(btn =>
    btn.addEventListener('click', () => switchPanel(btn.dataset.panel)));


// ========================================
// UNIFIED TREE ROOT COLLAPSE
// ========================================

function initUnifiedTree() {
    const testsRootRow = document.getElementById('tests-root-row');
    const testsRootNode = document.getElementById('tests-root-node');
    if (testsRootRow && testsRootNode) {
        testsRootRow.addEventListener('click', (e) => {
            if (!e.target.closest('.file-explorer-header-actions')) {
                testsRootNode.classList.toggle('expanded');
            }
        });
    }

    const aiStepsRootRow = document.getElementById('ai-steps-root-row');
    const aiStepsRootNode = document.getElementById('ai-steps-root-node');
    if (aiStepsRootRow && aiStepsRootNode) {
        aiStepsRootRow.addEventListener('click', (e) => {
            if (!e.target.closest('.file-explorer-header-actions')) {
                aiStepsRootNode.classList.toggle('expanded');
            }
        });
    }

    // Wire duplicate header buttons to the primary ones
    const newFolderBtn2 = document.getElementById('new-folder-tests-btn-2');
    const newFolderBtn1 = document.getElementById('new-folder-tests-btn');
    if (newFolderBtn2 && newFolderBtn1) {
        newFolderBtn2.addEventListener('click', () => newFolderBtn1.click());
    }
    const newTestBtn2 = document.getElementById('new-test-btn-2');
    const newTestBtn1 = document.getElementById('new-test-btn');
    if (newTestBtn2 && newTestBtn1) {
        newTestBtn2.addEventListener('click', () => newTestBtn1.click());
    }
}


// ========================================
// SCM PANEL
// ========================================

async function refreshScmPanel() {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/status`);
        const state = await res.json();
        if (res.ok) renderScmState(state);
    } catch (e) {
        console.warn('SCM refresh failed:', e);
    }
}

function renderScmState(state) {
    // Branch name
    const branchEl = document.getElementById('scm-branch-name');
    if (branchEl) branchEl.textContent = state.branch || '—';

    // Change count badge
    const totalChanges = (state.staged || []).length + (state.unstaged || []).length + (state.untracked || []).length;
    const badge = document.getElementById('scm-change-count');
    if (badge) {
        if (totalChanges > 0) {
            badge.textContent = totalChanges;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }

    // Staged
    renderScmChangeList('scm-staged-list', 'scm-staged-count', state.staged || [], 'staged');
    // Unstaged
    renderScmChangeList('scm-unstaged-list', 'scm-unstaged-count', state.unstaged || [], 'unstaged');
    // Untracked
    const untracked = (state.untracked || []).map(p => ({ path: p, status: 'U' }));
    renderScmChangeList('scm-untracked-list', 'scm-untracked-count', untracked, 'untracked');
}

function renderScmChangeList(listId, countId, items, listType) {
    const list = document.getElementById(listId);
    const countEl = document.getElementById(countId);
    if (countEl) countEl.textContent = items.length;
    if (!list) return;
    list.innerHTML = '';

    items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'scm-change-item';

        const badge = document.createElement('span');
        badge.className = `git-status-badge ${item.status || 'M'}`;
        badge.textContent = item.status || 'M';

        const pathSpan = document.createElement('span');
        pathSpan.className = 'scm-change-path';
        pathSpan.title = item.path;
        pathSpan.textContent = item.path;

        // Stage/unstage action button
        const actionBtn = document.createElement('button');
        actionBtn.className = 'btn-icon-small scm-change-action';
        const actionIcon = document.createElement('i');

        if (listType === 'staged') {
            actionIcon.className = 'lni lni-minus-circle';
            actionBtn.title = 'Unstage';
            actionBtn.appendChild(actionIcon);
            actionBtn.addEventListener('click', (e) => { e.stopPropagation(); scmUnstageFile(item.path); });
        } else {
            actionIcon.className = 'lni lni-plus-circle';
            actionBtn.title = 'Stage';
            actionBtn.appendChild(actionIcon);
            actionBtn.addEventListener('click', (e) => { e.stopPropagation(); scmStageFile(item.path); });
        }

        // Click row to view diff
        const isStaged = listType === 'staged';
        row.addEventListener('click', () => showScmDiff(item.path, isStaged));

        row.appendChild(badge);
        row.appendChild(pathSpan);
        row.appendChild(actionBtn);
        list.appendChild(row);
    });
}

async function scmStageFile(filepath) {
    if (!currentWorkspaceName) return;
    await authFetch(`/api/workspaces/${currentWorkspaceName}/git/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filepath })
    });
    refreshScmPanel();
}

async function scmUnstageFile(filepath) {
    if (!currentWorkspaceName) return;
    await authFetch(`/api/workspaces/${currentWorkspaceName}/git/unstage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filepath })
    });
    refreshScmPanel();
}

async function scmStageAll() {
    if (!currentWorkspaceName) return;
    await authFetch(`/api/workspaces/${currentWorkspaceName}/git/stage_all`, { method: 'POST' });
    refreshScmPanel();
}

async function scmCommit() {
    if (!currentWorkspaceName) return;
    const msgEl = document.getElementById('scm-commit-msg');
    const message = msgEl ? msgEl.value.trim() : '';
    if (!message) { alert('Please enter a commit message.'); return; }

    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/commit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await res.json();
        if (res.ok) {
            if (msgEl) msgEl.value = '';
            addLogEntry('info', `Committed: ${data.sha ? data.sha.slice(0, 7) : 'ok'} — ${message}`);
            refreshScmPanel();
        } else {
            alert(data.error || 'Commit failed');
        }
    } catch (e) {
        alert('Commit failed: ' + e.message);
    }
}

async function scmPush() {
    if (!currentWorkspaceName) return;
    // If GitHub is connected the stored token is used server-side; no prompt needed.
    const ghCfg = window._githubConfig || {};
    let tokenOverride = null;
    if (!ghCfg.connected) {
        const t = prompt('GitHub Personal Access Token (leave blank if SSH or already configured):');
        if (t === null) return; // user cancelled
        if (t) tokenOverride = t;
    }

    try {
        const body = {};
        if (tokenOverride) body.token = tokenOverride;
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (res.ok) {
            addLogEntry('info', 'Pushed to remote.');
        } else {
            alert(data.error || 'Push failed');
        }
    } catch (e) {
        alert('Push failed: ' + e.message);
    }
}

async function scmPull() {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/pull`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (res.ok) {
            addLogEntry('info', 'Pulled from remote.');
            loadFileExplorer();
            loadAiSteps();
            refreshScmPanel();
        } else {
            alert(data.error || 'Pull failed');
        }
    } catch (e) {
        alert('Pull failed: ' + e.message);
    }
}

async function showScmDiff(filepath, staged) {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/diff?path=${encodeURIComponent(filepath)}&staged=${staged ? '1' : '0'}`);
        const data = await res.json();
        const panel = document.getElementById('scm-diff-panel');
        const content = document.getElementById('scm-diff-content');
        const fp = document.getElementById('scm-diff-filepath');
        if (!panel || !content) return;
        if (fp) fp.textContent = filepath;
        // Colorize diff lines
        const lines = (data.diff || '(no diff)').split('\n');
        content.innerHTML = '';
        lines.forEach(line => {
            const span = document.createElement('span');
            if (line.startsWith('+') && !line.startsWith('+++')) span.className = 'diff-add';
            else if (line.startsWith('-') && !line.startsWith('---')) span.className = 'diff-del';
            else if (line.startsWith('@@') || line.startsWith('diff ')) span.className = 'diff-meta';
            span.textContent = line + '\n';
            content.appendChild(span);
        });
        panel.style.display = 'flex';
    } catch (e) {
        console.warn('Diff failed:', e);
    }
}

async function loadScmBranches() {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/branches`);
        const data = await res.json();
        if (!res.ok) return;
        const list = document.getElementById('scm-branch-list');
        if (!list) return;
        list.innerHTML = '';
        const all = [...(data.local || []), ...(data.remote || [])];
        all.forEach(branch => {
            const item = document.createElement('div');
            item.className = 'scm-branch-item';
            if (branch === data.current) item.classList.add('active');
            const icon = document.createElement('i');
            icon.className = 'lni lni-git';
            const label = document.createElement('span');
            label.textContent = branch;
            item.appendChild(icon);
            item.appendChild(label);
            item.addEventListener('click', () => {
                scmCheckoutBranch(branch);
                document.getElementById('scm-branch-picker').style.display = 'none';
            });
            list.appendChild(item);
        });
    } catch (e) {
        console.warn('loadScmBranches failed:', e);
    }
}

async function scmCheckoutBranch(branch) {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/checkout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ branch })
        });
        const data = await res.json();
        if (res.ok) {
            addLogEntry('info', `Switched to branch: ${branch}`);
            refreshScmPanel();
            loadFileExplorer();
            loadAiSteps();
        } else {
            alert(data.error || 'Checkout failed');
        }
    } catch (e) {
        alert('Checkout failed: ' + e.message);
    }
}

function initScmPanel() {
    // Refresh button
    const refreshBtn = document.getElementById('scm-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', refreshScmPanel);

    // Pull / Push
    const pullBtn = document.getElementById('scm-pull-btn');
    if (pullBtn) pullBtn.addEventListener('click', scmPull);
    const pushBtn = document.getElementById('scm-push-btn');
    if (pushBtn) pushBtn.addEventListener('click', scmPush);

    // Branch toggle
    const branchToggle = document.getElementById('scm-branch-toggle');
    const branchPicker = document.getElementById('scm-branch-picker');
    if (branchToggle && branchPicker) {
        branchToggle.addEventListener('click', () => {
            const isVisible = branchPicker.style.display !== 'none';
            branchPicker.style.display = isVisible ? 'none' : 'block';
            if (!isVisible) loadScmBranches();
        });
    }

    // Branch filter
    const branchFilter = document.getElementById('scm-branch-filter');
    if (branchFilter) {
        branchFilter.addEventListener('input', () => {
            const q = branchFilter.value.toLowerCase();
            document.querySelectorAll('#scm-branch-list .scm-branch-item').forEach(item => {
                item.style.display = item.textContent.toLowerCase().includes(q) ? '' : 'none';
            });
        });
    }

    // Stage all + commit
    const stageAllBtn = document.getElementById('scm-stage-all-btn');
    if (stageAllBtn) stageAllBtn.addEventListener('click', scmStageAll);
    const commitBtn = document.getElementById('scm-commit-btn');
    if (commitBtn) commitBtn.addEventListener('click', scmCommit);

    // Section collapse toggles
    document.querySelectorAll('.scm-section-header[data-toggle]').forEach(header => {
        header.addEventListener('click', () => {
            header.closest('.scm-section').classList.toggle('collapsed');
        });
    });

    // Diff close button
    const diffClose = document.getElementById('scm-diff-close');
    if (diffClose) {
        diffClose.addEventListener('click', () => {
            const panel = document.getElementById('scm-diff-panel');
            if (panel) panel.style.display = 'none';
        });
    }
}
// ========== END SCM PANEL ==========

// ========== GITHUB PANEL ==========

window._githubConfig = null; // cached: {connected, remote_url, owner, repo}

async function loadGithubConfig() {
    if (!currentWorkspaceName) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/config`);
        if (!res.ok) return;
        const cfg = await res.json();
        window._githubConfig = cfg;
        renderGithubStatusRow(cfg);
    } catch (_) { /* silent */ }
}

function renderGithubStatusRow(cfg) {
    const row = document.getElementById('github-status-row');
    const label = document.getElementById('github-status-label');
    const actions = document.getElementById('github-status-actions');
    const repoLink = document.getElementById('github-repo-link');
    const overflowWrapper = document.getElementById('github-overflow-wrapper');
    if (!row) return;

    if (cfg && cfg.connected) {
        row.className = 'github-status-row github-status-connected';
        label.style.display = 'none';
        actions.style.display = 'none';
        if (repoLink) {
            const repoUrl = cfg.remote_url.replace(/\.git$/, '');
            repoLink.href = repoUrl.startsWith('https://') ? repoUrl : `https://github.com/${cfg.owner}/${cfg.repo}`;
            repoLink.textContent = `${cfg.owner}/${cfg.repo}`;
            repoLink.style.display = '';
        }
        if (overflowWrapper) overflowWrapper.style.display = '';
    } else {
        row.className = 'github-status-row github-status-disconnected';
        label.style.display = '';
        label.textContent = 'Not connected to GitHub';
        actions.style.display = '';
        if (repoLink) repoLink.style.display = 'none';
        if (overflowWrapper) overflowWrapper.style.display = 'none';
    }
}

function openGithubWizard() {
    const modal = document.getElementById('github-wizard-modal');
    if (!modal) return;
    // Reset to step 0
    document.getElementById('github-wizard-step-0').style.display = '';
    document.getElementById('github-wizard-step-connect').style.display = 'none';
    document.getElementById('github-wizard-step-create').style.display = 'none';
    document.getElementById('github-wizard-step-progress').style.display = 'none';
    document.getElementById('github-wizard-title').textContent = 'Connect to GitHub';
    // Clear inputs
    ['github-remote-url','github-pat-connect','github-new-repo-name','github-new-repo-desc','github-pat-create'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const privCb = document.getElementById('github-new-repo-private');
    if (privCb) privCb.checked = true;
    ['github-connect-error','github-create-error'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    modal.style.display = 'flex';
}

function closeGithubWizard() {
    const modal = document.getElementById('github-wizard-modal');
    if (modal) modal.style.display = 'none';
}

function showGithubWizardProgress(msg) {
    ['github-wizard-step-0','github-wizard-step-connect','github-wizard-step-create'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    const step = document.getElementById('github-wizard-step-progress');
    const msgEl = document.getElementById('github-wizard-progress-msg');
    if (step) step.style.display = '';
    if (msgEl) msgEl.textContent = msg || 'Working…';
}

function showGithubWizardError(stepId, msg) {
    const errEl = document.getElementById(stepId);
    if (!errEl) return;
    errEl.textContent = msg;
    errEl.style.display = '';
    // Return to the form step
    document.getElementById('github-wizard-step-progress').style.display = 'none';
    if (stepId === 'github-connect-error') document.getElementById('github-wizard-step-connect').style.display = '';
    if (stepId === 'github-create-error') document.getElementById('github-wizard-step-create').style.display = '';
}

async function githubConnectSubmit() {
    const remoteUrl = (document.getElementById('github-remote-url') || {}).value?.trim();
    const pat = (document.getElementById('github-pat-connect') || {}).value?.trim();
    if (!remoteUrl || !pat) {
        showGithubWizardError('github-connect-error', 'Please fill in both fields.');
        return;
    }
    showGithubWizardProgress('Connecting to GitHub…');
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ remote_url: remoteUrl, pat })
        });
        const data = await res.json();
        if (!res.ok) {
            showGithubWizardError('github-connect-error', data.error || 'Connection failed.');
            return;
        }
        window._githubConfig = data;
        renderGithubStatusRow(data);
        closeGithubWizard();
        addLogEntry('info', `Connected to GitHub: ${data.owner}/${data.repo}`);
    } catch (e) {
        showGithubWizardError('github-connect-error', 'Network error: ' + e.message);
    }
}

async function githubCreateRepoSubmit() {
    const repoName = (document.getElementById('github-new-repo-name') || {}).value?.trim();
    const pat = (document.getElementById('github-pat-create') || {}).value?.trim();
    const description = (document.getElementById('github-new-repo-desc') || {}).value?.trim();
    const isPrivate = document.getElementById('github-new-repo-private')?.checked ?? true;
    if (!repoName || !pat) {
        showGithubWizardError('github-create-error', 'Repository name and token are required.');
        return;
    }
    showGithubWizardProgress('Creating repository on GitHub…');
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/create-repo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_name: repoName, pat, description, private: isPrivate })
        });
        const data = await res.json();
        if (!res.ok) {
            showGithubWizardError('github-create-error', data.error || 'Repo creation failed.');
            return;
        }
        window._githubConfig = data;
        renderGithubStatusRow(data);
        closeGithubWizard();
        addLogEntry('info', `Created GitHub repo: ${data.owner}/${data.repo}`);
    } catch (e) {
        showGithubWizardError('github-create-error', 'Network error: ' + e.message);
    }
}

async function githubDisconnect() {
    if (!currentWorkspaceName) return;
    if (!confirm('Disconnect this workspace from GitHub? The local repo and files are not affected.')) return;
    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceName}/github/disconnect`, {
            method: 'DELETE'
        });
        if (res.ok) {
            window._githubConfig = { connected: false };
            renderGithubStatusRow({ connected: false });
            addLogEntry('info', 'Disconnected from GitHub.');
        } else {
            const d = await res.json();
            alert(d.error || 'Disconnect failed.');
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}

async function githubSync() {
    // Pull then push using stored token
    if (!currentWorkspaceName) return;
    try {
        const pullRes = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/pull`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
        });
        if (!pullRes.ok) {
            const d = await pullRes.json();
            alert('Pull failed: ' + (d.error || 'unknown error'));
            return;
        }
        const pushRes = await authFetch(`/api/workspaces/${currentWorkspaceName}/git/push`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
        });
        const pd = await pushRes.json();
        if (!pushRes.ok) {
            alert('Push failed: ' + (pd.error || 'unknown error'));
        } else {
            addLogEntry('info', 'Synced with GitHub.');
        }
    } catch (e) {
        alert('Sync error: ' + e.message);
    }
}

function initGithubPanel() {
    // Connect button in status row
    const connectBtn = document.getElementById('github-connect-btn');
    if (connectBtn) connectBtn.addEventListener('click', openGithubWizard);

    // Wizard close
    const closeBtn = document.getElementById('github-wizard-close');
    if (closeBtn) closeBtn.addEventListener('click', closeGithubWizard);
    const modal = document.getElementById('github-wizard-modal');
    if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeGithubWizard(); });

    // Step 0 choices
    const choiceConnect = document.getElementById('github-choice-connect');
    if (choiceConnect) choiceConnect.addEventListener('click', () => {
        document.getElementById('github-wizard-step-0').style.display = 'none';
        document.getElementById('github-wizard-step-connect').style.display = '';
        document.getElementById('github-wizard-title').textContent = 'Connect existing repo';
    });
    const choiceCreate = document.getElementById('github-choice-create');
    if (choiceCreate) choiceCreate.addEventListener('click', () => {
        document.getElementById('github-wizard-step-0').style.display = 'none';
        document.getElementById('github-wizard-step-create').style.display = '';
        document.getElementById('github-wizard-title').textContent = 'Create new repo';
    });

    // Back buttons
    const backConnect = document.getElementById('github-back-from-connect');
    if (backConnect) backConnect.addEventListener('click', () => {
        document.getElementById('github-wizard-step-connect').style.display = 'none';
        document.getElementById('github-wizard-step-0').style.display = '';
        document.getElementById('github-wizard-title').textContent = 'Connect to GitHub';
    });
    const backCreate = document.getElementById('github-back-from-create');
    if (backCreate) backCreate.addEventListener('click', () => {
        document.getElementById('github-wizard-step-create').style.display = 'none';
        document.getElementById('github-wizard-step-0').style.display = '';
        document.getElementById('github-wizard-title').textContent = 'Connect to GitHub';
    });

    // Submit buttons
    const connectSubmit = document.getElementById('github-connect-submit');
    if (connectSubmit) connectSubmit.addEventListener('click', githubConnectSubmit);
    const createSubmit = document.getElementById('github-create-submit');
    if (createSubmit) createSubmit.addEventListener('click', githubCreateRepoSubmit);

    // Overflow menu
    const overflowBtn = document.getElementById('github-overflow-btn');
    const overflowMenu = document.getElementById('github-overflow-menu');
    if (overflowBtn && overflowMenu) {
        overflowBtn.addEventListener('click', e => {
            e.stopPropagation();
            overflowMenu.style.display = overflowMenu.style.display === 'none' ? '' : 'none';
        });
        document.addEventListener('click', () => { overflowMenu.style.display = 'none'; });
    }

    const syncBtn = document.getElementById('github-sync-btn');
    if (syncBtn) syncBtn.addEventListener('click', () => { overflowMenu && (overflowMenu.style.display = 'none'); githubSync(); });

    const copyUrlBtn = document.getElementById('github-copy-url-btn');
    if (copyUrlBtn) copyUrlBtn.addEventListener('click', () => {
        overflowMenu && (overflowMenu.style.display = 'none');
        const cfg = window._githubConfig;
        if (cfg && cfg.remote_url) {
            navigator.clipboard.writeText(cfg.remote_url).then(() => addLogEntry('info', 'Repo URL copied.'));
        }
    });

    const disconnectBtn = document.getElementById('github-disconnect-btn');
    if (disconnectBtn) disconnectBtn.addEventListener('click', () => {
        overflowMenu && (overflowMenu.style.display = 'none');
        githubDisconnect();
    });
}

// ========== END GITHUB PANEL ==========
