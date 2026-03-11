import requests

session = requests.Session()
login_url = 'http://127.0.0.1:5000/login'
report_url = 'http://127.0.0.1:5000/rapor/musteriler'

try:
    # First get the page to get CSRF token if needed, or just post directly
    login_data = {'email': 'test@test.com', 'sifre': '123456'} # we don't know the login
    headers = {'User-Agent': 'Mozilla'}
    
    # Just try to get the page with a dummy session
    r = session.get(report_url)
    print("Status:", r.status_code)
    print("URL after request:", r.url)
    
    if r.status_code == 200:
        html = r.text
        if 'chartData' in html:
            print("chartData Found!")
        else:
            print("chartData NOT Found!")
            
        if 'function normalize' in html:
            print("Normalize function found!")
            
except Exception as e:
    print('Error:', e)
