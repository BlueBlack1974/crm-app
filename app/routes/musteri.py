from flask import Blueprint, render_template, request, jsonify, send_file, session, current_app, flash, redirect, url_for
from app.extensions import db
from app.models import Musteri, KullaniciLog
from app.utils.decorators import login_required
from app.utils.helpers import get_client_ip
from app.utils.logging import log_user_action
from flask_babel import get_locale
import pandas as pd
import os
import re
import json
import tempfile
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from app.models import Randevu, RandevuDefterAyar, MusteriKategori
from collections import defaultdict
from io import BytesIO, StringIO
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

musteri_bp = Blueprint('musteri', __name__)

# Upload klasörü
UPLOAD_FOLDER = 'uploads/excel_imports'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_phone(phone):
    """Telefon numarası validasyonu"""
    # Boş değer kontrolü
    if phone is None or phone == '' or (isinstance(phone, float) and pd.isna(phone)):
        return False, 'Telefon numarası boş olamaz'
    
    # String'e çevir ve boşlukları temizle
    phone_str = str(phone).strip()
    
    # Boş string kontrolü (nan, None, empty string)
    if not phone_str or phone_str.lower() in ['nan', 'none', '']:
        return False, 'Telefon numarası boş olamaz'
    
    # Bilimsel notasyonu düzelt
    if 'e' in phone_str.lower():
        try:
            phone_str = str(int(float(phone_str)))
        except:
            pass
    
    # Float formatındaysa (nokta varsa) int'e çevir
    if '.' in phone_str:
        try:
            phone_str = str(int(float(phone_str)))
        except:
            pass
    
    # Sadece rakamları al
    phone_clean = re.sub(r'\D', '', phone_str)
    
    # 10 haneli (5XXXXXXXXX) veya 11 haneli (05XXXXXXXXX) olmalı
    if len(phone_clean) == 10 and phone_clean.startswith('5'):
        # 10 haneli format kabul edilir, 0 eklenmez
        pass
    elif len(phone_clean) == 11 and phone_clean.startswith('05'):
        # 11 haneli formatı 10 haneliye çevir (sıfırı kaldır)
        phone_clean = phone_clean[1:]
    else:
        return False, f'Telefon 10 (5XXXXXXXXX) veya 11 (05XXXXXXXXX) haneli olmalıdır'
    
    return True, phone_clean

def validate_email(email):
    """Email validasyonu"""
    if not email or pd.isna(email):
        return True, None  # Email opsiyonel
    
    email = str(email).strip()
    if not email:
        return True, None
    
    # Basit email regex
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, 'Geçersiz email formatı'
    
    return True, email

def validate_date(date_str):
    """Tarih validasyonu"""
    if not date_str or pd.isna(date_str):
        return True, None  # Tarih opsiyonel
    
    date_str = str(date_str).strip()
    if not date_str:
        return True, None
    
    # Farklı tarih formatlarını dene (Türk formatı öncelikli)
    date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d']
    
    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, date_format)
            return True, parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return False, 'Geçersiz tarih formatı (GG.AA.YYYY veya GG/AA/YYYY kullanın, örn: 18.05.1974)'

@musteri_bp.route('/musteriler/import')
@login_required
def musteriler_import():
    """Müşteri Excel import sayfası"""
    return render_template('musteriler_import.html')

