// AutoGen Web Tester - Frontend JavaScript

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
let currentWorkspaceId = null;

// ========== USER PREFERENCES SYNC ==========
// Debounce timer for batching preference saves to DB
let _prefSaveTimer = null;
let _pendingPrefUpdates = {};

function savePreferenceToDb(key, value) {
    _pendingPrefUpdates[key] = value;
    if (_prefSaveTimer) clearTimeout(_prefSaveTimer);
    _prefSaveTimer = setTimeout(_flushPreferences, 500);
}

function _flushPreferences() {
    const updates = _pendingPrefUpdates;
    _pendingPrefUpdates = {};
    _prefSaveTimer = null;

    if (Object.keys(updates).length === 0) return;

    authFetch('/api/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferences: updates })
    }).catch(err => console.error('Failed to save preferences to DB:', err));
}

async function loadPreferencesFromDb() {
    try {
        const response = await authFetch('/api/preferences');
        if (!response.ok) return null;
        const data = await response.json();
        return data.preferences || {};
    } catch (err) {
        console.error('Failed to load preferences from DB:', err);
        return null;
    }
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
const inviteMemberBtn = document.getElementById('invite-member-btn');
const workspaceMembersContainer = document.getElementById('workspace-members-container');
const workspaceMembersList = document.getElementById('workspace-members-list');

const newWorkspaceModal = document.getElementById('new-workspace-modal');
const newWorkspaceForm = document.getElementById('new-workspace-form');
const closeNewWorkspaceBtns = document.querySelectorAll('.close-new-workspace');
const newWorkspaceError = document.getElementById('new-workspace-error');

const inviteMemberModal = document.getElementById('invite-member-modal');
const inviteMemberForm = document.getElementById('invite-member-form');
const closeInviteMemberBtns = document.querySelectorAll('.close-invite-member');
const inviteMemberError = document.getElementById('invite-member-error');

let userWorkspaces = [];
let currentWorkspace = null;

// DOM Elements
const clearLogBtn = document.getElementById('clear-log');
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
let pendingCodegenTest = null;  // Track test info from codegen
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
        stopTestBtn.textContent = '⏹';
        stopTestBtn.title = 'Stop Test';
    } else {
        stopTestBtn.style.display = 'none';
        stopTestBtn.disabled = false;
        stopTestBtn.textContent = '⏹';
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
    // Hide loading state and show screenshot
    if (browserLoading) {
        browserLoading.classList.remove('active');
    }
    if (browserScreenshot) {
        browserScreenshot.style.display = 'block';
    }

    // Update browser screenshot (JPEG format for faster loading)
    browserScreenshot.src = `data:image/jpeg;base64,${data.image}`;

    // Update timestamp
    const timestamp = new Date(data.timestamp).toLocaleTimeString();

    // Show "LIVE" indicator for stream, or action name for specific actions
    if (data.action === 'stream') {
        screenshotTimestamp.textContent = `🔴 LIVE - ${timestamp}`;
    } else {
        screenshotTimestamp.textContent = `${data.action} - ${timestamp}`;
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
            authFetch(`/api/ai-steps/${runningAiStepTabId}/markdown?workspace_id=${currentWorkspaceId}`)
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

    // Update saved test status if this was a saved test run
    if (currentRunningTestFilename) {
        authFetch(`/api/saved-tests/${currentRunningTestFilename}/status?workspace_id=${currentWorkspaceId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: data.status })
        })
        .then(() => {
            // Reload file explorer to show updated status
            if (hasFileExplorer) {
                loadFileExplorer();
            }
            currentRunningTestFilename = null;
        })
        .catch(err => console.error('Error updating test status:', err));
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

    // Update UI: remove spinner, add status icon
    const fileItem = document.querySelector(`.file-item[data-filename="${filename}"]`);
    if (fileItem) {
        const spinner = fileItem.querySelector('.test-loading-spinner');
        if (spinner) spinner.remove();

        const statusIcon = status === 'success'
            ? '<span class="test-status test-status-success">✓</span>'
            : '<span class="test-status test-status-error">✗</span>';
        const actions = fileItem.querySelector('.file-item-actions');
        fileItem.insertAdjacentHTML('beforeend', statusIcon);
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
    updateBrowserStatus('passed', 'PASSED');
    addLogEntry('success', '✅ AI Step completed successfully!', '🎉 AI Step completed!');

    // Reload the AI step content to restore it (it may have been cleared during execution)
    const aiStepFilename = data.ai_step_filename;
    authFetch(`/api/ai-steps/${aiStepFilename}/markdown?workspace_id=${currentWorkspaceId}`)
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
                    authFetch(`/api/workspaces/${currentWorkspaceId}/tests`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: testName.trim(),
                            code: data.code,
                            source: 'ai_step'
                        })
                    })
                    .then(res => res.json())
                    .then(result => {
                        if (result.success) {
                            addLogEntry('success', `💾 Saved generated test: ${testName}`);

                            // Reload file explorer
                            if (hasFileExplorer) {
                                loadFileExplorer();
                            }

                            // Open the new test in a tab
                            openTab(result.filename, testName, data.code, 'test');
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
        browserStatus.textContent = 'Recording';
        browserStatus.classList.add('recording');
        browserStatus.style.background = 'var(--ctp-mauve)';
        addLogEntry('info', data.message, '🎥 Recording in progress...');
    }
});

socket.on('codegen_complete', (data) => {
    currentRecordingId = null;
    browserStatus.textContent = 'Recording Complete';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = 'var(--ctp-green)';

    // Display generated code
    setPlaywrightCode(data.code);

    // Store test info for saving with 'codegen' source
    pendingCodegenTest = {
        name: data.name,
        source: 'codegen'
    };

    addLogEntry('success', '✅ Recording complete! Code generated.', '✅ Recording complete!');

    // Scroll to code section
    const editorElement = document.getElementById('codemirror-editor');
    if (editorElement) {
        editorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
});

socket.on('codegen_error', (data) => {
    currentRecordingId = null;
    browserStatus.textContent = 'Recording Error';
    browserStatus.classList.remove('recording');
    browserStatus.style.background = 'var(--ctp-red)';

    addLogEntry('error', `❌ Recording failed: ${data.message}`, '❌ Recording failed');

    alert(`Recording failed:\n${data.message}`);
});

// UI Event Handlers
// Record, Run Test, Load Example, and Refresh buttons removed - use AI Steps section and file explorer instead

// Run Test and Stop Test buttons removed - use AI Steps section instead

// Load Example button removed - use AI Steps section instead

clearLogBtn.addEventListener('click', () => {
    humanLogContainer.innerHTML = '';
    technicalLogContainer.innerHTML = '';
    addLogEntry('info', 'Log cleared');
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

        // Handle AI Step saves
        if (tab.fileType === 'ai-step') {
            authFetch(`/api/ai-steps/${activeTabId}/markdown?workspace_id=${currentWorkspaceId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ markdown: code })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    addLogEntry('success', `💾 Saved AI Step: ${tab.name}`);
                    tab.isDirty = false;
                    tab.code = code;
                    lastSavedCode = code;
                    renderTabs();
                    loadAiSteps();
                } else {
                    alert('Error saving: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(err => alert('Error saving: ' + err));

            return;
        }

        authFetch(`/api/saved-tests/${activeTabId}?workspace_id=${currentWorkspaceId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: tab.name,
                code: code
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                tab.isDirty = false;
                tab.code = code;
                lastSavedCode = code;
                renderTabs();
                addLogEntry('success', `💾 Saved: ${tab.name}`);
            } else {
                alert('Error saving: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(err => {
            alert('Failed to save: ' + err);
        });
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
    if (browserScreenshot) {
        browserScreenshot.style.display = 'none';
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
        workspaceId: currentWorkspaceId
    });
}

async function runAllTests() {
    if (isBatchRunning || isTestRunning) {
        alert('A test is already running.');
        return;
    }

    const response = await authFetch(`/api/saved-tests?workspace_id=${currentWorkspaceId}`);
    const tests = await response.json();

    if (tests.length === 0) {
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
    addLogEntry('info', `🚀 Running ${tests.length} tests in parallel...`);

    // Show stop button
    updateStopButtonVisibility();

    // Mark all file items as batch running
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.add('batch-running');
    });

    // Disable Run All button
    const runAllBtn = document.getElementById('run-all-tests-btn');
    if (runAllBtn) {
        runAllBtn.disabled = true;
        runAllBtn.style.opacity = '0.5';
    }

    // Add loading spinners
    tests.forEach(test => {
        runningTestsSet.add(test.filename);
        const fileItem = document.querySelector(`.file-item[data-filename="${test.filename}"]`);
        if (fileItem) {
            fileItem.classList.add('batch-running-active');
            const statusIcon = fileItem.querySelector('.test-status');
            if (statusIcon) statusIcon.remove();

            const spinner = document.createElement('span');
            spinner.className = 'test-loading-spinner';
            spinner.dataset.filename = test.filename;
            const actions = fileItem.querySelector('.file-item-actions');
            fileItem.insertBefore(spinner, actions);
        }
    });

    // Emit batch run event
    socket.emit('run_all_tests', {
        filenames: tests.map(t => t.filename),
        workspaceId: currentWorkspaceId
    });
}

// Tab Management Functions
function openTab(filename, name, code, fileType = 'test') {
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
        fileType: fileType  // 'test' or 'ai-step'
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

    // Check if dirty (unsaved changes)
    if (tab.isDirty) {
        if (!confirm(`Close ${tab.name}?\nYou have unsaved changes.`)) {
            return;
        }
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
            // Hide dashboard content if it was showing
            hideDashboardContent();
        }
    }

    renderTabs();
    saveTabsState();  // Save state when closing a tab
}

function switchToTab(filename) {
    const tab = openTabs.find(t => t.id === filename);
    if (!tab) return;

    activeTabId = filename;

    // Handle dashboard tab specially
    if (tab.fileType === 'dashboard') {
        showDashboardContent();
    } else {
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
                    // Exclude temporary tabs
                    if (tab.id.startsWith('new_')) return false;
                    if (tab.id.startsWith('generated_')) return false;
                    if (tab.id.startsWith('chat_')) return false;
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

        // Restore each tab
        for (const tabInfo of tabsState.openTabs) {
            // Only restore saved test files (not temporary tabs like new_, generated_, chat_)
            if (!tabInfo.id.startsWith('new_') &&
                !tabInfo.id.startsWith('generated_') &&
                !tabInfo.id.startsWith('chat_')) {

                try {
                    // Handle dashboard tab restoration (no API fetch needed)
                    if (tabInfo.fileType === 'dashboard') {
                        const existingTab = openTabs.find(t => t.id === tabInfo.id);
                        if (!existingTab) {
                            openTabs.push({
                                id: '__dashboard__',
                                name: '📊 Dashboard',
                                code: '',
                                isDirty: false,
                                fileType: 'dashboard'
                            });
                        }
                    }
                    // Handle AI step restoration
                    else if (tabInfo.fileType === 'ai-step') {
                        const response = await authFetch(`/api/ai-steps/${tabInfo.id}/markdown?workspace_id=${currentWorkspaceId}`);
                        if (response.ok) {
                            const data = await response.json();
                            const existingTab = openTabs.find(t => t.id === tabInfo.id);
                            if (!existingTab) {
                                openTabs.push({
                                    id: tabInfo.id,
                                    name: tabInfo.name,
                                    code: data.markdown,
                                    isDirty: false,
                                    fileType: 'ai-step'
                                });
                            }
                        }
                    }
                    // Handle regular test file restoration
                    else {
                        const response = await authFetch(`/api/saved-tests/${tabInfo.id}?workspace_id=${currentWorkspaceId}`);
                        if (response.ok) {
                            const data = await response.json();

                            const existingTab = openTabs.find(t => t.id === tabInfo.id);
                            if (!existingTab) {
                                openTabs.push({
                                    id: tabInfo.id,
                                    name: tabInfo.name,
                                    code: data.code,
                                    isDirty: false,
                                    fileType: 'test'
                                });
                            }
                        }
                    }
                } catch (err) {
                    console.error(`Error restoring tab ${tabInfo.id}:`, err);
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
                <h1>🤖 AutoGen Web Tester</h1>
                <p class="welcome-subtitle">AI-powered browser automation and testing</p>
            </div>

            <div class="welcome-stats">
                <div class="stat-card">
                    <div class="stat-icon">📝</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.totalTests}</div>
                        <div class="stat-label">Saved Tests</div>
                    </div>
                </div>

                <div class="stat-card stat-success">
                    <div class="stat-icon">✓</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.passedTests}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                </div>

                <div class="stat-card stat-error">
                    <div class="stat-icon">✗</div>
                    <div class="stat-content">
                        <div class="stat-number">${stats.failedTests}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon">🤖</div>
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
                        <span class="action-icon">➕</span>
                        <div>
                            <div class="action-title">New Test</div>
                            <div class="action-desc">Create a new Playwright test</div>
                        </div>
                    </button>
                    <button class="action-btn" onclick="document.getElementById('new-ai-step-btn').click()">
                        <span class="action-icon">🤖</span>
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
    try {
        if (!currentWorkspaceId) {
            return { totalTests: 0, passedTests: 0, failedTests: 0, aiSteps: 0 };
        }

        // Fetch saved tests for current workspace
        const testsResponse = await authFetch(`/api/workspaces/${currentWorkspaceId}/tests`);
        const tests = await testsResponse.json();

        // Fetch AI steps for current workspace
        const aiStepsResponse = await authFetch(`/api/workspaces/${currentWorkspaceId}/ai-steps`);
        const aiStepsData = await aiStepsResponse.json();
        const aiSteps = aiStepsData.ai_steps || [];

        // Calculate statistics
        const totalTests = tests.length;
        const passedTests = tests.filter(t => t.last_run_status === 'success').length;
        const failedTests = tests.filter(t => t.last_run_status === 'error' || t.last_run_status === 'stopped').length;
        const aiStepsCount = aiSteps.length;

        return {
            totalTests,
            passedTests,
            failedTests,
            aiSteps: aiStepsCount
        };
    } catch (err) {
        console.error('Error fetching statistics:', err);
        return {
            totalTests: 0,
            passedTests: 0,
            failedTests: 0,
            aiSteps: 0
        };
    }
}

function updateFormatBtnVisibility() {
    if (!formatCodeBtn) return;
    const activeTab = openTabs.find(t => t.id === activeTabId);
    const hasFile = activeTab && activeTab.fileType !== 'dashboard';
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

        // Dashboard tab doesn't need an icon (already has emoji in name)
        const icon = tab.fileType === 'dashboard' ? '' : (tab.fileType === 'ai-step' ? '📝' : '🐍');
        const iconHtml = icon ? `<span class="editor-tab-icon">${icon}</span>` : '';

        const displayName = getDisplayName(tab.name, tab.fileType);
        tabEl.innerHTML = `
            ${iconHtml}
            <span class="editor-tab-name">${escapeHtml(displayName)}</span>
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

// File Explorer Functions
function loadFileExplorer() {
    if (!hasFileExplorer || !fileList) {
        console.warn('File explorer elements not found, skipping load');
        return;
    }

    if (!currentWorkspaceId) {
        fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--ctp-overlay1); font-size: 12px;">Select a workspace</div>';
        return;
    }

    authFetch(`/api/workspaces/${currentWorkspaceId}/tests`)
        .then(res => res.json())
        .then(data => {
            const tests = data.tests || [];
            fileList.innerHTML = '';

            if (tests.length === 0) {
                fileList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--ctp-overlay1); font-size: 12px;">No saved tests</div>';
                return;
            }

            tests.forEach(test => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.dataset.filename = test.filename;

                const sourceIcon = test.source === 'codegen' ? '🎥' : '🐍';

                // Status icon based on last run
                let statusIcon = '';
                if (test.last_run_status === 'success') {
                    statusIcon = '<span class="test-status test-status-success" title="Last run: Passed">✓</span>';
                } else if (test.last_run_status === 'error' || test.last_run_status === 'stopped') {
                    statusIcon = '<span class="test-status test-status-error" title="Last run: Failed">✗</span>';
                }

                // View recording button if valid artifacts exist
                let viewRecordingBtn = '';
                if (test.artifacts && test.artifacts.length > 0) {
                    // Check if any artifacts have valid video paths
                    const validArtifacts = test.artifacts.filter(a => a.video_path && a.video_path !== 'null');
                    if (validArtifacts.length > 0) {
                        viewRecordingBtn = `<button class="file-item-action" data-action="view-recording" title="View Recording (${validArtifacts.length})">📹</button>`;
                    }
                }

                // Show stop button if this test is currently running, otherwise show run button
                let runOrStopBtn = '';
                if (currentRunningTestFilename === test.filename) {
                    runOrStopBtn = `<button class="file-item-action" data-action="stop" title="Stop Test" style="color: var(--ctp-red);">⏹</button>`;
                } else {
                    runOrStopBtn = `<button class="file-item-action" data-action="run" title="Run Test">▶</button>`;
                }

                const testDisplayName = getDisplayName(test.name, 'test');
                fileItem.innerHTML = `
                    <span class="file-item-icon">${sourceIcon}</span>
                    <span class="file-item-name">${escapeHtml(testDisplayName)}</span>
                    ${statusIcon}
                    <div class="file-item-actions">
                        ${viewRecordingBtn}
                        ${runOrStopBtn}
                        <button class="file-item-action" data-action="delete" title="Delete">🗑</button>
                    </div>
                `;

                // Click to open
                fileItem.addEventListener('click', (e) => {
                    const action = e.target.dataset.action;
                    if (action === 'delete') {
                        deleteFileFromExplorer(test.filename, test.name);
                    } else if (action === 'run') {
                        e.stopPropagation();
                        runSavedTest(test.filename, test.name);
                    } else if (action === 'stop') {
                        e.stopPropagation();
                        if (isStopRequested) {
                            return; // Prevent double-click
                        }
                        if (confirm('Are you sure you want to stop the running test?')) {
                            isStopRequested = true;
                            socket.emit('stop_test');
                            addLogEntry('info', '⏹ Stop request sent to server');
                            // Update button immediately
                            if (stopTestBtn) {
                                stopTestBtn.disabled = true;
                                stopTestBtn.textContent = 'STOPPING...';
                                stopTestBtn.title = 'Stopping test...';
                            }
                        }
                    } else if (action === 'view-recording') {
                        e.stopPropagation();
                        showVideoViewerModal(test.filename, test.name);
                    } else {
                        openFileFromExplorer(test.filename, test.name);
                    }
                });

                fileList.appendChild(fileItem);
            });

            updateFileListActiveState();
        })
        .catch(err => {
            console.error('Failed to load file explorer:', err);
        });
}

function openFileFromExplorer(filename, name) {
    authFetch(`/api/workspaces/${currentWorkspaceId}/tests/${filename}`)
        .then(res => res.json())
        .then(data => {
            if (data && data.code) {
                openTab(filename, name, data.code);
            }
        })
        .catch(err => {
            alert('Failed to load test: ' + err);
        });
}

function deleteFileFromExplorer(filename, name) {
    if (!confirm(`Delete "${name}"?`)) return;

    authFetch(`/api/workspaces/${currentWorkspaceId}/tests/${filename}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Close tab if open
                closeTab(filename);
                // Reload file explorer
                loadFileExplorer();
                addLogEntry('info', `Deleted: ${name}`);
            }
        })
        .catch(err => {
            alert('Failed to delete test: ' + err);
        });
}

// Explorer Resizer
if (hasFileExplorer && explorerResizer) {
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    // Restore saved width on load
    const savedWidth = localStorage.getItem('fileExplorerWidth');
    if (savedWidth) {
        fileExplorer.style.width = savedWidth + 'px';
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

// New Test Button
if (newTestBtn) {
    newTestBtn.addEventListener('click', async () => {
        const name = prompt('Enter test name:');
        if (!name) return;

        const code = `from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Your code here

        await browser.close()

asyncio.run(run())`;

        // Save to DB immediately
        try {
            const response = await authFetch('/api/save-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, code, source: 'manual' })
            });
            const data = await response.json();
            if (data.success && data.filename) {
                openTab(data.filename, name, code);
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

// Run All Tests Button
const runAllTestsBtn = document.getElementById('run-all-tests-btn');
if (runAllTestsBtn) {
    runAllTestsBtn.addEventListener('click', () => {
        if (confirm('Run all saved tests in parallel?')) {
            runAllTests();
        }
    });
}

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
        name: '📊 Dashboard',
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

async function loadDashboardStats() {
    try {
        if (!currentWorkspaceId) return;

        // Fetch saved tests for current workspace
        const testsResponse = await authFetch(`/api/saved-tests?workspace_id=${currentWorkspaceId}`);
        const tests = await testsResponse.json();

        // Fetch AI steps for current workspace
        const aiStepsResponse = await authFetch(`/api/ai-steps?workspace_id=${currentWorkspaceId}`);
        const aiSteps = await aiStepsResponse.json();

        // Calculate statistics
        const totalTests = tests.length;
        const passedTests = tests.filter(t => t.last_run_status === 'success').length;
        const failedTests = tests.filter(t => t.last_run_status === 'error').length;
        const totalAiSteps = aiSteps.length;

        // Update dashboard stats
        document.getElementById('dashboard-saved-tests').textContent = totalTests;
        document.getElementById('dashboard-passed').textContent = passedTests;
        document.getElementById('dashboard-failed').textContent = failedTests;
        document.getElementById('dashboard-ai-steps').textContent = totalAiSteps;

        // Load recordings gallery from DB
        await loadRecordingsGallery();
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
    }
}

async function loadRecordingsGallery() {
    const recordingsGallery = document.getElementById('recordings-gallery');
    const noRecordingsMessage = document.getElementById('no-recordings-message');

    if (!recordingsGallery) return;

    try {
        const response = await authFetch(`/api/recent-recordings?workspace_id=${currentWorkspaceId}`);
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
    }
}

function createRecordingCard(recording) {
    const card = document.createElement('div');
    card.className = 'recording-card';

    const statusClass = recording.status === 'success' || recording.status === 'passed' ? 'passed' : 'failed';
    const statusText = recording.status === 'success' || recording.status === 'passed' ? 'PASSED' : 'FAILED';

    // Format timestamp
    const timestamp = recording.timestamp.replace(/_/g, ' ').replace(/-/g, ':');

    card.innerHTML = `
        <div class="recording-thumbnail">
            <div class="recording-placeholder">🎬</div>
            <div class="recording-play-overlay">
                <div class="recording-play-icon">▶</div>
            </div>
        </div>
        <div class="recording-info">
            <div class="recording-name" title="${escapeHtml(recording.test_name)}">${escapeHtml(recording.test_name)}</div>
            <div class="recording-meta">
                <span class="recording-status ${statusClass}">${statusText}</span>
                <span class="recording-timestamp">${timestamp}</span>
            </div>
        </div>
    `;

    // Click handler to open video viewer modal
    card.addEventListener('click', () => {
        showVideoViewerModal(recording.test_filename, recording.test_name);
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
});

// ========================================
// AI STEPS FUNCTIONALITY
// ========================================

async function loadAiSteps() {
    if (!aiStepsList) {
        console.warn('AI steps list element not found');
        return;
    }

    if (!currentWorkspaceId) {
        aiStepsList.innerHTML = '<div class="file-list-empty">Select a workspace</div>';
        return;
    }

    try {
        const response = await authFetch(`/api/workspaces/${currentWorkspaceId}/ai-steps`);
        const data = await response.json();
        const steps = data.ai_steps || [];

        aiStepsList.innerHTML = '';

        if (steps.length === 0) {
            aiStepsList.innerHTML = '<div class="file-list-empty">No AI steps yet</div>';
            return;
        }

        steps.forEach(step => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.dataset.filename = step.filename;
            const stepDisplayName = getDisplayName(step.name, 'ai-step');
            item.innerHTML = `
                <span class="file-item-icon">📝</span>
                <span class="file-item-name">${escapeHtml(stepDisplayName)}</span>
                <div class="file-item-actions">
                    <button class="file-item-action" data-action="run" title="Run AI Step">▶</button>
                    <button class="file-item-action" data-action="edit" title="Edit">✏️</button>
                    <button class="file-item-action" data-action="delete" title="Delete">🗑</button>
                </div>
            `;

            // Event listeners
            const runBtn = item.querySelector('[data-action="run"]');
            const editBtn = item.querySelector('[data-action="edit"]');
            const deleteBtn = item.querySelector('[data-action="delete"]');

            runBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                runAiStep(step.id, step.filename, step.name);
            });

            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openAiStepInEditor(step.filename, step.name);
            });

            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteAiStep(step.filename, step.name);
            });

            // Click handler for entire item
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.file-item-actions')) {
                    openAiStepInEditor(step.filename, step.name);
                }
            });

            aiStepsList.appendChild(item);
        });
    } catch (err) {
        console.error('Failed to load AI steps:', err);
        aiStepsList.innerHTML = '<div class="file-list-empty">Error loading AI steps</div>';
    }
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
    if (browserScreenshot) {
        browserScreenshot.style.display = 'none';
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
        workspaceId: currentWorkspaceId
    });

    addLogEntry('info', `🤖 Running AI steps: ${name}`);
}

function openAiStepInEditor(filename, name) {
    authFetch(`/api/ai-steps/${filename}/markdown?workspace_id=${currentWorkspaceId}`)
        .then(res => res.json())
        .then(data => {
            if (data.markdown) {
                openTab(filename, name, data.markdown, 'ai-step');
            }
        })
        .catch(err => {
            alert('Failed to load AI step: ' + err);
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
        authFetch(`/api/saved-tests/${lastTest.filename}/artifacts?workspace_id=${currentWorkspaceId}`)
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

    // Show modal immediately with loading state
    title.textContent = `📹 ${testName}`;
    loading.style.display = '';
    videoContainer.style.display = 'none';
    noRecording.style.display = 'none';
    videoPlayer.removeAttribute('src');
    modal.style.display = 'block';

    try {
        const res = await authFetch(`/api/workspaces/${currentWorkspaceId}/tests/${filename}/artifacts`);
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
        timestampElem.textContent = `Recorded: ${latestArtifact.timestamp.replace('_', ' at ').replace(/-/g, '/')}`;
        sizeElem.textContent = `Size: ${latestArtifact.video_size_mb} MB | Status: ${latestArtifact.status}`;
        downloadBtn.onclick = () => {
            const a = document.createElement('a');
            a.href = signedUrl;
            a.download = latestArtifact.video_path.split('/').pop();
            a.click();
        };
    } catch (err) {
        console.error('Error loading artifacts:', err);
        loading.style.display = 'none';
        noRecording.style.display = 'block';
    }
}

async function saveAiStep() {
    const name = aiStepNameInput.value.trim();
    const steps = aiStepStepsInput.value.trim();

    if (!name || !steps) {
        alert('Please enter both name and steps');
        return;
    }

    const method = currentEditingAiStep ? 'PUT' : 'POST';
    const url = currentEditingAiStep
        ? `/api/ai-steps/${currentEditingAiStep}`
        : '/api/ai-steps';

    try {
        const response = await authFetch(url, {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, steps})
        });

        if (response.ok) {
            loadAiSteps();
            aiStepModal.style.display = 'none';
            addLogEntry('success', `💾 AI step saved: ${name}`);
        } else {
            alert('Failed to save AI step');
        }
    } catch (err) {
        alert('Failed to save AI step: ' + err);
    }
}

async function deleteAiStep(filename, name) {
    if (!confirm(`Delete AI step "${name}"?`)) return;

    try {
        const response = await authFetch(`/api/ai-steps/${filename}?workspace_id=${currentWorkspaceId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadAiSteps();
            addLogEntry('info', `Deleted AI step: ${name}`);
        } else {
            alert('Failed to delete AI step');
        }
    } catch (err) {
        alert('Failed to delete AI step: ' + err);
    }
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
});

