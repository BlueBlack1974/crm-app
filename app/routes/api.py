from flask import Blueprint, jsonify, request, session
from app.extensions import db, csrf
from app.models import Bildirim, Todo, TodoDurum, AktifOturum, Kullanici, Musteri, Aktivite
from sqlalchemy import or_
from app.utils.decorators import login_required
from datetime import datetime
import json

api_bp = Blueprint('api', __name__)

# Not: /api/countries, /api/states, /api/cities endpoint'leri app.py'de tanımlı
# Burada tanımlanmışsa çakışma olur, bu yüzden kaldırıldı

# ── Türkiye 81 il & ilçe verileri (dış API bağımlılığı yok) ──────────────────
TR_ILLER = [
    {"id":"01","name":"Adana"},{"id":"02","name":"Adıyaman"},{"id":"03","name":"Afyonkarahisar"},
    {"id":"04","name":"Ağrı"},{"id":"05","name":"Amasya"},{"id":"06","name":"Ankara"},
    {"id":"07","name":"Antalya"},{"id":"08","name":"Artvin"},{"id":"09","name":"Aydın"},
    {"id":"10","name":"Balıkesir"},{"id":"11","name":"Bilecik"},{"id":"12","name":"Bingöl"},
    {"id":"13","name":"Bitlis"},{"id":"14","name":"Bolu"},{"id":"15","name":"Burdur"},
    {"id":"16","name":"Bursa"},{"id":"17","name":"Çanakkale"},{"id":"18","name":"Çankırı"},
    {"id":"19","name":"Çorum"},{"id":"20","name":"Denizli"},{"id":"21","name":"Diyarbakır"},
    {"id":"22","name":"Edirne"},{"id":"23","name":"Elazığ"},{"id":"24","name":"Erzincan"},
    {"id":"25","name":"Erzurum"},{"id":"26","name":"Eskişehir"},{"id":"27","name":"Gaziantep"},
    {"id":"28","name":"Giresun"},{"id":"29","name":"Gümüşhane"},{"id":"30","name":"Hakkari"},
    {"id":"31","name":"Hatay"},{"id":"32","name":"Isparta"},{"id":"33","name":"Mersin"},
    {"id":"34","name":"İstanbul"},{"id":"35","name":"İzmir"},{"id":"36","name":"Kars"},
    {"id":"37","name":"Kastamonu"},{"id":"38","name":"Kayseri"},{"id":"39","name":"Kırklareli"},
    {"id":"40","name":"Kırşehir"},{"id":"41","name":"Kocaeli"},{"id":"42","name":"Konya"},
    {"id":"43","name":"Kütahya"},{"id":"44","name":"Malatya"},{"id":"45","name":"Manisa"},
    {"id":"46","name":"Kahramanmaraş"},{"id":"47","name":"Mardin"},{"id":"48","name":"Muğla"},
    {"id":"49","name":"Muş"},{"id":"50","name":"Nevşehir"},{"id":"51","name":"Niğde"},
    {"id":"52","name":"Ordu"},{"id":"53","name":"Rize"},{"id":"54","name":"Sakarya"},
    {"id":"55","name":"Samsun"},{"id":"56","name":"Siirt"},{"id":"57","name":"Sinop"},
    {"id":"58","name":"Sivas"},{"id":"59","name":"Tekirdağ"},{"id":"60","name":"Tokat"},
    {"id":"61","name":"Trabzon"},{"id":"62","name":"Tunceli"},{"id":"63","name":"Şanlıurfa"},
    {"id":"64","name":"Uşak"},{"id":"65","name":"Van"},{"id":"66","name":"Yozgat"},
    {"id":"67","name":"Zonguldak"},{"id":"68","name":"Aksaray"},{"id":"69","name":"Bayburt"},
    {"id":"70","name":"Karaman"},{"id":"71","name":"Kırıkkale"},{"id":"72","name":"Batman"},
    {"id":"73","name":"Şırnak"},{"id":"74","name":"Bartın"},{"id":"75","name":"Ardahan"},
    {"id":"76","name":"Iğdır"},{"id":"77","name":"Yalova"},{"id":"78","name":"Karabük"},
    {"id":"79","name":"Kilis"},{"id":"80","name":"Osmaniye"},{"id":"81","name":"Düzce"},
]

