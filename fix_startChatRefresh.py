# Fix the nested JavaScript blocks in startChatRefresh function
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the problematic section (lines 458-479)
old_block = """                            const domMessages = chatArea.querySelectorAll('.message');
                            if (data.mesajlar.length > domMessages.length) {
                                // Yeni mesaj var!
                                chatArea.innerHTML = ''; // Temizle
                                const currentUserId = {{ session.user_id }};

                            data.mesajlar.forEach(msg => {
                                addMessage(msg.mesaj, msg.gonderen_id == currentUserId, msg.olusturma_tarihi);
                            });

                            if (isNearBottom) {
                                chatArea.scrollTop = chatArea.scrollHeight;
                            } else {
                                chatArea.scrollTop = currentScroll;
                            }
                        }
                    }
                    })
            .catch(err => console.error('Chat refresh error:', err));
    }
        }, 5000);
    }"""

new_block = """                            const domMessages = chatArea.querySelectorAll('.message');
                            if (data.mesajlar.length > domMessages.length) {
                                // Yeni mesaj var!
                                chatArea.innerHTML = ''; // Temizle
                                const currentUserId = {{ session.user_id }};

                                data.mesajlar.forEach(msg => {
                                    addMessage(msg.mesaj, msg.gonderen_id == currentUserId, msg.olusturma_tarihi);
                                });

                                if (isNearBottom) {
                                    chatArea.scrollTop = chatArea.scrollHeight;
                                } else {
                                    chatArea.scrollTop = currentScroll;
                                }
                            }
                        }
                    })
                    .catch(err => console.error('Chat refresh error:', err));
            }
        }, 5000);
    }"""

content = content.replace(old_block, new_block)

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed startChatRefresh function!")