// AI Chat Sidebar Toggle
toggleChatBtn.addEventListener('click', () => {
    const isOpen = aiChatSidebar.classList.toggle('open');
    codeEditorSection.classList.toggle('chat-open');

    // Update button appearance
    if (isOpen) {
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Chat';
        toggleChatBtn.classList.add('active');
        // Focus on chat input
        setTimeout(() => chatInput.focus(), 300);
    } else {
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">💬</span> Chat';
        toggleChatBtn.classList.remove('active');
    }
});

closeChatSidebarBtn.addEventListener('click', () => {
    aiChatSidebar.classList.remove('open');
    codeEditorSection.classList.remove('chat-open');
    toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">💬</span> Chat';
    toggleChatBtn.classList.remove('active');
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
            codeEditorContainer.classList.remove('browser-open');
            toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">🌐</span> Browser';
            toggleBrowserBtn.classList.remove('active');
        }
    });
}

closeBrowserSidebarBtn.addEventListener('click', () => {
    const codeEditorContainer = document.querySelector('.code-editor-container');
    browserSidebar.classList.remove('open');
    codeEditorContainer.classList.remove('browser-open');
    if (toggleBrowserBtn) {
        toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">🌐</span> Browser';
        toggleBrowserBtn.classList.remove('active');
    }
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
        const codeEditorContainer = document.querySelector('.code-editor-container');
        browserSidebar.classList.remove('open');
        codeEditorContainer.classList.remove('browser-open');
        if (toggleBrowserBtn) {
            toggleBrowserBtn.innerHTML = '<span style="margin-right: 4px;">🌐</span> Browser';
            toggleBrowserBtn.classList.remove('active');
        }
    }
});

