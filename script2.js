
    // Filtreleme
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            // Aktif butonu güncelle
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            const filter = this.dataset.filter;
            const gorevler = document.querySelectorAll('.gorev-item');

            gorevler.forEach(gorev => {
                if (filter === 'all' || gorev.dataset.durum === filter) {
                    gorev.style.display = 'block';
                } else {
                    gorev.style.display = 'none';
                }
            });
        });
    });

    // Görev düzenleme
    function editGorev(gorevId) {
        // Önce durumları yükle, sonra görev verilerini getir
        Promise.all([
            fetch('/api/gorev-durumlar').then(r => r.json()),
            fetch(`/todos/${gorevId}/guncelle`).then(r => r.json())
        ])
            .then(([durumlarResponse, gorevResponse]) => {
                if (durumlarResponse.success && gorevResponse.success) {
                    const durumlar = durumlarResponse.durumlar;
                    const data = gorevResponse;

                    // Modal'ı tamamen yeniden oluştur
                    const existingModal = document.getElementById('gorevModal');
                    if (existingModal) {
                        existingModal.remove();
                    }

                    // Durum seçeneklerini oluştur
                    let durumOptions = '<option value="">{{ _("Durum Seçin") }}</option>';
                    durumlar.forEach(durum => {
                        const selected = data.todo.DurumID == durum.DurumID ? 'selected' : '';
                        durumOptions += `<option value="${durum.DurumID}" ${selected} style="color: ${durum.Renk};">${durum.DurumAdi}</option>`;
                    });

                    // Yeni modal HTML'i oluştur
                    const newModalHTML = `
                <div class="modal fade" id="gorevModal" tabindex="-1" style="z-index: 9999 !important;">
                    <div class="modal-dialog modal-lg" style="z-index: 10000 !important;">
                        <div class="modal-content" style="z-index: 10001 !important; pointer-events: auto !important;">
                            <div class="modal-header" style="pointer-events: auto !important;">
                                <h5 class="modal-title" id="gorevModalLabel">{{ _("Görev Düzenle") }}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" style="pointer-events: auto !important; z-index: 10002 !important;"></button>
                            </div>
                            <div class="modal-body" style="pointer-events: auto !important;">
                                <form id="gorevForm">
                                    <input type="hidden" id="gorev_id" name="gorev_id" value="${data.todo.TodoID}">
                                    
                                    <div class="mb-3">
                                        <label for="gorev_baslik" class="form-label">{{ _("Başlık") }} *</label>
                                        <input type="text" class="form-control" id="gorev_baslik" name="baslik" value="${data.todo.Baslik}" required style="pointer-events: auto !important; z-index: 10002 !important;">
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label for="gorev_aciklama" class="form-label">{{ _("Açıklama") }}</label>
                                        <textarea class="form-control" id="gorev_aciklama" name="aciklama" rows="3" style="pointer-events: auto !important; z-index: 10002 !important;">${data.todo.Aciklama || ''}</textarea>
                                    </div>
                                    
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="gorev_oncelik" class="form-label">{{ _("Öncelik") }}</label>
                                                <select class="form-select" id="gorev_oncelik" name="oncelik" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                    <option value="Düşük" ${data.todo.Oncelik === 'Düşük' ? 'selected' : ''}>{{ _("Düşük") }}</option>
                                                    <option value="Orta" ${data.todo.Oncelik === 'Orta' ? 'selected' : ''}>{{ _("Orta") }}</option>
                                                    <option value="Yüksek" ${data.todo.Oncelik === 'Yüksek' ? 'selected' : ''}>{{ _("Yüksek") }}</option>
                                                </select>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="gorev_durum" class="form-label">{{ _("Durum") }}</label>
                                                <select class="form-select" id="gorev_durum" name="durum" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                    ${durumOptions}
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
                                                        <input type="text" class="form-control" id="gorev_musteri_adi" name="musteri_adi" value="${data.todo.MusteriAdi || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                    </div>
                                                </div>
                                                <div class="col-md-6">
                                                    <div class="mb-3">
                                                        <label for="gorev_musteri_soyadi" class="form-label">{{ _('Müşteri Soyadı') }}</label>
                                                        <input type="text" class="form-control" id="gorev_musteri_soyadi" name="musteri_soyadi" value="${data.todo.MusteriSoyadi || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="row">
                                                <div class="col-md-6">
                                                    <div class="mb-3">
                                                        <label for="gorev_musteri_telefon" class="form-label">{{ _('Telefon') }}</label>
                                                        <input type="tel" class="form-control" id="gorev_musteri_telefon" name="musteri_telefon" value="${data.todo.MusteriTelefon || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                    </div>
                                                </div>
                                                <div class="col-md-6">
                                                    <div class="mb-3">
                                                        <label for="gorev_musteri_email" class="form-label">{{ _('E-posta') }}</label>
                                                        <input type="email" class="form-control" id="gorev_musteri_email" name="musteri_email" value="${data.todo.MusteriEmail || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="gorev_bitis_tarihi" class="form-label">{{ _("Bitiş Tarihi") }}</label>
                                                <input type="date" class="form-control" id="gorev_bitis_tarihi" name="bitis_tarihi" value="${data.todo.BitisTarihi || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="gorev_hatirlatma_tarihi" class="form-label">{{ _("Hatırlatma Tarihi") }}</label>
                                                <input type="date" class="form-control" id="gorev_hatirlatma_tarihi" name="hatirlatma_tarihi" value="${data.todo.HatirlatmaTarihi || ''}" style="pointer-events: auto !important; z-index: 10002 !important;">
                                            </div>
                                        </div>
                                    </div>
                                </form>
                            </div>
                            <div class="modal-footer" style="pointer-events: auto !important;">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" style="pointer-events: auto !important; z-index: 10002 !important;">{{ _("İptal") }}</button>
                                <button type="button" class="btn btn-primary" id="kaydetBtn" style="pointer-events: auto !important; z-index: 10002 !important;">{{ _("Kaydet") }}</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

                    // Modal'ı body'ye ekle
                    document.body.insertAdjacentHTML('beforeend', newModalHTML);

                    // Kaydet butonuna event listener ekle
                    const kaydetBtn = document.getElementById('kaydetBtn');
                    if (kaydetBtn) {
                        kaydetBtn.addEventListener('click', function () {
                            console.log('YENİ MODAL - Kaydet butonuna tıklandı!');
                            saveGorev();
                        });
                        console.log('YENİ MODAL - Kaydet butonuna event listener eklendi');
                    }

                    // Modal'ı göster
                    const modal = new bootstrap.Modal(document.getElementById('gorevModal'));
                    modal.show();

                    console.log('YENİ MODAL - Modal başarıyla oluşturuldu ve gösterildi');
                } else {
                    alert('Görev verileri yüklenemedi: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Hata:', error);
                alert('Bir hata oluştu');
            });
    }

    // Görev kaydetme
    function saveGorev() {
        const gorevId = document.getElementById('gorev_id').value;
        const data = {
            baslik: document.getElementById('gorev_baslik').value,
            aciklama: document.getElementById('gorev_aciklama').value,
            oncelik: document.getElementById('gorev_oncelik').value,
            durum: document.getElementById('gorev_durum').value,
            bitis_tarihi: document.getElementById('gorev_bitis_tarihi').value,
            hatirlatma_tarihi: document.getElementById('gorev_hatirlatma_tarihi').value
        };

        if (!data.baslik.trim()) {
            alert('{{ _("Başlık gerekli!") }}');
            return;
        }

        const url = gorevId ? `/todos/${gorevId}/guncelle` : '/todos/ekle';
        const method = gorevId ? 'POST' : 'POST';

        fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    location.reload();
                } else {
                    alert('Hata: ' + result.message);
                }
            })
            .catch(error => {
                console.error('Hata:', error);
                alert('Bir hata oluştu');
            });
    }

    // Görev silme
    function deleteGorev(gorevId) {
        if (confirm('{{ _("Bu görevi silmek istediğinizden emin misiniz?") }}')) {
            fetch(`/todos/${gorevId}/sil`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        location.reload();
                    } else {
                        alert('Hata: ' + result.message);
                    }
                })
                .catch(error => {
                    console.error('Hata:', error);
                    alert('Bir hata oluştu');
                });
        }
    }

    // Müşteri bilgilerini çıkar


    // Randevu ekleme modal'ını aç
    function openRandevuModal(gorevId) {
        // Modal'ı oluştur veya güncelle
        let modal = document.getElementById('randevuModal');
        if (!modal) {
            createRandevuModal();
            modal = document.getElementById('randevuModal');
        }

        // Görev bilgilerini al
        fetch(`/api/gorev-bilgi/${gorevId}`)
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    // Görev bilgilerini doldur
                    document.getElementById('randevu_baslik').value = result.gorev.Baslik || '';
                    document.getElementById('randevu_aciklamasi').value = result.gorev.Aciklama || '';

                    // API'den gelen müşteri bilgilerini kullan
                    const musteriAdi = result.gorev.MusteriAdi || '';
                    const musteriSoyadi = result.gorev.MusteriSoyadi || '';
                    const telefon = result.gorev.Telefon || '';
                    const email = result.gorev.Email || '';

                    // Müşteri bilgilerini doldur
                    document.getElementById('musteri_adi').value = musteriAdi;
                    document.getElementById('musteri_soyadi').value = musteriSoyadi;
                    document.getElementById('musteri_telefon').value = telefon;
                    document.getElementById('musteri_email').value = email;
                }
            })
            .catch(error => {
                console.error('Görev bilgileri alınamadı:', error);
            });

        // Tarihi bugün olarak ayarla
        const today = new Date();
        const dateString = getLocalYMD(today);
        document.getElementById('tarih_gun').value = dateString;

        // Slot container'ı temizle
        document.getElementById('slotContainer').innerHTML = '<div class="text-muted small">{{ _("Select date and book first") }}</div>';
        document.getElementById('saat').value = '';

        // Görev ID'sini hidden input'a kaydet
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'gorev_id';
        hiddenInput.value = gorevId;
        document.getElementById('randevuForm').appendChild(hiddenInput);

        // Modal'ı göster
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    // Randevu ekleme modal'ını oluştur
    function createRandevuModal() {
        const modalHTML = `
        <div class="modal fade" id="randevuModal" tabindex="-1" aria-labelledby="randevuModalLabel" aria-hidden="true" data-bs-backdrop="false">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="randevuModalLabel">{{ _('Create Appointment from Task') }}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <form id="randevuForm" method="POST" action="{{ url_for('randevu_ekle') }}">
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="defter_id" class="form-label">{{ _('Appointment Book') }} *</label>
                                        <select class="form-select" id="defter_id" name="defter_id" required>
                                            <option value="">{{ _('Select Book') }}...</option>
                                            <!-- Defterler buraya yüklenecek -->
                                        </select>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="randevu_baslik" class="form-label">{{ _('Title') }} *</label>
                                        <input type="text" class="form-control" id="randevu_baslik" name="randevu_baslik" required>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="tarih_gun" class="form-label">{{ _('Date') }} *</label>
                                        <input type="date" class="form-control" id="tarih_gun" name="tarih_gun" required onchange="loadRandevuSlots()">
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="randevu_suresi" class="form-label">{{ _('Duration') }} ({{ _('minutes') }}) *</label>
                                        <input type="number" class="form-control" id="randevu_suresi" name="sure" value="60" min="15" step="15" required>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-12">
                                    <div class="mb-3">
                                        <label class="form-label">{{ _('Available Times') }} *</label>
                                        <div id="slotContainer" class="border rounded p-3" style="min-height: 100px;">
                                            <div class="text-muted small">{{ _('Select date and book first') }}</div>
                                        </div>
                                        <input type="hidden" id="saat" name="saat" required>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="musteri_adi" class="form-label">{{ _('Customer Name') }} *</label>
                                        <input type="text" class="form-control" id="musteri_adi" name="musteri_adi" required>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="musteri_soyadi" class="form-label">{{ _('Customer Surname') }} *</label>
                                        <input type="text" class="form-control" id="musteri_soyadi" name="musteri_soyadi" required>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="musteri_telefon" class="form-label">{{ _('Phone') }}</label>
                                        <input type="text" class="form-control" id="musteri_telefon" name="musteri_telefon">
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="musteri_email" class="form-label">{{ _('Email') }}</label>
                                        <input type="email" class="form-control" id="musteri_email" name="musteri_email">
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="randevu_aciklamasi" class="form-label">{{ _('Description') }}</label>
                                <textarea class="form-control" id="randevu_aciklamasi" name="randevu_aciklamasi" rows="3"></textarea>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ _('Cancel') }}</button>
                            <button type="submit" class="btn btn-primary">{{ _('Create Appointment') }}</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Defterleri yükle
        loadDefterler();
    }

    // Defterleri yükle
    function loadDefterler() {
        fetch('/api/randevu-defterleri')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const select = document.getElementById('defter_id');
                    select.innerHTML = '<option value="">{{ _("Select Book") }}...</option>';
                    data.defterler.forEach(defter => {
                        const option = document.createElement('option');
                        option.value = defter.AyarID;
                        option.textContent = defter.DefterAdi;
                        option.setAttribute('data-slot-dakika', defter.SlotDakika);
                        select.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Defterler yüklenirken hata:', error);
            });
    }

    // Randevu slotlarını yükle
    function loadRandevuSlots() {
        const tarih = document.getElementById('tarih_gun').value;
        const defterId = document.getElementById('defter_id').value;

        if (!tarih || !defterId) {
            document.getElementById('slotContainer').innerHTML = '<div class="text-muted small">{{ _("Select date and book first") }}</div>';
            return;
        }

        fetch(`/api/randevu-slotlari?tarih=${tarih}&defter_id=${defterId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const container = document.getElementById('slotContainer');
                    container.innerHTML = '';

                    if (data.tum_slotlar && data.tum_slotlar.length > 0) {
                        // Tüm slotları sıralı şekilde göster
                        data.tum_slotlar.forEach(slot => {
                            const button = document.createElement('button');
                            button.type = 'button';
                            button.textContent = slot;

                            // Dolu mu müsait mi kontrol et
                            if (data.dolu_slotlar && data.dolu_slotlar.includes(slot)) {
                                // Dolu slot - silik göster
                                button.className = 'btn btn-outline-secondary btn-sm me-2 mb-2';
                                button.style.opacity = '0.4';
                                button.disabled = true;
                            } else {
                                // Müsait slot - normal göster
                                button.className = 'btn btn-outline-primary btn-sm me-2 mb-2';
                                button.onclick = () => selectRandevuSlot(slot);
                            }

                            container.appendChild(button);
                        });
                    }

                    if (data.slotlar && data.slotlar.length === 0 && (!data.dolu_slotlar || data.dolu_slotlar.length === 0)) {
                        if (data.mesaj) {
                            // Çalışma günü değil mesajı
                            container.innerHTML = `<div class="text-warning small"><i class="fas fa-exclamation-triangle me-1"></i>${data.mesaj}</div>`;
                        } else {
                            container.innerHTML = '<div class="text-muted small">{{ _("No available times for this date") }}</div>';
                        }
                    }
                }
            })
            .catch(error => {
                console.error('Slotlar yüklenirken hata:', error);
                document.getElementById('slotContainer').innerHTML = '<div class="text-danger small">{{ _("Error loading times") }}</div>';
            });
    }

    // Randevu slotu seç
    function selectRandevuSlot(saat) {
        // Önceki seçimi temizle
        document.querySelectorAll('#slotContainer .btn').forEach(btn => {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        });

        // Yeni seçimi işaretle
        event.target.classList.remove('btn-outline-primary');
        event.target.classList.add('btn-primary');

        // Hidden input'a değeri yaz
        document.getElementById('saat').value = saat;
    }


    // Sağ tık menüsü
    function showContextMenu(event, gorevId) {
        console.log('showContextMenu çağrıldı, gorevId:', gorevId, 'event:', event);
        event.preventDefault();

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
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        z-index: 10000;
        padding: 5px 0;
        min-width: 150px;
    `;

        menu.innerHTML = `
        <div class="context-menu-item" onclick="editGorev(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; border-bottom: 1px solid #eee;">
            <i class="fas fa-edit me-2"></i>{{ _('Görev Düzenle') }}
        </div>
        <div class="context-menu-item" onclick="moveToRandevu(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; border-bottom: 1px solid #eee;">
            <i class="fas fa-calendar-plus me-2"></i>{{ _('Randevu') }}
        </div>
        <div class="context-menu-item" onclick="quickComplete(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; border-bottom: 1px solid #eee; color: #198754;">
            <i class="fas fa-check me-2"></i>{{ _('Tamamlandı') }}
        </div>
        <div class="context-menu-item" onclick="deleteGorev(${gorevId}); hideContextMenu();" style="padding: 8px 15px; cursor: pointer; color: #dc3545;">
            <i class="fas fa-trash me-2"></i>{{ _('Sil') }}
        </div>
    `;

        // Menüyü konumlandır
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';

        document.body.appendChild(menu);

        // Menü dışına tıklandığında kapat
        setTimeout(() => {
            document.addEventListener('click', hideContextMenu);
        }, 100);
    }

    // Sağ tık menüsünü gizle
    function hideContextMenu() {
        const menu = document.getElementById('contextMenu');
        if (menu) {
            menu.remove();
        }
        document.removeEventListener('click', hideContextMenu);
    }


    // CSS Override Fonksiyonu
    function applyCalendarStyles() {
        console.log('CSS override\'ları uygulanıyor...');

        // Header hücrelerini zorla stil uygula
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

        // Gün hücrelerini zorla stil uygula - BEYAZ ARKA PLAN
        const dayCells = document.querySelectorAll('#calendar .fc-daygrid-day');
        dayCells.forEach(cell => {
            cell.style.setProperty('background', '#ffffff', 'important');
            cell.style.setProperty('border', '1px solid #dee2e6', 'important');
            cell.style.setProperty('color', '#343a40', 'important');
            cell.style.setProperty('min-height', '120px', 'important');
            cell.style.setProperty('padding', '8px', 'important');
            cell.style.setProperty('position', 'relative', 'important');
        });

        // Gün numaralarını siyah yap
        const dayNumbers = document.querySelectorAll('#calendar .fc-daygrid-day-number');
        dayNumbers.forEach(number => {
            number.style.setProperty('color', '#000000', 'important');
            number.style.setProperty('font-weight', 'bold', 'important');
            number.style.setProperty('font-size', '14px', 'important');
            number.style.setProperty('padding', '5px', 'important');
            number.style.setProperty('background', 'transparent', 'important');
        });

        // Event'leri zorla stil uygula
        const events = document.querySelectorAll('#calendar .fc-event');
        events.forEach(event => {
            event.style.setProperty('border-radius', '4px', 'important');
            event.style.setProperty('border', 'none', 'important');
            event.style.setProperty('font-size', '0.8rem', 'important');
            event.style.setProperty('padding', '6px 10px', 'important');
            event.style.setProperty('margin', '2px 0', 'important');
            // Background rengini kaldırdık - API'den gelecek
            event.style.setProperty('color', 'white', 'important');
            event.style.setProperty('font-weight', '500', 'important');
            event.style.setProperty('position', 'relative', 'important');
            event.style.setProperty('cursor', 'move', 'important');
            event.style.setProperty('white-space', 'normal', 'important');
            event.style.setProperty('overflow', 'visible', 'important');
            event.style.setProperty('text-overflow', 'unset', 'important');
            event.style.setProperty('max-width', '100%', 'important');
            event.style.setProperty('box-shadow', '0 1px 3px rgba(0,0,0,0.2)', 'important');
            event.style.setProperty('min-height', '40px', 'important');
            event.style.setProperty('line-height', '1.2', 'important');
        });

        console.log('CSS override\'ları uygulandı!');
    }

    // Takvim başlatma
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

        // FullCalendar başlat
        const htmlLang = (document.documentElement.lang || 'tr').toLowerCase();
        const fcLocale = ({ 'tr': 'tr', 'en': 'en', 'en-us': 'en', 'en-gb': 'en-gb', 'fr': 'fr', 'de': 'de' })[htmlLang] || 'tr';
        window.gorevlerCalendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: fcLocale,
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,listWeek'
            },
            buttonText: (function () {
                if (fcLocale.startsWith('en')) return { today: 'Today', month: 'Month', week: 'Week', day: 'Day', list: 'List' };
                if (fcLocale.startsWith('fr')) return { today: 'Aujourd\'hui', month: 'Mois', week: 'Semaine', day: 'Jour', list: 'Liste' };
                if (fcLocale.startsWith('de')) return { today: 'Heute', month: 'Monat', week: 'Woche', day: 'Tag', list: 'Liste' };
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
            dayMaxEvents: false, // Tüm görevleri göster
            moreLinkClick: 'popover', // Fazla görevler için popover
            height: 'auto', // Otomatik yükseklik
            contentHeight: 'auto', // İçerik yükseklik otomatik
            displayEventTime: false, // Saat bilgisini gizle (başlıkta göstermiyoruz)
            eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
            eventDisplay: 'block',
            slotMinTime: '06:00:00', // Minimum saat
            slotMaxTime: '22:00:00', // Maksimum saat
            slotDuration: '00:15:00', // Slot süresi
            snapDuration: '00:15:00', // Snap süresi
            eventContent: function (arg) {
                const defterAdi = arg.event.extendedProps.defter_adi;
                console.log('Event content debug:', {
                    title: arg.event.title,
                    defterAdi: defterAdi,
                    extendedProps: arg.event.extendedProps
                });
                const title = document.createElement('div');
                title.style.whiteSpace = 'normal';
                title.style.lineHeight = '1.2';
                title.innerHTML = `<div>${arg.event.title}</div>` +
                    (defterAdi ? `<div style="font-size: 0.75rem; color: rgba(255,255,255,0.6); opacity: 0.8; text-align: left;">${defterAdi}</div>` : '');
                return { domNodes: [title] };
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
            eventDidMount: function (info) {
                console.log('eventDidMount çağrıldı!', info.event.extendedProps);
                // Tooltip ekle
                const gorev = info.event.extendedProps;
                if (gorev.aciklama) {
                    const currentLang = document.documentElement.lang || 'tr';
                    let labelPriority = 'Öncelik';
                    let labelStatus = 'Durum';
                    let valuePriority = gorev.oncelik || '';
                    if (currentLang === 'en') {
                        labelPriority = 'Priority';
                        labelStatus = 'Status';
                        if (valuePriority === 'Düşük') valuePriority = 'Low';
                        else if (valuePriority === 'Orta') valuePriority = 'Medium';
                        else if (valuePriority === 'Yüksek') valuePriority = 'High';
                    } else if (currentLang === 'fr') {
                        labelPriority = 'Priorité';
                        labelStatus = 'Statut';
                        if (valuePriority === 'Düşük') valuePriority = 'Faible';
                        else if (valuePriority === 'Orta') valuePriority = 'Moyen';
                        else if (valuePriority === 'Yüksek') valuePriority = 'Élevé';
                    } else if (currentLang === 'de') {
                        labelPriority = 'Priorität';
                        labelStatus = 'Status';
                        if (valuePriority === 'Düşük') valuePriority = 'Niedrig';
                        else if (valuePriority === 'Orta') valuePriority = 'Mittel';
                        else if (valuePriority === 'Yüksek') valuePriority = 'Hoch';
                    }
                    info.el.title = `${gorev.aciklama}\n${labelPriority}: ${valuePriority}\n${labelStatus}: ${gorev.durum}`;
                }

                // Sağ tık menüsü için event listener ekle
                const gorevId = info.event.extendedProps.gorev_id;
                if (gorevId) {
                    console.log('Context menu listener eklendi, gorevId:', gorevId);

                    // Context menu için event listener
                    info.el.addEventListener('contextmenu', function (e) {
                        console.log('Sağ tık algılandı!', e);
                        e.preventDefault();
                        e.stopPropagation();
                        showContextMenu(e, gorevId);
                    }, true); // capture phase'de çalıştır

                    // Mouse down event'i de ekle (sağ tık için)
                    info.el.addEventListener('mousedown', function (e) {
                        if (e.button === 2) { // Sağ tık
                            console.log('Sağ tık mousedown algılandı!', e);
                            e.preventDefault();
                            e.stopPropagation();
                            showContextMenu(e, gorevId);
                        }
                    }, true);
                }

                // Görev durumuna göre CSS sınıfı ekle - Randevular takvimi stili
                if (gorev.durum) {
                    const durum = gorev.durum.toLowerCase();
                    if (durum === 'beklemede') info.el.classList.add('beklemede');
                    else if (durum === 'onaylandi' || durum === 'tamamlandi') info.el.classList.add('onaylandi');
                    else if (durum === 'iptal') info.el.classList.add('iptal');
                    else if (durum === 'tamamlandi') info.el.classList.add('tamamlandi');
                }

                // Öncelik seviyesine göre CSS sınıfı ekle
                if (gorev.oncelik) {
                    const oncelik = gorev.oncelik.toLowerCase();
                    if (oncelik === 'yüksek') info.el.classList.add('yuksek-oncelik');
                    else if (oncelik === 'orta') info.el.classList.add('orta-oncelik');
                    else if (oncelik === 'düşük') info.el.classList.add('dusuk-oncelik');
                }
            },
            dayCellDidMount: function (info) {
                // Gün hücresine görev sayısına göre stil ekle
                const date = info.date;
                const dayEl = info.el;

                // Mevcut badge'i kaldır
                const existingBadge = dayEl.querySelector('.gorev-count-badge');
                if (existingBadge) {
                    existingBadge.remove();
                }

                // Mevcut aktivite class'larını kaldır
                dayEl.classList.remove('high-activity-day', 'medium-activity-day', 'low-activity-day');

                // Bu güne ait görevleri bul
                const events = window.gorevlerCalendar.getEvents();
                const dayEvents = events.filter(event => {
                    const eventDate = event.start;
                    return eventDate &&
                        eventDate.getFullYear() === date.getFullYear() &&
                        eventDate.getMonth() === date.getMonth() &&
                        eventDate.getDate() === date.getDate();
                });

                const eventCount = dayEvents.length;

                // Görev sayısına göre yükseklik ve stil ayarla
                if (eventCount > 0) {
                    // Mevcut dinamik yükseklik class'larını kaldır
                    for (let i = 1; i <= 10; i++) {
                        dayEl.classList.remove(`dynamic-height-${i}`);
                    }

                    // Görev sayısına göre dinamik class ekle
                    if (eventCount <= 10) {
                        dayEl.classList.add(`dynamic-height-${eventCount}`);
                    } else {
                        // 10'dan fazla görev varsa maksimum yükseklik
                        dayEl.classList.add('dynamic-height-10');
                    }

                    // Zorla yükseklik ayarla (CSS class'ı yeterli olmazsa)
                    const calculatedHeight = 120 + (eventCount * 30);
                    dayEl.style.setProperty('min-height', `${calculatedHeight}px`, 'important');
                    dayEl.style.setProperty('height', `${calculatedHeight}px`, 'important');

                    // Parent elementleri de ayarla
                    const dayFrame = dayEl.querySelector('.fc-daygrid-day-frame');
                    if (dayFrame) {
                        dayFrame.style.setProperty('height', '100%', 'important');
                        dayFrame.style.setProperty('min-height', `${calculatedHeight}px`, 'important');
                    }

                    const dayEvents = dayEl.querySelector('.fc-daygrid-day-events');
                    if (dayEvents) {
                        dayEvents.style.setProperty('height', 'auto', 'important');
                        dayEvents.style.setProperty('min-height', '60px', 'important');
                    }

                    // Görev sayısı badge'i ekle
                    const badge = document.createElement('div');
                    badge.className = 'gorev-count-badge';
                    badge.textContent = eventCount;
                    badge.style.cssText = `
                    position: absolute;
                    top: 8px;
                    right: 8px;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 13px;
                    font-weight: bold;
                    box-shadow: 0 3px 6px rgba(0,0,0,0.3);
                    z-index: 10;
                    cursor: pointer;
                    transition: all 0.3s ease;
                `;

                    // Badge hover efekti
                    badge.addEventListener('mouseenter', function () {
                        this.style.transform = 'scale(1.2)';
                        this.style.boxShadow = '0 5px 15px rgba(102, 126, 234, 0.5)';
                    });

                    badge.addEventListener('mouseleave', function () {
                        this.style.transform = 'scale(1)';
                        this.style.boxShadow = '0 3px 6px rgba(0,0,0,0.3)';
                    });

                    dayEl.appendChild(badge);

                    // Görev sayısına göre gün hücresine özel stil
                    if (eventCount >= 5) {
                        dayEl.classList.add('high-activity-day');
                        badge.style.background = 'linear-gradient(135deg, #dc3545, #c82333)';
                    } else if (eventCount >= 3) {
                        dayEl.classList.add('medium-activity-day');
                        badge.style.background = 'linear-gradient(135deg, #ffc107, #e0a800)';
                    } else {
                        dayEl.classList.add('low-activity-day');
                        badge.style.background = 'linear-gradient(135deg, #28a745, #1e7e34)';
                    }

                    // Gün hücresine hover efekti ekle
                    dayEl.style.cursor = 'pointer';
                    dayEl.addEventListener('mouseenter', function () {
                        this.style.transform = 'scale(1.02)';
                        this.style.zIndex = '5';
                    });

                    dayEl.addEventListener('mouseleave', function () {
                        this.style.transform = 'scale(1)';
                        this.style.zIndex = '1';
                    });

                } else {
                    // Görev yoksa dinamik class'ları kaldır
                    for (let i = 1; i <= 10; i++) {
                        dayEl.classList.remove(`dynamic-height-${i}`);
                    }

                    // Varsayılan yükseklik ayarla
                    dayEl.style.setProperty('min-height', '120px', 'important');
                    dayEl.style.setProperty('height', '120px', 'important');

                    // Parent elementleri de sıfırla
                    const dayFrame = dayEl.querySelector('.fc-daygrid-day-frame');
                    if (dayFrame) {
                        dayFrame.style.setProperty('height', '100%', 'important');
                        dayFrame.style.setProperty('min-height', '120px', 'important');
                    }

                    const dayEvents = dayEl.querySelector('.fc-daygrid-day-events');
                    if (dayEvents) {
                        dayEvents.style.setProperty('height', 'auto', 'important');
                        dayEvents.style.setProperty('min-height', '60px', 'important');
                    }

                    dayEl.style.cursor = 'default';
                }
            }
        });

        console.log('FullCalendar oluşturuldu, render ediliyor...');
        window.gorevlerCalendar.render();
        console.log('Takvim render edildi!');

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
                    const calculatedHeight = 120 + (eventCount * 30);
                    dayEl.style.setProperty('min-height', `${calculatedHeight}px`, 'important');
                    dayEl.style.setProperty('height', `${calculatedHeight}px`, 'important');

                    const dayFrame = dayEl.querySelector('.fc-daygrid-day-frame');
                    if (dayFrame) {
                        dayFrame.style.setProperty('height', '100%', 'important');
                        dayFrame.style.setProperty('min-height', `${calculatedHeight}px`, 'important');
                    }
                } else {
                    dayEl.style.setProperty('min-height', '120px', 'important');
                    dayEl.style.setProperty('height', '120px', 'important');
                }
            });
        }, 500);
    }


    // Sayfa yüklendiğinde
    document.addEventListener('DOMContentLoaded', function () {
        console.log('=== DOMContentLoaded BAŞLADI ===');
        console.log('Sayfa yüklendi, görevler sayfası başlatılıyor...');

        // Durum çeviri fonksiyonu
        function translateStatuses() {
            const currentLang = document.documentElement.lang || 'tr';
            const statusElements = document.querySelectorAll('.durum-text');

            statusElements.forEach(element => {
                const originalStatus = element.getAttribute('data-durum');
                if (originalStatus) {
                    let translatedStatus;
                    if (currentLang === 'en') {
                        if (originalStatus === 'Beklemede') translatedStatus = 'Pending';
                        else if (originalStatus === 'Devam Ediyor') translatedStatus = 'In Progress';
                        else if (originalStatus === 'Tamamlandı') translatedStatus = 'Complete';
                        else translatedStatus = originalStatus;
                    } else if (currentLang === 'fr') {
                        if (originalStatus === 'Beklemede') translatedStatus = 'En Attente';
                        else if (originalStatus === 'Devam Ediyor') translatedStatus = 'En Cours';
                        else if (originalStatus === 'Tamamlandı') translatedStatus = 'Terminé';
                        else translatedStatus = originalStatus;
                    } else if (currentLang === 'de') {
                        if (originalStatus === 'Beklemede') translatedStatus = 'Ausstehend';
                        else if (originalStatus === 'Devam Ediyor') translatedStatus = 'In Bearbeitung';
                        else if (originalStatus === 'Tamamlandı') translatedStatus = 'Abgeschlossen';
                        else translatedStatus = originalStatus;
                    } else {
                        translatedStatus = originalStatus;
                    }
                    element.textContent = translatedStatus;
                }
            });
        }

        // Öncelik çeviri fonksiyonu
        function translatePriorities() {
            const currentLang = document.documentElement.lang || 'tr';
            const priorityElements = document.querySelectorAll('.oncelik-text');

            priorityElements.forEach(element => {
                const originalPriority = element.getAttribute('data-oncelik');
                if (originalPriority) {
                    let translated;
                    if (currentLang === 'en') {
                        if (originalPriority === 'Düşük') translated = 'Low';
                        else if (originalPriority === 'Orta') translated = 'Medium';
                        else if (originalPriority === 'Yüksek') translated = 'High';
                        else translated = originalPriority;
                    } else if (currentLang === 'fr') {
                        if (originalPriority === 'Düşük') translated = 'Faible';
                        else if (originalPriority === 'Orta') translated = 'Moyen';
                        else if (originalPriority === 'Yüksek') translated = 'Élevé';
                        else translated = originalPriority;
                    } else if (currentLang === 'de') {
                        if (originalPriority === 'Düşük') translated = 'Niedrig';
                        else if (originalPriority === 'Orta') translated = 'Mittel';
                        else if (originalPriority === 'Yüksek') translated = 'Hoch';
                        else translated = originalPriority;
                    } else {
                        translated = originalPriority;
                    }
                    element.textContent = translated;
                }
            });
        }

        // Sayfa yüklendiğinde çevir
        translateStatuses();
        translatePriorities();

        try {

            // Global fonksiyonları tanımla
            window.changeView = changeView;
            window.initializeCalendar = initializeCalendar;
            window.applyCalendarStyles = applyCalendarStyles;
            window.editGorev = editGorev;
            window.updateGorev = updateGorev;
            window.addContextMenuListeners = addContextMenuListeners;
            window.showContextMenu = showContextMenu;
            window.hideContextMenu = hideContextMenu;
            window.deleteGorev = deleteGorev;
            window.moveToRandevu = function (gorevId) {
                console.log('moveToRandevu çağrıldı:', gorevId);
                openRandevuModal(gorevId);
            };

            // Kullanıcının tercih ettiği görünümü yükle
            const savedView = localStorage.getItem('gorevlerView') || 'cards';
            console.log('=== SAYFA YÜKLENDİ ===');
            console.log('Kaydedilen görünüm:', savedView);
            console.log('localStorage gorevlerView:', localStorage.getItem('gorevlerView'));

            // Önce tarih aralığını bu ay olarak set et (tüm kontrollerden önce)
            function setCurrentMonthDates() {
                const dateFilterStartEl = document.getElementById('dateFilterStart');
                const dateFilterEndEl = document.getElementById('dateFilterEnd');

                if (dateFilterStartEl && dateFilterEndEl) {
                    const today = new Date();
                    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
                    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                    const startDateStr = getLocalYMD(firstDay);
                    const endDateStr = getLocalYMD(lastDay);

                    dateFilterStartEl.value = startDateStr;
                    dateFilterEndEl.value = endDateStr;

                    console.log('[INIT] Bu ayın tarih aralığı set edildi:', startDateStr, '-', endDateStr);
                    console.log('[INIT] Element kontrolü - Start:', dateFilterStartEl.value, 'End:', dateFilterEndEl.value);

                    return true;
                } else {
                    console.error('[INIT] Tarih aralığı elementleri bulunamadı!');
                    return false;
                }
            }

            // Hemen set et
            setCurrentMonthDates();

            // Filtre durumunu geri yükle
            const savedFilters = localStorage.getItem('gorevlerFilters');
            const dateFilterStartEl = document.getElementById('dateFilterStart');
            const dateFilterEndEl = document.getElementById('dateFilterEnd');

            // Tarih aralığını tekrar bu ay olarak set et (localStorage'dan tarih okumayı engellemek için)
            setCurrentMonthDates();

            if (savedFilters) {
                try {
                    const filters = JSON.parse(savedFilters);
                    console.log('Kaydedilen filtreler:', filters);

                    if (filters.searchTerm) document.getElementById('searchInput').value = filters.searchTerm;
                    if (filters.statusFilter) document.getElementById('statusFilter').value = filters.statusFilter;
                    if (filters.priorityFilter) document.getElementById('priorityFilter').value = filters.priorityFilter;
                    // Tarih aralığı her zaman bu ay olarak set edildi (yukarıda)

                    console.log('Filtreler geri yüklendi (tarih aralığı bu ay olarak set edildi)');
                } catch (error) {
                    console.error('Filtre geri yükleme hatası:', error);
                }
            }

            // Filtreyi uygula - tarih aralığı HTML'de zaten set edilmiş
            setTimeout(function () {
                // Tarih aralığını kontrol et ve eğer boşsa bu ayı set et
                const dateFilterStartElCheck = document.getElementById('dateFilterStart');
                const dateFilterEndElCheck = document.getElementById('dateFilterEnd');
                if (dateFilterStartElCheck && dateFilterEndElCheck) {
                    // Eğer HTML'den değer gelmemişse bu ayı set et
                    if (!dateFilterStartElCheck.value || !dateFilterEndElCheck.value) {
                        const todayCheck = new Date();
                        const firstDayCheck = new Date(todayCheck.getFullYear(), todayCheck.getMonth(), 1);
                        const lastDayCheck = new Date(todayCheck.getFullYear(), todayCheck.getMonth() + 1, 0);
                        const expectedStartCheck = getLocalYMD(firstDayCheck);
                        const expectedEndCheck = getLocalYMD(lastDayCheck);

                        dateFilterStartElCheck.value = expectedStartCheck;
                        dateFilterEndElCheck.value = expectedEndCheck;
                        console.log('[SETTIMEOUT] Tarih aralığı boştu, bu ay set edildi:', expectedStartCheck, '-', expectedEndCheck);
                    } else {
                        console.log('[SETTIMEOUT] Tarih aralığı HTML\'den geldi - Start:', dateFilterStartElCheck.value, 'End:', dateFilterEndElCheck.value);
                    }
                }
                // Filtreyi uygula
                console.log('[SETTIMEOUT] filterTasks çağrılıyor...');
                filterTasks();
            }, 300);

            // Önce buton durumlarını güncelle
            console.log('=== SAYFA YÜKLENDİ - BUTON İŞARETLEME BAŞLADI ===');
            const buttons = document.querySelectorAll('[data-view]');
            console.log('Bulunan buton sayısı:', buttons.length);

            buttons.forEach((btn, index) => {
                const viewType = btn.getAttribute('data-view');
                console.log(`Buton ${index + 1}:`, viewType, 'text:', btn.textContent.trim());
                btn.classList.remove('active');

                if (viewType === savedView) {
                    btn.classList.add('active');
                    console.log('✅ SAYFA YÜKLENDİ - Buton işaretlendi:', viewType);
                    // Görsel olarak da gösterelim
                    btn.style.backgroundColor = '#007bff';
                    btn.style.color = 'white';
                    btn.style.borderColor = '#007bff';
                } else {
                    console.log('❌ SAYFA YÜKLENDİ - Buton işaretlenmedi:', viewType);
                    // Diğer butonları normal yapalım
                    btn.style.backgroundColor = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }
            });
            console.log('=== SAYFA YÜKLENDİ - BUTON İŞARETLEME BİTTİ ===');

            // Sonra görünümü değiştir
            changeView(savedView);

            // changeView'den sonra buton durumlarını tekrar güncelle
            console.log('=== CHANGEVIEW SONRASI - BUTON İŞARETLEME BAŞLADI ===');
            document.querySelectorAll('[data-view]').forEach(btn => {
                btn.classList.remove('active');
                if (btn.getAttribute('data-view') === savedView) {
                    btn.classList.add('active');
                    console.log('✅ CHANGEVIEW SONRASI - Buton işaretlendi:', btn.getAttribute('data-view'));
                    // Görsel olarak da gösterelim
                    btn.style.backgroundColor = '#007bff';
                    btn.style.color = 'white';
                    btn.style.borderColor = '#007bff';
                } else {
                    console.log('❌ CHANGEVIEW SONRASI - Buton işaretlenmedi:', btn.getAttribute('data-view'));
                    // Diğer butonları normal yapalım
                    btn.style.backgroundColor = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }
            });
            console.log('=== CHANGEVIEW SONRASI - BUTON İŞARETLEME BİTTİ ===');

            // Eğer takvim görünümü seçiliyse CSS override'ları uygula
            if (savedView === 'calendar') {
                setTimeout(() => {
                    applyCalendarStyles();
                }, 500);
            }

            // Event listener'ları bağla
            setupAllEventListeners();

            console.log('=== DOMContentLoaded BİTTİ ===');

        } catch (error) {
            console.error('DOMContentLoaded hatası:', error);
            console.error('Hata detayı:', error.message);
            console.error('Stack trace:', error.stack);
        }
    });

    // Sayfa yenilendiğinde de çalışması için
    window.addEventListener('load', function () {
        console.log('=== WINDOW LOAD BAŞLADI ===');
        console.log('Window load event - event listener\'lar yeniden bağlanıyor...');

        try {

            // Global fonksiyonları tekrar tanımla
            window.changeView = changeView;
            window.initializeCalendar = initializeCalendar;
            window.applyCalendarStyles = applyCalendarStyles;
            window.editGorev = editGorev;
            window.updateGorev = updateGorev;
            window.addContextMenuListeners = addContextMenuListeners;
            window.showContextMenu = showContextMenu;
            window.hideContextMenu = hideContextMenu;
            window.deleteGorev = deleteGorev;
            window.moveToRandevu = function (gorevId) {
                console.log('moveToRandevu çağrıldı:', gorevId);
                openRandevuModal(gorevId);
            };

            // Tarih aralığını kesinlikle bu ay olarak set et
            const dateFilterStartEl = document.getElementById('dateFilterStart');
            const dateFilterEndEl = document.getElementById('dateFilterEnd');
            if (dateFilterStartEl && dateFilterEndEl) {
                const today = new Date();
                const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
                const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                const startDateStr = getLocalYMD(firstDay);
                const endDateStr = getLocalYMD(lastDay);

                // Her zaman bu ayı set et
                dateFilterStartEl.value = startDateStr;
                dateFilterEndEl.value = endDateStr;
                console.log('[WINDOW LOAD] Bu ayın tarih aralığı set edildi:', startDateStr, '-', endDateStr);
                console.log('[WINDOW LOAD] Element değerleri - Start:', dateFilterStartEl.value, 'End:', dateFilterEndEl.value);

                // Filtreyi uygula
                setTimeout(function () {
                    if (typeof filterTasks === 'function') {
                        console.log('[WINDOW LOAD] filterTasks çağrılıyor...');
                        filterTasks();
                    }
                }, 200);
            }

            setupAllEventListeners();

            console.log('=== WINDOW LOAD BİTTİ ===');

        } catch (error) {
            console.error('Window load hatası:', error);
            console.error('Hata detayı:', error.message);
            console.error('Stack trace:', error.stack);
        }
    });

    // Tüm event listener'ları bağlayan fonksiyon
    function setupAllEventListeners() {
        console.log('=== setupAllEventListeners BAŞLADI ===');
        console.log('Event listener\'lar bağlanıyor...');

        try {

            // Görünüm değiştirme butonları
            setupViewChangeListeners();

            // Durum değiştirme butonları
            setupStatusChangeListeners();

            // Filtreleme butonları - onclick attribute'ları kullanılıyor

            // Durumları yükle
            loadDurumlar();

            // Yeni görev form submit - artık onclick ile yapılıyor

            // Modal temizleme
            const quickGorevModal = document.getElementById('quickGorevModal');
            if (quickGorevModal) {
                quickGorevModal.addEventListener('hidden.bs.modal', function () {
                    const form = document.getElementById('quickGorevForm');
                    if (form) form.reset();
                    // Müşteri arama önerilerini gizle
                    const suggestions = document.getElementById('musteri_adi_suggestions');
                    if (suggestions) suggestions.style.display = 'none';
                });

                // Modal açıldığında seçenekleri yükle
                quickGorevModal.addEventListener('shown.bs.modal', function () {
                    console.log('=== YENİ GÖREV MODALI AÇILDI ===');
                    console.log('Yeni görev modalı açıldı, seçenekler yükleniyor...');
                    loadDurumlar();
                    loadKullanicilar();
                    loadRandevuDefterleri();
                });
            }


            // Müşteri arama autocomplete
            setupMusteriArama();

            // Kullanıcıları yükle
            loadKullanicilar();

            // Randevu defterlerini yükle
            loadRandevuDefterleri();

            // Bugünün tarihini set et
            setTodayDate();

            // Modal butonları
            setupModalListeners();

            // Randevu modal butonları
            setupRandevuModalListeners();

            console.log('Event listener\'lar bağlandı!');
            console.log('=== setupAllEventListeners BİTTİ ===');

        } catch (error) {
            console.error('setupAllEventListeners hatası:', error);
            console.error('Hata detayı:', error.message);
            console.error('Stack trace:', error.stack);
        }
    }

    // Görünüm değiştirme event listener'ları
    function setupViewChangeListeners() {
        console.log('Görünüm değiştirme event listener\'ları bağlanıyor...');

        // Event delegation kullan - document seviyesinde dinle
        document.removeEventListener('click', handleViewClick);
        document.addEventListener('click', handleViewClick);

        console.log('Görünüm değiştirme event listener\'ları bağlandı!');
    }

    // Görünüm değiştirme click handler'ı
    function handleViewClick(e) {
        // Sadece data-view attribute'u olan butonları dinle
        if (e.target.closest('[data-view]')) {
            e.preventDefault();
            e.stopPropagation();
            const btn = e.target.closest('[data-view]');
            const viewType = btn.getAttribute('data-view');
            console.log('Görünüm butonu tıklandı:', viewType);
            changeView(viewType);
        }
    }

    // Randevu modal event listener'ları
    function setupRandevuModalListeners() {
        console.log('Randevu modal event listener\'ları bağlanıyor...');

        // Randevu modal'ı oluştur
        if (!document.getElementById('randevuModal')) {
            createRandevuModal();
        }

        // Defter seçildiğinde otomatik slot yükleme ve süre ayarlama
        const defterSelect = document.getElementById('defter_id');
        if (defterSelect) {
            // Önceki event listener'ları temizle
            defterSelect.removeEventListener('change', handleDefterChange);
            // Yeni event listener ekle
            defterSelect.addEventListener('change', handleDefterChange);
        }

        console.log('Randevu modal event listener\'ları bağlandı!');
    }

    // Defter değişikliği handler'ı
    function handleDefterChange() {
        const defterSelect = document.getElementById('defter_id');
        const tarihInput = document.getElementById('tarih_gun');

        if (defterSelect && tarihInput) {
            if (defterSelect.value && tarihInput.value) {
                loadRandevuSlots();
            }

            // Seçilen defterin slot süresini al ve süre alanına doldur
            const selectedOption = defterSelect.options[defterSelect.selectedIndex];
            const slotDakika = selectedOption.getAttribute('data-slot-dakika');
            if (slotDakika) {
                const sureInput = document.getElementById('randevu_suresi');
                if (sureInput) {
                    sureInput.value = slotDakika;
                }
            }
        }
    }

    // Modal event listener'ları ekle
    const gorevModal = document.getElementById('gorevModal');
    if (gorevModal) {
        gorevModal.addEventListener('shown.bs.modal', function () {
            console.log('Görev modal\'ı açıldı, butonları aktif ediliyor...');

            // Modal açıldıktan sonra butonları aktif et - AGRESİF ÇÖZÜM
            setTimeout(() => {
                const buttons = gorevModal.querySelectorAll('button');
                const inputs = gorevModal.querySelectorAll('input, select, textarea');

                console.log('Modal event listener - Bulunan buton sayısı:', buttons.length);
                console.log('Modal event listener - Bulunan input sayısı:', inputs.length);

                // Butonları aktif et
                buttons.forEach((button, index) => {
                    console.log(`Modal event - Buton ${index}:`, button);
                    button.disabled = false;
                    button.removeAttribute('disabled');
                    button.style.pointerEvents = 'auto';
                    button.style.opacity = '1';
                    button.style.cursor = 'pointer';
                    button.style.backgroundColor = '';
                    button.style.color = '';
                    button.style.zIndex = '9999';
                    button.style.position = 'relative';
                    button.tabIndex = 0;
                    button.classList.remove('disabled');

                    // Event listener'ları yeniden ekle
                    if (button.onclick) {
                        const originalOnclick = button.onclick;
                        button.onclick = originalOnclick;
                    }

                    console.log(`Modal event - Buton ${index} aktif edildi:`, button.disabled, button.style.pointerEvents);
                });

                // Input'ları aktif et
                inputs.forEach((input, index) => {
                    console.log(`Modal event - Input ${index}:`, input);
                    input.disabled = false;
                    input.removeAttribute('disabled');
                    input.readOnly = false;
                    input.removeAttribute('readonly');
                    input.style.pointerEvents = 'auto';
                    input.style.opacity = '1';
                    input.style.cursor = 'text';
                    input.style.backgroundColor = '';
                    input.style.color = '';
                    input.style.zIndex = '9999';
                    input.style.position = 'relative';
                    input.classList.remove('disabled', 'form-control-plaintext');
                    input.classList.add('form-control');
                    input.tabIndex = 0;

                    console.log(`Modal event - Input ${index} aktif edildi:`, input.disabled, input.readOnly, input.style.pointerEvents);
                });

                console.log('Modal event listener - Modal butonları ve input\'ları aktif edildi');

                // Ek test - Kaydet butonuna manuel event listener ekle
                const kaydetBtn = document.querySelector('#gorevModal .btn-primary');
                if (kaydetBtn) {
                    console.log('Kaydet butonu bulundu:', kaydetBtn);

                    // Mevcut onclick'i kaldır ve yeniden ekle
                    kaydetBtn.onclick = null;
                    kaydetBtn.addEventListener('click', function (e) {
                        console.log('Kaydet butonuna tıklandı!');
                        e.preventDefault();
                        e.stopPropagation();
                        saveGorev();
                    });

                    // Test için butona tıklama eventi ekle
                    kaydetBtn.addEventListener('mousedown', function () {
                        console.log('Kaydet butonuna mousedown eventi!');
                    });

                    kaydetBtn.addEventListener('mouseup', function () {
                        console.log('Kaydet butonuna mouseup eventi!');
                    });

                    console.log('Kaydet butonuna manuel event listener eklendi');
                }
            }, 200);
        });
    }

    // Görünüm butonlarına event listener ekle
    // Görünüm değiştirme butonları - onclick attribute'u kullanılıyor, burada event listener eklemeye gerek yok

    // Modern filtreleme ve arama fonksiyonları
    initializeAdvancedFilters();

    // Kullanıcı dostu özellikleri başlat
    initializeUserFriendlyFeatures();

    // Animasyonları başlat
    setTimeout(animateStats, 500);
});

    // Gelişmiş filtreleme sistemi
    function initializeAdvancedFilters() {
        const searchInput = document.getElementById('searchInput');
        const statusFilter = document.getElementById('statusFilter');
        const priorityFilter = document.getElementById('priorityFilter');

        // Arama fonksiyonu
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                filterTasks();
            });
        }

        // Durum filtresi
        if (statusFilter) {
            statusFilter.addEventListener('change', function () {
                filterTasks();
            });
        }

        // Öncelik filtresi
        if (priorityFilter) {
            priorityFilter.addEventListener('change', function () {
                filterTasks();
            });
        }

        // Tarih aralığı filtresi - değiştiğinde filtreyi uygula (tarihi değiştirmesine izin ver)
        const dateFilterStart = document.getElementById('dateFilterStart');
        const dateFilterEnd = document.getElementById('dateFilterEnd');
        if (dateFilterStart) {
            dateFilterStart.addEventListener('change', function () {
                // Kullanıcı tarihi değiştirdi, filtreyi uygula
                console.log('[DATE CHANGE] Başlangıç tarihi değişti:', dateFilterStart.value);
                filterTasks();
            });
        }
        if (dateFilterEnd) {
            dateFilterEnd.addEventListener('change', function () {
                // Kullanıcı tarihi değiştirdi, filtreyi uygula
                console.log('[DATE CHANGE] Bitiş tarihi değişti:', dateFilterEnd.value);
                filterTasks();
            });
        }

        // Tarih aralığı her zaman bu ay olarak set edilmeli
        if (dateFilterStart && dateFilterEnd) {
            const setCurrentMonth = function () {
                const today = new Date();
                const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
                const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                const expectedStart = getLocalYMD(firstDay);
                const expectedEnd = getLocalYMD(lastDay);

                // Her zaman bu ayı set et
                dateFilterStart.value = expectedStart;
                dateFilterEnd.value = expectedEnd;
                console.log('[AUTO-SET] Tarih aralığı bu ay olarak set edildi:', expectedStart, '-', expectedEnd);
            };

            // Sayfa yüklendikten sonra kesinlikle bu ayı set et
            setTimeout(setCurrentMonth, 150);
        }
    }

    // Eski fonksiyonlar kaldırıldı - script bloğunun başına taşındı

    // Veri yenileme
    function refreshData() {
        // Mevcut görünümü koru
        const currentView = localStorage.getItem('gorevlerView') || 'cards';

        // Sayfayı yenile
        window.location.reload();
    }

    // Animasyonlar için
    function animateStats() {
        const statNumbers = document.querySelectorAll('.h5.mb-0.font-weight-bold.text-gray-800');
        statNumbers.forEach(stat => {
            const finalValue = parseInt(stat.textContent);
            let currentValue = 0;
            const increment = finalValue / 50;

            const timer = setInterval(() => {
                currentValue += increment;
                if (currentValue >= finalValue) {
                    stat.textContent = finalValue;
                    clearInterval(timer);
                } else {
                    stat.textContent = Math.floor(currentValue);
                }
            }, 30);
        });
    }


    // Kullanıcı dostu özellikleri başlat
    function initializeUserFriendlyFeatures() {
        initializeDragAndDrop();
        initializeSmartSearch();
        initializeToastSystem();
        initializeFilterChips();
    }

    // Drag & Drop sistemi
    function initializeDragAndDrop() {
        const tasks = document.querySelectorAll('.gorev-item');

        tasks.forEach(task => {
            task.addEventListener('dragstart', function (e) {
                this.classList.add('dragging');
                e.dataTransfer.setData('text/plain', this.dataset.taskId || '');
            });

            task.addEventListener('dragend', function () {
                this.classList.remove('dragging');
            });
        });
    }

    // Akıllı arama sistemi
    function initializeSmartSearch() {
        const searchInput = document.getElementById('searchInput');
        const suggestions = document.getElementById('searchSuggestions');

        if (!searchInput || !suggestions) return;

        let searchTimeout;

        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            const query = this.value.toLowerCase();

            if (query.length < 2) {
                suggestions.style.display = 'none';
                return;
            }

            searchTimeout = setTimeout(() => {
                showSearchSuggestions(query);
            }, 300);
        });

        // Arama kutusundan çıkınca önerileri gizle
        document.addEventListener('click', function (e) {
            if (!searchInput.contains(e.target) && !suggestions.contains(e.target)) {
                suggestions.style.display = 'none';
            }
        });
    }

    // Arama önerilerini göster
    function showSearchSuggestions(query) {
        const suggestions = document.getElementById('searchSuggestions');
        const tasks = document.querySelectorAll('.gorev-item');
        const matches = [];

        tasks.forEach(task => {
            const title = task.querySelector('.card-title, .gorev-list-title')?.textContent.toLowerCase() || '';
            const description = task.querySelector('.card-text, .gorev-list-description')?.textContent.toLowerCase() || '';

            if (title.includes(query) || description.includes(query)) {
                matches.push({
                    title: task.querySelector('.card-title, .gorev-list-title')?.textContent || '',
                    element: task
                });
            }
        });

        if (matches.length > 0) {
            suggestions.innerHTML = matches.slice(0, 5).map(match =>
                `<div class="search-suggestion" onclick="highlightTask('${match.title}')">${match.title}</div>`
            ).join('');
            suggestions.style.display = 'block';
        } else {
            suggestions.style.display = 'none';
        }
    }

    // Görevi vurgula
    function highlightTask(title) {
        const tasks = document.querySelectorAll('.gorev-item');
        tasks.forEach(task => {
            const taskTitle = task.querySelector('.card-title, .gorev-list-title')?.textContent || '';
            if (taskTitle === title) {
                task.scrollIntoView({ behavior: 'smooth', block: 'center' });
                task.style.animation = 'pulse 1s ease-in-out';
                setTimeout(() => {
                    task.style.animation = '';
                }, 1000);
            }
        });

        document.getElementById('searchSuggestions').style.display = 'none';
    }

    // Toast bildirim sistemi
    function initializeToastSystem() {
        window.showToast = function (message, type = 'success', duration = 3000) {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
                <span>${message}</span>
                <button class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;

            container.appendChild(toast);

            // Animasyonu başlat
            setTimeout(() => toast.classList.add('show'), 100);

            // Otomatik kaldır
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        };
    }

    // Filtre çipleri sistemi
    function initializeFilterChips() {
        updateFilterChips();
    }

    // Filtre çiplerini güncelle
    function updateFilterChips() {
        const container = document.getElementById('activeFilters');
        if (!container) return;

        const searchTerm = document.getElementById('searchInput').value;
        const statusFilter = document.getElementById('statusFilter').value;
        const priorityFilter = document.getElementById('priorityFilter').value;
        const dateFilterStart = document.getElementById('dateFilterStart').value;
        const dateFilterEnd = document.getElementById('dateFilterEnd').value;

        let chips = [];

        if (searchTerm) {
            chips.push(`<div class="filter-chip" onclick="clearSearch()">
            <span>Arama: "${searchTerm}"</span>
            <span class="remove">×</span>
        </div>`);
        }

        if (statusFilter !== 'all') {
            const statusText = document.getElementById('statusFilter').selectedOptions[0].text;
            chips.push(`<div class="filter-chip" onclick="clearStatusFilter()">
            <span>Durum: ${statusText}</span>
            <span class="remove">×</span>
        </div>`);
        }

        if (priorityFilter !== 'all') {
            const priorityText = document.getElementById('priorityFilter').selectedOptions[0].text;
            chips.push(`<div class="filter-chip" onclick="clearPriorityFilter()">
            <span>Öncelik: ${priorityText}</span>
            <span class="remove">×</span>
        </div>`);
        }

        if (dateFilterStart || dateFilterEnd) {
            const dateRange = dateFilterStart && dateFilterEnd ?
                `${dateFilterStart} - ${dateFilterEnd}` :
                (dateFilterStart ? `Başlangıç: ${dateFilterStart}` : `Bitiş: ${dateFilterEnd}`);
            chips.push(`<div class="filter-chip" onclick="clearDateFilter()">
            <span>Tarih: ${dateRange}</span>
            <span class="remove">×</span>
        </div>`);
        }

        container.innerHTML = chips.join('');
    }

    // Hızlı tamamlama
    window.quickComplete = function (taskId) {
        try { event && event.stopPropagation && event.stopPropagation(); } catch (e) { }
        try { event && event.preventDefault && event.preventDefault(); } catch (e) { }
        try { console.log('quickComplete clicked for taskId:', taskId); } catch (e) { }
        if (confirm('Bu görevi tamamlandı olarak işaretlemek istediğinizden emin misiniz?')) {
            fetch(`/todos/${taskId}/durum`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ durum: 'Tamamlandı' })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showToast('Görev başarıyla tamamlandı!', 'success');
                        // Takvim olaylarını yenile
                        try {
                            if (window.gorevlerCalendar) {
                                const evId = 'gorev_' + String(taskId);
                                const ev = window.gorevlerCalendar.getEventById(evId);
                                if (ev) { ev.remove(); }
                            }
                        } catch (e) { }
                        // Kart ve liste görünümlerinde tamamlandı olarak işaretle (DOM'dan kaldırma)
                        try {
                            document.querySelectorAll(`.gorev-item[data-gorev-id="${taskId}"]`).forEach(el => {
                                if (window.completedStatusId) {
                                    el.setAttribute('data-durum-id', String(window.completedStatusId));
                                }
                                el.classList.add('tamamlandi');
                                const badge = el.querySelector('.durum-text');
                                if (badge) {
                                    badge.setAttribute('data-durum', 'Tamamlandı');
                                    const lang = document.documentElement.lang || 'tr';
                                    let text = 'Tamamlandı';
                                    if (lang.startsWith('en')) text = 'Completed';
                                    else if (lang.startsWith('fr')) text = 'Terminé';
                                    else if (lang.startsWith('de')) text = 'Abgeschlossen';
                                    badge.textContent = text;
                                    badge.style.backgroundColor = '#28a745';
                                    badge.style.color = 'white';
                                }
                                const titleEl = el.querySelector('.card-title, h6.mb-1');
                                if (titleEl && !titleEl.classList.contains('text-decoration-line-through')) {
                                    titleEl.classList.add('text-decoration-line-through', 'text-muted');
                                }
                            });
                        } catch (e) { }
                        // Yedek olarak kısa bir gecikmeden sonra görünümü güncelle
                        // Eğer tamamen kaldırıldıysa boş durum görünebilir; tam sayfa yenilemeye gerek yok
                    } else {
                        showToast('Hata: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showToast('Bir hata oluştu', 'error');
                });
        }
    }

    // Yeni görev modal'ı
    function showNewTaskModal() {
        showToast('Yeni görev özelliği yakında eklenecek!', 'info');
    }

    // Toplu işlemler
    function showBulkActions() {
        showToast('Toplu işlemler özelliği yakında eklenecek!', 'info');
    }

    // Filtre temizleme fonksiyonları
    function clearSearch() {
        document.getElementById('searchInput').value = '';
        filterTasks();
        updateFilterChips();
    }

    function clearStatusFilter() {
        document.getElementById('statusFilter').value = 'all';
        filterTasks();
        updateFilterChips();
    }

    function clearPriorityFilter() {
        document.getElementById('priorityFilter').value = 'all';
        filterTasks();
        updateFilterChips();
    }

    function clearDateFilter() {
        // Tarih aralığını bu ay olarak set et (temizleme değil, bu ayı göster)
        const dateFilterStartEl = document.getElementById('dateFilterStart');
        const dateFilterEndEl = document.getElementById('dateFilterEnd');
        if (dateFilterStartEl && dateFilterEndEl) {
            const today = new Date();
            const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
            dateFilterStartEl.value = getLocalYMD(firstDay);
            dateFilterEndEl.value = getLocalYMD(lastDay);
            console.log('[CLEAR DATE FILTER] Tarih aralığı bu ay olarak set edildi');
        }
        filterTasks();
        updateFilterChips();
    }

    // İkinci filterTasks fonksiyonu kaldırıldı - global scope'taki kullanılıyor