TR_ILCELER = {
    "01": ["Aladağ","Ceyhan","Çukurova","Feke","İmamoğlu","Karaisalı","Karataş","Kozan","Pozantı","Saimbeyli","Sarıçam","Seyhan","Tufanbeyli","Yumurtalık","Yüreğir"],
    "02": ["Besni","Çelikhan","Gerger","Gölbaşı","Kahta","Merkez","Samsat","Sincik","Tut"],
    "03": ["Başmakçı","Bayat","Bolvadin","Çay","Çobanlar","Dazkırı","Dinar","Emirdağ","Evciler","Hocalar","İhsaniye","İscehisar","Kızılören","Merkez","Sandıklı","Sinanpaşa","Sultandağı","Şuhut"],
    "04": ["Diyadin","Doğubayazıt","Eleşkirt","Hamur","Merkez","Patnos","Taşlıçay","Tutak"],
    "05": ["Göynücek","Gümüşhacıköy","Hamamözü","Merkez","Merzifon","Suluova","Taşova"],
    "06": ["Akyurt","Altındağ","Ayaş","Bala","Beypazarı","Çamlıdere","Çankaya","Çubuk","Elmadağ","Etimesgut","Evren","Gölbaşı","Güdül","Haymana","Kahramankazan","Kalecik","Keçiören","Kızılcahamam","Mamak","Nallıhan","Polatlı","Pursaklar","Sincan","Şereflikoçhisar","Yenimahalle"],
    "07": ["Akseki","Aksu","Alanya","Demre","Döşemealtı","Elmalı","Finike","Gazipaşa","Gündoğmuş","İbradı","Kaş","Kemer","Kepez","Konyaaltı","Korkuteli","Kumluca","Manavgat","Muratpaşa","Serik"],
    "08": ["Ardanuç","Arhavi","Borçka","Hopa","Kemalpaşa","Merkez","Murgul","Şavşat","Yusufeli"],
    "09": ["Bozdoğan","Buharkent","Çine","Didim","Efeler","Germencik","İncirliova","Karacasu","Karpuzlu","Koçarlı","Köşk","Kuşadası","Kuyucak","Merkez","Nazilli","Söke","Sultanhisar","Yenipazar"],
    "10": ["Altıeylül","Ayvalık","Balya","Bandırma","Bigadiç","Burhaniye","Dursunbey","Edremit","Erdek","Gömeç","Gönen","Havran","İvrindi","Karesi","Kepsut","Manyas","Marmara","Savaştepe","Sındırgı","Susurluk"],
    "11": ["Bozüyük","Gölpazarı","İnhisar","Merkez","Osmaneli","Pazaryeri","Söğüt","Yenipazar"],
    "12": ["Adaklı","Genç","Karlıova","Kiğı","Merkez","Solhan","Yayladere","Yedisu"],
    "13": ["Adilcevaz","Ahlat","Güroymak","Hizan","Merkez","Mutki","Tatvan"],
    "14": ["Dörtdivan","Gerede","Göynük","Kıbrıscık","Mengen","Merkez","Mudurnu","Seben","Yeniçağa"],
    "15": ["Ağlasun","Altınyayla","Bucak","Çavdır","Çeltikçi","Gölhisar","Karamanlı","Kemer","Merkez","Tefenni","Yeşilova"],
    "16": ["Büyükorhan","Gemlik","Gürsu","Harmancık","İnegöl","İznik","Karacabey","Keles","Kestel","Mudanya","Mustafakemalpaşa","Nilüfer","Orhaneli","Orhangazi","Osmangazi","Yenişehir"],
    "17": ["Ayvacık","Bayramiç","Biga","Bozcaada","Çan","Eceabat","Ezine","Gelibolu","Gökçeada","Lapseki","Merkez","Yenice"],
    "18": ["Atkaracalar","Bayramören","Çerkeş","Eldivan","Ilgaz","Khanönü","Korgun","Kurşunlu","Merkez","Orta","Şabanözü","Yapraklı"],
    "19": ["Alaca","Bayat","Boğazkale","Dodurga","İskilip","Kargı","Laçin","Mecitözü","Merkez","Oğuzlar","Ortaköy","Osmancık","Sungurlu","Uğurludağ"],
    "20": ["Acıpayam","Babadağ","Baklan","Bekilli","Beyağaç","Bozkurt","Buldan","Çal","Çameli","Çardak","Çivril","Güney","Honaz","Kale","Merkezefendi","Pamukkale","Sarayköy","Serinhisar","Tavas"],
    "21": ["Bağlar","Bismil","Çermik","Çınar","Çüngüş","Dicle","Eğil","Ergani","Hani","Hazro","Kayapınar","Kocaköy","Kulp","Lice","Silvan","Sur","Yenişehir"],
    "22": ["Enez","Havsa","İpsala","Keşan","Lalapaşa","Meriç","Merkez","Süloğlu","Uzunköprü"],
    "23": ["Ağın","Alacakaya","Arıcak","Baskil","Karakoçan","Keban","Kovancılar","Maden","Merkez","Palu","Sivrice"],
    "24": ["Çayırlı","İliç","Kemah","Kemaliye","Merkez","Otlukbeli","Refahiye","Tercan","Üzümlü"],
    "25": ["Aşkale","Aziziye","Çat","Hınıs","Horasan","İspir","Karaçoban","Karayazı","Köprüköy","Merkez","Narman","Oltu","Olur","Palandöken","Pazaryolu","Şenkaya","Tekman","Tortum","Uzundere","Yakutiye"],
    "26": ["Alpu","Beylikova","Çifteler","Günyüzü","Han","İnönü","Mahmudiye","Mihalgazi","Mihalıççık","Merkez","Odunpazarı","Sarıcakaya","Seyitgazi","Sivrihisar","Tepebaşı"],
    "27": ["Araban","İslahiye","Karkamış","Merkez","Nizip","Nurdağı","Oğuzeli","Şahinbey","Şehitkamil","Yavuzeli"],
    "28": ["Alucra","Bulancak","Çamoluk","Çanakçı","Dereli","Doğankent","Espiye","Eynesil","Görele","Güce","Keşap","Merkez","Piraziz","Şebinkarahisar","Tirebolu","Yağlıdere"],
    "29": ["Kelkit","Köse","Kürtün","Merkez","Şiran","Torul"],
    "30": ["Çukurca","Derecik","Merkez","Şemdinli","Yüksekova"],
    "31": ["Altınözü","Antakya","Arsuz","Belen","Defne","Dörtyol","Erzin","Hassa","İskenderun","Kırıkhan","Kumlu","Payas","Reyhanlı","Samandağ","Yayladağı"],
    "32": ["Aksu","Atabey","Eğirdir","Gelendost","Gönen","Keçiborlu","Merkez","Senirkent","Sütçüler","Şarkikaraağaç","Uluborlu","Yalvaç","Yenişarbademli"],
    "33": ["Akdeniz","Anamur","Aydıncık","Bozyazı","Çamlıyayla","Erdemli","Gülnar","Mezitli","Mut","Silifke","Tarsus","Toroslar","Yenişehir"],
    "34": ["Adalar","Arnavutköy","Ataşehir","Avcılar","Bağcılar","Bahçelievler","Bakırköy","Başakşehir","Bayrampaşa","Beşiktaş","Beykoz","Beylikdüzü","Beyoğlu","Büyükçekmece","Çatalca","Çekmeköy","Esenler","Esenyurt","Eyüpsultan","Fatih","Gaziosmanpaşa","Güngören","Kadıköy","Kağıthane","Kartal","Küçükçekmece","Maltepe","Pendik","Sancaktepe","Sarıyer","Silivri","Sultanbeyli","Sultangazi","Şile","Şişli","Tuzla","Ümraniye","Üsküdar","Zeytinburnu"],
    "35": ["Aliağa","Balçova","Bayındır","Bayraklı","Bergama","Beydağ","Bornova","Buca","Çeşme","Çiğli","Dikili","Foça","Gaziemir","Güzelbahçe","Karabağlar","Karaburun","Karşıyaka","Kemalpaşa","Kınık","Kiraz","Konak","Menderes","Menemen","Narlıdere","Ödemiş","Seferihisar","Selçuk","Tire","Torbalı","Urla"],
    "36": ["Akyaka","Arpaçay","Digor","Kağızman","Merkez","Sarıkamış","Selim","Susuz"],
    "37": ["Abana","Ağlı","Araç","Azdavay","Bozkurt","Cide","Çatalzeytin","Daday","Devrekani","Doğanyurt","Hanönü","İhsangazi","İnebolu","Küre","Merkez","Pınarbaşı","Seydiler","Şenpazar","Taşköprü","Tosya"],
    "38": ["Akkışla","Bünyan","Develi","Felahiye","Hacılar","İncesu","Kocasinan","Melikgazi","Özvatan","Pınarbaşı","Sarıoğlan","Sarız","Talas","Tomarza","Yahyalı","Yeşilhisar"],
    "39": ["Babaeski","Demirköy","Kofçaz","Lüleburgaz","Merkez","Pehlivanköy","Pınarhisar","Vize"],
    "40": ["Akçakent","Akpınar","Boztepe","Çiçekdağı","Kaman","Merkez","Mucur","Savcılı"],
    "41": ["Başiskele","Çayırova","Darıca","Derince","Dilovası","Gebze","Gölcük","İzmit","Kandıra","Karamürsel","Kartepe","Körfez"],
    "42": ["Ahırlı","Akören","Akşehir","Altınekin","Beyşehir","Bozkır","Cihanbeyli","Çeltik","Çumra","Derbent","Derebucak","Doğanhisar","Emirgazi","Ereğli","Güneysınır","Hadim","Halkapınar","Hüyük","Ilgın","Kadınhanı","Karapınar","Karatay","Kulu","Meram","Sarayönü","Selçuklu","Seydişehir","Taşkent","Tuzlukçu","Yalıhüyük","Yunak"],
    "43": ["Altıntaş","Aslanapa","Çavdarhisar","Domaniç","Dumlupınar","Emet","Gediz","Hisarcık","Merkez","Pazarlar","Simav","Şaphane","Tavşanlı"],
    "44": ["Akçadağ","Arapgir","Arguvan","Battalgazi","Darende","Doğanşehir","Doğanyol","Hekimhan","Kale","Kuluncak","Merkez","Pütürge","Yazıhan","Yeşilyurt"],
    "45": ["Ahmetli","Akhisar","Alaşehir","Demirci","Gölmarmara","Gördes","Kırkağaç","Köprübaşı","Kula","Merkez","Sarıgöl","Saruhanlı","Selendi","Soma","Şehzadeler","Turgutlu","Yunusemre"],
    "46": ["Afşin","Andırın","Çağlayancerit","Dulkadiroğlu","Ekinözü","Elbistan","Göksun","Merkez","Nurhak","Onikişubat","Pazarcık","Türkoğlu"],
    "47": ["Artuklu","Dargeçit","Derik","Kızıltepe","Mazıdağı","Midyat","Nusaybin","Ömerli","Savur","Yeşilli"],
    "48": ["Bodrum","Dalaman","Datça","Fethiye","Kavaklıdere","Köyceğiz","Marmaris","Menteşe","Milas","Ortaca","Seydikemer","Ula","Yatağan"],
    "49": ["Bulanık","Hasköy","Korkut","Malazgirt","Merkez","Varto"],
    "50": ["Acıgöl","Avanos","Derinkuyu","Gülşehir","Hacıbektaş","Kozaklı","Merkez","Ürgüp"],
    "51": ["Altunhisar","Bor","Çamardı","Çiftlik","Merkez","Ulukışla"],
    "52": ["Akkuş","Altınordu","Aybastı","Çamaş","Çatalpınar","Çaybaşı","Fatsa","Gölköy","Gülyalı","Gürgentepe","İkizce","Kabadüz","Kabataş","Korgan","Kumru","Mesudiye","Perşembe","Ulubey","Ünye"],
    "53": ["Ardeşen","Çamlıhemşin","Çayeli","Derepazarı","Fındıklı","Güneysu","Hemşin","İkizdere","İyidere","Kalkandere","Merkez","Pazar"],
    "54": ["Adapazarı","Akyazı","Arifiye","Erenler","Ferizli","Geyve","Hendek","Karapürçek","Karasu","Kaynarca","Kocaali","Mithatpaşa","Pamukova","Sapanca","Serdivan","Söğütlü","Taraklı"],
    "55": ["Alaçam","Asarcık","Atakum","Ayvacık","Bafra","Canik","Çarşamba","Havza","İlkadım","Kavak","Ladik","19 Mayıs","Salıpazarı","Tekkeköy","Terme","Vezirköprü","Yakakent"],
    "56": ["Baykan","Eruh","Kurtalan","Merkez","Pervari","Şirvan","Tillo"],
    "57": ["Ayancık","Boyabat","Dikmen","Durağan","Erfelek","Gerze","Merkez","Saraydüzü","Türkeli"],
    "58": ["Akıncılar","Altınyayla","Divriği","Doğanşar","Gemerek","Gölova","Gürün","Hafik","İmranlı","Kangal","Koyulhisar","Merkez","Suşehri","Şarkışla","Ulaş","Yıldızeli","Zara"],
    "59": ["Çerkezköy","Çorlu","Ergene","Hayrabolu","Malkara","Marmaraereğlisi","Muratlı","Saray","Süleymanpaşa","Şarköy"],
    "60": ["Almus","Artova","Başçiftlik","Erbaa","Merkez","Niksar","Pazar","Reşadiye","Sulusaray","Turhal","Yeşilyurt","Zile"],
    "61": ["Akçaabat","Araklı","Arsin","Beşikdüzü","Çarşıbaşı","Çaykara","Dernekpazarı","Düzköy","Hayrat","Köprübaşı","Maçka","Of","Ortahisar","Sürmene","Şalpazarı","Tonya","Vakfıkebir","Yomra"],
    "62": ["Çemişgezek","Hozat","Mazgirt","Merkez","Nazımiye","Ovacık","Pertek","Pülümür"],
    "63": ["Akçakale","Birecik","Bozova","Ceylanpınar","Eyyübiye","Halfeti","Haliliye","Harran","Hilvan","Karaköprü","Siverek","Suruç","Viranşehir"],
    "64": ["Banaz","Eşme","Karahallı","Merkez","Sivaslı","Ulubey"],
    "65": ["Bahçesaray","Başkale","Çaldıran","Çatak","Edremit","Erciş","Gevaş","Gürpınar","İpekyolu","Merkez","Muradiye","Özalp","Saray","Tuşba"],
    "66": ["Akdağmadeni","Aydıncık","Boğazlıyan","Çandır","Çayıralan","Çekerek","Kadışehri","Merkez","Saraykent","Sarıkaya","Şefaatli","Sorgun","Yenifakılı","Yerköy"],
    "67": ["Alapli","Çaycuma","Devrek","Ereğli","Gökçebey","Kilimli","Kozlu","Merkez"],
    "68": ["Ağaçören","Eskil","Gülağaç","Güzelyurt","Merkez","Ortaköy","Sarıyahşi","Sultanhanı"],
    "69": ["Aydıntepe","Demirözü","Merkez"],
    "70": ["Ayrancı","Başyayla","Ermenek","Kazımkarabekir","Merkez","Sarıveliler"],
    "71": ["Bahşili","Balışeyh","Çelebi","Delice","Karakeçili","Keskin","Merkez","Sulakyurt","Yahşihan"],
    "72": ["Beşiri","Gercüş","Hasankeyf","Kozluk","Merkez","Sason"],
    "73": ["Beytüşşebap","Cizre","Güçlükonak","İdil","Merkez","Silopi","Uludere"],
    "74": ["Amasra","Kurucaşile","Merkez","Ulus"],
    "75": ["Çıldır","Damal","Göle","Hanak","Merkez","Posof"],
    "76": ["Aralık","Karakoyunlu","Merkez","Tuzluca"],
    "77": ["Altınova","Armutlu","Çınarcık","Çiftlikköy","Merkez","Termal"],
    "78": ["Eflani","Eskipazar","Merkez","Ovacık","Safranbolu","Yenice"],
    "79": ["Elbeyli","Merkez","Musabeyli","Polateli"],
    "80": ["Bahçe","Düziçi","Hasanbeyli","Kadirli","Merkez","Sumbas","Toprakkale"],
    "81": ["Akçakoca","Cumayeri","Çilimli","Gölyaka","Gümüşova","Güzeldere","Kaynaşlı","Merkez","Yığılca"],
}