// Output Panel Toggle (VS Code style)
toggleOutputBtn.addEventListener('click', () => {
    outputPanel.classList.toggle('open');
});

// Function to open output panel automatically
function openOutputPanel() {
    if (!outputPanel.classList.contains('open')) {
        outputPanel.classList.add('open');
    }
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
            <span class="cm-hover-tooltip-icon">📘</span>
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
        aiChatSidebar.classList.add('open');
        codeEditorSection.classList.add('chat-open');
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">✕</span> Chat';
        toggleChatBtn.classList.add('active');
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
        file_type: fileType  // Send file type for context-aware assistance
    });

    // Clear image after sending
    if (currentImage) {
        currentImage = null;
        imagePreviewContainer.style.display = 'none';
        imagePreview.src = '';
        fileInput.value = '';
    }

    // Show loading indicator
    appendChatMessage('system', 'Thinking...');
}

function appendChatMessage(type, content, isCode = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;

    if (isCode) {
        messageDiv.className = 'chat-message code';

        // Add code header
        const codeHeader = document.createElement('div');
        codeHeader.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--ctp-surface0); border-bottom: 1px solid var(--ctp-base);';
        codeHeader.innerHTML = '<span style="font-size: 11px; color: var(--ctp-overlay1); text-transform: uppercase; letter-spacing: 0.5px;">Python</span>';

        // Add copy button
        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = '📋';
        copyBtn.style.cssText = 'background: transparent; border: none; color: var(--ctp-overlay1); cursor: pointer; padding: 2px 6px; border-radius: 3px; font-size: 12px;';
        copyBtn.onmouseover = () => copyBtn.style.background = 'var(--ctp-surface1)';
        copyBtn.onmouseout = () => copyBtn.style.background = 'transparent';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(content);
            copyBtn.innerHTML = '✓';
            setTimeout(() => copyBtn.innerHTML = '📋', 2000);
        };
        codeHeader.appendChild(copyBtn);
        messageDiv.appendChild(codeHeader);

        const codeBlock = document.createElement('pre');
        const code = document.createElement('code');
        code.className = 'language-python';
        code.textContent = content;
        codeBlock.appendChild(code);
        messageDiv.appendChild(codeBlock);
    } else {
        const contentSpan = document.createElement('span');
        contentSpan.textContent = content;
        messageDiv.appendChild(contentSpan);
    }

    chatMessages.appendChild(messageDiv);
    // Smooth scroll to bottom
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}