@musteri_bp.route('/api/musteri-import/template')
@login_required
def musteri_import_template():
    """Excel template dosyasını kullanıcının diline göre oluştur ve indir"""
    
    # Kullanıcının dil seçimini al
    locale = str(get_locale())
    
    # Dil bazlı çeviriler
    translations = {
        'tr': {
            'columns': ['Ad', 'Soyad', 'Ülke Kodu', 'Telefon', 'Email', 'Cinsiyet', 'Doğum Tarihi', 'Adres'],
            'sample_data': {
                'Ad': ['Ahmet', 'Ayşe', 'Mehmet'],
                'Soyad': ['Yılmaz', 'Demir', 'Kaya'],
                'Ülke Kodu': ['90', '90', '90'],
                'Telefon': ['5551234567', '5559876543', '5551112233'],
                'Email': ['ahmet@mail.com', 'ayse@mail.com', 'mehmet@mail.com'],
                'Cinsiyet': ['Erkek', 'Kadın', 'Erkek'],
                'Doğum Tarihi': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Adres': ['İstanbul, Kadıköy', 'Ankara, Çankaya', 'İzmir, Karşıyaka']
            },
            'guide_title': 'Müşteri İçe Aktarma - Kullanım Kılavuzu',
            'guide_sheet': 'Kullanım Kılavuzu',
            'customers_sheet': 'Müşteriler'
        },
        'en': {
            'columns': ['Name', 'Surname', 'Country Code', 'Phone', 'Email', 'Gender', 'Birth Date', 'Address'],
            'sample_data': {
                'Name': ['John', 'Jane', 'Michael'],
                'Surname': ['Smith', 'Doe', 'Johnson'],
                'Country Code': ['90', '90', '90'],
                'Phone': ['5551234567', '5559876543', '5551112233'],
                'Email': ['john@mail.com', 'jane@mail.com', 'michael@mail.com'],
                'Gender': ['Male', 'Female', 'Male'],
                'Birth Date': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Address': ['Istanbul, Kadikoy', 'Ankara, Cankaya', 'Izmir, Karsiyaka']
            },
            'guide_title': 'Customer Import - User Guide',
            'guide_sheet': 'User Guide',
            'customers_sheet': 'Customers'
        },
        'de': {
            'columns': ['Vorname', 'Nachname', 'Ländercode', 'Telefon', 'E-Mail', 'Geschlecht', 'Geburtsdatum', 'Adresse'],
            'sample_data': {
                'Vorname': ['Hans', 'Anna', 'Michael'],
                'Nachname': ['Schmidt', 'Müller', 'Weber'],
                'Ländercode': ['90', '90', '90'],
                'Telefon': ['5551234567', '5559876543', '5551112233'],
                'E-Mail': ['hans@mail.com', 'anna@mail.com', 'michael@mail.com'],
                'Geschlecht': ['Männlich', 'Weiblich', 'Männlich'],
                'Geburtsdatum': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Adresse': ['Istanbul, Kadikoy', 'Ankara, Cankaya', 'Izmir, Karsiyaka']
            },
            'guide_title': 'Kundenimport - Benutzerhandbuch',
            'guide_sheet': 'Benutzerhandbuch',
            'customers_sheet': 'Kunden'
        },
        'fr': {
            'columns': ['Prénom', 'Nom', 'Code Pays', 'Téléphone', 'E-mail', 'Genre', 'Date de Naissance', 'Adresse'],
            'sample_data': {
                'Prénom': ['Pierre', 'Marie', 'Jean'],
                'Nom': ['Martin', 'Dubois', 'Durand'],
                'Code Pays': ['90', '90', '90'],
                'Téléphone': ['5551234567', '5559876543', '5551112233'],
                'E-mail': ['pierre@mail.com', 'marie@mail.com', 'jean@mail.com'],
                'Genre': ['Homme', 'Femme', 'Homme'],
                'Date de Naissance': ['15.05.1990', '20.08.1985', '10.03.1995'],
                'Adresse': ['Istanbul, Kadikoy', 'Ankara, Cankaya', 'Izmir, Karsiyaka']
            },
            'guide_title': 'Importation de Clients - Guide d\'Utilisation',
            'guide_sheet': 'Guide d\'Utilisation',
            'customers_sheet': 'Clients'
        }
    }
    
    # Varsayılan olarak Türkçe
    lang_data = translations.get(locale, translations['tr'])
    
    # DataFrame oluştur
    df = pd.DataFrame(lang_data['sample_data'])
    
    # Geçici dosya oluştur
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    temp_path = temp_file.name
    temp_file.close()
    
    # Excel'e yaz
    df.to_excel(temp_path, index=False, sheet_name=lang_data['customers_sheet'])
    
    # Workbook'u yükle ve stil ekle
    wb = load_workbook(temp_path)
    ws = wb[lang_data['customers_sheet']]
    
    # Başlık stili
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=12)
    header_alignment = Alignment(horizontal='center', vertical='center')
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Başlık satırına stil uygula
    for col in range(1, len(df.columns) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = border
    
    # Kolon genişliklerini ayarla
    for col in range(1, len(df.columns) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    # Veri satırlarına border ekle ve telefon+ülke kodu kolonlarını TEXT formatına çevir
    telefon_col_index = None
    ulke_kodu_col_index = None
    
    for col_idx, col_name in enumerate(df.columns, start=1):
        col_lower = str(col_name).lower()
        if 'telefon' in col_lower or 'phone' in col_lower or 'téléphone' in col_lower:
            if 'kod' not in col_lower and 'code' not in col_lower:  # "Ülke Kodu" değilse
                telefon_col_index = col_idx
        elif 'kod' in col_lower or 'code' in col_lower:
            ulke_kodu_col_index = col_idx
    
    for row in range(2, len(df) + 2):
        for col in range(1, len(df.columns) + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = border
            # Telefon ve ülke kodu kolonlarını TEXT olarak formatla
            if col == telefon_col_index or col == ulke_kodu_col_index:
                cell.number_format = '@'  # TEXT format
    
    # Kaydet
    wb.save(temp_path)
    
    # Dosya adını dile göre ayarla
    filename = f'customer_import_template_{locale}.xlsx'
    
    return send_file(temp_path, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@musteri_bp.route('/api/musteri-import/upload', methods=['POST'])
@login_required
def musteri_import_upload():
    """Excel dosyasını yükle ve parse et"""
    try:
        # Dosya kontrolü
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Dosya seçilmedi'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Dosya seçilmedi'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Sadece .xlsx veya .xls dosyaları yüklenebilir'}), 400
        
        # Upload klasörünü oluştur
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        # Güvenli dosya adı oluştur
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{session['user_id']}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Dosyayı kaydet
        file.save(filepath)
        
        # Excel'i oku - telefon kolonunu string olarak oku
        df = pd.read_excel(filepath, sheet_name=0, dtype=str, keep_default_na=False)
        
        # Boş satırları temizle
        df = df.dropna(how='all')
        
        # Kolonları al
        columns = df.columns.tolist()
        
        # İlk 5 satırı önizleme için al
        preview_data = df.head(5).fillna('').to_dict('records')
        
        return jsonify({
            'success': True,
            'filename': unique_filename,
            'filepath': filepath,
            'columns': columns,
            'preview': preview_data,
            'total_rows': len(df),
            'message': f'{len(df)} satır müşteri verisi yüklendi'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Dosya yüklenirken hata: {str(e)}'}), 500

@musteri_bp.route('/api/musteri-import/preview', methods=['POST'])
@login_required
def musteri_import_preview():
    """Kolon eşleştirmesi sonrası önizleme ve validasyon"""
    try:
        data = request.json
        filepath = data.get('filepath')
        column_mapping = data.get('column_mapping')  # {'excel_column': 'db_field'}
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'success': False, 'message': 'Dosya bulunamadı'}), 400
        
        # Excel'i oku - tüm kolonları string olarak oku
        df = pd.read_excel(filepath, sheet_name=0, dtype=str, keep_default_na=False)
        df = df.dropna(how='all')
        
        # Validasyon sonuçları
        validated_data = []
        errors_count = 0
        warnings_count = 0
        
        # Mevcut telefon numaralarını al (duplicate kontrolü için)
        existing_phones = set()
        mevcut_musteriler = Musteri.query.filter_by(
            FirmaID=session['firma_id'],
            Aktif=True
        ).all()
        for m in mevcut_musteriler:
            if m.Telefon:
                # Telefon numarasını normalize et (hem 10 hem 11 haneli formatları kabul et)
                phone_normalized = m.Telefon.strip()
                if phone_normalized.startswith('0') and len(phone_normalized) == 11:
                    # 11 haneli: 0531714415 -> 531714415
                    existing_phones.add(phone_normalized[1:])
                    existing_phones.add(phone_normalized)  # Orijinal formatı da ekle
                elif len(phone_normalized) == 10 and phone_normalized.startswith('5'):
                    # 10 haneli: 531714415 -> 0531714415
                    existing_phones.add(phone_normalized)
                    existing_phones.add('0' + phone_normalized)  # 0 eklenmiş formatı da ekle
                else:
                    existing_phones.add(phone_normalized)
        
        # Dosyadaki telefon numaralarını takip et (dosya içi duplicate kontrolü)
        file_phones = set()
        
        for idx, row in df.iterrows():
            row_data = {
                'row_number': idx + 2,  # Excel satır numarası (1=header)
                'data': {},
                'errors': [],
                'warnings': [],
                'status': 'valid'
            }
            
            # Her kolon için veriyi al ve validate et
            for excel_col, db_field in column_mapping.items():
                if excel_col not in df.columns:
                    continue
                
                value = row[excel_col]
                
                # Ad validasyonu
                if db_field == 'MusteriAdi':
                    if pd.isna(value) or str(value).strip() == '':
                        row_data['errors'].append('Ad boş olamaz')
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['MusteriAdi'] = str(value).strip()
                
                # Soyad validasyonu
                elif db_field == 'MusteriSoyadi':
                    if pd.isna(value) or str(value).strip() == '':
                        row_data['errors'].append('Soyad boş olamaz')
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['MusteriSoyadi'] = str(value).strip()
                
                # Telefon validasyonu
                elif db_field == 'Telefon':
                    valid, result = validate_phone(value)
                    if not valid:
                        row_data['errors'].append(result)
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['Telefon'] = result
                        
                        # Duplicate kontrolü - normalize edilmiş telefon ile kontrol et
                        phone_for_check = result
                        if len(result) == 10 and result.startswith('5'):
                            # 10 haneli format için 11 haneli versiyonunu da kontrol et
                            phone_11_digit = '0' + result
                            if phone_for_check in existing_phones or phone_11_digit in existing_phones:
                                row_data['warnings'].append('Bu telefon numarası sistemde zaten kayıtlı')
                                if row_data['status'] != 'error':
                                    row_data['status'] = 'duplicate'
                        elif len(result) == 11 and result.startswith('05'):
                            # 11 haneli format için 10 haneli versiyonunu da kontrol et
                            phone_10_digit = result[1:]
                            if phone_for_check in existing_phones or phone_10_digit in existing_phones:
                                row_data['warnings'].append('Bu telefon numarası sistemde zaten kayıtlı')
                                if row_data['status'] != 'error':
                                    row_data['status'] = 'duplicate'
                        elif result in existing_phones:
                            row_data['warnings'].append('Bu telefon numarası sistemde zaten kayıtlı')
                            if row_data['status'] != 'error':
                                row_data['status'] = 'duplicate'
                        elif result in file_phones:
                            row_data['warnings'].append('Bu telefon numarası dosyada birden fazla kez var')
                            if row_data['status'] != 'error':
                                row_data['status'] = 'warning'
                        else:
                            file_phones.add(result)
                
                # Email validasyonu
                elif db_field == 'Email':
                    valid, result = validate_email(value)
                    if not valid:
                        row_data['errors'].append(result)
                        row_data['status'] = 'error'
                    else:
                        row_data['data']['Email'] = result
                
                # Ülke Kodu (opsiyonel, sadece kaydet)
                elif db_field == 'UlkeKodu':
                    if not pd.isna(value) and str(value).strip():
                        row_data['data']['UlkeKodu'] = str(value).strip()
                
                # Cinsiyet
                elif db_field == 'Cinsiyet':
                    if not pd.isna(value) and str(value).strip():
                        cinsiyet = str(value).strip()
                        cinsiyet_lower = cinsiyet.lower()
                        
                        # Erkek için tüm dillerdeki değerler
                        erkek_values = [
                            # Türkçe
                            'erkek', 'e', 'e.',
                            # İngilizce
                            'male', 'm', 'm.', 'man', 'men',
                            # Fransızca
                            'homme', 'masculin', 'mâle',
                            # Almanca
                            'männlich', 'mann', 'm'
                        ]
                        
                        # Kadın için tüm dillerdeki değerler
                        kadin_values = [
                            # Türkçe
                            'kadın', 'kadýn', 'k', 'k.',
                            # İngilizce
                            'female', 'f', 'f.', 'woman', 'women',
                            # Fransızca
                            'femme', 'féminin', 'femelle',
                            # Almanca
                            'weiblich', 'frau', 'w'
                        ]
                        
                        if cinsiyet_lower in erkek_values:
                            row_data['data']['Cinsiyet'] = 'Erkek'
                        elif cinsiyet_lower in kadin_values:
                            row_data['data']['Cinsiyet'] = 'Kadın'
                        else:
                            row_data['warnings'].append(f'Bilinmeyen cinsiyet: {cinsiyet}')
                            row_data['data']['Cinsiyet'] = None
                
                # Doğum tarihi
                elif db_field == 'DogumTarihi':
                    valid, result = validate_date(value)
                    if not valid:
                        row_data['errors'].append(result)
                        if row_data['status'] != 'error':
                            row_data['status'] = 'warning'
                    else:
                        row_data['data']['DogumTarihi'] = result
                
                # Diğer alanlar (Adres, Notlar)
                else:
                    if not pd.isna(value) and str(value).strip():
                        row_data['data'][db_field] = str(value).strip()
            
            # İstatistikleri güncelle
            if row_data['status'] == 'error':
                errors_count += 1
            elif row_data['status'] in ['duplicate', 'warning']:
                warnings_count += 1
            
            validated_data.append(row_data)
        
        return jsonify({
            'success': True,
            'data': validated_data,
            'stats': {
                'total': len(validated_data),
                'valid': len([d for d in validated_data if d['status'] == 'valid']),
                'errors': errors_count,
                'warnings': warnings_count,
                'duplicates': len([d for d in validated_data if d['status'] == 'duplicate'])
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Önizleme hatası: {str(e)}'}), 500

@musteri_bp.route('/api/musteri-import/process', methods=['POST'])
@login_required
def musteri_import_process():
    """Validasyondan geçen verileri işle ve kaydet"""
    try:
        data = request.json
        validated_data = data.get('data', [])
        import_options = data.get('options', {})
        
        # Import seçenekleri
        skip_errors = import_options.get('skip_errors', True)
        update_duplicates = import_options.get('update_duplicates', False)
        skip_duplicates = import_options.get('skip_duplicates', True)
        
        # Sonuçlar
        results = {
            'success': 0,
            'skipped': 0,
            'updated': 0,
            'errors': 0,
            'details': []
        }
        
        for row in validated_data:
            row_number = row['row_number']
            status = row['status']
            row_data = row['data']
            
            try:
                # Hatalı kayıtları atla
                if status == 'error':
                    if skip_errors:
                        results['skipped'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'skipped',
                            'message': 'Validasyon hatası nedeniyle atlandı'
                        })
                        continue
                    else:
                        results['errors'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'error',
                            'message': ', '.join(row['errors'])
                        })
                        continue
                
                # Duplicate kontrolü
                if status == 'duplicate':
                    telefon = row_data.get('Telefon')
                    existing = Musteri.query.filter_by(
                        FirmaID=session['firma_id'],
                        Telefon=telefon,
                        Aktif=True
                    ).first()
                    
                    if existing and update_duplicates:
                        # Mevcut kaydı güncelle
                        for key, value in row_data.items():
                            if value is not None:
                                setattr(existing, key, value)
                        
                        db.session.commit()
                        
                        # Güncellenen müşteri için log
                        log_user_action(
                            action_type='musteri_excel_import_update',
                            table_name='Musteri',
                            record_id=existing.MusteriID,
                            old_data={
                                'MusteriAdi': existing.MusteriAdi,
                                'MusteriSoyadi': existing.MusteriSoyadi,
                                'Telefon': existing.Telefon,
                                'Email': existing.Email
                            },
                            new_data={
                                'MusteriAdi': row_data.get('MusteriAdi'),
                                'MusteriSoyadi': row_data.get('MusteriSoyadi'),
                                'Telefon': row_data.get('Telefon'),
                                'Email': row_data.get('Email')
                            },
                            detail=f'Excel import ile müşteri güncellendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")} (Telefon: {row_data.get("Telefon")})'
                        )
                        
                        results['updated'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'updated',
                            'message': f'Mevcut müşteri güncellendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")}'
                        })
                        continue
                    elif skip_duplicates:
                        results['skipped'] += 1
                        results['details'].append({
                            'row': row_number,
                            'status': 'skipped',
                            'message': 'Duplicate kayıt atlandı'
                        })
                        continue
                
                # Yeni müşteri oluştur
                yeni_musteri = Musteri(
                    FirmaID=session['firma_id'],
                    MusteriAdi=row_data.get('MusteriAdi'),
                    MusteriSoyadi=row_data.get('MusteriSoyadi'),
                    Telefon=row_data.get('Telefon'),
                    Email=row_data.get('Email'),
                    Cinsiyet=row_data.get('Cinsiyet'),
                    DogumTarihi=row_data.get('DogumTarihi'),
                    Adres=row_data.get('Adres'),
                    Notlar=row_data.get('Notlar'),
                    Aktif=True
                )
                
                db.session.add(yeni_musteri)
                db.session.commit()
                
                # Her müşteri için ayrı log
                log_user_action(
                    action_type='musteri_excel_import_add',
                    table_name='Musteri',
                    record_id=yeni_musteri.MusteriID,
                    new_data={
                        'MusteriAdi': row_data.get('MusteriAdi'),
                        'MusteriSoyadi': row_data.get('MusteriSoyadi'),
                        'Telefon': row_data.get('Telefon'),
                        'Email': row_data.get('Email'),
                        'Cinsiyet': row_data.get('Cinsiyet'),
                        'DogumTarihi': row_data.get('DogumTarihi'),
                        'Adres': row_data.get('Adres'),
                        'Notlar': row_data.get('Notlar')
                    },
                    detail=f'Excel import ile müşteri eklendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")} (Telefon: {row_data.get("Telefon")})'
                )
                
                results['success'] += 1
                results['details'].append({
                    'row': row_number,
                    'status': 'success',
                    'message': f'Müşteri eklendi: {row_data.get("MusteriAdi")} {row_data.get("MusteriSoyadi")}'
                })
                
            except Exception as e:
                db.session.rollback()
                results['errors'] += 1
                results['details'].append({
                    'row': row_number,
                    'status': 'error',
                    'message': f'Kayıt hatası: {str(e)}'
                })
        
        # Genel Excel import log kaydı
        log_mesaj = f"Excel import tamamlandı: {results['success']} müşteri eklendi, {results['updated']} müşteri güncellendi, {results['skipped']} kayıt atlandı, {results['errors']} hata oluştu"
        log_user_action(
            action_type='musteri_excel_import_summary',
            table_name='Musteri',
            detail=log_mesaj
        )
        
        return jsonify({
            'success': True,
            'results': results,
            'message': log_mesaj
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'İşlem hatası: {str(e)}'}), 500

@musteri_bp.route('/api/musteri/<int:musteri_id>')
def api_musteri_get(musteri_id):
    """Müşteri bilgilerini getir"""
    try:
        # Manuel session kontrolü - daha esnek
        # user_id kullan, kullanici_id değil
        kullanici_id = session.get('user_id')
        if not kullanici_id or not session.get('firma_id'):
            return jsonify({'success': False, 'message': 'Oturum süresi dolmuş. Lütfen tekrar giriş yapın.', 'redirect': '/login'}), 401
        
        firma_id = session.get('firma_id')
        
        # Müşteriyi bul
        musteri = Musteri.query.filter(
            Musteri.MusteriID == musteri_id,
            Musteri.FirmaID == firma_id,
            Musteri.Aktif == True
        ).first()
        
        if not musteri:
            return jsonify({'success': False, 'message': 'Müşteri bulunamadı'}), 404
        
        # Müşteri bilgilerini döndür
        return jsonify({
            'success': True,
            'musteri': {
                'MusteriID': musteri.MusteriID,
                'MusteriAdi': musteri.MusteriAdi,
                'MusteriSoyadi': musteri.MusteriSoyadi,
                'Telefon': musteri.Telefon,
                'Email': musteri.Email,
                'Yas': musteri.Yas,
                'Cinsiyet': musteri.Cinsiyet,
                'DogumTarihi': musteri.DogumTarihi.isoformat() if musteri.DogumTarihi else None,
                'Sehir': musteri.Sehir,
                'Ilce': musteri.Ilce,
                'Adres': musteri.Adres,
                'Notlar': musteri.Notlar
            }
        })
        
    except Exception as e:
        print(f"Müşteri getirme hatası: {e}")
        return jsonify({'success': False, 'message': 'Sunucu hatası'}), 500

@musteri_bp.route('/api/musteri/ekle', methods=['POST'])
@login_required
def api_musteri_ekle():
    """Yeni müşteri ekle"""
    try:
        # Yetki kontrolü
        firma_id = session.get('firma_id')
        user_id = session.get('user_id')
        if not firma_id:
             return jsonify({'success': False, 'message': 'Oturum hatası'}), 401
            
        data = request.get_json()
        
        # Zorunlu alan kontrolü
        if not data.get('musteri_adi') or not data.get('musteri_soyadi'):
            return jsonify({'success': False, 'message': 'Ad ve Soyad zorunludur'}), 400
            
        # Telefon boş olabilir, varsa formatla
        telefon = data.get('telefon', '').strip() or None
        if telefon:
             # Basit temizlik
             if telefon.startswith('0'): telefon = telefon[1:]
             
        yeni_musteri = Musteri(
            FirmaID=firma_id,
            MusteriAdi=data.get('musteri_adi', '').strip(),
            MusteriSoyadi=data.get('musteri_soyadi', '').strip(),
            Telefon=telefon,
            Email=data.get('email', '').strip() or None,
            Cinsiyet=data.get('cinsiyet'),
            Sehir=data.get('sehir'),
            Ilce=data.get('ilce'),
            Adres=data.get('adres'),
            Notlar=data.get('notlar'),
            InstagramKullaniciAdi=data.get('instagram_kullanici_adi', '').strip() or None,
            OlusturanKullaniciID=user_id,
            Aktif=True
        )
        
        # Doğum tarihi
        if data.get('dogum_tarihi'):
            try:
                yeni_musteri.DogumTarihi = datetime.strptime(data['dogum_tarihi'], '%Y-%m-%d').date()
                # Yaş hesapla
                today = datetime.now().date()
                yeni_musteri.Yas = today.year - yeni_musteri.DogumTarihi.year - ((today.month, today.day) < (yeni_musteri.DogumTarihi.month, yeni_musteri.DogumTarihi.day))
            except:
                pass

        db.session.add(yeni_musteri)
        db.session.commit()
        
        log_user_action('ADD', 'Musteri', record_id=yeni_musteri.MusteriID, detail=f"Yeni müşteri: {yeni_musteri.MusteriAdi} {yeni_musteri.MusteriSoyadi}")
        
        return jsonify({'success': True, 'message': 'Müşteri başarıyla eklendi', 'musteri_id': yeni_musteri.MusteriID})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@musteri_bp.route('/api/musteri/<int:musteri_id>/update', methods=['POST'])
def api_musteri_update(musteri_id):
    """Müşteri bilgilerini güncelle"""
    try:
        # Manuel session kontrolü - daha esnek
        # user_id kullan, kullanici_id değil
        kullanici_id = session.get('user_id')
        if not kullanici_id or not session.get('firma_id'):
            return jsonify({'success': False, 'message': 'Oturum süresi dolmuş. Lütfen tekrar giriş yapın.', 'redirect': '/login'}), 401
        
        firma_id = session.get('firma_id')
        kullanici_id = session.get('user_id')
        
        # Müşteriyi bul
        musteri = Musteri.query.filter(
            Musteri.MusteriID == musteri_id,
            Musteri.FirmaID == firma_id,
            Musteri.Aktif == True
        ).first()
        
        if not musteri:
            return jsonify({'success': False, 'message': 'Müşteri bulunamadı'}), 404
        
        # Form verilerini al
        data = request.get_json()
        
        # Eski verileri kaydet (log için)
        old_data = {
            'MusteriAdi': musteri.MusteriAdi,
            'MusteriSoyadi': musteri.MusteriSoyadi,
            'Telefon': musteri.Telefon,
            'Email': musteri.Email,
            'Yas': musteri.Yas,
            'Cinsiyet': musteri.Cinsiyet,
            'DogumTarihi': musteri.DogumTarihi.isoformat() if musteri.DogumTarihi else None,
            'Sehir': musteri.Sehir,
            'Ilce': musteri.Ilce,
            'Adres': musteri.Adres,
            'Notlar': musteri.Notlar
        }
        
        # Validasyon
        if not data.get('musteri_adi') or not data.get('musteri_soyadi'):
            return jsonify({'success': False, 'message': 'Ad ve soyad zorunludur'}), 400
        
        # Telefon validasyonu
        if data.get('telefon'):
            phone = str(data['telefon']).strip()
            if phone:
                # Sıfırları temizle
                if phone.startswith('0'):
                    phone = phone[1:]
                if len(phone) == 10 and phone.startswith('5'):
                    data['telefon'] = phone
                else:
                    return jsonify({'success': False, 'message': 'Geçersiz telefon numarası formatı'}), 400
        
        # Müşteri bilgilerini güncelle
        musteri.MusteriAdi = data.get('musteri_adi', '').strip()
        musteri.MusteriSoyadi = data.get('musteri_soyadi', '').strip()
        musteri.Telefon = data.get('telefon', '').strip() or None
        musteri.Email = data.get('email', '').strip() or None
        musteri.Yas = data.get('yas') or None
        musteri.Cinsiyet = data.get('cinsiyet', '').strip() or None
        musteri.Sehir = data.get('sehir', '').strip() or None
        musteri.Ilce = data.get('ilce', '').strip() or None
        musteri.Adres = data.get('adres', '').strip() or None
        musteri.Notlar = data.get('notlar', '').strip() or None
        musteri.InstagramKullaniciAdi = data.get('instagram_kullanici_adi', '').strip() or None
        
        # Doğum tarihi
        if data.get('dogum_tarihi'):
            try:
                musteri.DogumTarihi = datetime.strptime(data['dogum_tarihi'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': 'Geçersiz doğum tarihi formatı'}), 400
        else:
            musteri.DogumTarihi = None
        
        # Veritabanına kaydet
        db.session.commit()
        
        # Log kaydı
        new_data = {
            'MusteriAdi': musteri.MusteriAdi,
            'MusteriSoyadi': musteri.MusteriSoyadi,
            'Telefon': musteri.Telefon,
            'Email': musteri.Email,
            'Yas': musteri.Yas,
            'Cinsiyet': musteri.Cinsiyet,
            'DogumTarihi': musteri.DogumTarihi.isoformat() if musteri.DogumTarihi else None,
            'Sehir': musteri.Sehir,
            'Ilce': musteri.Ilce,
            'Adres': musteri.Adres,
            'Notlar': musteri.Notlar
        }
        
        # Log kaydı oluştur
        log_user_action(
            action_type='UPDATE',
            table_name='Musteri',
            record_id=musteri_id,
            old_data=old_data,
            new_data=new_data,
            detail=f'Müşteri güncellendi: {musteri.MusteriAdi} {musteri.MusteriSoyadi}'
        )
        
        return jsonify({
            'success': True,
            'message': 'Müşteri başarıyla güncellendi'
        })
        
    except Exception as e:
        print(f"Müşteri güncelleme hatası: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Sunucu hatası'}), 500

# Plaka kodları - şehir isimleri dönüşüm tablosu
plaka_to_sehir = {
    '01': 'Adana', '02': 'Adıyaman', '03': 'Afyonkarahisar', '04': 'Ağrı', '05': 'Amasya',
    '06': 'Ankara', '07': 'Antalya', '08': 'Artvin', '09': 'Aydın', '10': 'Balıkesir',
    '11': 'Bilecik', '12': 'Bingöl', '13': 'Bitlis', '14': 'Bolu', '15': 'Burdur',
    '16': 'Bursa', '17': 'Çanakkale', '18': 'Çankırı', '19': 'Çorum', '20': 'Denizli',
    '21': 'Diyarbakır', '22': 'Edirne', '23': 'Elazığ', '24': 'Erzincan', '25': 'Erzurum',
    '26': 'Eskişehir', '27': 'Gaziantep', '28': 'Giresun', '29': 'Gümüşhane', '30': 'Hakkari',
    '31': 'Hatay', '32': 'Isparta', '33': 'Mersin', '34': 'İstanbul', '35': 'İzmir',
    '36': 'Kars', '37': 'Kastamonu', '38': 'Kayseri', '39': 'Kırklareli', '40': 'Kırşehir',
    '41': 'Kocaeli', '42': 'Konya', '43': 'Kütahya', '44': 'Malatya', '45': 'Manisa',
    '46': 'Kahramanmaraş', '47': 'Mardin', '48': 'Muğla', '49': 'Muş', '50': 'Nevşehir',
    '51': 'Niğde', '52': 'Ordu', '53': 'Rize', '54': 'Sakarya', '55': 'Samsun',
    '56': 'Siirt', '57': 'Sinop', '58': 'Sivas', '59': 'Tekirdağ', '60': 'Tokat',
    '61': 'Trabzon', '62': 'Tunceli', '63': 'Şanlıurfa', '64': 'Uşak', '65': 'Van',
    '66': 'Yozgat', '67': 'Zonguldak', '68': 'Aksaray', '69': 'Bayburt', '70': 'Karaman',
    '71': 'Kırıkkale', '72': 'Batman', '73': 'Şırnak', '74': 'Bartın', '75': 'Ardahan',
    '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye', '81': 'Düzce'
}

@musteri_bp.route('/rapor/musteriler')
@login_required
def rapor_musteriler():
    # Modül izin kontrolü
    if not session.get('raporlar_modulu', False):
        flash('Bu sayfaya erişim yetkiniz yok', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Müşteri raporu: filtreler, KPI'lar, tablo ve CSV dışa aktarım
    firma_id = session['firma_id']

    # Filtreler
    kategori_id = request.args.get('kategori_id', type=int)
    sadece_aktif = request.args.get('aktif', default='1')  # '1' aktif, '' hepsi
    iletisim_var = request.args.get('iletisim_var')  # 'telefon', 'email', 'herikisi'
    
    # Yeni filtreler
    yas_min = request.args.get('yas_min', type=int)
    yas_max = request.args.get('yas_max', type=int)
    cinsiyet = request.args.get('cinsiyet')
    dogum_tarihi = request.args.get('dogum_tarihi')
    sehir = request.args.get('sehir')
    ilce = request.args.get('ilce')
    
    format_tip = request.args.get('format')  # 'csv' ise CSV döndür

    # Müşteri temel sorgusu
    musteri_query = Musteri.query.filter_by(FirmaID=firma_id)
    if sadece_aktif == '1':
        musteri_query = musteri_query.filter(Musteri.Aktif == True)
    elif sadece_aktif == '0':
        musteri_query = musteri_query.filter(Musteri.Aktif == False)
    if kategori_id:
        musteri_query = musteri_query.filter(Musteri.KategoriID == kategori_id)
    if iletisim_var == 'telefon':
        musteri_query = musteri_query.filter(Musteri.Telefon.isnot(None), Musteri.Telefon != '')
    elif iletisim_var == 'email':
        musteri_query = musteri_query.filter(Musteri.Email.isnot(None), Musteri.Email != '')
    elif iletisim_var == 'herikisi':
        musteri_query = musteri_query.filter(
            Musteri.Telefon.isnot(None), Musteri.Telefon != '',
            Musteri.Email.isnot(None), Musteri.Email != ''
        )
    
    # Yeni filtreler
    if yas_min is not None:
        musteri_query = musteri_query.filter(Musteri.Yas >= yas_min)
    if yas_max is not None:
        musteri_query = musteri_query.filter(Musteri.Yas <= yas_max)
    if cinsiyet:
        musteri_query = musteri_query.filter(Musteri.Cinsiyet == cinsiyet)
    if dogum_tarihi:
        try:
            dogum_tarihi_obj = datetime.strptime(dogum_tarihi, '%Y-%m-%d').date()
            musteri_query = musteri_query.filter(Musteri.DogumTarihi == dogum_tarihi_obj)
        except:
            pass
    if sehir:
        # Seçilen şehir ismini plaka koduna dönüştür
        sehir_to_plaka = {v: k for k, v in plaka_to_sehir.items()}
        plaka_kodu = sehir_to_plaka.get(sehir, sehir)  # Eğer şehir ismi plaka kodunda yoksa orijinal değeri kullan
        musteri_query = musteri_query.filter(Musteri.Sehir == plaka_kodu)
    if ilce:
        musteri_query = musteri_query.filter(Musteri.Ilce == ilce)

    musteriler = musteri_query.order_by(Musteri.MusteriAdi, Musteri.MusteriSoyadi).all()

    # KPI'lar
    toplam_musteri = Musteri.query.filter_by(FirmaID=firma_id).count()
    aktif_musteri = Musteri.query.filter_by(FirmaID=firma_id, Aktif=True).count()
    yeni_musteri = 0

    # Randevu istatistikleri (müşteri başına randevu sayısı)
    randevu_q = db.session.query(Randevu.MusteriID, db.func.count(Randevu.RandevuID).label('adet')) 
    randevu_q = randevu_q.filter(Randevu.FirmaID == firma_id, Randevu.MusteriID.isnot(None))
    randevu_q = randevu_q.group_by(Randevu.MusteriID)
    musteri_id_to_randevu_adet = {mid: adet for mid, adet in randevu_q.all()}

    # Müşterileri birleştir (ad+soyad+telefon)
    def _norm_name(v):
        return (v or '').strip().lower()
    def _norm_phone(v):
        v = ''.join(ch for ch in (v or '') if ch.isdigit())
        return v[-10:] if len(v) >= 10 else v

    merged = {}
    for m in musteriler:
        k = (_norm_name(m.MusteriAdi), _norm_name(m.MusteriSoyadi), _norm_phone(m.Telefon))
        if k not in merged:
            merged[k] = {
                'id': m.MusteriID,
                'ad': m.MusteriAdi,
                'soyad': m.MusteriSoyadi,
                'telefon': m.Telefon or '',
                'email': m.Email or '',
                'aktif': bool(m.Aktif),
                'kategori': m.kategori.KategoriAdi if m.kategori else None,
                'olusturma': m.OlusturmaTarihi,
                'randevu_sayisi': musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            }
        else:
            it = merged[k]
            it['randevu_sayisi'] += musteri_id_to_randevu_adet.get(m.MusteriID, 0)
            if not it['email'] and m.Email:
                it['email'] = m.Email
            if not it['kategori'] and m.kategori:
                it['kategori'] = m.kategori.KategoriAdi
            it['aktif'] = it['aktif'] or bool(m.Aktif)
            if it['olusturma'] is None or (m.OlusturmaTarihi and m.OlusturmaTarihi < it['olusturma']):
                it['olusturma'] = m.OlusturmaTarihi

    merged_rows = list(merged.values())

    # En çok randevusu olan 10 müşteri (birleştirilmiş verilerden)
    top_musteriler = sorted(merged_rows, key=lambda x: x['randevu_sayisi'], reverse=True)[:10]

    # Export işlemleri
    if format_tip in ['csv', 'excel', 'pdf']:
        # Çıktı alma logla
        # try:
        #     log_user_action('VIEW', 'Rapor', detail=f"Müşteri raporu {format_tip.upper()} indirildi")
        # except Exception:
        #     pass
        
        if format_tip == 'csv':
            # CSV Export
            output = StringIO()
            writer = csv.writer(output, delimiter=';')
            writer.writerow(['MusteriID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'OlusturmaTarihi', 'RandevuSayisi'])
            for r in merged_rows:
                # Telefon numarasını Excel'de metin olarak tanıması için +90'dan sonra boşluk ekle
                telefon = r['telefon'] or ''
                if telefon and telefon.startswith('+90'):
                    telefon = telefon.replace('+90', '+90 ')  # +90'dan sonra boşluk ekle
                writer.writerow([
                    r['id'], r['ad'], r['soyad'], telefon, r['email'], 'Evet' if r['aktif'] else 'Hayır', r['kategori'] or '', (r['olusturma'].strftime('%Y-%m-%d %H:%M') if r['olusturma'] else ''), r['randevu_sayisi']
                ])
            output.seek(0)
            filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = output.getvalue().encode('utf-8-sig')
            return send_file(BytesIO(data), mimetype='text/csv; charset=utf-8', as_attachment=True, download_name=filename)
        
        elif format_tip == 'excel':
            # Excel Export
            wb = Workbook()
            ws = wb.active
            ws.title = "Müşteri Raporu"
            
            # Başlık satırı
            headers = ['Müşteri ID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'Oluşturma Tarihi', 'Randevu Sayısı']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            
            # Veri satırları
            for row, r in enumerate(merged_rows, 2):
                telefon = r['telefon'] or ''
                if telefon and telefon.startswith('+90'):
                    telefon = telefon.replace('+90', '+90 ')
                
                ws.cell(row=row, column=1, value=r['id'])
                ws.cell(row=row, column=2, value=r['ad'])
                ws.cell(row=row, column=3, value=r['soyad'])
                ws.cell(row=row, column=4, value=telefon)
                ws.cell(row=row, column=5, value=r['email'])
                ws.cell(row=row, column=6, value='Evet' if r['aktif'] else 'Hayır')
                ws.cell(row=row, column=7, value=r['kategori'] or '')
                ws.cell(row=row, column=8, value=r['olusturma'].strftime('%Y-%m-%d %H:%M') if r['olusturma'] else '')
                ws.cell(row=row, column=9, value=r['randevu_sayisi'])
            
            # Sütun genişliklerini ayarla
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Excel dosyasını kaydet
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        
        elif format_tip == 'pdf':
            # PDF Export
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            
            # Türkçe font desteği
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
                turkish_font = 'DejaVuSans'
                turkish_font_bold = 'DejaVuSans-Bold'
            except:
                try:
                    pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
                    turkish_font = 'DejaVuSans'
                    turkish_font_bold = 'DejaVuSans-Bold'
                except:
                    turkish_font = 'Helvetica'
                    turkish_font_bold = 'Helvetica-Bold'
            
            # Stil tanımları
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
            
            # Başlık
            title = Paragraph("Müşteri Raporu", title_style)
            
            # Özet bilgiler
            summary_data = [
                ['Toplam Müşteri', str(toplam_musteri)],
                ['Aktif Müşteri', str(aktif_musteri)],
                ['Yeni Müşteri', str(yeni_musteri)]
            ]
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # Tablo verileri
            table_data = [['Müşteri ID', 'Ad', 'Soyad', 'Telefon', 'Email', 'Aktif', 'Kategori', 'Randevu Sayısı']]
            
            for r in merged_rows[:50]:  # İlk 50 kayıt
                telefon = r['telefon'] or ''
                if telefon and telefon.startswith('+90'):
                    telefon = telefon.replace('+90', '+90 ')
                
                table_data.append([
                    str(r['id']),
                    r['ad'],
                    r['soyad'],
                    telefon,
                    r['email'],
                    'Evet' if r['aktif'] else 'Hayır',
                    r['kategori'] or '',
                    str(r['randevu_sayisi'])
                ])
            
            # Tablo oluştur
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), turkish_font),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            # PDF oluştur
            elements = [title, Spacer(1, 12), summary_table, Spacer(1, 12), table]
            doc.build(elements)
            buffer.seek(0)
            
            filename = f"musteri_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )

    # Kategoriler dropdown için
    kategoriler = MusteriKategori.query.filter_by(FirmaID=firma_id).order_by(MusteriKategori.KategoriAdi).all()
    
    # Şehir ve ilçe seçenekleri
    sehirler = db.session.query(Musteri.Sehir).filter(
        Musteri.FirmaID == firma_id,
        Musteri.Sehir.isnot(None),
        Musteri.Sehir != ''
    ).distinct().order_by(Musteri.Sehir).all()
    
    
    # Plaka kodlarını şehir isimlerine dönüştür ve benzersiz hale getir
    sehir_listesi = []
    for s in sehirler:
        plaka = s[0]
        sehir_adi = plaka_to_sehir.get(plaka, plaka)  # Eğer plaka kodunda yoksa orijinal değeri kullan
        if sehir_adi not in sehir_listesi:
            sehir_listesi.append(sehir_adi)
    
    sehir_listesi.sort()  # Alfabetik sırala
    
    ilceler = db.session.query(Musteri.Ilce).filter(
        Musteri.FirmaID == firma_id,
        Musteri.Ilce.isnot(None),
        Musteri.Ilce != ''
    ).distinct().order_by(Musteri.Ilce).all()
    ilce_listesi = [i[0] for i in ilceler]
    
    # Grafik verileri
    # Cinsiyet dağılımı
    gender_stats = db.session.query(Musteri.Cinsiyet, db.func.count(Musteri.MusteriID)).filter(
        Musteri.FirmaID == firma_id
    ).group_by(Musteri.Cinsiyet).all()
    gender_data = {gender: count for gender, count in gender_stats if gender}
    
    # Yaş dağılımı (yaş grupları)
    age_groups = {
        '0-18': 0, '19-25': 0, '26-35': 0, '36-45': 0, '46-55': 0, '56-65': 0, '65+': 0
    }
    age_stats = db.session.query(Musteri.Yas).filter(
        Musteri.FirmaID == firma_id, Musteri.Yas.isnot(None)
    ).all()
    for (yas,) in age_stats:
        if yas <= 18:
            age_groups['0-18'] += 1
        elif yas <= 25:
            age_groups['19-25'] += 1
        elif yas <= 35:
            age_groups['26-35'] += 1
        elif yas <= 45:
            age_groups['36-45'] += 1
        elif yas <= 55:
            age_groups['46-55'] += 1
        elif yas <= 65:
            age_groups['56-65'] += 1
        else:
            age_groups['65+'] += 1
    
    # Kategori dağılımı
    category_stats = db.session.query(
        MusteriKategori.KategoriAdi, db.func.count(Musteri.MusteriID)
    ).join(Musteri, Musteri.KategoriID == MusteriKategori.KategoriID).filter(
        Musteri.FirmaID == firma_id
    ).group_by(MusteriKategori.KategoriAdi).all()
    category_data = {kategori: count for kategori, count in category_stats}
    
    # Şehir dağılımı (top 10)
    city_stats = db.session.query(
        Musteri.Sehir, db.func.count(Musteri.MusteriID)
    ).filter(
        Musteri.FirmaID == firma_id, Musteri.Sehir.isnot(None), Musteri.Sehir != ''
    ).group_by(Musteri.Sehir).order_by(db.func.count(Musteri.MusteriID).desc()).limit(10).all()
    city_data = {sehir: count for sehir, count in city_stats}

    # Görüntülenecek satırlar için zenginleştirme
    rows = []
    for r in merged_rows:
        rows.append({
            'id': r['id'],
            'ad': r['ad'],
            'soyad': r['soyad'],
            'tam_ad': f"{r['ad']} {r['soyad']}".strip(),
            'telefon': r['telefon'],
            'email': r['email'],
            'aktif': r['aktif'],
            'kategori': r['kategori'],
            'olusturma': r['olusturma'],
            'randevu_sayisi': r['randevu_sayisi']
        })

    # Zaman serisi analizi - Aylık müşteri artışı
    # Sayfalama
    SAYFA_BOYUTU = 50
    sayfa = request.args.get('sayfa', 1, type=int)
    sayfa = max(1, sayfa)
    toplam_kayit = len(rows)
    toplam_sayfa = max(1, (toplam_kayit + SAYFA_BOYUTU - 1) // SAYFA_BOYUTU)
    sayfa = min(sayfa, toplam_sayfa)
    start = (sayfa - 1) * SAYFA_BOYUTU
    sayfa_rows = rows[start:start + SAYFA_BOYUTU]

    # Zaman serisi analizi - Aylık müşteri artışı
    monthly_data = {}
    for m in musteriler:
        if m.OlusturmaTarihi:
            month_key = m.OlusturmaTarihi.strftime('%Y-%m')
            monthly_data[month_key] = monthly_data.get(month_key, 0) + 1
    
    # Zaman serisi analizi - Haftalık müşteri artışı (son 12 hafta)
    weekly_data = {}
    today = datetime.now().date()
    
    # Son 12 hafta için haftalık veriler
    for i in range(12):
        week_start = today - timedelta(weeks=i+1)
        week_end = today - timedelta(weeks=i)
        week_key = f"{week_start.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}"
        weekly_data[week_key] = 0
    
    for m in musteriler:
        if m.OlusturmaTarihi:
            m_date = m.OlusturmaTarihi.date()
            for i in range(12):
                week_start = today - timedelta(weeks=i+1)
                week_end = today - timedelta(weeks=i)
                if week_start <= m_date < week_end:
                    week_key = f"{week_start.strftime('%Y-%m-%d')} - {week_end.strftime('%Y-%m-%d')}"
                    weekly_data[week_key] = weekly_data.get(week_key, 0) + 1
                    break
    
    # Randevu trendleri - Müşteri başına randevu sayısı analizi
    # Müşteri başına randevu sayısı dağılımı
    randevu_sayisi_dagilimi = defaultdict(int)
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        randevu_sayisi_dagilimi[randevu_sayisi] += 1
    
    # En çok randevu alan müşteriler (top 10)
    en_cok_randevu_alan = []
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        if randevu_sayisi > 0:
            en_cok_randevu_alan.append({
                'musteri_adi': f"{m.MusteriAdi} {m.MusteriSoyadi}",
                'randevu_sayisi': randevu_sayisi
            })
    
    # Randevu sayısına göre sırala (azalan)
    en_cok_randevu_alan.sort(key=lambda x: x['randevu_sayisi'], reverse=True)
    en_cok_randevu_alan = en_cok_randevu_alan[:10]
    
    # Randevu sıklığı analizi (0, 1, 2-5, 6-10, 10+ randevu)
    randevu_siklik_dagilimi = {
        '0 Randevu': 0,
        '1 Randevu': 0,
        '2-5 Randevu': 0,
        '6-10 Randevu': 0,
        '10+ Randevu': 0
    }
    
    for m in musteriler:
        randevu_sayisi = musteri_id_to_randevu_adet.get(m.MusteriID, 0)
        if randevu_sayisi == 0:
            randevu_siklik_dagilimi['0 Randevu'] += 1
        elif randevu_sayisi == 1:
            randevu_siklik_dagilimi['1 Randevu'] += 1
        elif 2 <= randevu_sayisi <= 5:
            randevu_siklik_dagilimi['2-5 Randevu'] += 1
        elif 6 <= randevu_sayisi <= 10:
            randevu_siklik_dagilimi['6-10 Randevu'] += 1
        else:
            randevu_siklik_dagilimi['10+ Randevu'] += 1
    
    return render_template(
        'rapor_musteriler.html',
        rows=sayfa_rows,
        toplam_kayit=toplam_kayit,
        sayfa=sayfa,
        toplam_sayfa=toplam_sayfa,
        toplam_musteri=toplam_musteri,
        aktif_musteri=aktif_musteri,
        yeni_musteri=yeni_musteri,
        top_musteriler=top_musteriler,
        kategoriler=kategoriler,
        sehir_listesi=sehir_listesi,
        ilce_listesi=ilce_listesi,
        gender_data=gender_data,
        age_groups=age_groups,
        category_data=category_data,
        city_data=city_data,
        monthly_data=monthly_data,
        weekly_data=weekly_data,
        randevu_sayisi_dagilimi=dict(randevu_sayisi_dagilimi),
        en_cok_randevu_alan=en_cok_randevu_alan,
        randevu_siklik_dagilimi=randevu_siklik_dagilimi,
        filtreler={
            'kategori_id': kategori_id or '',
            'aktif': sadece_aktif,
            'iletisim_var': iletisim_var or '',
            'yas_min': yas_min or '',
            'yas_max': yas_max or '',
            'cinsiyet': cinsiyet or '',
            'dogum_tarihi': dogum_tarihi or '',
            'sehir': sehir or '',
            'ilce': ilce or ''
        }
    )

@musteri_bp.route('/rapor/musteri-detay-modal/<int:musteri_id>')
@login_required
def musteri_detay_modal(musteri_id):
    """Müşteri detay raporu modal içeriği"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('auth.login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        return '<div class="alert alert-danger">Müşteri bulunamadı.</div>'
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Aylık randevu dağılımı
    aylik_randevu = defaultdict(int)
    for randevu in randevular:
        if randevu.RandevuTarihi:
            ay_key = randevu.RandevuTarihi.strftime('%Y-%m')
            aylik_randevu[ay_key] += 1
    
    # Defter dağılımı
    defter_dagilimi = defaultdict(int)
    for randevu in randevular:
        if randevu.DefterID:
            defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
            if defter:
                defter_dagilimi[defter.DefterAdi] += 1
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    # Aktivite timeline'ı getir
    try:
        from app.routes.aktivite import get_customer_activities
        aktiviteler = get_customer_activities(musteri_id, limit=50)
    except Exception as e:
        print(f"Aktivite yükleme hatası: {e}")
        aktiviteler = []  # Hata durumunda boş liste
    
    return render_template('musteri_detay_modal.html',
                         musteri=musteri,
                         randevular=randevular,
                         toplam_randevu=toplam_randevu,
                         tamamlanan_randevu=tamamlanan_randevu,
                         iptal_randevu=iptal_randevu,
                         bekleyen_randevu=bekleyen_randevu,
                         aylik_randevu=dict(aylik_randevu),
                         defter_dagilimi=dict(defter_dagilimi),
                         sehir_adi=sehir_adi,
                         aktiviteler=aktiviteler)

@musteri_bp.route('/rapor/musteri-detay/<int:musteri_id>/pdf')
@login_required
def musteri_detay_pdf(musteri_id):
    """Müşteri detay raporu PDF"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('auth.login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('musteri.rapor_musteriler'))
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    # PDF oluştur
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Türkçe font desteği için DejaVu Sans fontunu kaydet
    try:
        # Windows sistem fontları
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/dejavu-sans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/dejavu-sans-bold.ttf'))
        turkish_font = 'DejaVuSans'
        turkish_font_bold = 'DejaVuSans-Bold'
    except:
        try:
            # Alternatif font yolları
            pdfmetrics.registerFont(TTFont('DejaVuSans', 'C:/Windows/Fonts/arial.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
            turkish_font = 'DejaVuSans'
            turkish_font_bold = 'DejaVuSans-Bold'
        except:
            # Varsayılan font
            turkish_font = 'Helvetica'
            turkish_font_bold = 'Helvetica-Bold'
    
    # Stil tanımları
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, fontName=turkish_font_bold)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceAfter=12, fontName=turkish_font_bold)
    
    # İçerik oluştur
    story = []
    
    # Başlık
    story.append(Paragraph("Müşteri Detay Raporu", title_style))
    story.append(Spacer(1, 12))
    
    # Müşteri bilgileri
    story.append(Paragraph("Müşteri Bilgileri", heading_style))
    
    musteri_data = [
        ['Ad Soyad:', f"{musteri.MusteriAdi} {musteri.MusteriSoyadi}"],
        ['Telefon:', musteri.Telefon or 'Belirtilmemiş'],
        ['E-posta:', musteri.Email or 'Belirtilmemiş'],
        ['Yaş:', str(musteri.Yas) if musteri.Yas else 'Belirtilmemiş'],
        ['Cinsiyet:', musteri.Cinsiyet or 'Belirtilmemiş'],
        ['Şehir:', sehir_adi],
        ['İlçe:', musteri.Ilce or 'Belirtilmemiş'],
        ['Doğum Tarihi:', musteri.DogumTarihi.strftime('%d.%m.%Y') if musteri.DogumTarihi else 'Belirtilmemiş']
    ]
    
    if musteri.Adres:
        musteri_data.append(['Adres:', musteri.Adres])
    if musteri.Notlar:
        musteri_data.append(['Notlar:', musteri.Notlar])
    
    musteri_table = Table(musteri_data, colWidths=[2*inch, 4*inch])
    musteri_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), turkish_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(musteri_table)
    story.append(Spacer(1, 20))
    
    # Randevu istatistikleri
    story.append(Paragraph("Randevu İstatistikleri", heading_style))
    
    stats_data = [
        ['Toplam Randevu:', str(toplam_randevu)],
        ['Tamamlanan:', str(tamamlanan_randevu)],
        ['Beklemede:', str(bekleyen_randevu)],
        ['İptal:', str(iptal_randevu)]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), turkish_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Randevu geçmişi
    if randevular:
        story.append(Paragraph("Randevu Geçmişi", heading_style))
        
        randevu_data = [['Tarih', 'Saat', 'Defter', 'Durum', 'Notlar']]
        
        for randevu in randevular:
            defter_adi = 'Bilinmeyen'
            if randevu.DefterID:
                defter = RandevuDefterAyar.query.filter_by(AyarID=randevu.DefterID).first()
                if defter:
                    defter_adi = defter.DefterAdi
            
            randevu_data.append([
                randevu.RandevuTarihi.strftime('%d.%m.%Y') if randevu.RandevuTarihi else '-',
                randevu.RandevuTarihi.strftime('%H:%M') if randevu.RandevuTarihi else '-',
                defter_adi,
                randevu.Durum,
                randevu.RandevuAciklamasi or '-'
            ])
        
        randevu_table = Table(randevu_data, colWidths=[1*inch, 0.8*inch, 1.2*inch, 1*inch, 2*inch])
        randevu_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), turkish_font_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), turkish_font),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(randevu_table)
    
    doc.build(story)
    buffer.seek(0)
    
    filename = f"musteri_detay_raporu_{musteri.MusteriAdi}_{musteri.MusteriSoyadi}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@musteri_bp.route('/rapor/musteri-detay/<int:musteri_id>')
@login_required
def musteri_detay_raporu(musteri_id):
    """Müşteri detay raporu"""
    firma_id = session.get('firma_id')
    if not firma_id:
        return redirect(url_for('auth.login'))
    
    # Müşteri bilgilerini getir
    musteri = Musteri.query.filter_by(MusteriID=musteri_id, FirmaID=firma_id).first()
    if not musteri:
        flash('Müşteri bulunamadı.', 'error')
        return redirect(url_for('musteri.rapor_musteriler'))
    
    # Plaka kodlarını şehir isimlerine dönüştür - Global değişken kullanılıyor
    # plaka_to_sehir = {...} 
    
    # Müşteri randevularını getir
    randevular = Randevu.query.filter_by(
        MusteriID=musteri_id,
        FirmaID=firma_id
    ).order_by(Randevu.RandevuTarihi.desc()).all()
    
    # Randevu istatistikleri
    toplam_randevu = len(randevular)
    tamamlanan_randevu = len([r for r in randevular if r.Durum == 'Tamamlandı'])
    iptal_randevu = len([r for r in randevular if r.Durum == 'İptal'])
    bekleyen_randevu = len([r for r in randevular if r.Durum == 'Beklemede'])
    
    # Son randevu tarihi
    son_randevu = randevular[0] if randevular else None
    
    # Aylık randevu dağılımı (son 12 ay)
    aylik_randevu = defaultdict(int)
    for r in randevular:
        if r.RandevuTarihi:
            ay_key = r.RandevuTarihi.strftime('%Y-%m')
            aylik_randevu[ay_key] += 1
    
    # Randevu defteri dağılımı
    defter_dagilimi = defaultdict(int)
    for r in randevular:
        if r.DefterID:
            # DefterID'den defter adını al
            defter = RandevuDefterAyar.query.filter_by(AyarID=r.DefterID).first()
            if defter:
                defter_dagilimi[defter.DefterAdi] += 1
            else:
                defter_dagilimi['Bilinmeyen Defter'] += 1
    
    # Şehir bilgisini dönüştür
    sehir_adi = plaka_to_sehir.get(musteri.Sehir, musteri.Sehir) if musteri.Sehir else 'Belirtilmemiş'
    
    return render_template('musteri_detay_raporu.html',
                         musteri=musteri,
                         randevular=randevular,
                         toplam_randevu=toplam_randevu,
                         tamamlanan_randevu=tamamlanan_randevu,
                         iptal_randevu=iptal_randevu,
                         bekleyen_randevu=bekleyen_randevu,
                         son_randevu=son_randevu,
                         aylik_randevu=dict(aylik_randevu),
                         defter_dagilimi=dict(defter_dagilimi),
                         sehir_adi=sehir_adi)