@api_bp.route('/api/states/<country_iso2>')
def api_states(country_iso2):
    """İl/eyalet listesi - Türkiye için yerel veri"""
    if country_iso2.upper() == 'TR':
        return jsonify([{"iso2": il["id"], "name": il["name"]} for il in TR_ILLER])
    # Diğer ülkeler için boş döndür
    return jsonify([])

@api_bp.route('/api/cities/<country_iso2>/<state_iso2>')
def api_cities(country_iso2, state_iso2):
    """İlçe listesi - Türkiye için yerel veri"""
    if country_iso2.upper() == 'TR':
        ilceler = TR_ILCELER.get(state_iso2, [])
        return jsonify([{"name": ilce} for ilce in ilceler])
    return jsonify([])



@api_bp.route('/api/bildirimler')
@login_required
def api_bildirimler():
    bildirimler = Bildirim.query.filter_by(KullaniciID=session['user_id']).order_by(Bildirim.OlusturmaTarihi.desc()).limit(10).all()
    data = []
    for b in bildirimler:
        data.append({
            'id': b.BildirimID,
            'metin': b.Metin,
            'tarih': b.OlusturmaTarihi.strftime('%d.%m.%Y %H:%M'),
            'okundu': b.Okundu,
            'tip': b.Tip,
            'randevu_id': b.IlgiliRandevuID
        })
    return jsonify(data)