function appendChatMessageWithImage(type, content, imageSrc) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;

    // Add text content
    const contentSpan = document.createElement('span');
    contentSpan.textContent = content;
    messageDiv.appendChild(contentSpan);

    // Add image
    const img = document.createElement('img');
    img.src = imageSrc;
    img.alt = 'Attached image';
    messageDiv.appendChild(img);

    chatMessages.appendChild(messageDiv);
    // Smooth scroll to bottom
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}

// Socket.IO event handlers for chat
socket.on('chat_response', (data) => {
    // Remove loading indicator
    const systemMessages = chatMessages.querySelectorAll('.chat-message.system');
    systemMessages.forEach(msg => {
        if (msg.textContent.includes('thinking')) {
            msg.remove();
        }
    });

    // Add AI response
    appendChatMessage('ai', data.message);
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
    // Remove loading indicator
    const systemMessages = chatMessages.querySelectorAll('.chat-message.system');
    systemMessages.forEach(msg => {
        if (msg.textContent.includes('thinking')) {
            msg.remove();
        }
    });

    appendChatMessage('system', `Error: ${data.message}`);
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
        const { filename, fileType, workspaceId, code } = pendingCodeSuggestion;
        const isSteps = fileType === 'ai_step';
        const apiPath = isSteps
            ? `/api/ai-steps/${filename}?workspace_id=${workspaceId}`
            : `/api/workspaces/${workspaceId}/tests/${filename}`;
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
                if (currentWorkspaceId) loadFileExplorer(currentWorkspaceId);
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
        aiChatSidebar.classList.remove('open');
        codeEditorSection.classList.remove('chat-open');
        toggleChatBtn.innerHTML = '<span style="margin-right: 4px;">💬</span> Chat';
        toggleChatBtn.classList.remove('active');
    }
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
        socket.emit('clear_chat');
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
        } else {
            showLoginModal();
            return false;
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        showLoginModal();
        return false;
    }
}

