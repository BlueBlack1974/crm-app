# Kullanılmayan Dosyalar Listesi

## Tek Seferlik Migration Scriptleri (Kullanıldı, Artık Gerekli Değil)
- `fix_mysql_kullaniciloglari.py` - MySQL KullaniciLoglari tablosu düzeltme scripti
- `add_durumlar.py` - Durum ekleme scripti
- `add_missing_durumlar.py` - Eksik durumları ekleme scripti
- `add_randevu_columns.py` - Randevu kolonları ekleme scripti

## Test/Development Scriptleri
- `simple_create.py` - Basit tablo oluşturma test scripti
- `create_tables.py` - Tablo oluşturma scripti (basit versiyon)
- `simple_server.py` - Test Flask server

## Favicon Oluşturma Scriptleri (Tek Seferlik)
- `create_favicon_from_png.py` - PNG'den favicon oluşturma
- `create_original_favicon.py` - Orijinal favicon oluşturma
- `create_transparent_favicon.py` - Şeffaf favicon oluşturma

## Eski/Geçersiz Dosyalar
- `crm.db` - SQLite database (artık MySQL/MSSQL kullanılıyor)
- `taticimgCRMTIA-Logo.png` - Yanlış isimli dosya (typo: "tatic" yerine "static" olmalı)

## Translation Backup Dosyaları
- `translations/tr/LC_MESSAGES/messages_backup.po`
- `translations/tr/LC_MESSAGES/messages_clean.po`
- `translations/tr/LC_MESSAGES/messages_new.po`
- `translations/tr/LC_MESSAGES/messages_temp.po`

## Kullanılmayan Dizinler
- `babel/` - Eski babel çeviri dizini (artık `translations/` kullanılıyor)

## Güvenlik Riskleri (Hardcoded Şifreler)
- `create_admin_user.py` - Admin kullanıcı oluşturma scripti (hardcoded şifreler içeriyor, veritabanı scriptlerinde zaten mevcut) ✅ **SİLİNDİ**
- `create_missing_tables.py` - Eksik tabloları oluşturma scripti (hardcoded şifreler içeriyor, tablolar zaten veritabanı scriptlerinde mevcut) ✅ **SİLİNDİ**
- `create_mysql_database.py` - MySQL veritabanı oluşturma scripti (hardcoded şifreler içeriyor, kullanıcılar SQL scriptini direkt çalıştırabilir) ✅ **SİLİNDİ**
- `setup_mysql_settings.py` - MySQL ayarlarını SistemAyarlar'a kaydetme scripti (hardcoded şifreler içeriyor, web arayüzünden yapılabilir) ✅ **SİLİNDİ**

## Gereksiz Tablo Oluşturma Scriptleri
- `create_sistem_ayarlar_table.py` - SistemAyarlar tablosu oluşturma scripti (tablo zaten veritabanı scriptlerinde mevcut) ✅ **SİLİNDİ**

