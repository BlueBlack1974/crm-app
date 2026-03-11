
import os

target_path = r"d:\Yazılım_Projeler\Python\CRM\app\templates\instagram_mesajlar.html"

content = r'''{% extends "base.html" %}

{% block title %}{{ _('Instagram Messages') }} - Crandyx CRM{% endblock %}

{% block extra_css %}
<style>
    :root {
        --i-primary: #0095f6;
        --i-gradient: linear-gradient(90deg, #7f39fb 0%, #0095f6 100%);
        --bubble-received: #efefef;
        --bubble-sent-text: #fff;
        --border-color: #dbdbdb;
    }

    .chat-container {
        height: calc(100vh - 130px);
        background-color: #fff;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    .chat-sidebar {
        background-color: #fff;
        border-right: 1px solid var(--border-color);
        display: flex;
        flex-direction: column;
    }

    .chat-item {
        cursor: pointer;
        padding: 10px 15px;
        transition: background-color 0.1s;
        display: flex;
        align-items: center;
        border: none;
        position: relative;
        z-index: 5;
    }

    .chat-item:hover {
        background-color: #fafafa;
    }

    .chat-item.active {
        background-color: #efefef;
    }

    .user-avatar-initials {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: var(--i-gradient);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1.2rem;
        margin-right: 15px;
    }

    /* Header avatar smaller */
    .header-avatar-initials {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: var(--i-gradient);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 0.9rem;
        margin-right: 10px;
    }

    .chat-main {
        display: flex;
        flex-direction: column;
        background-color: #fff;
        height: 100%;
        overflow: hidden;
    }

    .chat-header {
        border-bottom: 1px solid var(--border-color);
        padding: 0 20px;
        height: 65px;
        display: flex;
        align-items: center;
        background-color: #fff;
        flex-shrink: 0;
    }

    .chat-history {
        flex-grow: 1;
        overflow-y: auto;
        padding: 20px;
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-height: 0;
    }

    .message {
        max-width: 65%;
        padding: 12px 16px;
        border-radius: 22px;
        position: relative;
        word-wrap: break-word;
        font-size: 0.95rem;
        line-height: 1.3;
        margin-bottom: 4px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }

    .mesaj-gelen {
        align-self: flex-start;
        background-color: var(--bubble-received);
        color: #000;
        border-bottom-left-radius: 4px;
    }

    .mesaj-giden {
        align-self: flex-end;
        background: var(--i-gradient);
        color: var(--bubble-sent-text);
        border-bottom-right-radius: 4px;
    }

    .message-time {
        font-size: 0.65rem;
        margin-top: 4px;
        text-align: right;
        opacity: 0.7;
        display: block;
    }

    .chat-input-area {
        padding: 20px;
        border-top: 1px solid var(--border-color);
    }

    .chat-input-wrapper {
        border: 1px solid var(--border-color);
        border-radius: 22px;
        padding: 5px 15px;
        display: flex;
        align-items: center;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }

    .chat-input {
        border: none;
        outline: none;
        width: 100%;
        height: 40px;
        background: transparent;
    }

    .btn-send {
        color: var(--i-primary);
        background: transparent;
        border: none;
        font-weight: 600;
        transition: opacity 0.2s;
    }

    .btn-send:hover {
        opacity: 0.7;
    }

    /* Scrollbar */
    .chat-history::-webkit-scrollbar {
        width: 6px;
    }

    .chat-history::-webkit-scrollbar-thumb {
        background-color: #dbdbdb;
        border-radius: 20px;
    }
</style>
{% endblock %}



{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h3 mb-0 text-gray-800">{{ _('Instagram Direct Messages') }}</h1>
</div>

<div class="chat-container row g-0">
    <!-- Sidebar -->
    <div class="col-md-4 col-lg-3 chat-sidebar">
        <div class="p-3 border-bottom">
            <input type="text" class="form-control rounded-pill border-0 bg-light" id="userSearch"
                placeholder="{{ _('Search...') }}">
        </div>
        <div class="list-group list-group-flush overflow-auto" style="flex-grow: 1;" id="conversationList">
            {% for conv in conversations %}
            <div class="chat-item" onclick="/*alert('Click 1');*/ loadChat(this)"
                data-user-id="{{ conv.api_target_id if conv.api_target_id else '' }}"
                data-user-name="{{ conv.musteri.tam_adi }}" data-is-customer="true">

                <div class="user-avatar-initials">
                    {% if conv.musteri.ProfilFotografi %}
                    <img src="{{ conv.musteri.ProfilFotografi }}"
                        style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">
                    {% else %}
                    <i class="fab fa-instagram"></i>
                    {% endif %}
                </div>

                <div class="flex-grow-1 overflow-hidden">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-0 text-truncate font-weight-bold text-dark">{{ conv.musteri.tam_adi }}</h6>
                        {% if conv.son_mesaj %}
                        <small class="text-muted small">{{ conv.son_mesaj.Tarih.strftime('%H:%M') }}</small>
                        {% endif %}
                    </div>
                    <p class="mb-0 text-muted small text-truncate">
                        {% if conv.son_mesaj %}
                        {{ conv.son_mesaj.MesajMetni }}
                        {% else %}
                        <span class="text-info">{{ _('Start a conversation') }}</span>
                        {% endif %}
                    </p>
                    <small class="text-xs text-secondary">{{ conv.musteri.InstagramKullaniciAdi }}</small>
                </div>
            </div>
            {% else %}
            <div class="p-4 text-center text-muted">
                {{ _('No customers with Instagram account found.') }}
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Main Chat -->
    <div class="col-md-8 col-lg-9 chat-main">
        <!-- Header -->
        <div class="chat-header" id="chatHeader" style="visibility: hidden;">
            <div id="headerAvatarContainer"></div>
            <div>
                <h6 class="m-0 font-weight-bold text-dark" id="chatTitle"></h6>
            </div>
        </div>

        <!-- Chat Area -->
        <div class="chat-history" id="chatArea">
            <div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted">
                <i class="fab fa-instagram fa-3x mb-3 text-gray-300"></i>
                <h5>{{ _('Select a conversation') }}</h5>
            </div>
        </div>

        <!-- Input -->
        <div class="chat-input-area" id="inputArea" style="display: none;">
            <form id="messageForm" onsubmit="sendMessage(event)">
                <input type="hidden" id="activeRecipientId">
                <div class="chat-input-wrapper">
                    <input type="text" class="chat-input" id="messageInput" placeholder="{{ _('Message...') }}"
                        autocomplete="off">
                    <button type="submit" class="btn-send" id="sendBtn">
                        {{ _('Send') }}
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
    console.log("Instagram Script Starting...");

    // Centralized Translations
    const STRINGS = {
        unknown_user: {{ _("Unknown User") | tojson }},
        no_history: {{ _("No message history available.") | tojson }},
        customer_not_contacted: {{ _("Customer has not contacted us yet.") | tojson }},
        no_messages: {{ _("No messages yet.") | tojson }},
        error_loading: {{ _("Error loading messages.") | tojson }},
        start_conversation: {{ _("Start a conversation") | tojson }},
        cannot_send: {{ _("Cannot send message: This customer has no linked Instagram ID (PSID). They must contact you first.") | tojson }},
        message_placeholder: {{ _("Message...") | tojson }}
    };

    // Ensure globally available
    window.loadChat = function (element) {
        // console.log('loadChat called', element);
        try {
            doLoadChat(element);
        } catch (e) {
            alert('JS Error: ' + e.message);
            console.error(e);
        }
    }

    function doLoadChat(element) {
        const userId = element.getAttribute('data-user-id');
        // UI Active State
        document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
        if (element) element.classList.add('active');

        // Header Update
        const userName = element.getAttribute('data-user-name');
        document.getElementById('chatTitle').innerText = userName || userId || STRINGS.unknown_user;

        document.getElementById('headerAvatarContainer').innerHTML = `
            <div class="header-avatar-initials">
                <i class="fab fa-instagram"></i>
            </div>`;

        // Always show the chat interface
        document.getElementById('chatHeader').style.visibility = 'visible';
        document.getElementById('inputArea').style.display = 'block';

        const msgInput = document.getElementById('messageInput');
        const activeRecipientId = document.getElementById('activeRecipientId');
        const chatArea = document.getElementById('chatArea');

        // Reset state
        msgInput.value = '';
        chatArea.innerHTML = '<div class="d-flex justify-content-center mt-5"><div class="spinner-border text-primary" role="status"></div></div>';
        
        if (!userId || userId === 'None' || userId === '') {
            // Case: Customer has no Instagram ID history
            activeRecipientId.value = '';
            msgInput.disabled = false; 

            chatArea.innerHTML = '<div class="text-center text-muted mt-5"><i class="fas fa-info-circle mb-2"></i><br>' + STRINGS.no_history + '<br><small>' + STRINGS.customer_not_contacted + '</small></div>';
            return;
        }

        // Case: Standard chat load
        activeRecipientId.value = userId;
        msgInput.disabled = false;
        msgInput.placeholder = STRINGS.message_placeholder;
        msgInput.focus();

        // Fetch messages
        fetch(`/instagram/api/mesajlar/${userId}`)
            .then(response => response.json())
            .then(data => {
                chatArea.innerHTML = '';
                if (data.error) {
                    chatArea.innerHTML = `<div class="text-danger text-center mt-4">${data.error}</div>`;
                    return;
                }

                if (data.length === 0) {
                    chatArea.innerHTML = '<div class="text-center text-muted mt-5">' + STRINGS.no_messages + '</div>';
                }

                data.forEach(msg => {
                    const isReceived = msg.yon === 'Gelen';
                    addMessage(msg.metin, !isReceived, msg.tarih);
                });

                chatArea.scrollTop = chatArea.scrollHeight;
            })
            .catch(err => {
                chatArea.innerHTML = '<div class="text-danger text-center mt-5">' + STRINGS.error_loading + '</div>';
                console.error(err);
            });
    }

    function addMessage(text, isSent, timestamp) {
        const chatArea = document.getElementById('chatArea');
        const placeholder = chatArea.querySelector('.text-center.text-muted');
        const spinner = chatArea.querySelector('.spinner-border');
        if (placeholder) placeholder.parentElement.remove();
        if (spinner) spinner.parentElement.parentElement.remove();

        const div = document.createElement('div');
        div.className = `message ${isSent ? 'mesaj-giden' : 'mesaj-gelen'}`;

        let displayTime = timestamp;
        if (timestamp && timestamp.includes(' ')) {
            displayTime = timestamp.split(' ')[1];
        } else if (!timestamp) {
            displayTime = new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
        }

        div.innerHTML = `
            ${escapeHtml(text)}
            <span class="message-time">${displayTime}</span>
        `;
        chatArea.appendChild(div);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/\n/g, '<br>');
    }

    // Bind sendMessage to window
    window.sendMessage = function (e) {
        e.preventDefault();
        const recipientId = document.getElementById('activeRecipientId').value;
        const input = document.getElementById('messageInput');
        const text = input.value.trim();

        if (!text) return;

        if (!recipientId) {
            alert(STRINGS.cannot_send);
            return;
        }

        addMessage(text, true, null);
        input.value = '';

        fetch('/instagram/api/mesaj-gonder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': "{{ csrf_token() }}"
            },
            body: JSON.stringify({
                recipient_id: recipientId,
                message_text: text
            })
        })
            .then(res => res.json())
            .then(data => {
                if (!data.success) {
                    alert('Message failed: ' + (data.message || 'Error'));
                }
            })
            .catch(err => {
                console.error(err);
                alert('Network error');
            });
    }

    // Search
    document.addEventListener('DOMContentLoaded', function (e) {
        const searchInput = document.getElementById('userSearch');
        if (searchInput) {
            searchInput.addEventListener('input', function (e) {
                const searchTerm = e.target.value.toLowerCase();
                const items = document.querySelectorAll('.chat-item');
                items.forEach(item => {
                    const userName = item.getAttribute('data-user-name').toLowerCase();
                    if (userName.includes(searchTerm)) {
                        item.style.display = 'flex';
                    } else {
                        item.style.display = 'none';
                    }
                });
            });
        }
    });

    console.log("Instagram Script Loaded & Ready");
</script>
{% endblock %}
'''

try:
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