async function loadUserWorkspaces() {
    try {
        const response = await authFetch('/api/current-user');
        if (!response.ok) {
            if (response.status === 401) {
                showLoginModal();
                return;
            }
            throw new Error('Failed to load workspaces');
        }

        const data = await response.json();
        currentUser = data.user;

        // Try to restore previously selected workspace from localStorage, then DB
        let savedWorkspaceId = localStorage.getItem('selectedWorkspaceId');
        let workspaceFound = false;

        // Fall back to DB if localStorage is empty
        if (!savedWorkspaceId) {
            const dbPrefs = await loadPreferencesFromDb();
            if (dbPrefs && dbPrefs.selectedWorkspaceId) {
                savedWorkspaceId = dbPrefs.selectedWorkspaceId;
                localStorage.setItem('selectedWorkspaceId', savedWorkspaceId);
            }
            // Also restore editorTabsState from DB if missing locally
            if (dbPrefs && dbPrefs.editorTabsState && !localStorage.getItem('editorTabsState')) {
                localStorage.setItem('editorTabsState', dbPrefs.editorTabsState);
            }
        }

        if (savedWorkspaceId && data.workspaces && data.workspaces.length > 0) {
            const savedId = parseInt(savedWorkspaceId);
            const hasAccess = data.workspaces.some(w => w.id === savedId);

            if (hasAccess) {
                currentWorkspaceId = savedId;
                workspaceFound = true;
                console.log('Restored workspace from localStorage:', savedId);
            }
        }

        // Fall back to first workspace if no saved workspace or user doesn't have access
        if (!workspaceFound && data.workspaces && data.workspaces.length > 0) {
            currentWorkspaceId = data.workspaces[0].id;
            console.log('Using default workspace:', currentWorkspaceId);
        }

        // Persist the selection so it survives page reloads and re-login
        if (currentWorkspaceId) {
            localStorage.setItem('selectedWorkspaceId', currentWorkspaceId);
            savePreferenceToDb('selectedWorkspaceId', String(currentWorkspaceId));
        }

        console.log('User authenticated:', currentUser.username);
        console.log('Current workspace:', currentWorkspaceId);

        // Load tests and AI steps for the current workspace
        if (hasFileExplorer && currentWorkspaceId) {
            loadFileExplorer();
            loadAiSteps();
        }
    } catch (error) {
        console.error('Failed to load workspaces:', error);
    }
}

