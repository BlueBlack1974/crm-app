import urllib.request
from bs4 import BeautifulSoup

try:
    req = urllib.request.Request('http://127.0.0.1:5000/rapor/musteriler')
    # Because of login_required, this might redirect to login. We need to scrape output.html that we already saved, or login.
    with open('output.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    chart_data = soup.find(id='chartData')
    if chart_data:
        print("chartData tag FOUND.")
        print(str(chart_data)[:500])
    else:
        print("chartData tag NOT FOUND.")
except Exception as e:
    print('Error:', e)
