# Comprehensive fix for the loadChat function
with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the entire problematic section
old_section = """                } else {
                    const currentUserId = {{ session.user_id if session.user_id else 'null' }}; 


                    data.mesajlar.forEach(msg => {
                        addMessage(msg.mesaj, msg.gonderen_id == currentUserId, msg.olusturma_tarihi);
                    });
                }

                chatArea.scrollTop = chatArea.scrollHeight;

        updateUnreadCount();
        startChatRefresh(userId);
    })
            .catch (err => {"""

new_section = """                } else {
                    const currentUserId = {{ session.user_id if session.user_id else 'null' }}; 

                    data.mesajlar.forEach(msg => {
                        addMessage(msg.mesaj, msg.gonderen_id == currentUserId, msg.olusturma_tarihi);
                    });
                }

                chatArea.scrollTop = chatArea.scrollHeight;

                updateUnreadCount();
                startChatRefresh(userId);
            })
            .catch(err => {"""

content = content.replace(old_section, new_section)

with open(r'd:\Yazılım_Projeler\Python\CRM\app\templates\kullanici_mesajlar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed loadChat function indentation!")
