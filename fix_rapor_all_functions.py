
import os

file_path = r"D:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html"

# Define correct function bodies
create_charts_code = """    function createCharts() {
        // Cinsiyet dağılımı grafiği
        const genderCtx = document.getElementById('genderChart');
        if (!genderCtx) {
            console.error('genderChart elementi bulunamadı');
            return;
        }

        const genderData = {{ gender_data | tojson }};

        if (Object.keys(genderData).length === 0) {
            const ctx = genderCtx.getContext('2d');
            ctx.font = '16px Arial';
            ctx.fillStyle = '#666';
            ctx.textAlign = 'center';
            ctx.fillText('Cinsiyet bilgisi bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
        } else {
            // Etiketlere göre renkleri doğru ata (Kadın=pembe, Erkek=mavi)
            const genderLabelsRaw = Object.keys(genderData);
            const genderValues = Object.values(genderData);
            const normalize = (s) => (s || '').toString().trim().toLowerCase()
                .replace(/İ/g, 'i').replace(/Ğ/g, 'g').replace(/Ü/g, 'u')
                .replace(/Ş/g, 's').replace(/Ö/g, 'o').replace(/Ç/g, 'c');
            const genderColors = genderLabelsRaw.map(label => {
                const k = normalize(label);
                if (k === 'kadin' || k === 'female') return '#FF6384'; // pink for female
                if (k === 'erkek' || k === 'male') return '#36A2EB';   // blue for male
                return '#FFCE56'; // neutral for others/unknown
            });

            // Etiket çevirileri (i18n)
            const G = { male: '{{ _("Male") }}', female: '{{ _("Female") }}' };
            const genderLabels = genderLabelsRaw.map(label => {
                const k = normalize(label);
                if (k === 'kadin' || k === 'female') return G.female;
                if (k === 'erkek' || k === 'male') return G.male;
                return label;
            });

            new Chart(genderCtx, {
                type: 'doughnut',
                data: {
                    labels: genderLabels,
                    datasets: [{
                        data: genderValues,
                        backgroundColor: genderColors,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }

        // Yaş dağılımı grafiği
        const ageCtx = document.getElementById('ageChart');
        if (ageCtx) {
            const ageData = {{ age_groups | tojson }};

            if (Object.values(ageData).every(val => val === 0)) {
                const ctx = ageCtx.getContext('2d');
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.textAlign = 'center';
                ctx.fillText('Yaş bilgisi bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
            } else {
                new Chart(ageCtx, {
                    type: 'bar',
                    data: {
                        labels: Object.keys(ageData),
                        datasets: [{
                            label: '{{ _("Customer Count") }}',
                            data: Object.values(ageData),
                            backgroundColor: '#36A2EB',
                            borderColor: '#36A2EB',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1,
                                    callback: function (value) {
                                        return Number.isInteger(value) ? value : null;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }

        // Kategori dağılımı grafiği
        const categoryCtx = document.getElementById('categoryChart');
        if (categoryCtx) {
            const categoryData = {{ category_data | tojson }};

            if (Object.keys(categoryData).length === 0) {
                const ctx = categoryCtx.getContext('2d');
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.textAlign = 'center';
                ctx.fillText('Kategori bilgisi bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
            } else {
                const categoryLabelsRaw = Object.keys(categoryData);
                const categoryValues = Object.values(categoryData);
                const C = { vip: '{{ _("VIP") }}', normal: '{{ _("Normal") }}' };
                const normalize = (s) => (s || '').toString().trim().toLowerCase();
                const categoryLabels = categoryLabelsRaw.map(label => {
                    const k = normalize(label);
                    if (k === 'vip' || k.includes('vip')) return C.vip;
                    if (k === 'normal' || k.includes('normal')) return C.normal;
                    return label;
                });

                new Chart(categoryCtx, {
                    type: 'pie',
                    data: {
                        labels: categoryLabels,
                        datasets: [{
                            data: categoryValues,
                            backgroundColor: [
                                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                                '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
            }
        }

        // Şehir dağılımı grafiği
        const cityCtx = document.getElementById('cityChart');
        if (cityCtx) {
            const cityData = {{ city_data | tojson }};

            if (Object.keys(cityData).length === 0) {
                const ctx = cityCtx.getContext('2d');
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.textAlign = 'center';
                ctx.fillText('Şehir bilgisi bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
            } else {
                const plakaToSehir = {
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
                    '76': 'Iğdır', '77': 'Yalova', '78': 'Karabük', '79': 'Kilis', '80': 'Osmaniye',
                    '81': 'Düzce'
                };

                const convertedCityData = {};
                for (const [plaka, count] of Object.entries(cityData)) {
                    const sehirAdi = plakaToSehir[plaka] || plaka;
                    convertedCityData[sehirAdi] = count;
                }

                const sortedCities = Object.keys(convertedCityData).sort();
                const cityLabels = sortedCities;
                const cityValues = sortedCities.map(city => convertedCityData[city]);

                new Chart(cityCtx, {
                    type: 'bar',
                    data: {
                        labels: cityLabels,
                        datasets: [{
                            label: '{{ _("Customer Count") }}',
                            data: cityValues,
                            backgroundColor: '#4BC0C0',
                            borderColor: '#4BC0C0',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        indexAxis: 'y',
                        scales: {
                            x: {
                                beginAtZero: true
                            }
                        },
                        plugins: {
                            legend: {
                                display: true
                            }
                        }
                    }
                });
            }
        }
    }
"""

