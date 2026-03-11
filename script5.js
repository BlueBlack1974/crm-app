
    // Global fonksiyonları en başta tanımla - HTML onclick attribute'ları için

    // Yeni görev modalını açma fonksiyonu - Global scope
    function openNewTaskModal() {
        console.log('Yeni Görev butonuna tıklandı!');
        console.log('Modal açılıyor...');

        try {
            // Bootstrap kontrolü
            console.log('Bootstrap mevcut mu:', typeof bootstrap !== 'undefined');
            console.log('Bootstrap Modal mevcut mu:', typeof bootstrap?.Modal !== 'undefined');

            // Modal elementini bul
            const modalElement = document.getElementById('quickGorevModal');
            console.log('Modal elementi bulundu:', modalElement);

            if (!modalElement) {
                console.error('Modal elementi bulunamadı!');
                return;
            }

            if (typeof bootstrap === 'undefined') {
                console.error('Bootstrap yüklenmemiş!');
                // Fallback: jQuery modal kullan
                if (typeof $ !== 'undefined') {
                    $('#quickGorevModal').modal('show');
                } else {
                    console.error('jQuery de yüklenmemiş!');
                }
                return;
            }

            // Bootstrap Modal instance oluştur
            const modal = new bootstrap.Modal(modalElement);
            console.log('Bootstrap Modal instance oluşturuldu:', modal);

            // Modal'ı göster
            modal.show();
            console.log('Modal.show() çağrıldı');

            // Seçenekleri yükle
            setTimeout(() => {
                console.log('Seçenekler yükleniyor...');
                if (typeof loadDurumlar === 'function') loadDurumlar();
                if (typeof loadKullanicilar === 'function') loadKullanicilar();
                if (typeof loadRandevuDefterleri === 'function') loadRandevuDefterleri();

                // Müşteri arama özelliğini aktif et
                if (typeof setupMusteriArama === 'function') {
                    console.log('Müşteri arama özelliği aktif ediliyor...');
                    setupMusteriArama();
                }

                // Tarih senkronizasyon özelliğini aktif et
                if (typeof setupTarihSenkronizasyonu === 'function') {
                    console.log('Tarih senkronizasyon özelliği aktif ediliyor...');
                    setupTarihSenkronizasyonu();
                }

                // Bugünün tarihini set et
                setTodayDate();
            }, 100);

        } catch (error) {
            console.error('Modal açılırken hata:', error);
            console.error('Hata detayı:', error.message);
            console.error('Stack trace:', error.stack);
        }
    }

    window.filterTasks = function () {
        console.log('=== filterTasks BAŞLADI ===');
        console.log('filterTasks çağrıldı');

        try {
            // Tarih input'larından değerleri oku
            const dateFilterStartEl = document.getElementById('dateFilterStart');
            const dateFilterEndEl = document.getElementById('dateFilterEnd');

            // Eğer tarih input'ları boşsa, bu ayı set et
            if (dateFilterStartEl && dateFilterEndEl) {
                if (!dateFilterStartEl.value || !dateFilterEndEl.value) {
                    const today = new Date();
                    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
                    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                    const expectedStart = getLocalYMD(firstDay);
                    const expectedEnd = getLocalYMD(lastDay);

                    dateFilterStartEl.value = expectedStart;
                    dateFilterEndEl.value = expectedEnd;
                    console.log('[FILTER] Tarih aralığı boştu, bu ay set edildi:', expectedStart, '-', expectedEnd);
                }
            }

            const searchTerm = document.getElementById('searchInput') ? document.getElementById('searchInput').value.toLowerCase() : '';
            const statusFilter = document.getElementById('statusFilter') ? document.getElementById('statusFilter').value : 'all';
            const priorityFilter = document.getElementById('priorityFilter') ? document.getElementById('priorityFilter').value : 'all';
            const dateFilterStart = dateFilterStartEl ? dateFilterStartEl.value : '';
            const dateFilterEnd = dateFilterEndEl ? dateFilterEndEl.value : '';

            console.log('=== FİLTRE DEĞERLERİ ===');
            console.log('Arama:', searchTerm);
            console.log('Durum:', statusFilter);
            console.log('Öncelik:', priorityFilter);
            console.log('Tarih Başlangıç:', dateFilterStart);
            console.log('Tarih Bitiş:', dateFilterEnd);
            console.log('Tarih filtresi aktif mi?', !!(dateFilterStart && dateFilterEnd));

            // Durum filtresi seçeneklerini kontrol et
            const statusSelect = document.getElementById('statusFilter');
            if (statusSelect) {
                console.log('Durum filtresi seçenekleri:');
                Array.from(statusSelect.options).forEach((option, index) => {
                    console.log(`  ${index}: value="${option.value}", text="${option.textContent}"`);
                });

                // Seçilen durumun adını bul
                const selectedOption = statusSelect.options[statusSelect.selectedIndex];
                console.log('Seçilen durum:', selectedOption.textContent, '(ID:', selectedOption.value + ')');
                var selectedStatusName = selectedOption.textContent.replace(/\([^)]*\)$/, '').trim(); // 'Ad (N)' -> 'Ad'
                var selectedStatusKey = normalizeStatusLabel(selectedStatusName);
            }

            // Tüm görünümlerdeki görevleri bul
            const cardTasks = document.querySelectorAll('.gorev-item');
            const listTasks = document.querySelectorAll('.gorev-list-item');
            const calendarTasks = document.querySelectorAll('.fc-event');

            console.log('Kart görevleri:', cardTasks.length);
            console.log('Liste görevleri:', listTasks.length);
            console.log('Takvim görevleri:', calendarTasks.length);

            const tasks = [...cardTasks, ...listTasks, ...calendarTasks];
            console.log('Toplam görev sayısı:', tasks.length);

            tasks.forEach((task, index) => {
                let showTask = true;
                console.log(`Görev ${index + 1}:`, task.className, task);

                // Görevin durum adını bul
                let statusText = 'Bilinmiyor';
                if (task.classList.contains('fc-event')) {
                    // Takvim event'i için
                    const eventId = task.getAttribute('data-event-id');
                    if (eventId && window.gorevlerCalendar) {
                        const event = window.gorevlerCalendar.getEventById(eventId);
                        if (event && event.extendedProps) {
                            statusText = event.extendedProps.durum ||
                                event.extendedProps.durum_adi ||
                                event.extendedProps.durumAdi ||
                                'Bilinmiyor';
                        }
                    }
                } else {
                    // Kart ve liste görünümü için
                    const statusBadge = task.querySelector('.badge');
                    statusText = statusBadge ? statusBadge.textContent.trim() : 'Bilinmiyor';
                }
                console.log(`Görev ${index + 1} durum adı:`, statusText);

                // Arama filtresi
                if (searchTerm) {
                    const title = task.querySelector('.card-title, .gorev-list-title, .fc-title')?.textContent.toLowerCase() || '';
                    const description = task.querySelector('.card-text, .gorev-list-description, .fc-description')?.textContent.toLowerCase() || '';
                    const taskText = task.textContent.toLowerCase();
                    if (!title.includes(searchTerm) && !description.includes(searchTerm) && !taskText.includes(searchTerm)) {
                        showTask = false;
                    }
                }

                // Durum filtresi
                if (statusFilter !== 'all') {
                    let taskStatusId = task.getAttribute('data-durum-id');

                    // Takvim event'i için özel durum ID alma
                    if (task.classList.contains('fc-event') && !taskStatusId) {
                        const eventId = task.getAttribute('data-event-id');
                        console.log(`Takvim event ID:`, eventId);

                        if (eventId && window.gorevlerCalendar) {
                            const event = window.gorevlerCalendar.getEventById(eventId);
                            console.log(`Takvim event objesi:`, event);

                            if (event && event.extendedProps) {
                                console.log(`Event extendedProps:`, event.extendedProps);
                                taskStatusId = event.extendedProps.durum_id ||
                                    event.extendedProps.durumID ||
                                    event.extendedProps.durum_id ||
                                    event.extendedProps.durum;
                                console.log(`Bulunan durum ID:`, taskStatusId);
                            }
                        }
                    }

                    console.log(`Görev ${index + 1} durum karşılaştırması:`, {
                        taskStatusId: taskStatusId,
                        statusFilter: statusFilter,
                        eşleşiyor: taskStatusId === statusFilter
                    });
                    // Karşılaştırma: ID eşleşmesi YA DA isim (lokalize) eşleşmesi
                    const statusBadge = task.querySelector('.badge, .durum-text');
                    const statusText = statusBadge ? statusBadge.textContent.trim() : '';
                    const taskStatusKey = normalizeStatusLabel(statusText);
                    const idMatches = String(taskStatusId) === String(statusFilter);
                    const nameMatches = taskStatusKey && typeof selectedStatusKey !== 'undefined' && (taskStatusKey === selectedStatusKey);
                    if (!idMatches && !nameMatches) {
                        showTask = false;
                    }
                }

                // Öncelik filtresi
                if (priorityFilter !== 'all') {
                    const taskPriority = task.classList.contains(`oncelik-${priorityFilter}`) ||
                        task.getAttribute('data-priority') === priorityFilter;
                    if (!taskPriority) {
                        showTask = false;
                    }
                }

                // Tarih aralığı filtresi - eğer tarih filtresi varsa kontrol et
                // NOT: Tarih filtresi aktifken, görevin herhangi bir tarihi aralıkta olmalı
                if (dateFilterStart && dateFilterEnd) {
                    console.log(`Görev ${index + 1} için tarih filtresi uygulanıyor: ${dateFilterStart} - ${dateFilterEnd}`);
                    let taskDateValues = [];

                    // Tarih bilgisi olmayan görevleri atla (gösterilecek)
                    // Çünkü tarih filtresi sadece tarihi olan görevler için çalışmalı

                    // Takvim event'i için
                    if (task.classList.contains('fc-event')) {
                        const eventId = task.getAttribute('data-event-id');
                        if (eventId && window.gorevlerCalendar) {
                            const event = window.gorevlerCalendar.getEventById(eventId);
                            if (event && event.start) {
                                taskDateValues.push(getLocalYMD(event.start));
                            }
                        }
                    } else {
                        // Kart ve liste görünümü için - önce task elementinin kendisinden tarih bilgilerini al
                        const bitisTarihi = task.getAttribute('data-bitis-tarihi');
                        const hatirlatmaTarihi = task.getAttribute('data-hatirlatma-tarihi');
                        const olusturmaTarihi = task.getAttribute('data-olusturma-tarihi');

                        // Eğer task elementinde yoksa, içindeki elementlerden al
                        if (!bitisTarihi || !hatirlatmaTarihi || !olusturmaTarihi) {
                            const bitisEl = task.querySelector('[data-bitis-tarihi]');
                            const hatirlatmaEl = task.querySelector('[data-hatirlatma-tarihi]');
                            const olusturmaEl = task.querySelector('[data-olusturma-tarihi]');

                            if (!bitisTarihi && bitisEl) {
                                taskDateValues.push(bitisEl.getAttribute('data-bitis-tarihi'));
                            }
                            if (!hatirlatmaTarihi && hatirlatmaEl) {
                                taskDateValues.push(hatirlatmaEl.getAttribute('data-hatirlatma-tarihi'));
                            }
                            if (!olusturmaTarihi && olusturmaEl) {
                                taskDateValues.push(olusturmaEl.getAttribute('data-olusturma-tarihi'));
                            }
                        }

                        // Task elementinden direkt alınan tarihler
                        if (bitisTarihi) taskDateValues.push(bitisTarihi);
                        if (hatirlatmaTarihi) taskDateValues.push(hatirlatmaTarihi);
                        if (olusturmaTarihi) taskDateValues.push(olusturmaTarihi);

                        // Eğer hiç tarih yoksa, task'ın kendisinden kontrol et
                        if (taskDateValues.length === 0) {
                            const taskStart = task.getAttribute('data-start');
                            if (taskStart) taskDateValues.push(taskStart);
                        }
                    }

                    console.log(`Görev ${index + 1} tarih değerleri:`, taskDateValues);

                    if (taskDateValues.length > 0) {
                        // Tarih aralığı içinde olup olmadığını kontrol et
                        // Görevin herhangi bir tarihi aralıkta ise göster
                        const startDate = dateFilterStart ? new Date(dateFilterStart + 'T00:00:00') : null;
                        const endDate = dateFilterEnd ? new Date(dateFilterEnd + 'T23:59:59') : null;

                        console.log(`Görev ${index + 1} tarih aralığı kontrolü - Start:`, startDate, 'End:', endDate);

                        let dateInRange = false;
                        for (let dateStr of taskDateValues) {
                            if (dateStr) {
                                const taskDate = new Date(dateStr + 'T00:00:00');
                                let isInRange = true;

                                if (startDate && taskDate < startDate) {
                                    isInRange = false;
                                    console.log(`Görev ${index + 1} tarih ${dateStr} başlangıçtan önce`);
                                }
                                if (endDate && taskDate > endDate) {
                                    isInRange = false;
                                    console.log(`Görev ${index + 1} tarih ${dateStr} bitişten sonra`);
                                }

                                if (isInRange) {
                                    dateInRange = true;
                                    console.log(`Görev ${index + 1} tarih ${dateStr} aralıkta`);
                                    break; // Herhangi bir tarih aralıkta ise yeterli
                                }
                            }
                        }

                        if (!dateInRange) {
                            console.log(`Görev ${index + 1} tarih aralığı dışında - gizleniyor`);
                            showTask = false;
                        } else {
                            console.log(`Görev ${index + 1} tarih aralığında - gösteriliyor`);
                        }
                    } else {
                        // Tarih bilgisi yoksa - tarih filtresi varsa bile göster
                        // Çünkü kullanıcı sadece tarihi olan görevleri filtrelemek ister, tarihi olmayan görevler her zaman görünür olmalı
                        console.log(`Görev ${index + 1} tarih bilgisi yok - varsayılan olarak gösteriliyor`);
                        // Tarih bilgisi olmayan görevleri her zaman göster
                        // showTask zaten true, değiştirmeye gerek yok
                    }
                } else {
                    // Tarih filtresi yoksa, tüm görevleri göster
                    console.log(`Görev ${index + 1} için tarih filtresi yok - gösteriliyor`);
                }

                // Görevi göster/gizle
                if (showTask) {
                    // Liste görünümü için flex, diğerleri için block
                    const displayValue = task.classList.contains('list-group-item') ? 'flex' : 'block';
                    task.style.setProperty('display', displayValue, 'important');
                    task.style.setProperty('visibility', 'visible', 'important');
                    task.style.setProperty('opacity', '1', 'important');
                    task.classList.remove('filtered-hidden');

                    // Takvim event'i için özel işlem
                    if (task.classList.contains('fc-event')) {
                        task.style.setProperty('display', 'block', 'important');
                        task.style.setProperty('visibility', 'visible', 'important');
                        task.style.setProperty('opacity', '1', 'important');
                    }
                } else {
                    task.style.setProperty('display', 'none', 'important');
                    task.style.setProperty('visibility', 'hidden', 'important');
                    task.style.setProperty('opacity', '0', 'important');
                    task.classList.add('filtered-hidden');

                    // Takvim event'i için özel işlem
                    if (task.classList.contains('fc-event')) {
                        task.style.setProperty('display', 'none', 'important');
                        task.style.setProperty('visibility', 'hidden', 'important');
                        task.style.setProperty('opacity', '0', 'important');
                    }
                }
                console.log(`Görev ${index + 1} gösterilecek mi:`, showTask, 'display:', task.style.display, 'classList:', task.classList.toString());
            });

            // Takvim event'leri için CSS ile gizleme
            if (window.gorevlerCalendar) {
                console.log('Takvim event\'leri CSS ile güncelleniyor...');
                // Tüm event'leri göster
                const allEvents = window.gorevlerCalendar.getEvents();
                allEvents.forEach(event => {
                    const eventEl = event.el;
                    if (eventEl) {
                        // Event elementini bul ve stilini güncelle
                        const isVisible = !eventEl.classList.contains('filtered-hidden');
                        if (isVisible) {
                            eventEl.style.setProperty('display', 'block', 'important');
                            eventEl.style.setProperty('visibility', 'visible', 'important');
                            eventEl.style.setProperty('opacity', '1', 'important');
                        } else {
                            eventEl.style.setProperty('display', 'none', 'important');
                            eventEl.style.setProperty('visibility', 'hidden', 'important');
                            eventEl.style.setProperty('opacity', '0', 'important');
                        }
                    }
                });
            }

            // Sonuçları tarihe göre (Yakından Uzağa) sırala. Tamamlananları en alta at
            const sortTasksChronologically = (containerSelector, itemSelector) => {
                const container = document.querySelector(containerSelector);
                if (!container) return;
                const items = Array.from(container.querySelectorAll(itemSelector));
                items.sort((a, b) => {
                    const getSortDate = (el) => {
                        const statusBadge = el.querySelector('.durum-text');
                        const statusText = statusBadge ? statusBadge.getAttribute('data-durum') || statusBadge.textContent.trim() : '';
                        if (statusText === 'Tamamlandı' || statusText.toLowerCase() === 'completed') return '9999-12-32';
                        return el.getAttribute('data-bitis-tarihi') || el.getAttribute('data-hatirlatma-tarihi') || el.getAttribute('data-olusturma-tarihi') || '9999-12-31';
                    };
                    return getSortDate(a).localeCompare(getSortDate(b));
                });
                items.forEach(item => container.appendChild(item));
            };

            sortTasksChronologically('#gorevlerListesi', '.gorev-item');
            sortTasksChronologically('#listView .list-group', '.gorev-item');

            // Filtre sonuçlarını güncelle
            updateFilterResults();

            console.log('=== filterTasks BİTTİ ===');

        } catch (error) {
            console.error('filterTasks hatası:', error);
            console.error('Hata detayı:', error.message);
            console.error('Stack trace:', error.stack);
        }
    };

    window.clearFilters = function () {
        console.log('=== clearFilters BAŞLADI ===');
        console.log('clearFilters çağrıldı');

        try {
            document.getElementById('searchInput').value = '';
            document.getElementById('statusFilter').value = 'all';
            document.getElementById('priorityFilter').value = 'all';

            // Tarih aralığını bu ay olarak set et (temizleme, bu ayı göster)
            const dateFilterStartEl = document.getElementById('dateFilterStart');
            const dateFilterEndEl = document.getElementById('dateFilterEnd');
            if (dateFilterStartEl && dateFilterEndEl) {
                const today = new Date();
                const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
                const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                dateFilterStartEl.value = getLocalYMD(firstDay);
                dateFilterEndEl.value = getLocalYMD(lastDay);
                console.log('[CLEAR FILTERS] Tarih aralığı bu ay olarak set edildi');
            }

            // Tüm görevleri göster
            const cardTasks = document.querySelectorAll('.gorev-item');
            const listTasks = document.querySelectorAll('.gorev-list-item');
            const calendarTasks = document.querySelectorAll('.fc-event');

            [...cardTasks, ...listTasks, ...calendarTasks].forEach(task => {
                // Liste görünümü için flex, diğerleri için block
                const displayValue = task.classList.contains('list-group-item') ? 'flex' : 'block';
                task.style.setProperty('display', displayValue, 'important');
                task.style.setProperty('visibility', 'visible', 'important');
                task.style.setProperty('opacity', '1', 'important');
                task.classList.remove('filtered-hidden');
            });

            updateFilterResults();

            // Filtre durumunu localStorage'dan temizle
            localStorage.removeItem('gorevlerFilters');

            console.log('=== clearFilters BİTTİ ===');

        } catch (error) {
            console.error('clearFilters hatası:', error);
            console.error('Hata detayı:', error.message);
            console.error('Stack trace:', error.stack);
        }
    };

    window.updateFilterResults = function () {
        const visibleTasks = document.querySelectorAll('.gorev-item[style*="block"], .gorev-item:not([style*="none"]), .gorev-list-item[style*="block"], .gorev-list-item:not([style*="none"]), .fc-event[style*="block"], .fc-event:not([style*="none"])');
        const totalTasks = document.querySelectorAll('.gorev-item, .gorev-list-item, .fc-event').length;

        // Sonuç sayısını göster
        const resultInfo = document.querySelector('.filter-results');
        if (resultInfo) {
            resultInfo.textContent = `${visibleTasks.length} / ${totalTasks} görev gösteriliyor`;
        }
    };

    function showContextMenu(event, gorevId) {
        console.log('showContextMenu çağrıldı, gorevId:', gorevId, 'event:', event);
        event.preventDefault();
        event.stopPropagation();

        // Mevcut menüyü kaldır
        const existingMenu = document.getElementById('contextMenu');
        if (existingMenu) {
            existingMenu.remove();
        }

        // Yeni menü oluştur
        const menu = document.createElement('div');
        menu.id = 'contextMenu';
        menu.className = 'context-menu';
        menu.style.cssText = `
        position: fixed;
        background: white;
        border: 1px solid #ccc;
        border-radius: 4px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        z-index: 99999;
        padding: 5px 0;
        min-width: 150px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;

        menu.innerHTML = `
        <div class="context-menu-item" onclick="editGorev(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; border-bottom: 1px solid #eee; display: flex; align-items: center;">
            <i class="fas fa-edit me-2"></i>{{ _('Görev Düzenle') }}
        </div>
        <div class="context-menu-item" onclick="moveToRandevu(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; border-bottom: 1px solid #eee; display: flex; align-items: center;">
            <i class="fas fa-calendar-plus me-2"></i>{{ _('Randevu') }}
        </div>
        <div class="context-menu-item" onclick="quickComplete(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; border-bottom: 1px solid #eee; color: #198754; display: flex; align-items: center;">
            <i class="fas fa-check me-2"></i>{{ _('Tamamlandı') }}
        </div>
        <div class="context-menu-item" onclick="deleteGorev(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; color: #dc3545; display: flex; align-items: center;">
            <i class="fas fa-trash me-2"></i>{{ _('Sil') }}
        </div>
    `;

        // Menüyü konumlandır - mouse pozisyonunu doğru al
        let left, top;

        // Mouse pozisyonunu al - farklı yöntemlerle dene
        if (event.clientX !== undefined && event.clientY !== undefined && event.clientX > 0 && event.clientY > 0) {
            left = event.clientX;
            top = event.clientY;
            console.log('clientX/Y kullanıldı:', { left, top });
        } else if (event.pageX !== undefined && event.pageY !== undefined && event.pageX > 0 && event.pageY > 0) {
            left = event.pageX;
            top = event.pageY;
            console.log('pageX/Y kullanıldı:', { left, top });
        } else if (event.screenX !== undefined && event.screenY !== undefined) {
            // Screen koordinatlarını viewport koordinatlarına çevir
            left = event.screenX - window.screenX;
            top = event.screenY - window.screenY;
            console.log('screenX/Y kullanıldı:', { left, top });
        } else {
            // Fallback - rastgele pozisyon
            left = Math.random() * 300 + 100;
            top = Math.random() * 300 + 100;
            console.log('Fallback kullanıldı:', { left, top });
        }

        console.log('Mouse pozisyonu:', {
            left,
            top,
            pageX: event.pageX,
            pageY: event.pageY,
            clientX: event.clientX,
            clientY: event.clientY,
            screenX: event.screenX,
            screenY: event.screenY,
            type: event.type,
            target: event.target
        });

        // Viewport sınırlarını kontrol et
        const menuWidth = 150;
        const menuHeight = 120;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (left + menuWidth > viewportWidth) {
            left = viewportWidth - menuWidth - 10;
        }
        if (top + menuHeight > viewportHeight) {
            top = viewportHeight - menuHeight - 10;
        }

        menu.style.left = left + 'px';
        menu.style.top = top + 'px';

        console.log('Menü konumu:', { left, top });

        document.body.appendChild(menu);

        // Menü dışına tıklandığında kapat
        setTimeout(() => {
            document.addEventListener('click', hideContextMenu, true);
        }, 50);
    }

    // Sağ tık menüsünü gizle
    function hideContextMenu(event) {
        // Eğer menü içine tıklandıysa kapatma
        if (event && event.target && event.target.closest('#contextMenu')) {
            return;
        }

        const menu = document.getElementById('contextMenu');
        if (menu) {
            menu.remove();
        }
        document.removeEventListener('click', hideContextMenu, true);
    }

    // Görev silme fonksiyonu (yukarıda tanımlı)

    // Element'ten görev ID'sini al
    function getGorevIdFromElement(element) {
        // Önce data-event-id'den dene
        const eventId = element.getAttribute('data-event-id');
        if (eventId) {
            const event = window.gorevlerCalendar.getEventById(eventId);
            if (event && event.extendedProps.gorev_id) {
                return event.extendedProps.gorev_id;
            }
        }

        // FullCalendar'ın event sisteminden tüm event'leri al
        const allEvents = window.gorevlerCalendar.getEvents();
        if (allEvents.length > 0) {
            // İlk event'i kullan (tek event var)
            const event = allEvents[0];
            if (event && event.extendedProps && event.extendedProps.gorev_id) {
                return event.extendedProps.gorev_id;
            }
        }

        return null;
    }

    function addContextMenuListeners() {
        console.log('Context menu listener\'ları ekleniyor...');

        // Takvim event'lerini bul
        const eventElements = document.querySelectorAll('.fc-event');
        console.log('Bulunan event elementleri:', eventElements.length);

        eventElements.forEach((element, index) => {
            console.log(`Event ${index} element:`, element);

            // Context menu için event listener
            element.addEventListener('contextmenu', function (e) {
                console.log('Sağ tık algılandı!', e);
                e.preventDefault();
                e.stopPropagation();

                // Doğrudan context menu göster - FullCalendar eventClick'i kullanma
                const gorevId = getGorevIdFromElement(element);
                if (gorevId) {
                    console.log('Görev ID bulundu:', gorevId);
                    showContextMenu(e, gorevId);
                } else {
                    console.log('Görev ID bulunamadı');
                }
            }, true);

            // Mouse down event'i de ekle (sağ tık için)
            element.addEventListener('mousedown', function (e) {
                if (e.button === 2) { // Sağ tık
                    console.log('Sağ tık mousedown algılandı!', e);
                    e.preventDefault();
                    e.stopPropagation();

                    // Doğrudan context menu göster - FullCalendar eventClick'i kullanma
                    const gorevId = getGorevIdFromElement(element);
                    if (gorevId) {
                        console.log('Görev ID bulundu:', gorevId);
                        showContextMenu(e, gorevId);
                    } else {
                        console.log('Görev ID bulunamadı');
                    }
                }
            }, true);
        });
    }

    function editGorev(gorevId) {
        console.log('=== editGorev BAŞLADI ===');
        console.log('Görev ID:', gorevId);

        // Önce durumları, kullanıcıları, defterleri ve görev verilerini yükle
        Promise.all([
            fetch('/api/gorev-durumlar').then(r => {
                console.log('Durumlar API response status:', r.status);
                return r.json();
            }),
            fetch('/api/kullanicilar').then(r => {
                console.log('Kullanıcılar API response status:', r.status);
                return r.json();
            }),
            fetch('/api/randevu-defterleri').then(r => {
                console.log('Defterler API response status:', r.status);
                return r.json();
            }),
            fetch(`/todos/${gorevId}/guncelle`).then(r => {
                console.log('Görev güncelleme API response status:', r.status);
                return r.json();
            })
        ])
            .then(([durumlarResponse, kullanicilarResponse, defterlerResponse, gorevResponse]) => {
                console.log('Durumlar response:', durumlarResponse);
                console.log('Kullanıcılar response:', kullanicilarResponse);
                console.log('Defterler response:', defterlerResponse);
                console.log('Görev response:', gorevResponse);

                if (!durumlarResponse.success || !kullanicilarResponse.success || !gorevResponse.success) {
                    console.error('API response başarısız:', {
                        durumlar: durumlarResponse.success,
                        kullanicilar: kullanicilarResponse.success,
                        defterler: defterlerResponse ? defterlerResponse.success : 'undefined',
                        gorev: gorevResponse.success
                    });
                    throw new Error('Veri yüklenirken hata oluştu');
                }

                // Defterler response'unu kontrol et
                if (!defterlerResponse || !defterlerResponse.success) {
                    console.warn('Defterler API başarısız, boş liste kullanılıyor:', defterlerResponse);
                }

                const durumlar = durumlarResponse.durumlar || [];
                const kullanicilar = kullanicilarResponse.kullanicilar || [];
                const defterler = (defterlerResponse && defterlerResponse.defterler) ? defterlerResponse.defterler : [];
                const gorev = gorevResponse.todo;

                console.log('Durumlar:', durumlar);
                console.log('Kullanıcılar:', kullanicilar);
                console.log('Defterler:', defterler);
                console.log('Görev:', gorev);
                console.log('Görev KullaniciID:', gorev.KullaniciID, 'tip:', typeof gorev.KullaniciID);
                console.log('Görev tüm alanları:', Object.keys(gorev));
                console.log('Görev KullaniciID alternatifleri:', {
                    KullaniciID: gorev.KullaniciID,
                    AtananKullaniciID: gorev.AtananKullaniciID,
                    kullanici_id: gorev.kullanici_id,
                    Kullanici: gorev.Kullanici,
                    kullanici: gorev.kullanici,
                    UserID: gorev.UserID,
                    user_id: gorev.user_id
                });
                console.log('Kullanıcı ID\'leri:', kullanicilar.map(k => ({ id: k.id, tip: typeof k.id })));

                // Müşteri bilgilerini çek (eğer ad ve soyad varsa)
                let musteriPromise = Promise.resolve({ telefon: '', email: '' });
                if (gorev.MusteriAdi && gorev.MusteriSoyadi) {
                    musteriPromise = fetch(`/api/musteri-bilgi?ad=${encodeURIComponent(gorev.MusteriAdi)}&soyad=${encodeURIComponent(gorev.MusteriSoyadi)}`)
                        .then(r => r.json())
                        .then(data => {
                            if (data.success && data.musteri) {
                                return {
                                    telefon: data.musteri.telefon || gorev.MusteriTelefon || '',
                                    email: data.musteri.email || gorev.MusteriEmail || ''
                                };
                            }
                            return {
                                telefon: gorev.MusteriTelefon || '',
                                email: gorev.MusteriEmail || ''
                            };
                        })
                        .catch(error => {
                            console.error('Müşteri bilgisi çekilirken hata:', error);
                            return {
                                telefon: gorev.MusteriTelefon || '',
                                email: gorev.MusteriEmail || ''
                            };
                        });
                }

                return musteriPromise.then(musteriBilgileri => {
                    // Müşteri bilgilerini güncelle
                    gorev.MusteriTelefon = musteriBilgileri.telefon;
                    gorev.MusteriEmail = musteriBilgileri.email;

                    return { durumlar, kullanicilar, defterler, gorev };
                });
            })
            .then(({ durumlar, kullanicilar, defterler, gorev }) => {

                // Modal HTML'ini oluştur
                const modalHTML = `
            <div class="modal fade" id="editGorevModal" tabindex="-1" aria-labelledby="editGorevModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="editGorevModalLabel">{{ _('Görev Düzenle') }}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <form id="editGorevForm">
                            <div class="modal-body">
                                <input type="hidden" id="edit_gorev_id" name="gorev_id" value="${gorev.TodoID}">
                                
                                <div class="mb-3">
                                    <label for="edit_baslik" class="form-label">{{ _('Başlık') }} *</label>
                                    <input type="text" class="form-control" id="edit_baslik" name="baslik" value="${gorev.Baslik || ''}" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="edit_aciklama" class="form-label">{{ _('Açıklama') }}</label>
                                    <textarea class="form-control" id="edit_aciklama" name="aciklama" rows="3">${gorev.Aciklama || ''}</textarea>
                                </div>
                                
                                <div class="row">
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label for="edit_oncelik" class="form-label">{{ _('Öncelik') }}</label>
                                            <select class="form-select" id="edit_oncelik" name="oncelik">
                                                <option value="Düşük" ${gorev.Oncelik === 'Düşük' ? 'selected' : ''}>{{ _('Düşük') }}</option>
                                                <option value="Orta" ${gorev.Oncelik === 'Orta' ? 'selected' : ''}>{{ _('Orta') }}</option>
                                                <option value="Yüksek" ${gorev.Oncelik === 'Yüksek' ? 'selected' : ''}>{{ _('Yüksek') }}</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label for="edit_durum" class="form-label">{{ _('Durum') }}</label>
                                            <select class="form-select" id="edit_durum" name="durum">
                                                <option value="">{{ _('Durum Seçin') }}</option>
                                                ${durumlar.map(durum =>
                    `<option value="${durum.DurumAdi}" ${gorev.Durum === durum.DurumAdi ? 'selected' : ''}>${durum.DurumAdi}</option>`
                ).join('')}
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="mb-3">
                                            <label for="edit_bitis_tarihi" class="form-label">{{ _('Bitiş Tarihi') }}</label>
                                            <input type="date" class="form-control" id="edit_bitis_tarihi" name="bitis_tarihi" value="${gorev.BitisTarihi || ''}">
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="edit_hatirlatma_tarihi" class="form-label">{{ _('Hatırlatma Tarihi') }}</label>
                                            <input type="date" class="form-control" id="edit_hatirlatma_tarihi" name="hatirlatma_tarihi" value="${gorev.HatirlatmaTarihi || ''}">
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Kullanıcı ve Defter Seçimi -->
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="edit_kullanici" class="form-label">{{ _('Atanan Kullanıcı') }}</label>
                                            <select class="form-select" id="edit_kullanici" name="kullanici_id">
                                                <option value="">{{ _('Kullanıcı Seçin') }}</option>
                                                ${kullanicilar.map(kullanici =>
                    `<option value="${kullanici.id}" ${gorev.AtananKullaniciID == kullanici.id || gorev.AtananKullaniciID == parseInt(kullanici.id) ? 'selected' : ''}>${kullanici.tam_adi}</option>`
                ).join('')}
                                            </select>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="edit_randevu_defteri" class="form-label">{{ _('Randevu Defteri') }}</label>
                                            <select class="form-select" id="edit_randevu_defteri" name="randevu_defteri_id">
                                                <option value="">{{ _('Defter Seçin') }}</option>
                                                ${defterler.map(defter =>
                    `<option value="${defter.AyarID}" ${gorev.RandevuDefteriID == defter.AyarID ? 'selected' : ''}>${defter.DefterAdi}</option>`
                ).join('')}
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Müşteri Bilgileri -->
                                <div class="card mb-3">
                                    <div class="card-header">
                                        <h6 class="mb-0">{{ _('Müşteri Bilgileri') }}</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="gorev_musteri_adi" class="form-label">{{ _('Müşteri Adı') }}</label>
                                                    <input type="text" class="form-control" id="gorev_musteri_adi" name="musteri_adi" value="${gorev.MusteriAdi || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="gorev_musteri_soyadi" class="form-label">{{ _('Müşteri Soyadı') }}</label>
                                                    <input type="text" class="form-control" id="gorev_musteri_soyadi" name="musteri_soyadi" value="${gorev.MusteriSoyadi || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                </div>
                                            </div>
                                        </div>
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="gorev_musteri_telefon" class="form-label">{{ _('Telefon') }}</label>
                                                    <input type="tel" class="form-control" id="gorev_musteri_telefon" name="musteri_telefon" value="${gorev.MusteriTelefon || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="gorev_musteri_email" class="form-label">{{ _('E-posta') }}</label>
                                                    <input type="email" class="form-control" id="gorev_musteri_email" name="musteri_email" value="${gorev.MusteriEmail || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ _('İptal') }}</button>
                                <button type="submit" class="btn btn-primary">{{ _('Güncelle') }}</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

                // Mevcut modal'ı kaldır
                const existingModal = document.getElementById('editGorevModal');
                if (existingModal) {
                    existingModal.remove();
                }

                // Modal'ı body'ye ekle
                document.body.insertAdjacentHTML('beforeend', modalHTML);

                // Form submit event'ini bağla
                document.getElementById('editGorevForm').addEventListener('submit', function (e) {
                    e.preventDefault();
                    updateGorev(gorevId);
                });

                // Modal'ı göster
                const modal = new bootstrap.Modal(document.getElementById('editGorevModal'));
                modal.show();
            })
            .catch(error => {
                console.error('Görev düzenleme hatası:', error);
                alert('Görev bilgileri yüklenirken hata oluştu: ' + error.message);
            });
    }

    function updateGorev(gorevId) {
        const form = document.getElementById('editGorevForm');
        const formData = new FormData(form);

        const data = {
            baslik: formData.get('baslik'),
            aciklama: formData.get('aciklama'),
            oncelik: formData.get('oncelik'),
            durum: formData.get('durum'),
            bitis_tarihi: formData.get('bitis_tarihi'),
            hatirlatma_tarihi: formData.get('hatirlatma_tarihi'),
            AtananKullaniciID: formData.get('kullanici_id'),
            randevu_defteri_id: formData.get('randevu_defteri_id'),
            musteri_adi: formData.get('musteri_adi'),
            musteri_soyadi: formData.get('musteri_soyadi'),
            musteri_telefon: formData.get('musteri_telefon'),
            musteri_email: formData.get('musteri_email')
        };

        fetch(`/todos/${gorevId}/guncelle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("{{ _('Görev başarıyla güncellendi!') }}");
                    // Modal'ı kapat
                    const modal = bootstrap.Modal.getInstance(document.getElementById('editGorevModal'));
                    modal.hide();
                    // Sayfayı yenile
                    location.reload();
                } else {
                    alert("{{ _('Görev güncellenirken hata: ') }} " + data.message);
                }
            })
            .catch(error => {
                console.error('Görev güncelleme hatası:', error);
                alert("{{ _('Görev güncellenirken hata oluştu') }}");
            });
    }

    function changeView(viewType) {
        console.log('=== changeView BAŞLADI ===');
        console.log('changeView çağrıldı:', viewType);
        console.log('localStorage gorevlerView:', localStorage.getItem('gorevlerView'));
        console.log('Görünüm değiştiriliyor:', viewType);

        // Tüm görünümleri gizle
        const cardsView = document.getElementById('cardsView');
        const listView = document.getElementById('listView');
        const calendarView = document.getElementById('calendarView');

        console.log('View elementleri:', {
            cardsView: cardsView ? 'BULUNDU' : 'BULUNAMADI',
            listView: listView ? 'BULUNDU' : 'BULUNAMADI',
            calendarView: calendarView ? 'BULUNDU' : 'BULUNAMADI'
        });

        console.log('Tüm görünümler gizleniyor...');
        if (cardsView) {
            cardsView.style.display = 'none';
            console.log('cardsView gizlendi');
        }
        if (listView) {
            listView.style.display = 'none';
            console.log('listView gizlendi');
        }
        if (calendarView) {
            calendarView.style.display = 'none';
            console.log('calendarView gizlendi');
        }

        // Seçilen görünümü göster
        if (viewType === 'cards' && cardsView) {
            console.log('✅ Kartlar görünümü gösteriliyor');
            cardsView.style.display = 'block';
            console.log('cardsView display:', cardsView.style.display);
        } else if (viewType === 'list' && listView) {
            console.log('✅ Liste görünümü gösteriliyor');
            listView.style.display = 'block';
            console.log('listView display:', listView.style.display);
        } else if (viewType === 'calendar' && calendarView) {
            console.log('✅ Takvim görünümü seçiliyor...');
            calendarView.style.display = 'block';
            console.log('calendarView display:', calendarView.style.display);
            // Takvim görünümü seçildiğinde takvimi başlat
            setTimeout(() => {
                console.log('Takvim başlatılıyor...');
                if (typeof initializeCalendar === 'function') {
                    initializeCalendar();
                    // Varsayılan olarak tamamlananları gizle
                    try { window.filterTasks && window.filterTasks(); } catch (e) { }
                } else {
                    console.error('initializeCalendar fonksiyonu bulunamadı!');
                }
                // CSS override'ları da uygula
                setTimeout(() => {
                    if (typeof applyCalendarStyles === 'function') {
                        applyCalendarStyles();
                    } else {
                        console.error('applyCalendarStyles fonksiyonu bulunamadı!');
                    }

                    // Takvim yüklendikten sonra mevcut filtreleri uygula
                    setTimeout(() => {
                        console.log('Takvim yüklendikten sonra filtreler uygulanıyor...');
                        filterTasks();
                    }, 500);
                }, 200);
            }, 100);
        } else {
            console.log('Görünüm bulunamadı veya element yok:', viewType);
            console.log('Mevcut elementler:', { cardsView: !!cardsView, listView: !!listView, calendarView: !!calendarView });
        }

        // Tercihi kaydet
        localStorage.setItem('gorevlerView', viewType);

        // Filtre durumunu kaydet
        const searchTerm = document.getElementById('searchInput').value;
        const statusFilter = document.getElementById('statusFilter').value;
        const priorityFilter = document.getElementById('priorityFilter').value;
        const dateFilterStart = document.getElementById('dateFilterStart').value;
        const dateFilterEnd = document.getElementById('dateFilterEnd').value;

        localStorage.setItem('gorevlerFilters', JSON.stringify({
            searchTerm: searchTerm,
            statusFilter: statusFilter,
            priorityFilter: priorityFilter,
            dateFilterStart: dateFilterStart,
            dateFilterEnd: dateFilterEnd
        }));

        // Buton durumlarını güncelle
        console.log('=== CHANGEVIEW - BUTON İŞARETLEME BAŞLADI ===');
        document.querySelectorAll('[data-view]').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-view') === viewType) {
                btn.classList.add('active');
                console.log('✅ CHANGEVIEW - Buton işaretlendi:', btn.getAttribute('data-view'));
                // Görsel olarak da gösterelim
                btn.style.backgroundColor = '#007bff';
                btn.style.color = 'white';
                btn.style.borderColor = '#007bff';
            } else {
                console.log('❌ CHANGEVIEW - Buton işaretlenmedi:', btn.getAttribute('data-view'));
                // Diğer butonları normal yapalım
                btn.style.backgroundColor = '';
                btn.style.color = '';
                btn.style.borderColor = '';
            }
        });
        console.log('=== CHANGEVIEW - BUTON İŞARETLEME BİTTİ ===');

        console.log('=== changeView BİTTİ ===');
    }

    // Takvim başlatma fonksiyonu (duplicate)
    function initializeCalendar() {
        console.log('Takvim başlatılıyor...');
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('Calendar element bulunamadı!');
            return;
        }

        console.log('Calendar element bulundu:', calendarEl);

        // Eğer takvim zaten başlatılmışsa, temizle
        if (window.gorevlerCalendar) {
            console.log('Eski takvim temizleniyor...');
            window.gorevlerCalendar.destroy();
        }

        // FullCalendar başlat (ikinci takvim örneği)
        const htmlLang2 = (document.documentElement.lang || 'tr').toLowerCase();
        const fcLocale2 = ({ 'tr': 'tr', 'en': 'en', 'en-us': 'en', 'en-gb': 'en-gb', 'fr': 'fr', 'de': 'de' })[htmlLang2] || 'tr';
        window.gorevlerCalendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: fcLocale2,
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,listWeek'
            },
            buttonText: (function () {
                if (fcLocale2.startsWith('en')) return { today: 'Today', month: 'Month', week: 'Week', day: 'Day', list: 'List' };
                if (fcLocale2.startsWith('fr')) return { today: 'Aujourd\'hui', month: 'Mois', week: 'Semaine', day: 'Jour', list: 'Liste' };
                if (fcLocale2.startsWith('de')) return { today: 'Heute', month: 'Monat', week: 'Woche', day: 'Tag', list: 'Liste' };
                return { today: 'Bugün', month: 'Ay', week: 'Hafta', day: 'Gün', list: 'Liste' };
            })(),
            events: function (info, successCallback, failureCallback) {
                // Cache-busting için timestamp ekle
                const url = `/api/gorevler/calendar?start=${info.startStr}&end=${info.endStr}&_t=${Date.now()}`;
                console.log('Takvim API çağrısı:', url);

                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        console.log('Takvim verileri:', data);
                        successCallback(data);
                    })
                    .catch(error => {
                        console.error('Takvim API hatası:', error);
                        failureCallback(error);
                    });
            },
            dayMaxEvents: false,
            moreLinkClick: 'popover',
            height: 'auto',
            contentHeight: 'auto',
            displayEventTime: false,
            eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
            eventDisplay: 'block',
            slotMinTime: '06:00:00',
            slotMaxTime: '22:00:00',
            slotDuration: '00:15:00',
            snapDuration: '00:15:00',
            eventContent: function (arg) {
                const defterAdi = arg.event.extendedProps && arg.event.extendedProps.defter_adi;
                const container = document.createElement('div');
                container.style.whiteSpace = 'normal';
                container.style.lineHeight = '1.2';
                container.innerHTML = `<div>${arg.event.title}</div>` +
                    (defterAdi ? `<div style="font-size: 0.75rem; color: rgba(255,255,255,0.6); opacity: 0.8; text-align: left;">${defterAdi}</div>` : '');
                return { domNodes: [container] };
            },
            eventDidMount: function (info) {
                const el = info.el;
                el.style.setProperty('border-radius', '4px', 'important');
                el.style.setProperty('font-size', '0.8rem', 'important');
                el.style.setProperty('padding', '2px 4px', 'important');
                el.style.setProperty('border', 'none', 'important');
                el.style.setProperty('color', 'white', 'important');
                el.style.setProperty('font-weight', '500', 'important');
                el.style.setProperty('box-shadow', '0 1px 3px rgba(0,0,0,0.2)', 'important');
                el.style.setProperty('min-height', '40px', 'important');
                el.style.setProperty('line-height', '1.2', 'important');
            },
            eventClick: function (info) {
                console.log('Event click:', info);
                console.log('Mouse button:', info.jsEvent.button);

                // Sadece sağ tıklamada context menu göster
                if (info.jsEvent.button === 2) {
                    const gorevId = info.event.extendedProps.gorev_id;
                    if (gorevId) {
                        // Orijinal mouse event'ini kullan
                        const originalEvent = info.jsEvent.originalEvent || info.jsEvent;
                        console.log('Orijinal event:', originalEvent);
                        showContextMenu(originalEvent, gorevId);
                    }
                }
            },
        });

        // Takvimi render et
        window.gorevlerCalendar.render();
        console.log('Takvim render edildi!');

        // Event'ler render edildikten sonra context menu listener'larını ekle
        setTimeout(() => {
            addContextMenuListeners();
        }, 1000);

        // CSS'lerin uygulanması için kısa bir bekleme
        setTimeout(() => {
            console.log('CSS override\'ları uygulanıyor...');
            applyCalendarStyles();
        }, 100);

        // Takvim render edildikten sonra yükseklikleri zorla ayarla
        setTimeout(() => {
            const allDays = document.querySelectorAll('.fc-daygrid-day');
            allDays.forEach(dayEl => {
                const events = dayEl.querySelectorAll('.fc-event');
                const eventCount = events.length;

                if (eventCount > 0) {
                    dayEl.style.minHeight = '120px';
                }
            });
        }, 200);
    }

    // CSS Override Fonksiyonu
    function applyCalendarStyles() {
        console.log('CSS override\'ları uygulanıyor...');

        // Header hücrelerini zorla stil uygula (randevu takvimi gibi - koyu gri arka plan, beyaz yazı)
        const headerCells = document.querySelectorAll('#calendar .fc-col-header-cell');
        headerCells.forEach(cell => {
            cell.style.setProperty('background', '#343a40', 'important');
            cell.style.setProperty('color', '#ffffff', 'important');
            cell.style.setProperty('border', '1px solid #dee2e6', 'important');
            cell.style.setProperty('font-weight', 'bold', 'important');
            cell.style.setProperty('text-align', 'center', 'important');
            cell.style.setProperty('padding', '0.5rem', 'important');
            cell.style.setProperty('font-size', '14px', 'important');
        });

        // Header cushion (gün isimleri) zorla stil uygula
        const headerCushions = document.querySelectorAll('#calendar .fc-col-header-cell-cushion');
        headerCushions.forEach(cushion => {
            cushion.style.setProperty('color', '#ffffff', 'important');
            cushion.style.setProperty('text-decoration', 'none', 'important');
            cushion.style.setProperty('font-weight', 'bold', 'important');
            cushion.style.setProperty('font-size', '14px', 'important');
        });

        // Gün hücrelerini zorla stil uygula
        const dayCells = document.querySelectorAll('#calendar .fc-daygrid-day');
        dayCells.forEach(cell => {
            cell.style.setProperty('border', '1px solid #dee2e6', 'important');
            cell.style.setProperty('min-height', '120px', 'important');
            cell.style.setProperty('background-color', '#ffffff', 'important');
        });

        // Tarih numaralarını siyah yap
        const dayNumbers = document.querySelectorAll('#calendar .fc-daygrid-day-number');
        dayNumbers.forEach(dayNumber => {
            dayNumber.style.setProperty('color', '#000000', 'important');
            dayNumber.style.setProperty('font-weight', 'normal', 'important');
        });

        // Bugün hücresini vurgula
        const todayCell = document.querySelector('#calendar .fc-day-today');
        if (todayCell) {
            todayCell.style.setProperty('background-color', '#e3f2fd', 'important');
            // Bugünün tarih numarasını mavi yap
            const todayNumber = todayCell.querySelector('.fc-daygrid-day-number');
            if (todayNumber) {
                todayNumber.style.setProperty('color', '#007bff', 'important');
                todayNumber.style.setProperty('font-weight', 'bold', 'important');
            }
        }

        // Event'leri zorla stil uygula
        const events = document.querySelectorAll('#calendar .fc-event');
        events.forEach(event => {
            event.style.setProperty('border-radius', '4px', 'important');
            event.style.setProperty('font-size', '0.8rem', 'important');
            event.style.setProperty('padding', '2px 4px', 'important');
        });

        // Takvim container'ını zorla stil uygula
        const calendarContainer = document.querySelector('#calendar .fc-view-harness');
        if (calendarContainer) {
            calendarContainer.style.setProperty('min-height', '600px', 'important');
        }

        // Takvim genel arka plan rengi
        const calendarElement = document.querySelector('#calendar');
        if (calendarElement) {
            calendarElement.style.setProperty('background-color', '#ffffff', 'important');
        }

        console.log('CSS override\'ları uygulandı!');
    }

    function moveToRandevu(gorevId) {
        console.log('moveToRandevu çağrıldı:', gorevId);
        openRandevuModal(gorevId);
    }

    function openRandevuModal(gorevId) {
        console.log('Randevu modal açılıyor, görev ID:', gorevId);

        // Önce görev bilgilerini al
        fetch(`/api/gorev-bilgi/${gorevId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Modal'ı oluştur ve aç
                    createNewRandevuModal(data.gorev);
                } else {
                    alert('Görev bilgileri alınamadı: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Görev bilgileri alınırken hata:', error);
                alert('Görev bilgileri alınırken hata oluştu');
            });
    }

    function createNewRandevuModal(gorev) {
        // Mevcut modal'ı kaldır
        const existingModal = document.getElementById('randevuModal');
        if (existingModal) {
            existingModal.remove();
        }

        const modalHTML = `
        <div class="modal fade" id="randevuModal" tabindex="-1" aria-labelledby="randevuModalLabel" aria-hidden="true" data-bs-backdrop="false">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="randevuModalLabel">{{ _('Görevden Randevu Oluştur') }}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="randevuForm">
                            <input type="hidden" id="gorev_id" name="gorev_id" value="${gorev.TodoID}">
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="musteri_adi" class="form-label">{{ _('Müşteri Adı') }} *</label>
                                        <input type="text" class="form-control" id="musteri_adi" name="musteri_adi" value="${gorev.MusteriAdi || ''}" required>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="musteri_soyadi" class="form-label">{{ _('Müşteri Soyadı') }} *</label>
                                        <input type="text" class="form-control" id="musteri_soyadi" name="musteri_soyadi" value="${gorev.MusteriSoyadi || ''}" required>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="telefon" class="form-label">{{ _('Telefon') }} *</label>
                                        <input type="tel" class="form-control" id="telefon" name="telefon" value="${gorev.Telefon || ''}" required>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="email" class="form-label">{{ _('E-posta') }}</label>
                                        <input type="email" class="form-control" id="email" name="email" value="${gorev.Email || ''}">
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="defter_id" class="form-label">{{ _('Randevu Defteri') }} *</label>
                                        <select class="form-select" id="defter_id" name="defter_id" required>
                                            <option value="">{{ _('Defter Seçin') }}</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="tarih_gun" class="form-label">{{ _('Tarih') }} *</label>
                                        <input type="date" class="form-control" id="tarih_gun" name="tarih_gun" required>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="randevu_suresi" class="form-label">{{ _('Süre (Dakika)') }}</label>
                                <input type="number" class="form-control" id="randevu_suresi" name="randevu_suresi" value="30" min="15" max="240" step="15">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">{{ _('Müsait Saatler') }}</label>
                                <div id="slotContainer" class="row">
                                    <div class="col-12">
                                        <p class="text-muted">{{ _('Önce randevu defteri ve tarih seçin') }}</p>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="aciklama" class="form-label">{{ _('Açıklama') }}</label>
                                <textarea class="form-control" id="aciklama" name="aciklama" rows="3">${gorev.Aciklama || ''}</textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ _('İptal') }}</button>
                        <button type="button" class="btn btn-primary" onclick="saveRandevu()">{{ _('Randevu Oluştur') }}</button>
                    </div>
                </div>
            </div>
        </div>
    `;

        // Modal'ı body'ye ekle
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Defterleri yükle
        loadDefterler();

        // Bugünün tarihini set et
        const today = getLocalYMD(new Date());
        document.getElementById('tarih_gun').value = today;

        // Event listener'ları bağla
        setupRandevuModalListeners();

        // Modal'ı göster
        const modal = new bootstrap.Modal(document.getElementById('randevuModal'));
        modal.show();
    }

    function loadDefterler() {
        fetch('/api/randevu-defterleri')
            .then(response => response.json())
            .then(data => {
                const select = document.getElementById('defter_id');
                select.innerHTML = "<option value=\"\">{{ _('Defter Seçin') }}</option>";

                data.defterler.forEach(defter => {
                    const option = document.createElement('option');
                    option.value = defter.AyarID;
                    option.textContent = defter.DefterAdi;
                    option.dataset.slotDakika = defter.SlotDakika;
                    select.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Defterler yüklenirken hata:', error);
            });
    }

    function setupRandevuModalListeners() {
        // Defter seçildiğinde süreyi otomatik doldur
        const defterSelect = document.getElementById('defter_id');
        if (defterSelect) {
            defterSelect.addEventListener('change', function () {
                const selectedOption = this.options[this.selectedIndex];
                if (selectedOption.dataset.slotDakika) {
                    document.getElementById('randevu_suresi').value = selectedOption.dataset.slotDakika;
                }

                // Tarih seçilmişse slotları yükle
                const tarih = document.getElementById('tarih_gun').value;
                if (tarih) {
                    loadRandevuSlots();
                }
            });
        }

        // Tarih değiştiğinde slotları yükle
        const tarihInput = document.getElementById('tarih_gun');
        if (tarihInput) {
            tarihInput.addEventListener('change', function () {
                const defterId = document.getElementById('defter_id').value;
                if (defterId) {
                    loadRandevuSlots();
                }
            });
        }
    }

    function loadRandevuSlots() {
        const defterId = document.getElementById('defter_id').value;
        const tarih = document.getElementById('tarih_gun').value;

        if (!defterId || !tarih) {
            return;
        }

        const slotContainer = document.getElementById('slotContainer');
        slotContainer.innerHTML = "<div class=\"col-12\"><p class=\"text-muted\">{{ _('Yükleniyor...') }}</p></div>";

        fetch(`/api/randevu-slotlari?tarih=${tarih}&defter_id=${defterId}`)
            .then(response => response.json())
            .then(data => {
                console.log('Slot API yanıtı:', data);
                if (data.success) {
                    // API'den gelen veri yapısını kontrol et
                    const slots = data.tum_slotlar || data.slotlar || data.all_slots || [];
                    const doluSlots = data.dolu_slotlar || [];
                    displayRandevuSlots(slots, doluSlots);
                } else {
                    slotContainer.innerHTML = `<div class="col-12"><p class="text-danger">${data.message}</p></div>`;
                }
            })
            .catch(error => {
                console.error('Slotlar yüklenirken hata:', error);
                slotContainer.innerHTML = "<div class=\"col-12\"><p class=\"text-danger\">{{ _('Slotlar yüklenirken hata oluştu') }}</p></div>";
            });
    }

    function displayRandevuSlots(slots, doluSlots = []) {
        const slotContainer = document.getElementById('slotContainer');
        slotContainer.innerHTML = '';

        // Slots parametresini kontrol et
        if (!slots || !Array.isArray(slots)) {
            console.error('Geçersiz slots verisi:', slots);
            slotContainer.innerHTML = '<div class="col-12"><p class="text-danger">{{ _('Slot verileri geçersiz') }}</p></div>';
            return;
        }

        if (slots.length === 0) {
            slotContainer.innerHTML = '<div class="col-12"><p class="text-muted">{{ _('Bu tarih için müsait slot bulunmuyor') }}</p></div>';
            return;
        }

        slots.forEach(slot => {
            const col = document.createElement('div');
            col.className = 'col-md-2 col-sm-3 col-4 mb-1'; // Küçültülmüş boyutlar

            // Slot dolu mu kontrol et
            const isDolu = doluSlots.includes(slot);

            const button = document.createElement('button');
            button.type = 'button';
            button.className = `btn btn-outline-primary w-100 ${isDolu ? 'disabled' : ''}`;
            button.style.opacity = isDolu ? '0.5' : '1';
            button.style.fontSize = '0.8rem'; // Küçük yazı boyutu
            button.style.padding = '0.25rem 0.75rem'; // Küçük padding
            button.style.minWidth = '80px'; // Minimum genişlik
            button.disabled = isDolu;
            button.textContent = slot;
            button.onclick = (event) => selectRandevuSlot(slot, event.target); // event.target eklendi

            col.appendChild(button);
            slotContainer.appendChild(col);
        });
    }

    function selectRandevuSlot(saat, targetButton) {
        // Seçilen saati form'a ekle
        const form = document.getElementById('randevuForm');
        let saatInput = document.getElementById('selected_saat');
        if (!saatInput) {
            saatInput = document.createElement('input');
            saatInput.type = 'hidden';
            saatInput.id = 'selected_saat';
            saatInput.name = 'selected_saat';
            form.appendChild(saatInput);
        }
        saatInput.value = saat;

        // Seçilen slot'u vurgula
        document.querySelectorAll('#slotContainer .btn').forEach(btn => {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        });

        targetButton.classList.remove('btn-outline-primary');
        targetButton.classList.add('btn-primary');
    }

    function saveRandevu() {
        const form = document.getElementById('randevuForm');
        const formData = new FormData(form);

        // Seçilen saati kontrol et
        const selectedSaat = document.getElementById('selected_saat');
        if (!selectedSaat || !selectedSaat.value) {
            alert("{{ _('Lütfen bir saat seçin') }}");
            return;
        }

        // Form verilerini topla
        const data = {
            defter_id: formData.get('defter_id'),
            musteri_adi: formData.get('musteri_adi'),
            musteri_soyadi: formData.get('musteri_soyadi'),
            telefon: formData.get('telefon'),
            email: formData.get('email'),
            tarih_gun: formData.get('tarih_gun'),
            selected_saat: selectedSaat.value,
            sure: formData.get('randevu_suresi'),
            aciklama: formData.get('aciklama'),
            gorev_id: formData.get('gorev_id')
        };

        // API'ye gönder
        fetch('/randevu-ekle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("{{ _('Randevu başarıyla oluşturuldu!') }}");
                    // Modal'ı kapat
                    const modal = bootstrap.Modal.getInstance(document.getElementById('randevuModal'));
                    modal.hide();
                    // Sayfayı yenile
                    location.reload();
                } else {
                    alert("{{ _('Randevu oluşturulurken hata: ') }} " + data.message);
                }
            })
            .catch(error => {
                console.error('Randevu kaydedilirken hata:', error);
                alert("{{ _('Randevu kaydedilirken hata oluştu') }}");
            });
    }

    // Durumları yükle (DOMContentLoaded içinde çağrılacak)
    function loadDurumlar() {
        console.log('loadDurumlar çağrıldı...');
        fetch('/api/gorev-durumlar')
            .then(response => {
                console.log('Durumlar API response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Durumlar API yanıtı:', data);
                if (data.success) {
                    try {
                        // Global tamamlandı durum ID'sini tut
                        const tamamlandi = (data.durumlar || []).find(d => d.DurumAdi === 'Tamamlandı');
                        window.completedStatusId = tamamlandi ? String(tamamlandi.DurumID) : null;
                        console.log('completedStatusId set:', window.completedStatusId);
                    } catch (e) { console.warn('completedStatusId set edilemedi', e); }
                    const durumSelect = document.getElementById('quick_durum');
                    if (durumSelect) {
                        durumSelect.innerHTML = '<option value="">{{ _("Durum Seçin") }}</option>';

                        data.durumlar.forEach(durum => {
                            const option = document.createElement('option');
                            option.value = durum.DurumID;
                            option.textContent = durum.DurumAdi;
                            option.style.color = durum.Renk;
                            durumSelect.appendChild(option);
                        });
                        console.log('Durumlar yüklendi:', data.durumlar.length, 'adet');
                    } else {
                        console.error('quick_durum select elementi bulunamadı!');
                    }
                } else {
                    console.error('Durumlar API başarısız:', data.message);
                }
            })
            .catch(error => {
                console.error('Durumlar yüklenirken hata:', error);
                console.error('Hata detayı:', error.message);
            });
    }

    function saveQuickGorev() {
        console.log('=== saveQuickGorev BAŞLADI ===');

        try {
            const formData = new FormData(document.getElementById('quickGorevForm'));
            const data = Object.fromEntries(formData);

            console.log('Form verisi:', data);

            // Durum bilgisini al
            const durumSelect = document.getElementById('quick_durum');
            const selectedDurumOption = durumSelect.options[durumSelect.selectedIndex];
            const durumId = selectedDurumOption.value;
            const durumAdi = selectedDurumOption.textContent;

            console.log('Seçilen durum ID:', durumId);
            console.log('Seçilen durum adı:', durumAdi);

            // Görevler için özel veri hazırla
            const gorevData = {
                baslik: data.baslik,
                aciklama: data.aciklama,
                oncelik: data.oncelik,
                durum_id: durumId, // Durum ID'sini gönder
                durum_adi: durumAdi, // Durum adını da gönder
                bitis_tarihi: data.bitis_tarihi,
                hatirlatma_tarihi: data.hatirlatma_tarihi,
                randevu_tarihi: data.randevu_tarihi,
                randevu_defteri_id: data.randevu_defteri_id,
                selected_randevu_saat: data.selected_randevu_saat,
                musteri_adi: data.musteri_adi,
                musteri_soyadi: data.musteri_soyadi,
                musteri_telefon: data.musteri_telefon,
                musteri_email: data.musteri_email,
                kullanici_id: data.kullanici_id,
                tip: 'Randevu' // Görevler için Randevu tipi
            };

            console.log('Görev verisi hazırlandı:', gorevData);

            // Zorunlu alanları kontrol et
            if (!gorevData.baslik || gorevData.baslik.trim() === '') {
                alert('Başlık alanı zorunludur!');
                return;
            }

            fetch('/todos/ekle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(gorevData)
            })
                .then(response => {
                    console.log('API response status:', response.status);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('API response data:', data);
                    if (data.success) {
                        console.log('Görev başarıyla kaydedildi!');
                        // Modal'ı kapat
                        const modal = bootstrap.Modal.getInstance(document.getElementById('quickGorevModal'));
                        if (modal) {
                            modal.hide();
                        }

                        // Sayfayı yenile
                        location.reload();
                    } else {
                        console.error('Görev kaydedilemedi:', data.message);
                        alert('Görev kaydedilirken hata oluştu: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Görev kaydetme hatası:', error);
                    console.error('Hata detayı:', error.message);
                    alert('Bir hata oluştu: ' + error.message);
                });

        } catch (error) {
            console.error('saveQuickGorev genel hatası:', error);
            console.error('Hata detayı:', error.message);
            alert('Bir hata oluştu: ' + error.message);
        }

        console.log('=== saveQuickGorev BİTTİ ===');
    }

    // Müşteri arama autocomplete
    function setupMusteriArama() {
        const musteriAdiInput = document.getElementById('quick_musteri_adi');
        const musteriSoyadiInput = document.getElementById('quick_musteri_soyadi');
        const musteriTelefonInput = document.getElementById('quick_musteri_telefon');
        const musteriEmailInput = document.getElementById('quick_musteri_email');
        const suggestionsDiv = document.getElementById('musteri_adi_suggestions');

        let searchTimeout;
        let selectedIndex = -1;

        if (!musteriAdiInput || !suggestionsDiv) {
            return;
        }

        musteriAdiInput.addEventListener('input', function () {
            const query = this.value.trim();
            clearTimeout(searchTimeout);
            if (query.length < 2) {
                suggestionsDiv.style.display = 'none';
                return;
            }
            searchTimeout = setTimeout(() => {
                searchMusteriler(query);
            }, 300);
        });

        musteriAdiInput.addEventListener('keydown', function (e) {
            const suggestions = suggestionsDiv.querySelectorAll('.list-group-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
                updateSelection();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, -1);
                updateSelection();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && suggestions[selectedIndex]) {
                    selectMusteri(suggestions[selectedIndex]);
                }
            } else if (e.key === 'Escape') {
                suggestionsDiv.style.display = 'none';
                selectedIndex = -1;
            }
        });

        musteriAdiInput.addEventListener('blur', function () {
            setTimeout(() => {
                suggestionsDiv.style.display = 'none';
                selectedIndex = -1;
            }, 200);
        });

        function searchMusteriler(query) {
            console.log('Müşteri arama yapılıyor:', query);
            fetch(`/api/musteri-ara?q=${encodeURIComponent(query)}`)
                .then(response => {
                    console.log('Müşteri arama API response status:', response.status);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Müşteri arama sonuçları:', data);
                    displaySuggestions(data);
                })
                .catch(error => {
                    console.error('Müşteri arama hatası:', error);
                    console.error('Hata detayı:', error.message);
                    suggestionsDiv.style.display = 'none';
                });
        }

        function displaySuggestions(musteriler) {
            if (musteriler.length === 0) {
                suggestionsDiv.style.display = 'none';
                return;
            }
            suggestionsDiv.innerHTML = '';
            musteriler.forEach((musteri, index) => {
                const item = document.createElement('div');
                item.className = 'list-group-item list-group-item-action';
                item.style.cursor = 'pointer';
                item.dataset.ad = musteri.ad;
                item.dataset.soyad = musteri.soyad;
                item.dataset.telefon = musteri.telefon;
                item.dataset.email = musteri.email;
                item.innerHTML = `
                <div class="fw-bold">${musteri.display}</div>
                <small class="text-muted">${musteri.telefon} • ${musteri.email}</small>
            `;
                item.addEventListener('click', () => selectMusteri(item));
                suggestionsDiv.appendChild(item);
            });
            suggestionsDiv.style.display = 'block';
            selectedIndex = -1;
        }

        function updateSelection() {
            const suggestions = suggestionsDiv.querySelectorAll('.list-group-item');
            suggestions.forEach((item, index) => {
                if (index === selectedIndex) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        }

        function selectMusteri(item) {
            const musteriData = item.dataset;
            if (musteriData.ad) {
                musteriAdiInput.value = musteriData.ad;
                musteriSoyadiInput.value = musteriData.soyad || '';
                musteriTelefonInput.value = musteriData.telefon || '';
                musteriEmailInput.value = musteriData.email || '';
            }
            suggestionsDiv.style.display = 'none';
            selectedIndex = -1;
        }
    }

    // Randevu tarihi değiştiğinde diğer tarihleri güncelle
    function setupTarihSenkronizasyonu() {
        const randevuTarihiInput = document.getElementById('quick_randevu_tarihi');
        if (!randevuTarihiInput) return;

        randevuTarihiInput.addEventListener('change', function () {
            const randevuTarihi = this.value;
            if (randevuTarihi) {
                // Bitiş tarihini güncelle
                const bitisTarihiInput = document.getElementById('quick_bitis_tarihi');
                if (bitisTarihiInput) {
                    bitisTarihiInput.value = randevuTarihi;
                }

                // Hatırlatma tarihini güncelle
                const hatirlatmaTarihiInput = document.getElementById('quick_hatirlatma_tarihi');
                if (hatirlatmaTarihiInput) {
                    hatirlatmaTarihiInput.value = randevuTarihi;
                }

                console.log('Randevu tarihi değişti, diğer tarihler güncellendi:', randevuTarihi);
            }
        });
    }

    // Kullanıcıları yükle
    function loadKullanicilar() {
        console.log('loadKullanicilar çağrıldı...');
        fetch('/api/kullanicilar')
            .then(response => {
                console.log('Kullanıcılar API response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Kullanıcılar API yanıtı:', data);
                const select = document.getElementById('quick_kullanici');
                if (select && data.success) {
                    select.innerHTML = "<option value=\"\">{{ _('Kullanıcı Seçin') }}</option>";
                    data.kullanicilar.forEach(kullanici => {
                        const option = document.createElement('option');
                        option.value = kullanici.id;
                        option.textContent = kullanici.tam_adi;
                        select.appendChild(option);
                    });
                    console.log('Kullanıcılar yüklendi:', data.kullanicilar.length, 'adet');
                } else {
                    console.error('quick_kullanici select elementi bulunamadı veya API başarısız!');
                }
            })
            .catch(error => {
                console.error('Kullanıcı yükleme hatası:', error);
                console.error('Hata detayı:', error.message);
            });
    }

    // Randevu defterlerini yükle
    function loadRandevuDefterleri() {
        console.log('loadRandevuDefterleri çağrıldı...');
        fetch('/api/randevu-defterleri')
            .then(response => {
                console.log('Randevu defterleri API response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Randevu defterleri API yanıtı:', data);
                const select = document.getElementById('quick_randevu_defteri');
                if (select && data.defterler) {
                    select.innerHTML = "<option value=\"\">{{ _('Defter Seçin') }}</option>";
                    data.defterler.forEach(defter => {
                        const option = document.createElement('option');
                        option.value = defter.AyarID;
                        option.textContent = defter.DefterAdi;
                        option.dataset.slotDakika = defter.SlotDakika;
                        select.appendChild(option);
                    });
                    console.log('Randevu defterleri yüklendi:', data.defterler.length, 'adet');

                    // Event listener'ları ekle
                    setupRandevuSlotListeners();
                } else {
                    console.error('quick_randevu_defteri select elementi bulunamadı veya defterler yok!');
                }
            })
            .catch(error => {
                console.error('Randevu defterleri yükleme hatası:', error);
                console.error('Hata detayı:', error.message);
            });
    }

    // Randevu slot event listener'ları
    function setupRandevuSlotListeners() {
        const defterSelect = document.getElementById('quick_randevu_defteri');
        const tarihInput = document.getElementById('quick_randevu_tarihi');

        if (defterSelect) {
            defterSelect.addEventListener('change', function () {
                const selectedOption = this.options[this.selectedIndex];
                if (selectedOption.dataset.slotDakika) {
                    // Süre otomatik doldur
                    const sureInput = document.getElementById('quick_randevu_suresi');
                    if (sureInput) {
                        sureInput.value = selectedOption.dataset.slotDakika;
                        console.log('Süre otomatik dolduruldu:', selectedOption.dataset.slotDakika);
                    }
                }

                const tarih = tarihInput.value;
                if (tarih) {
                    loadQuickRandevuSlots();
                } else {
                    // Tarih seçilmemişse slot container'ı gizle
                    const container = document.getElementById('randevu_saatleri_container');
                    if (container) {
                        container.style.display = 'none';
                    }
                }
            });
        }

        if (tarihInput) {
            tarihInput.addEventListener('change', function () {
                const defterId = defterSelect.value;
                if (defterId) {
                    loadQuickRandevuSlots();
                } else {
                    // Defter seçilmemişse slot container'ı gizle
                    const container = document.getElementById('randevu_saatleri_container');
                    if (container) {
                        container.style.display = 'none';
                    }
                }
            });
        }
    }

    // Randevu slotlarını yükle (Yeni Görev modal için)
    function loadQuickRandevuSlots() {
        const defterId = document.getElementById('quick_randevu_defteri').value;
        const tarih = document.getElementById('quick_randevu_tarihi').value;

        if (!defterId || !tarih) {
            return;
        }

        const container = document.getElementById('randevu_saatleri_container');
        const slotContainer = document.getElementById('randevu_saatleri');

        container.style.display = 'block';
        slotContainer.innerHTML = "<div class=\"col-12\"><p class=\"text-muted\">{{ _('Yükleniyor...') }}</p></div>";

        fetch(`/api/randevu-slotlari?tarih=${tarih}&defter_id=${defterId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const slots = data.tum_slotlar || data.slotlar || data.all_slots || [];
                    const doluSlots = data.dolu_slotlar || [];
                    displayQuickRandevuSlots(slots, doluSlots);
                } else {
                    slotContainer.innerHTML = `<div class="col-12"><p class="text-danger">${data.message}</p></div>`;
                }
            })
            .catch(error => {
                console.error('Slotlar yüklenirken hata:', error);
                slotContainer.innerHTML = "<div class=\"col-12\"><p class=\"text-danger\">{{ _('Slotlar yüklenirken hata oluştu') }}</p></div>";
            });
    }

    // Randevu slotlarını göster (Yeni Görev modal için)
    function displayQuickRandevuSlots(slots, doluSlots = []) {
        const slotContainer = document.getElementById('randevu_saatleri');
        slotContainer.innerHTML = '';

        if (!slots || !Array.isArray(slots) || slots.length === 0) {
            slotContainer.innerHTML = '<div class="col-12"><p class="text-muted">{{ _('Bu tarih için müsait slot bulunmuyor') }}</p></div>';
            return;
        }

        slots.forEach(slot => {
            const col = document.createElement('div');
            col.className = 'col-auto';

            const isDolu = doluSlots.includes(slot);

            const button = document.createElement('button');
            button.type = 'button';
            button.className = `btn btn-outline-primary px-2 py-1 ${isDolu ? 'disabled' : ''}`;
            button.style.opacity = isDolu ? '0.5' : '1';
            button.style.fontSize = '0.72rem';
            button.style.minWidth = '58px';
            button.disabled = isDolu;
            button.textContent = slot;
            button.onclick = (event) => selectQuickRandevuSlot(slot, event.target);

            col.appendChild(button);
            slotContainer.appendChild(col);
        });
    }

    // Randevu slot seç (Yeni Görev modal için)
    function selectQuickRandevuSlot(saat, targetButton) {
        // Seçilen saati form'a ekle
        const form = document.getElementById('quickGorevForm');
        let saatInput = document.getElementById('selected_quick_randevu_saat');
        if (!saatInput) {
            saatInput = document.createElement('input');
            saatInput.type = 'hidden';
            saatInput.id = 'selected_quick_randevu_saat';
            saatInput.name = 'selected_randevu_saat';
            form.appendChild(saatInput);
        }
        saatInput.value = saat;

        // Saat input'una da yaz (manuel alan var ise)
        const manualSaat = document.getElementById('quick_randevu_saati');
        if (manualSaat) {
            manualSaat.value = saat;
        }

        // Bitiş saatini hesapla ve göster
        updateQuickEndTime();

        // Seçilen slot'u vurgula
        document.querySelectorAll('#randevu_saatleri .btn').forEach(btn => {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        });

        targetButton.classList.remove('btn-outline-primary');
        targetButton.classList.add('btn-primary');
    }

    // Süre değişince bitiş saatini güncelle
    const quickSureInput = document.getElementById('quick_randevu_suresi');
    if (quickSureInput) {
        quickSureInput.addEventListener('input', updateQuickEndTime);
        quickSureInput.addEventListener('change', updateQuickEndTime);
    }

    function updateQuickEndTime() {
        // Başlangıç saati seçilen slot'tan (hidden input) alınır
        const startTimeEl = document.getElementById('selected_quick_randevu_saat');
        const durationEl = document.getElementById('quick_randevu_suresi');
        const infoEl = document.getElementById('quick_end_info');

        if (!startTimeEl || !durationEl || !infoEl) return;

        const start = startTimeEl.value; // HH:MM
        const durationMin = parseInt(durationEl.value || '0', 10);
        if (!start || !durationMin) {
            infoEl.textContent = '';
            return;
        }

        const [h, m] = start.split(':').map(Number);
        const startDate = new Date();
        startDate.setHours(h, m, 0, 0);
        const endDate = new Date(startDate.getTime() + durationMin * 60000);
        const eh = String(endDate.getHours()).padStart(2, '0');
        const em = String(endDate.getMinutes()).padStart(2, '0');
        infoEl.textContent = `${start} → ${eh}:${em}`;
    }

    // Bugünün tarihini set et
    function setTodayDate() {
        const today = getLocalYMD(new Date());

        const bitisTarihiInput = document.getElementById('quick_bitis_tarihi');
        const hatirlatmaTarihiInput = document.getElementById('quick_hatirlatma_tarihi');
        const randevuTarihiInput = document.getElementById('quick_randevu_tarihi');

        if (bitisTarihiInput) {
            bitisTarihiInput.value = today;
        }

        if (hatirlatmaTarihiInput) {
            hatirlatmaTarihiInput.value = today;
        }

        if (randevuTarihiInput) {
            randevuTarihiInput.value = today;
        }
    }
