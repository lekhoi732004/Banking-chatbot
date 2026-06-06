/* ============================================
   VietBank AI - Chat Application v2
   WebSocket | History | Multi-Conversation
   ============================================ */

(function () {
    'use strict';

    // --- Configuration ---
    var protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    var WS_BASE_URL = protocol + window.location.host + '/ws/chat/';
    var MAX_RECONNECT_ATTEMPTS = 5;
    var RECONNECT_INTERVAL_MS = 3000;
    var STORAGE_KEY = 'vietbank_chat_history';

    // --- State ---
    var ws = null;
    var currentConversationId = null;
    var conversations = {}; // { id: { id, title, messages: [{text, sender, time}], createdAt, updatedAt } }
    var reconnectAttempts = 0;
    var reconnectTimer = null;
    var isConnected = false;
    var typingIndicatorEl = null;

    // --- DOM References ---
    var chatMessages = document.getElementById('chatMessages');
    var messageInput = document.getElementById('messageInput');
    var sendBtn = document.getElementById('sendBtn');
    var statusDot = document.getElementById('statusDot');
    var statusText = document.getElementById('statusText');
    var quickReplies = document.getElementById('quickReplies');
    var chatTitle = document.getElementById('chatTitle');
    var conversationList = document.getElementById('conversationList');
    var newChatBtn = document.getElementById('newChatBtn');
    var clearAllBtn = document.getElementById('clearAllBtn');
    var searchInput = document.getElementById('searchInput');
    var sidebar = document.getElementById('sidebar');
    var headerMenuBtn = document.getElementById('headerMenuBtn');
    var sidebarOverlay = document.getElementById('sidebarOverlay');

    // ============================================
    // INITIALIZATION
    // ============================================
    function init() {
        loadConversations();

        // If no conversations, create one
        if (Object.keys(conversations).length === 0) {
            createNewConversation();
        } else {
            // Load most recent conversation
            var sorted = getSortedConversations();
            switchConversation(sorted[0].id);
        }

        bindEvents();
        renderSidebar();
        setupSidebarResize();
    }

    // ============================================
    // UUID GENERATOR
    // ============================================
    function generateId() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = (Math.random() * 16) | 0;
            var v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    // ============================================
    // CONVERSATION MANAGEMENT
    // ============================================
    function createNewConversation() {
        var id = generateId();
        conversations[id] = {
            id: id,
            title: 'Cuộc trò chuyện mới',
            messages: [],
            createdAt: Date.now(),
            updatedAt: Date.now()
        };

        saveConversations();
        switchConversation(id);
        renderSidebar();
    }

    function switchConversation(id) {
        if (!conversations[id]) return;

        // Disconnect old WS
        if (ws) {
            ws.onclose = null; // prevent reconnect
            ws.close();
            ws = null;
        }
        isConnected = false;
        reconnectAttempts = 0;

        currentConversationId = id;

        // Update UI
        renderMessages();
        updateChatTitle();
        renderSidebar();

        // Connect WS for this conversation
        connectWebSocket();
    }

    function deleteConversation(id) {
        delete conversations[id];
        saveConversations();

        if (id === currentConversationId) {
            var sorted = getSortedConversations();
            if (sorted.length > 0) {
                switchConversation(sorted[0].id);
            } else {
                createNewConversation();
            }
        }

        renderSidebar();
    }

    function clearAllConversations() {
        conversations = {};
        saveConversations();
        createNewConversation();
    }

    function getSortedConversations() {
        return Object.values(conversations).sort(function (a, b) {
            return b.updatedAt - a.updatedAt;
        });
    }

    function getCurrentConversation() {
        return conversations[currentConversationId] || null;
    }

    function hasAccents(text) {
        var regex = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;
        return regex.test(text);
    }

    function getAccentedTitle(text) {
        var lower = text.toLowerCase().trim().replace(/\s+/g, ' ');
        lower = lower.replace(/[.!?]+$/, '').trim();

        if (/^(lai suat|lai suat tiet kiem|lai xuat|lai xuat tiet kiem|lai tiet kiem)$/.test(lower)) {
            return 'Lãi suất tiết kiệm';
        }
        if (/^(ty gia|ty gia ngoai te|ti gia|ti gia ngoai te|usd|ngoai te)$/.test(lower)) {
            return 'Tỷ giá ngoại tệ';
        }
        if (/^(mo tai khoan|mo tk|dang ky tai khoan|mo tai khoan online)$/.test(lower)) {
            return 'Mở tài khoản';
        }
        if (/^(the tin dung|the visa|the mastercard|credit card|mo the)$/.test(lower)) {
            return 'Thẻ tín dụng';
        }
        if (/^(vay von|vay mua nha|vay mua xe|vay tin chap|vay tieu dung)$/.test(lower)) {
            return 'Vay vốn cá nhân';
        }
        if (/^(bieu phi|phi dich vu|phi chuyen khoan|phi atm|phi sms)$/.test(lower)) {
            return 'Biểu phí dịch vụ';
        }
        if (/^(tiet kiem|gui tiet kiem|tiet kiem online)$/.test(lower)) {
            return 'Gửi tiết kiệm';
        }

        var replacements = [
            { raw: 'lai suat', clean: 'Lãi suất' },
            { raw: 'lai xuat', clean: 'Lãi suất' },
            { raw: 'tiet kiem', clean: 'tiết kiệm' },
            { raw: 'ty gia', clean: 'Tỷ giá' },
            { raw: 'ti gia', clean: 'Tỷ giá' },
            { raw: 'ngoai te', clean: 'ngoại tệ' },
            { raw: 'mo tai khoan', clean: 'Mở tài khoản' },
            { raw: 'the tin dung', clean: 'Thẻ tín dụng' },
            { raw: 'vay von', clean: 'Vay vốn' },
            { raw: 'bieu phi', clean: 'Biểu phí' }
        ];

        var title = text;
        replacements.forEach(function (r) {
            var regex = new RegExp(r.raw, 'gi');
            title = title.replace(regex, r.clean);
        });

        if (title.length > 0) {
            title = title.charAt(0).toUpperCase() + title.slice(1);
        }

        return title;
    }

    function updateConversationTitle(id, firstMessage) {
        if (!conversations[id]) return;
        if (conversations[id].title !== 'Cuộc trò chuyện mới') return;

        var cleanTitle = getAccentedTitle(firstMessage);
        var title = cleanTitle.length > 35 ? cleanTitle.substring(0, 35) + '...' : cleanTitle;
        conversations[id].title = title;
        saveConversations();
        updateChatTitle();
        renderSidebar();
    }

    // ============================================
    // LOCAL STORAGE
    // ============================================
    function saveConversations() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
        } catch (e) {
            console.warn('[Storage] Save failed:', e);
        }
    }

    function loadConversations() {
        try {
            var data = localStorage.getItem(STORAGE_KEY);
            if (data) {
                conversations = JSON.parse(data);
            }
        } catch (e) {
            console.warn('[Storage] Load failed:', e);
            conversations = {};
        }
    }

    // ============================================
    // SIDEBAR RENDERING
    // ============================================
    function renderSidebar() {
        var sorted = getSortedConversations();
        var filterText = (searchInput.value || '').toLowerCase();

        if (sorted.length === 0) {
            conversationList.innerHTML =
                '<div class="sidebar-empty">' +
                '<div class="sidebar-empty-icon">&#x1F4AC;</div>' +
                '<div class="sidebar-empty-text">Chưa có cuộc trò chuyện nào</div>' +
                '</div>';
            return;
        }

        var html = '';
        sorted.forEach(function (conv) {
            // Filter
            if (filterText && conv.title.toLowerCase().indexOf(filterText) === -1) {
                return;
            }

            var isActive = conv.id === currentConversationId;
            var preview = '';
            if (conv.messages.length > 0) {
                var lastMsg = conv.messages[conv.messages.length - 1];
                var previewText = lastMsg.text;
                if (lastMsg.sender === 'bot') {
                    // Remove emojis
                    previewText = previewText.replace(/\p{Extended_Pictographic}/gu, '');
                    // Remove heading numbers (e.g., 6.1. or ## 6.)
                    previewText = previewText.replace(/(^|\n)(\s*#+\s*)?(\d+(?:\.\d+)+\.?)\s+/g, '$1$2');
                    previewText = previewText.replace(/(^|\n)(\s*#+\s+)(\d+\.)\s+/g, '$1$2');
                }
                preview = previewText.replace(/[*#\n]/g, ' ').trim().substring(0, 50);
            }
            var timeStr = formatRelativeTime(conv.updatedAt);

            html +=
                '<div class="conversation-item' + (isActive ? ' active' : '') + '" data-id="' + conv.id + '">' +
                '  <div class="conv-icon">&#x1F4AC;</div>' +
                '  <div class="conv-info">' +
                '    <div class="conv-title">' + escapeHTML(conv.title) + '</div>' +
                '    <div class="conv-preview">' + escapeHTML(preview) + '</div>' +
                '  </div>' +
                '  <div class="conv-time">' + timeStr + '</div>' +
                '  <button class="conv-delete-btn" data-delete-id="' + conv.id + '" title="Xóa">' +
                '    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>' +
                '  </button>' +
                '</div>';
        });

        if (!html) {
            html = '<div class="sidebar-empty"><div class="sidebar-empty-text">Không tìm thấy kết quả</div></div>';
        }

        conversationList.innerHTML = html;

        // Bind click events for conversation items
        var items = conversationList.querySelectorAll('.conversation-item');
        items.forEach(function (item) {
            item.addEventListener('click', function (e) {
                // Ignore delete button clicks
                if (e.target.closest('.conv-delete-btn')) return;
                var id = item.getAttribute('data-id');
                switchConversation(id);
                closeSidebar();
            });
        });

        // Bind delete button events
        var delBtns = conversationList.querySelectorAll('.conv-delete-btn');
        delBtns.forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var id = btn.getAttribute('data-delete-id');
                deleteConversation(id);
            });
        });
    }

    function updateChatTitle() {
        var conv = getCurrentConversation();
        if (conv) {
            chatTitle.textContent = conv.title;
        }
    }

    // ============================================
    // MESSAGE RENDERING
    // ============================================
    function renderMessages() {
        chatMessages.innerHTML = '';
        var conv = getCurrentConversation();
        if (!conv) return;

        conv.messages.forEach(function (msg, index) {
            addMessageToDOM(msg.text, msg.sender, index === 0 && msg.sender === 'bot', false);
        });

        scrollToBottom();
    }

    function addMessageToDOM(text, sender, isWelcome, animate) {
        var wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper ' + sender;
        if (isWelcome) wrapper.classList.add('welcome-card');

        // Disable animation for history replay
        if (animate === false) {
            wrapper.style.opacity = '1';
            wrapper.style.animation = 'none';
        }

        var row = document.createElement('div');
        row.className = 'message-row';

        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = sender === 'bot' ? '&#x1FAB6;' : '&#x1F464;';

        var bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = formatMessage(text, sender);

        row.appendChild(avatar);
        row.appendChild(bubble);

        var time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = formatTimestamp(new Date());

        wrapper.appendChild(row);
        wrapper.appendChild(time);

        chatMessages.appendChild(wrapper);
    }

    // ============================================
    // WEBSOCKET CONNECTION
    // ============================================
    function connectWebSocket() {
        if (!currentConversationId) return;
        updateConnectionStatus('connecting');

        try {
            ws = new WebSocket(WS_BASE_URL + currentConversationId);
        } catch (err) {
            console.error('[WS] Failed:', err);
            updateConnectionStatus('offline');
            scheduleReconnect();
            return;
        }

        ws.onopen = function () {
            console.log('[WS] Connected. Session:', currentConversationId);
            isConnected = true;
            reconnectAttempts = 0;
            updateConnectionStatus('online');
        };

        ws.onmessage = function (event) {
            try {
                var data = JSON.parse(event.data);

                if (data.type === 'typing') {
                    showTypingIndicator();
                    return;
                }

                hideTypingIndicator();

                if (data.type === 'welcome') {
                    var conv = getCurrentConversation();
                    if (conv && conv.messages.length > 0) {
                        return;
                    }
                }

                var text = data.content || data.message || data.response || data.text || '';
                if (!text.trim()) return;

                addMessage(text, data.sender || 'bot');

                // If conversation title is still default/unaccented, refine it using the bot metadata
                var conv = getCurrentConversation();
                if (conv && (conv.title === 'Cuộc trò chuyện mới' || !hasAccents(conv.title))) {
                    if (data.metadata && data.metadata.current_topic) {
                        var topic = data.metadata.current_topic;
                        var capitalizedTopic = topic.charAt(0).toUpperCase() + topic.slice(1);

                        // Look for the user's first message to build a detailed title
                        var userMsgs = conv.messages.filter(function (m) { return m.sender === 'user'; });
                        if (userMsgs.length > 0) {
                            var firstUserMsg = userMsgs[0].text;
                            var refinedTitle = getAccentedTitle(firstUserMsg);
                            if (!hasAccents(refinedTitle)) {
                                refinedTitle = capitalizedTopic;
                            }
                            conv.title = refinedTitle.length > 35 ? refinedTitle.substring(0, 35) + '...' : refinedTitle;
                        } else {
                            conv.title = capitalizedTopic;
                        }

                        saveConversations();
                        updateChatTitle();
                        renderSidebar();
                    }
                }
            } catch (e) {
                hideTypingIndicator();
                addMessage(event.data, 'bot');
            }
        };

        ws.onerror = function (err) {
            console.error('[WS] Error:', err);
        };

        ws.onclose = function (event) {
            console.log('[WS] Closed. Code:', event.code);
            isConnected = false;
            hideTypingIndicator();
            updateConnectionStatus('offline');
            scheduleReconnect();
        };
    }

    function scheduleReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            statusText.textContent = 'Mất kết nối';
            return;
        }

        reconnectAttempts++;
        statusText.textContent = 'Đang kết nối lại (' + reconnectAttempts + '/' + MAX_RECONNECT_ATTEMPTS + ')...';
        updateConnectionStatus('connecting');

        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(function () {
            connectWebSocket();
        }, RECONNECT_INTERVAL_MS);
    }

    function updateConnectionStatus(status) {
        statusDot.className = 'status-dot';
        if (status === 'online') {
            statusDot.classList.add('online');
            statusText.textContent = 'Trực tuyến';
        } else if (status === 'connecting') {
            statusDot.classList.add('connecting');
            statusText.textContent = 'Đang kết nối...';
        } else {
            statusDot.classList.add('offline');
            statusText.textContent = 'Ngoại tuyến';
        }
    }

    // ============================================
    // EVENT BINDING
    // ============================================
    function bindEvents() {
        sendBtn.addEventListener('click', handleSend);

        messageInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });

        // Quick replies
        var qrBtns = quickReplies.querySelectorAll('.quick-reply-btn');
        qrBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var msg = btn.getAttribute('data-message');
                if (msg) {
                    messageInput.value = msg;
                    handleSend();
                }
            });
        });

        // New chat
        newChatBtn.addEventListener('click', function () {
            createNewConversation();
            closeSidebar();
        });

        // Clear all
        clearAllBtn.addEventListener('click', function () {
            if (Object.keys(conversations).length > 0) {
                clearAllConversations();
            }
        });

        // Search filter
        searchInput.addEventListener('input', function () {
            renderSidebar();
        });

        // Sidebar toggle (mobile)
        if (headerMenuBtn) {
            headerMenuBtn.addEventListener('click', function () {
                toggleSidebar();
            });
        }

        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', function () {
                closeSidebar();
            });
        }
    }

    // ============================================
    // SIDEBAR TOGGLE
    // ============================================
    function toggleSidebar() {
        sidebar.classList.toggle('open');
        sidebarOverlay.classList.toggle('visible');
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('visible');
    }

    // ============================================
    // SEND MESSAGE
    // ============================================
    function handleSend() {
        var text = messageInput.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        messageInput.value = '';
        messageInput.focus();

        if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
            try {
                ws.send(JSON.stringify({ message: text }));
            } catch (err) {
                console.error('[WS] Send error:', err);
                addMessage('Không thể gửi tin nhắn. Vui lòng thử lại.', 'bot');
                return;
            }
            showTypingIndicator();
        } else {
            addMessage('Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối và thử lại.', 'bot');
        }
    }

    // ============================================
    // ADD MESSAGE (with persistence)
    // ============================================
    function addMessage(text, sender, isWelcome) {
        // Save to conversation history
        var conv = getCurrentConversation();
        if (conv) {
            conv.messages.push({
                text: text,
                sender: sender,
                time: Date.now()
            });
            conv.updatedAt = Date.now();

            // Update title from first user message
            if (sender === 'user' && conv.title === 'Cuộc trò chuyện mới') {
                updateConversationTitle(conv.id, text);
            }

            saveConversations();
            renderSidebar();
        }

        // Add to DOM (with animation)
        addMessageToDOM(text, sender, isWelcome, true);
        scrollToBottom();
    }

    // ============================================
    // FORMAT MESSAGE (markdown-like & table support)
    // ============================================
    function parseMarkdownTables(text) {
        var lines = text.split('\n');
        var inTable = false;
        var tableRows = [];
        var newLines = [];
        var headers = [];

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            
            if (line.startsWith('|') && line.endsWith('|')) {
                if (/^[|\s\-:.]+$/.test(line)) {
                    inTable = true;
                    continue;
                }
                
                var cells = line.split('|').map(function(c) { return c.trim(); });
                if (cells.length > 1) {
                    if (cells[0] === '') cells.shift();
                    if (cells[cells.length - 1] === '') cells.pop();
                }

                if (!inTable) {
                    headers = cells;
                    inTable = true;
                    tableRows = [];
                } else {
                    tableRows.push(cells);
                }
            } else {
                if (inTable && (headers.length > 0 || tableRows.length > 0)) {
                    var tableHtml = renderHtmlTable(headers, tableRows);
                    newLines.push(tableHtml);
                    inTable = false;
                    headers = [];
                    tableRows = [];
                }
                newLines.push(lines[i]);
            }
        }
        
        if (inTable && (headers.length > 0 || tableRows.length > 0)) {
            var tableHtml = renderHtmlTable(headers, tableRows);
            newLines.push(tableHtml);
        }

        return newLines.join('\n');
    }

    function renderHtmlTable(headers, rows) {
        var html = '<div class="table-container"><table class="premium-table">';
        
        if (headers.length > 0) {
            html += '<thead><tr>';
            headers.forEach(function(h) {
                html += '<th>' + h + '</th>';
            });
            html += '</tr></thead>';
        }
        
        if (rows.length > 0) {
            html += '<tbody>';
            rows.forEach(function(row) {
                html += '<tr>';
                row.forEach(function(cell) {
                    html += '<td>' + cell + '</td>';
                });
                html += '</tr>';
            });
            html += '</tbody>';
        }
        
        html += '</table></div>';
        return html;
    }

    function formatMessage(text, sender) {
        if (sender === 'bot') {
            // Remove emoji / icons
            text = text.replace(/\p{Extended_Pictographic}/gu, '');
            // Remove heading numbers (e.g., 6.1. or ## 6.)
            text = text.replace(/(^|\n)(\s*#+\s*)?(\d+(?:\.\d+)+\.?)\s+/g, '$1$2');
            text = text.replace(/(^|\n)(\s*#+\s+)(\d+\.)\s+/g, '$1$2');
            // Remove markdown header hashes (#)
            text = text.replace(/#+/g, '');
        }

        var escaped = escapeHTML(text);

        // 1. Parse markdown tables
        escaped = parseMarkdownTables(escaped);

        // 2. Bold: **text**
        escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // 3. Bullet lists
        escaped = escaped.replace(/^[•\-]\s+(.+)$/gm, '<li>$1</li>');
        escaped = escaped.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // 4. Line breaks
        escaped = escaped.replace(/\n/g, '<br>');
        escaped = escaped.replace(/<br><ul>/g, '<ul>');
        escaped = escaped.replace(/<\/ul><br>/g, '</ul>');

        // 5. Strip unwanted <br> elements from around/inside table tags to avoid broken layout
        escaped = escaped.replace(/<br>\s*<\/?(table|thead|tbody|tr|th|td|div)/gi, function(match) {
            return match.replace('<br>', '').trim();
        });
        escaped = escaped.replace(/(table|thead|tbody|tr|th|td|div|thead|tbody)>\s*<br>/gi, function(match) {
            return match.replace('<br>', '').trim();
        });

        return escaped;
    }

    function escapeHTML(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // ============================================
    // TYPING INDICATOR
    // ============================================
    function showTypingIndicator() {
        if (typingIndicatorEl) return;

        typingIndicatorEl = document.createElement('div');
        typingIndicatorEl.className = 'typing-indicator';

        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = '&#x1FAB6;';

        var bubble = document.createElement('div');
        bubble.className = 'typing-bubble';
        bubble.innerHTML =
            '<span class="typing-dot"></span>' +
            '<span class="typing-dot"></span>' +
            '<span class="typing-dot"></span>';

        typingIndicatorEl.appendChild(avatar);
        typingIndicatorEl.appendChild(bubble);
        chatMessages.appendChild(typingIndicatorEl);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        if (typingIndicatorEl) {
            typingIndicatorEl.remove();
            typingIndicatorEl = null;
        }
    }

    // ============================================
    // UTILITIES
    // ============================================
    function formatTimestamp(date) {
        var h = date.getHours();
        var m = date.getMinutes();
        return (h < 10 ? '0' + h : '' + h) + ':' + (m < 10 ? '0' + m : '' + m);
    }

    function formatRelativeTime(timestamp) {
        var now = Date.now();
        var diff = now - timestamp;
        var minutes = Math.floor(diff / 60000);
        var hours = Math.floor(diff / 3600000);
        var days = Math.floor(diff / 86400000);

        if (minutes < 1) return 'Vừa xong';
        if (minutes < 60) return minutes + ' phút';
        if (hours < 24) return hours + ' giờ';
        if (days < 7) return days + ' ngày';

        var d = new Date(timestamp);
        return (d.getDate() < 10 ? '0' : '') + d.getDate() + '/' +
               (d.getMonth() + 1 < 10 ? '0' : '') + (d.getMonth() + 1);
    }

    function scrollToBottom() {
        requestAnimationFrame(function () {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // --- Sidebar Resize ---
    function setupSidebarResize() {
        var resizer = document.getElementById('sidebarResizer');
        var sidebar = document.getElementById('sidebar');
        var isResizing = false;

        if (!resizer || !sidebar) return;

        // Load saved width from localStorage
        var savedWidth = localStorage.getItem('vietbank_sidebar_width');
        if (savedWidth) {
            sidebar.style.width = savedWidth + 'px';
            sidebar.style.minWidth = savedWidth + 'px';
        }

        resizer.addEventListener('mousedown', function (e) {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', function (e) {
            if (!isResizing) return;
            var newWidth = e.clientX;
            // Limit width bounds
            if (newWidth < 200) newWidth = 200;
            if (newWidth > 450) newWidth = 450;
            
            sidebar.style.width = newWidth + 'px';
            sidebar.style.minWidth = newWidth + 'px';
        });

        document.addEventListener('mouseup', function () {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                localStorage.setItem('vietbank_sidebar_width', sidebar.offsetWidth);
            }
        });

        // Touch support for resizing
        resizer.addEventListener('touchstart', function (e) {
            isResizing = true;
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('touchmove', function (e) {
            if (!isResizing) return;
            var touch = e.touches[0];
            var newWidth = touch.clientX;
            if (newWidth < 200) newWidth = 200;
            if (newWidth > 450) newWidth = 450;
            sidebar.style.width = newWidth + 'px';
            sidebar.style.minWidth = newWidth + 'px';
        });

        document.addEventListener('touchend', function () {
            if (isResizing) {
                isResizing = false;
                document.body.style.userSelect = '';
                localStorage.setItem('vietbank_sidebar_width', sidebar.offsetWidth);
            }
        });
    }

    // --- Start ---
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