@api_bp.route('/api/bildirim/okundu/<int:bildirim_id>', methods=['POST'])
@login_required
def api_bildirim_okundu(bildirim_id):
    b = Bildirim.query.filter_by(BildirimID=bildirim_id, KullaniciID=session['user_id']).first()
    if b:
        b.Okundu = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@api_bp.route('/api/today-reminders')
@login_required
def today_reminders():
    from sqlalchemy import cast, Date
    # Bugün hatırlatması olan görevleri getir
    bugun = datetime.now().date()
    
    # MSSQL uyumlu: CAST(column AS DATE) kullan (db.func.date MSSQL'de çalışmaz)
    todos = Todo.query.filter(
        Todo.KullaniciID == session['user_id'],
        Todo.Tip == 'Kisisel',
        ((cast(Todo.HatirlatmaTarihi, Date) == bugun) | 
         ((cast(Todo.BitisTarihi, Date) == bugun) & (Todo.HatirlatmaTarihi == None)))
    ).all()
    
    # Tamamlanmışları filtrele
    active_todos = []
    for t in todos:
        if t.durum and t.durum.DurumAdi != 'Tamamlandı':
            active_todos.append({
                'id': t.TodoID,
                'baslik': t.Baslik,
                'aciklama': t.Aciklama,
                'saat': t.HatirlatmaTarihi.strftime('%H:%M') if t.HatirlatmaTarihi else '09:00'
            })
            
    return jsonify(active_todos)