async function handleLogin(event) {
    event.preventDefault();

    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const remember = document.getElementById('login-remember').checked;

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
            if (hasFileExplorer && currentWorkspaceId) {
                loadFileExplorer();
                loadAiSteps();
            }

            // Open dashboard tab if no tabs
            if (openTabs.length === 0) {
                openDashboardTab();
            }
        } else {
            loginError.textContent = data.error || 'Login failed';
            loginError.style.display = 'block';
        }
    } catch (error) {
        console.error('Login error:', error);
        loginError.textContent = 'Login failed. Please try again.';
        loginError.style.display = 'block';
    }
}

async function handleRegister(event) {
    event.preventDefault();

    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const passwordConfirm = document.getElementById('register-password-confirm').value;

    // Client-side validation
    if (password !== passwordConfirm) {
        registerError.textContent = 'Passwords do not match';
        registerError.style.display = 'block';
        return;
    }

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
            if (hasFileExplorer && currentWorkspaceId) {
                loadFileExplorer();
                loadAiSteps();
            }

            // Open dashboard tab
            if (openTabs.length === 0) {
                openDashboardTab();
            }
        } else {
            registerError.textContent = data.error || 'Registration failed';
            registerError.style.display = 'block';
        }
    } catch (error) {
        console.error('Registration error:', error);
        registerError.textContent = 'Registration failed. Please try again.';
        registerError.style.display = 'block';
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
            option.value = workspace.id;
            option.textContent = `${workspace.name} ${workspace.type === 'shared' ? '(Shared)' : ''}`;
            workspaceDropdown.appendChild(option);
        });

        // Set current workspace - try localStorage, then DB, then default
        if (userWorkspaces.length > 0) {
            let savedWorkspaceId = localStorage.getItem('selectedWorkspaceId');

            // Fall back to DB if localStorage is empty
            if (!savedWorkspaceId) {
                const dbPrefs = await loadPreferencesFromDb();
                if (dbPrefs) {
                    if (dbPrefs.selectedWorkspaceId) {
                        savedWorkspaceId = dbPrefs.selectedWorkspaceId;
                        localStorage.setItem('selectedWorkspaceId', savedWorkspaceId);
                    }
                    // Also restore editorTabsState from DB if missing locally
                    if (!localStorage.getItem('editorTabsState') && dbPrefs.editorTabsState) {
                        localStorage.setItem('editorTabsState', dbPrefs.editorTabsState);
                    }
                    // Apply saved theme from DB
                    if (dbPrefs.theme && VALID_THEMES.includes(dbPrefs.theme)) {
                        applyTheme(dbPrefs.theme);
                        localStorage.setItem('theme', dbPrefs.theme);
                    }
                }
            }

            if (savedWorkspaceId) {
                const savedId = parseInt(savedWorkspaceId);
                const hasAccess = userWorkspaces.some(w => w.id === savedId);
                if (hasAccess) {
                    currentWorkspaceId = savedId;
                } else {
                    currentWorkspaceId = userWorkspaces[0].id;
                }
            } else if (!currentWorkspaceId) {
                currentWorkspaceId = userWorkspaces[0].id;
            }
            // Persist the selection so it survives page reloads and re-login
            localStorage.setItem('selectedWorkspaceId', currentWorkspaceId);
            savePreferenceToDb('selectedWorkspaceId', String(currentWorkspaceId));
        }

        // Select current workspace
        workspaceDropdown.value = currentWorkspaceId;

        // Load workspace details
        await loadWorkspaceDetails();

    } catch (error) {
        console.error('Failed to load workspaces:', error);
    }
}