create_time_series_code = """    function createTimeSeriesCharts() {
        // Aylık müşteri artışı grafiği
        const monthlyCtx = document.getElementById('monthlyChart');
        if (monthlyCtx) {
            const monthlyData = {{ monthly_data | tojson }};

            if (Object.keys(monthlyData).length === 0) {
                const ctx = monthlyCtx.getContext('2d');
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.textAlign = 'center';
                ctx.fillText('Aylık veri bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
            } else {
                const sortedMonthlyData = Object.keys(monthlyData).sort();
                const monthlyLabels = sortedMonthlyData;
                const monthlyValues = sortedMonthlyData.map(key => monthlyData[key]);

                new Chart(monthlyCtx, {
                    type: 'line',
                    data: {
                        labels: monthlyLabels.length > 0 ? monthlyLabels : [{{ _('No Data')| tojson }}],
                        datasets: [{
                            label: {{ _('Appointments')| tojson }},
                            data: monthlyValues.length > 0 ? monthlyValues : [0],
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            tension: 0.1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1,
                                    callback: function (value) {
                                        return Number.isInteger(value) ? value : null;
                                    }
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: true
                            }
                        }
                    }
                });
            }
        }

        // Haftalık müşteri artışı grafiği
        const weeklyCtx = document.getElementById('weeklyChart');
        if (weeklyCtx) {
            const weeklyData = {{ weekly_data | tojson }};

            if (Object.keys(weeklyData).length === 0) {
                const ctx = weeklyCtx.getContext('2d');
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.textAlign = 'center';
                ctx.fillText('Haftalık veri bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
            } else {
                const sortedWeeklyData = Object.keys(weeklyData).sort();
                const weeklyLabels = sortedWeeklyData.map(label => {
                    const parts = label.split(' - ');
                    return parts[0].substring(5); // Sadece ay-gün kısmını al
                });
                const weeklyValues = sortedWeeklyData.map(key => weeklyData[key]);

                new Chart(weeklyCtx, {
                    type: 'bar',
                    data: {
                        labels: weeklyLabels,
                        datasets: [{
                            label: '{{ _("Customer Count") }}',
                            data: weeklyValues,
                            backgroundColor: '#4BC0C0',
                            borderColor: '#4BC0C0',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1,
                                    callback: function (value) {
                                        return Number.isInteger(value) ? value : null;
                                    }
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: true
                            }
                        }
                    }
                });
            }
        }
    }
"""

