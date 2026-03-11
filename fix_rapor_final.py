
import os

file_path = r"D:\Yazılım_Projeler\Python\CRM\app\templates\rapor_musteriler.html"

correct_init_function = """    // Müşteri detay raporu grafiklerini başlat
    function initializeCustomerDetailCharts() {
        console.log('initializeCustomerDetailCharts çağrıldı');

        // Chart.js yüklendiğini kontrol et
        if (typeof Chart === 'undefined') {
            console.error('Chart.js kütüphanesi yüklenemedi!');
            return;
        }

        console.log('Chart.js yüklendi, grafikler oluşturuluyor...');

        // Verileri data attribute'dan al (her iki grafik için)
        const chartDataEl = document.getElementById('chartData');
        let monthlyData = {};
        let bookData = {};

        if (chartDataEl) {
            try {
                monthlyData = JSON.parse(chartDataEl.getAttribute('data-monthly') || '{}');
                bookData = JSON.parse(chartDataEl.getAttribute('data-book') || '{}');
            } catch (e) {
                console.error('Data parse hatası:', e);
            }
        }

        console.log('Data attribute\\'dan alınan monthlyData:', monthlyData);
        console.log('Data attribute\\'dan alınan bookData:', bookData);

        // Aylık randevu dağılımı grafiği
        const monthlyCtx = document.getElementById('monthlyAppointmentChart');
        if (monthlyCtx) {
            try {
                const monthlyLabels = Object.keys(monthlyData).sort();
                const monthlyValues = monthlyLabels.map(label => monthlyData[label]);

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
                        plugins: {
                            title: {
                                display: true,
                                text: {{ _('Monthly Appointment Distribution') | tojson }}
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Aylık grafik oluşturma hatası:', error);
            }
        }

        // Defter dağılımı grafiği
        const bookCtx = document.getElementById('bookDistributionChart');
        if (bookCtx) {
            try {
                const bookLabels = Object.keys(bookData);
                const bookValues = Object.values(bookData);

                new Chart(bookCtx, {
                    type: 'doughnut',
                    data: {
                        labels: bookLabels.length > 0 ? bookLabels : [{{ _('No Data')| tojson }}],
                        datasets: [{
                            data: bookValues.length > 0 ? bookValues : [1],
                            backgroundColor: [
                                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: {{ _('Appointment Book Distribution') | tojson }}
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Defter grafik oluşturma hatası:', error);
            }
        }
    }
"""

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

final_lines = []
skip = False
found_init = False

for line in lines:
    # Detect start of initializeCustomerDetailCharts
    if "function initializeCustomerDetailCharts() {" in line:
        final_lines.append(correct_init_function)
        skip = True
        found_init = True
    # Detect start of createCharts (end of previous function)
    elif "function createCharts() {" in line:
        skip = False
        final_lines.append(line)
    elif skip:
        continue
    else:
        # Fix other syntax errors in createCharts or elsewhere
        # Fix extra braces in variable assignments
        if "const genderData =" in line and "tojson" in line:
             line = "        const genderData = {{ gender_data | tojson }};\n"
        elif "const ageData =" in line and "tojson" in line:
             line = "    const ageData = {{ age_groups | tojson }};\n"
        elif "const categoryData =" in line and "tojson" in line:
             line = "    const categoryData = {{ category_data | tojson }};\n"
        elif "const cityData =" in line and "tojson" in line:
             line = "    const cityData = {{ city_data | tojson }};\n"
        
        # General cleanup of malformed tags if any remain
        line = line.replace("{ {", "{{").replace("} }", "}}")
        
        final_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("File updated successfully.")