async function loadWorkspaceDetails() {
    if (!currentWorkspaceId) return;

    try {
        const response = await authFetch(`/api/workspaces/${currentWorkspaceId}`);
        if (!response.ok) {
            throw new Error('Failed to load workspace details');
        }

        const data = await response.json();
        currentWorkspace = data.workspace;

        // Show/hide members section based on workspace type and ownership
        if (currentWorkspace.type === 'shared' && currentWorkspace.owner_id === currentUser.id) {
            workspaceMembersContainer.style.display = 'block';
            displayWorkspaceMembers(currentWorkspace.members || []);
        } else {
            workspaceMembersContainer.style.display = 'none';
        }

    } catch (error) {
        console.error('Failed to load workspace details:', error);
    }
}

function displayWorkspaceMembers(members) {
    workspaceMembersList.innerHTML = '';

    if (members.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.style.cssText = 'color: var(--ctp-overlay1); font-size: 12px; padding: 8px;';
        emptyMsg.textContent = 'No members yet';
        workspaceMembersList.appendChild(emptyMsg);
        return;
    }

    members.forEach(member => {
        const memberEl = document.createElement('div');
        memberEl.className = 'workspace-member-item';
        memberEl.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-bottom: 1px solid var(--ctp-surface0);';

        const infoDiv = document.createElement('div');

        const nameDiv = document.createElement('div');
        nameDiv.style.cssText = 'font-size: 13px; color: var(--ctp-text);';
        nameDiv.textContent = member.username;

        const roleDiv = document.createElement('div');
        roleDiv.style.cssText = 'font-size: 11px; color: var(--ctp-overlay1);';
        roleDiv.textContent = member.role;

        infoDiv.appendChild(nameDiv);
        infoDiv.appendChild(roleDiv);

        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn-icon-small remove-member-btn';
        removeBtn.textContent = '✕';
        removeBtn.title = 'Remove';
        removeBtn.dataset.userId = member.user_id;
        removeBtn.addEventListener('click', async () => {
            await removeMember(member.user_id);
        });

        memberEl.appendChild(infoDiv);
        memberEl.appendChild(removeBtn);
        workspaceMembersList.appendChild(memberEl);
    });
}