@api_bp.route('/api/clear-session', methods=['POST'])
@csrf.exempt
def clear_session():
    session.clear()
    return jsonify({'status': 'success'})

@api_bp.route('/api/update-last-seen', methods=['POST'])
@csrf.exempt
def update_last_seen():
    if 'user_id' in session and 'session_token' in session:
        try:
            AktifOturum.query.filter_by(
                KullaniciID=session['user_id'],
                SessionToken=session['session_token']
            ).update({'SonGorulmeZamani': datetime.now()})
            db.session.commit()
            return jsonify({'status': 'success'})
        except:
            pass
    return jsonify({'status': 'error'}), 401

@api_bp.route('/api/session/check')
def check_session():
    if 'user_id' not in session:
        return jsonify({'valid': False})
        
    # Veritabanından kontrol et
    try:
        oturum = AktifOturum.query.filter_by(
            KullaniciID=session['user_id'],
            SessionToken=session.get('session_token')
        ).first()
        
        if not oturum:
            return jsonify({'valid': False})
            
        # Son görülme zamanını kontrol et (örn: 2 saat timeout)
        # if (datetime.now() - oturum.SonGorulmeZamani).total_seconds() > 7200:
        #     return jsonify({'valid': False})
            
        return jsonify({'valid': True})
    except:
        return jsonify({'valid': False})