create_trend_code = """    function createAppointmentTrendCharts() {
        // Randevu sıklığı dağılımı grafiği
        const frequencyCtx = document.getElementById('appointmentFrequencyChart');
        if (!frequencyCtx) {
            console.error('appointmentFrequencyChart elementi bulunamadı');
            return;
        }

        const frequencyData = {{ randevu_siklik_dagilimi | tojson }};

        if (Object.keys(frequencyData).length === 0) {
            const ctx = frequencyCtx.getContext('2d');
            ctx.font = '16px Arial';
            ctx.fillStyle = '#666';
            ctx.textAlign = 'center';
            ctx.fillText('Randevu verisi bulunamadı', ctx.canvas.width / 2, ctx.canvas.height / 2);
        } else {
            // Etiketleri dile göre çevir
            const freqLabelsRaw = Object.keys(frequencyData);
            const freqValues = Object.values(frequencyData);
            const normalize = (s) => (s || '').toString().trim().toLowerCase();
            const freqLabels = freqLabelsRaw.map(label => {
                const k = normalize(label);
                if (k === '0 randevu' || k === '0 appointment' || k === '0 appointments') return '{{ _("0 Appointments") }}';
                if (k === '1 randevu' || k === '1 appointment') return '{{ _("1 Appointment") }}';
                if (k === '2-5 randevu' || k === '2-5 appointments') return '{{ _("2-5 Appointments") }}';
                if (k === '6-10 randevu' || k === '6-10 appointments') return '{{ _("6-10 Appointments") }}';
                if (k === '10+ randevu' || k === '10+ appointments') return '{{ _("10+ Appointments") }}';
                return label;
            });

            new Chart(frequencyCtx, {
                type: 'doughnut',
                data: {
                    labels: freqLabels,
                    datasets: [{
                        data: freqValues,
                        backgroundColor: [
                            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
                        ],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
    }
"""

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

final_lines = []
skip = False
current_function = None

for line in lines:
    if "function createCharts() {" in line:
        final_lines.append(create_charts_code)
        skip = True
        current_function = "createCharts"
    elif "function createTimeSeriesCharts() {" in line:
        final_lines.append(create_time_series_code)
        skip = True
        current_function = "createTimeSeriesCharts"
    elif "function createAppointmentTrendCharts() {" in line:
        final_lines.append(create_trend_code)
        skip = True
        current_function = "createAppointmentTrendCharts"
    
    if skip:
        # Check if we reached the end of the replaced function
        # This is heuristic: if we see the start of the next function, we stop skipping
        # OR if we see the end of the script block (unlikely to be on same line as function start)
        if current_function == "createCharts" and "function createTimeSeriesCharts() {" in line:
            # We found the next function, so we must have finished skipping createCharts
            # But wait, we already appended the code for createTimeSeriesCharts above if we processed this line?
            # No, the loop processes line by line.
            # If we are skipping, we should check if the CURRENT line is the start of the NEXT function.
            # If so, we stop skipping and process this line normally (which will trigger the elif block above? No, we are inside the loop)
            pass
        
        # Better approach:
        # If we are skipping, ignore the line unless it matches the start of another function we want to keep/replace.
        if "function createTimeSeriesCharts() {" in line and current_function == "createCharts":
            skip = False # Stop skipping
            # Now we need to process this line again or just append the new code?
            # Since we are in the loop, we can't "process again".
            # We should append the new code for createTimeSeriesCharts HERE.
            final_lines.append(create_time_series_code)
            skip = True
            current_function = "createTimeSeriesCharts"
        elif "function createAppointmentTrendCharts() {" in line and current_function == "createTimeSeriesCharts":
             skip = False
             final_lines.append(create_trend_code)
             skip = True
             current_function = "createAppointmentTrendCharts"
        elif "document.addEventListener('DOMContentLoaded'" in line:
             skip = False
             final_lines.append(line)
        elif line.strip() == "</script>":
             skip = False
             final_lines.append(line)
    else:
        final_lines.append(line)

# This logic is a bit flawed because if we append the code, we need to make sure we don't append it twice.
# Let's refine.

final_lines = []
skip = False

for line in lines:
    if "function createCharts() {" in line:
        final_lines.append(create_charts_code)
        skip = True
    elif "function createTimeSeriesCharts() {" in line:
        if skip: # We were skipping createCharts, now we found the next one
            pass # We already appended createCharts code, now we append createTimeSeriesCharts code
        final_lines.append(create_time_series_code)
        skip = True
    elif "function createAppointmentTrendCharts() {" in line:
        final_lines.append(create_trend_code)
        skip = True
    elif "document.addEventListener('DOMContentLoaded'" in line:
        skip = False
        final_lines.append(line)
    elif line.strip() == "</script>":
        skip = False
        final_lines.append(line)
    elif not skip:
        final_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("File updated successfully.")