async function switchWorkspace(workspaceId) {
    const wsSwitchOverlay = document.getElementById('workspace-switch-overlay');
    if (wsSwitchOverlay) wsSwitchOverlay.style.display = 'flex';

    try {
        currentWorkspaceId = parseInt(workspaceId);

        // Sync the dropdown immediately so it reflects the selection
        if (workspaceDropdown) workspaceDropdown.value = currentWorkspaceId;

        // Close all open tabs — tests belong to a specific workspace
        openTabs = [];
        activeTabId = null;
        lastSavedCode = '';
        setPlaywrightCode('');
        renderTabs();
        saveTabsState();

        // Save selected workspace to localStorage and DB
        localStorage.setItem('selectedWorkspaceId', currentWorkspaceId);
        savePreferenceToDb('selectedWorkspaceId', String(currentWorkspaceId));

        await loadWorkspaceDetails();

        // Reload file lists for new workspace
        if (hasFileExplorer) {
            loadFileExplorer();
            loadAiSteps();
        }

        // Re-open dashboard tab so the main area shows workspace stats (not "No file open")
        openDashboardTab();

        addLogEntry('info', `Switched to workspace: ${currentWorkspace.name}`);
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
    const type = document.getElementById('workspace-type').value;

    try {
        const response = await authFetch('/api/workspaces', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, type })
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

            // Reload workspaces
            await loadWorkspaces();

            // Switch to new workspace
            await switchWorkspace(data.workspace.id);
        } else {
            newWorkspaceError.textContent = data.error || 'Failed to create workspace';
            newWorkspaceError.style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to create workspace:', error);
        newWorkspaceError.textContent = 'Failed to create workspace';
        newWorkspaceError.style.display = 'block';
    }
}

async function inviteMember(event) {
    event.preventDefault();

    const username = document.getElementById('invite-username').value.trim();
    const role = document.getElementById('invite-role').value;

    try {
        const response = await authFetch(`/api/workspaces/${currentWorkspaceId}/members`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, role })
        });

        const data = await response.json();

        if (response.ok) {
            inviteMemberModal.style.display = 'none';
            inviteMemberForm.reset();
            addLogEntry('info', `✓ Invited ${username} to workspace`);

            // Reload workspace details
            await loadWorkspaceDetails();
        } else {
            inviteMemberError.textContent = data.error || 'Failed to invite member';
            inviteMemberError.style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to invite member:', error);
        inviteMemberError.textContent = 'Failed to invite member';
        inviteMemberError.style.display = 'block';
    }
}

async function removeMember(userId) {
    if (!confirm('Remove this member from the workspace?')) {
        return;
    }

    try {
        const response = await authFetch(`/api/workspaces/${currentWorkspaceId}/members/${userId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            addLogEntry('info', '✓ Member removed');
            await loadWorkspaceDetails();
        } else {
            const data = await response.json();
            alert(data.error || 'Failed to remove member');
        }
    } catch (error) {
        console.error('Failed to remove member:', error);
        alert('Failed to remove member');
    }
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
    currentWorkspaceId = null;
    userWorkspaces = [];
    showLoginModal();
    addLogEntry('info', '👋 Logged out successfully');
}

// Event listeners for workspace management
if (logoutBtn) logoutBtn.addEventListener('click', handleLogout);
if (workspaceDropdown) workspaceDropdown.addEventListener('change', (e) => switchWorkspace(e.target.value));
if (newWorkspaceBtn) newWorkspaceBtn.addEventListener('click', () => {
    newWorkspaceModal.style.display = 'block';
    newWorkspaceError.style.display = 'none';
});
if (inviteMemberBtn) inviteMemberBtn.addEventListener('click', () => {
    inviteMemberModal.style.display = 'block';
    inviteMemberError.style.display = 'none';
});

if (newWorkspaceForm) newWorkspaceForm.addEventListener('submit', createWorkspace);
if (inviteMemberForm) inviteMemberForm.addEventListener('submit', inviteMember);

// Close modal buttons
closeNewWorkspaceBtns.forEach(btn => {
    btn.addEventListener('click', () => newWorkspaceModal.style.display = 'none');
});
closeInviteMemberBtns.forEach(btn => {
    btn.addEventListener('click', () => inviteMemberModal.style.display = 'none');
});

// ========== END WORKSPACE MANAGEMENT FUNCTIONS ==========

// ========== THEME MANAGEMENT ==========
const VALID_THEMES = ['mocha', 'macchiato', 'frappe', 'latte'];

function applyTheme(themeName) {
    if (!VALID_THEMES.includes(themeName)) themeName = 'mocha';
    document.documentElement.setAttribute('data-theme', themeName);
    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === themeName);
    });
}

function initThemePicker() {
    const savedTheme = localStorage.getItem('theme') || 'mocha';
    applyTheme(savedTheme);

    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.theme;
            applyTheme(theme);
            localStorage.setItem('theme', theme);
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

// Load default example on page load
window.addEventListener('load', async () => {
    // Initialize theme picker (apply saved theme from localStorage immediately)
    initThemePicker();

    // Check authentication first
    const isAuthenticated = await checkAuthentication();

    if (!isAuthenticated) {
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

    // Load workspaces
    await loadWorkspaces();

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
