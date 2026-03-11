# -*- coding: utf-8 -*-
import os

translations = {
    'tr': {
        'Create New Appointment': 'Yeni Randevu Oluştur',
        'Back': 'Geri',
        'Appointment Book Selection': 'Randevu Defteri Seçimi',
        'Appointment Book': 'Randevu Defteri',
        'Select appointment book...': 'Randevu defteri seçin...',
        'Date and Time Selection': 'Tarih ve Saat Seçimi',
        'Date': 'Tarih',
        'Loading available time slots...': 'Uygun saat dilimleri yükleniyor...',
        'Appointment Details': 'Randevu Detayları',
        'Reference': 'Referans',
        'None': 'Hiçbiri',
        'Operation': 'İşlem',
        'Select Operation': 'İşlem Seçin',
        'Duration (minutes)': 'Süre (dakika)',
        'Description': 'Açıklama',
        'Assign to User': 'Kullanıcıya Ata',
        'Select user (optional)': 'Kullanıcı seçin (isteğe bağlı)',
        'Seçilen kullanıcıya bu randevu için otomatik görev oluşturulacak': 'Seçilen kullanıcıya bu randevu için otomatik görev oluşturulacak',
        'Customer Information': 'Müşteri Bilgileri',
        'Customer Name': 'Müşteri Adı',
        'Type name, existing customers will appear...': 'İsim yazın, mevcut müşteriler görünecektir...',
        'Type at least 2 characters. Matching customers will appear. If not found, a new customer will be created.': 'En az 2 karakter yazın. Eşleşen müşteriler listelenir, bulunamazsa yeni müşteri kaydedilir.',
        'Customer Surname': 'Müşteri Soyadı',
        'Phone Number': 'Telefon Numarası',
        'Enter a valid phone number (e.g.: 536 555 66 44)': 'Geçerli bir telefon numarası girin (örn: 536 555 66 44)',
        'Email': 'E-posta',
        'username': 'kullaniciadi',
        'Enter a valid email address': 'Geçerli bir e-posta adresi girin',
        'Gender': 'Cinsiyet',
        'Select': 'Seçiniz',
        'Male': 'Erkek',
        'Female': 'Kadın',
        'Birth Date': 'Doğum Tarihi',
        'Age will be calculated automatically.': 'Yaş otomatik olarak hesaplanacaktır.',
        'Category': 'Kategori',
        'Select Category': 'Kategori Seçin',
        'No categories available': 'Kategori bulunmuyor',
        'No categories found. Please create categories in settings.': 'Kategori bulunamadı. Ayarlardan tanımlayabilirsiniz.',
        'Country': 'Ülke',
        'Select Country': 'Ülke Seçiniz',
        'State/City': 'İl/Şehir',
        'Select State/City': 'İl/Şehir Seçiniz',
        'District': 'İlçe',
        'Select District': 'İlçe Seçiniz',
        'Address': 'Adres',
        'Street, building, apartment...': 'Mahalle, sokak, bina, daire...',
        'Customer Notes': 'Müşteri Notları',
        'Allergies, preferences, important information...': 'Alerjiler, tercihler, önemli bilgiler...',
        'Save and Send Info via WhatsApp / SMS': 'Kaydet ve WhatsApp / SMS ile Bilgi Gönder',
        'Save Appointment': 'Randevuyu Kaydet',
        'Appointment Saved Successfully!': 'Randevu Başarıyla Kaydedildi!'
    },
    'en': {
        'Create New Appointment': 'Create New Appointment',
        'Back': 'Back',
        'Appointment Book Selection': 'Appointment Book Selection',
        'Appointment Book': 'Appointment Book',
        'Select appointment book...': 'Select appointment book...',
        'Date and Time Selection': 'Date and Time Selection',
        'Date': 'Date',
        'Loading available time slots...': 'Loading available time slots...',
        'Appointment Details': 'Appointment Details',
        'Reference': 'Reference',
        'None': 'None',
        'Operation': 'Operation',
        'Select Operation': 'Select Operation',
        'Duration (minutes)': 'Duration (minutes)',
        'Description': 'Description',
        'Assign to User': 'Assign to User',
        'Select user (optional)': 'Select user (optional)',
        'Seçilen kullanıcıya bu randevu için otomatik görev oluşturulacak': 'An automatic task will be created for the selected user',
        'Customer Information': 'Customer Information',
        'Customer Name': 'Customer Name',
        'Type name, existing customers will appear...': 'Type name, existing customers will appear...',
        'Type at least 2 characters. Matching customers will appear. If not found, a new customer will be created.': 'Type at least 2 characters. Matching customers will appear. If not found, a new customer will be created.',
        'Customer Surname': 'Customer Surname',
        'Phone Number': 'Phone Number',
        'Enter a valid phone number (e.g.: 536 555 66 44)': 'Enter a valid phone number (e.g.: 536 555 66 44)',
        'Email': 'Email',
        'username': 'username',
        'Enter a valid email address': 'Enter a valid email address',
        'Gender': 'Gender',
        'Select': 'Select',
        'Male': 'Male',
        'Female': 'Female',
        'Birth Date': 'Birth Date',
        'Age will be calculated automatically.': 'Age will be calculated automatically.',
        'Category': 'Category',
        'Select Category': 'Select Category',
        'No categories available': 'No categories available',
        'No categories found. Please create categories in settings.': 'No categories found. Please create categories in settings.',
        'Country': 'Country',
        'Select Country': 'Select Country',
        'State/City': 'State/City',
        'Select State/City': 'Select State/City',
        'District': 'District',
        'Select District': 'Select District',
        'Address': 'Address',
        'Street, building, apartment...': 'Street, building, apartment...',
        'Customer Notes': 'Customer Notes',
        'Allergies, preferences, important information...': 'Allergies, preferences, important information...',
        'Save and Send Info via WhatsApp / SMS': 'Save and Send Info via WhatsApp / SMS',
        'Save Appointment': 'Save Appointment',
        'Appointment Saved Successfully!': 'Appointment Saved Successfully!'
    },
    'de': {
        'Create New Appointment': 'Neuen Termin erstellen',
        'Back': 'Zurück',
        'Appointment Book Selection': 'Terminbuchauswahl',
        'Appointment Book': 'Terminbuch',
        'Select appointment book...': 'Terminbuch wählen...',
        'Date and Time Selection': 'Datums- und Zeitauswahl',
        'Date': 'Datum',
        'Loading available time slots...': 'Verfügbare Zeitfenster werden geladen...',
        'Appointment Details': 'Termindetails',
        'Reference': 'Referenz',
        'None': 'Keine',
        'Operation': 'Aktion',
        'Select Operation': 'Aktion auswählen',
        'Duration (minutes)': 'Dauer (Minuten)',
        'Description': 'Beschreibung',
        'Assign to User': 'Benutzer zuweisen',
        'Select user (optional)': 'Benutzer auswählen (optional)',
        'Seçilen kullanıcıya bu randevu için otomatik görev oluşturulacak': 'Für den ausgewählten Benutzer wird eine Aufgabe erstellt',
        'Customer Information': 'Kundeninformationen',
        'Customer Name': 'Kundenname',
        'Type name, existing customers will appear...': 'Namen eingeben, bestehende Kunden werden angezeigt...',
        'Type at least 2 characters. Matching customers will appear. If not found, a new customer will be created.': 'Mindestens 2 Zeichen eingeben, um Kunden zu suchen.',
        'Customer Surname': 'Kunden Nachname',
        'Phone Number': 'Telefonnummer',
        'Enter a valid phone number (e.g.: 536 555 66 44)': 'Gültige Handynummer eingeben',
        'Email': 'E-Mail',
        'username': 'benutzername',
        'Enter a valid email address': 'Gültige E-Mail eingeben',
        'Gender': 'Geschlecht',
        'Select': 'Auswählen',
        'Male': 'Männlich',
        'Female': 'Weiblich',
        'Birth Date': 'Geburtsdatum',
        'Age will be calculated automatically.': 'Das Alter wird berechnet.',
        'Category': 'Kategorie',
        'Select Category': 'Kategorie wählen',
        'No categories available': 'Keine Kategorien verfügbar',
        'No categories found. Please create categories in settings.': 'Keine Kategorien gefunden. Bitte erstellen Sie diese.',
        'Country': 'Land',
        'Select Country': 'Land auswählen',
        'State/City': 'Bundesland/Stadt',
        'Select State/City': 'Stadt auswählen',
        'District': 'Bezirk',
        'Select District': 'Bezirk auswählen',
        'Address': 'Adresse',
        'Street, building, apartment...': 'Straße, Hausnummer...',
        'Customer Notes': 'Kundennotizen',
        'Allergies, preferences, important information...': 'Allergien, wichtige Infos...',
        'Save and Send Info via WhatsApp / SMS': 'Speichern & WhatsApp/SMS senden',
        'Save Appointment': 'Termin speichern',
        'Appointment Saved Successfully!': 'Termin erfolgreich gespeichert!'
    },
    'fr': {
        'Create New Appointment': 'Créer un nouveau rendez-vous',
        'Back': 'Retour',
        'Appointment Book Selection': 'Sélection du carnet de rendez-vous',
        'Appointment Book': 'Carnet de rendez-vous',
        'Select appointment book...': 'Sélectionner le carnet...',
        'Date and Time Selection': 'Sélection de la date et lheure',
        'Date': 'Date',
        'Loading available time slots...': 'Chargement des créneaux...',
        'Appointment Details': 'Détails du rendez-vous',
        'Reference': 'Référence',
        'None': 'Aucun',
        'Operation': 'Opération',
        'Select Operation': 'Sélectionner lopération',
        'Duration (minutes)': 'Durée (minutes)',
        'Description': 'Description',
        'Assign to User': 'Assigner à',
        'Select user (optional)': 'Sélectionner un utilisateur',
        'Seçilen kullanıcıya bu randevu için otomatik görev oluşturulacak': 'Une tâche automatique sera créée pour cet utilisateur',
        'Customer Information': 'Informations client',
        'Customer Name': 'Nom du client',
        'Type name, existing customers will appear...': 'Saisir le nom...',
        'Type at least 2 characters. Matching customers will appear. If not found, a new customer will be created.': 'Saisissez 2 caractères minimum pour chercher le client.',
        'Customer Surname': 'Prénom du client',
        'Phone Number': 'Numéro de téléphone',
        'Enter a valid phone number (e.g.: 536 555 66 44)': 'Saisissez un numéro de téléphone',
        'Email': 'Email',
        'username': 'utilisateur',
        'Enter a valid email address': 'Saisissez un email valide',
        'Gender': 'Genre',
        'Select': 'Sélectionner',
        'Male': 'Homme',
        'Female': 'Femme',
        'Birth Date': 'Date de naissance',
        'Age will be calculated automatically.': 'Lâge sera calculé',
        'Category': 'Catégorie',
        'Select Category': 'Sélectionner la catégorie',
        'No categories available': 'Aucune catégorie',
        'No categories found. Please create categories in settings.': 'Aucune catégorie trouvée. Créez-en une.',
        'Country': 'Pays',
        'Select Country': 'Sélectionner le pays',
        'State/City': 'Région/Ville',
        'Select State/City': 'Sélectionner la région',
        'District': 'Quartier',
        'Select District': 'Sélectionner le quartier',
        'Address': 'Adresse',
        'Street, building, apartment...': 'Rue, bâtiment...',
        'Customer Notes': 'Notes client',
        'Allergies, preferences, important information...': 'Allergies, infos importantes...',
        'Save and Send Info via WhatsApp / SMS': 'Enregistrer & Envoyer SMS WhatsApp',
        'Save Appointment': 'Enregistrer le rendez-vous',
        'Appointment Saved Successfully!': 'Rendez-vous enregistré avec succès!'
    }
}

keys = list(translations['tr'].keys())

for lang in translations.keys():
    filepath = os.path.join('translations', lang, 'LC_MESSAGES', 'messages.po')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        out_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#~ msgid '):
                msgid = line[9:].strip().strip('"')
                if msgid in keys:
                    out_lines.append('msgid "{}"\n'.format(msgid))
                    i += 1
                    while i < len(lines) and lines[i].startswith('#~ msgstr '):
                        i += 1
                    msgstr = translations[lang][msgid]
                    out_lines.append('msgstr "{}"\n\n'.format(msgstr))
                    continue
            if line.startswith('msgid '):
                msgid = line[6:].strip().strip('"')
                if msgid in keys:
                    out_lines.append(line)
                    i += 1
                    while i < len(lines) and lines[i].startswith('msgstr '):
                        i += 1
                    msgstr = translations[lang][msgid]
                    out_lines.append('msgstr "{}"\n\n'.format(msgstr))
                    continue
            out_lines.append(line)
            i += 1
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)