@api_bp.route('/api/kullanicilar')
@login_required
def api_kullanicilar():
    """Tüm kullanıcıları listele"""
    kullanicilar = Kullanici.query.filter_by(FirmaID=session['firma_id']).all()
    return jsonify({'success': True, 'kullanicilar': [{
        'id': k.KullaniciID,
        'adi': k.Ad,
        'soyadi': k.Soyad,
        'tam_adi': f"{k.Ad} {k.Soyad}"
    } for k in kullanicilar]})

@api_bp.route('/api/musteri-ara')
@login_required
def api_musteri_ara():
    """Müşteri ara"""
    try:
        q = request.args.get('q', '').strip()
        if len(q) < 2:
            return jsonify([])
            
        firma_id = session.get('firma_id')
        if not firma_id:
            return jsonify({'error': 'Firma bilgisi bulunamadı'}), 401
        
        # Müşteri arama sorgusu
        try:
            # MSSQL için concat yerine + operatörü kullan
            from sqlalchemy import func
            try:
                # MySQL için concat
                full_name = db.func.concat(Musteri.MusteriAdi, ' ', Musteri.MusteriSoyadi)
            except:
                # MSSQL için + operatörü
                full_name = (Musteri.MusteriAdi + ' ' + Musteri.MusteriSoyadi)
            
            musteriler = Musteri.query.filter(
                Musteri.FirmaID == firma_id,
                Musteri.Aktif == True,
                or_(
                    Musteri.MusteriAdi.ilike(f'%{q}%'),
                    Musteri.MusteriSoyadi.ilike(f'%{q}%'),
                    Musteri.Telefon.ilike(f'%{q}%'),
                    Musteri.Email.ilike(f'%{q}%'),
                    # Tam isim araması (Ad + Soyad)
                    full_name.ilike(f'%{q}%')
                )
            ).limit(10).all()
        except Exception as e:
            # Eğer concat hatası varsa, sadece ad ve soyad ile ara
            print(f"Concat hatası, basit arama yapılıyor: {e}")
            musteriler = Musteri.query.filter(
                Musteri.FirmaID == firma_id,
                Musteri.Aktif == True,
                or_(
                    Musteri.MusteriAdi.ilike(f'%{q}%'),
                    Musteri.MusteriSoyadi.ilike(f'%{q}%'),
                    Musteri.Telefon.ilike(f'%{q}%'),
                    Musteri.Email.ilike(f'%{q}%')
                )
            ).limit(10).all()
        
        # Eğer sonuç bulunamadıysa, kelime bazlı arama yap
        if not musteriler and ' ' in q:
            words = q.split()
            if len(words) >= 2:
                from sqlalchemy import and_
                # İlk kelime ad, ikinci kelime soyad başlangıcı
                first_word = words[0]
                second_word = words[1]
                
                musteriler = Musteri.query.filter(
                    Musteri.FirmaID == firma_id,
                    Musteri.Aktif == True,
                    and_(
                        Musteri.MusteriAdi.ilike(f'%{first_word}%'),
                        Musteri.MusteriSoyadi.ilike(f'%{second_word}%')
                    )
                ).limit(10).all()
        
        # Plaka kodlarını şehir isimlerine dönüştür
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
        
        results = []
        for m in musteriler:
            sehir_kodu = m.Sehir or ''
            sehir_adi = plaka_to_sehir.get(sehir_kodu, sehir_kodu) if sehir_kodu else None

            # Telefonu temizle: başındaki +90 veya 90'ı at, yalnızca yerel numarayı ver
            telefon_raw = m.Telefon or ''
            telefon_temiz = telefon_raw
            if telefon_temiz.startswith('+90'):
                telefon_temiz = telefon_temiz[3:].strip()
            elif telefon_temiz.startswith('90') and len(telefon_temiz) >= 12:
                telefon_temiz = telefon_temiz[2:].strip()
            # Sondaki/öndeki boşlukları ve tire/parantez vs. temizle - sadece rakam bırak
            telefon_temiz = ''.join(c for c in telefon_temiz if c.isdigit())

            dogum_tarihi_str = None
            if m.DogumTarihi:
                try:
                    dogum_tarihi_str = m.DogumTarihi.strftime('%Y-%m-%d')
                except Exception:
                    pass

            results.append({
                'id': m.MusteriID,
                'ad': m.MusteriAdi or '',
                'soyad': m.MusteriSoyadi or '',
                'display': f"{m.MusteriAdi or ''} {m.MusteriSoyadi or ''}".strip(),
                'telefon': telefon_temiz,
                'telefon_ham': telefon_raw,
                'email': m.Email or '',
                'sehir': sehir_adi,
                'sehir_kodu': sehir_kodu,
                'ilce': m.Ilce or '',
                'adres': m.Adres or '',
                'ulke': 'TR',
                'dogum_tarihi': dogum_tarihi_str,
                'cinsiyet': m.Cinsiyet or '',
                'yas': m.Yas,
                'notlar': m.Notlar or '',
            })
        
        return jsonify(results)

        
    except Exception as e:
        print(f"Müşteri arama hatası: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api/aktivite-ekle', methods=['POST'])
@login_required
@csrf.exempt
def api_aktivite_ekle():
    """
    Yeni aktivite oluşturma API endpoint'i (Backup)
    POST /api/aktivite-ekle
    """
    try:
        firma_id = session.get('firma_id')
        user_id = session.get('user_id')
        
        if not firma_id or not user_id:
            return jsonify({'success': False, 'error': 'Oturum bilgisi bulunamadı'}), 401
        
        data = request.get_json()
        
        # Validasyon
        if not data.get('musteri_id'):
            return jsonify({'success': False, 'error': 'Müşteri ID gerekli'}), 400
        
        if not data.get('aktivite_tipi'):
            return jsonify({'success': False, 'error': 'Aktivite tipi gerekli'}), 400
        
        if not data.get('baslik'):
            return jsonify({'success': False, 'error': 'Başlık gerekli'}), 400
        
        # Müşteri kontrolü
        musteri = Musteri.query.filter_by(
            MusteriID=data['musteri_id'],
            FirmaID=firma_id
        ).first()
        
        if not musteri:
            return jsonify({'success': False, 'error': 'Müşteri bulunamadı'}), 404
        
        # Aktivite tarihi
        aktivite_tarihi = datetime.now()
        if data.get('aktivite_tarihi'):
            try:
                aktivite_tarihi = datetime.fromisoformat(data['aktivite_tarihi'].replace('Z', '+00:00'))
            except:
                try:
                    aktivite_tarihi = datetime.strptime(data['aktivite_tarihi'], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
        
        # Ek bilgileri JSON string'e çevir
        ek_bilgiler = None
        if data.get('ek_bilgiler'):
            if isinstance(data['ek_bilgiler'], dict):
                ek_bilgiler = json.dumps(data['ek_bilgiler'], ensure_ascii=False)
            else:
                ek_bilgiler = str(data['ek_bilgiler'])
        
        # Yeni aktivite oluştur
        yeni_aktivite = Aktivite(
            MusteriID=data['musteri_id'],
            FirmaID=firma_id,
            AktiviteTipi=data['aktivite_tipi'],
            Baslik=data['baslik'],
            Aciklama=data.get('aciklama'),
            IlgiliNesneTipi=data.get('ilgili_nesne_tipi'),
            IlgiliNesneID=data.get('ilgili_nesne_id'),
            AktiviteTarihi=aktivite_tarihi,
            EkBilgiler=ek_bilgiler,
            OlusturanKullaniciID=user_id
        )
        
        db.session.add(yeni_aktivite)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Aktivite başarıyla oluşturuldu',
            'data': yeni_aktivite.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/api/aktivite-sil/<int:aktivite_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def api_aktivite_sil_backup(aktivite_id):
    """
    Aktivite silme API endpoint'i (Backup)
    DELETE /api/aktivite-sil/123
    """
    try:
        firma_id = session.get('firma_id')
        
        aktivite = Aktivite.query.filter_by(
            AktiviteID=aktivite_id,
            FirmaID=firma_id
        ).first()
        
        if not aktivite:
            return jsonify({'success': False, 'error': 'Aktivite bulunamadı'}), 404
        
        db.session.delete(aktivite)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Aktivite başarıyla silindi'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
