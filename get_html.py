import urllib.request
req = urllib.request.Request('http://127.0.0.1:5000/rapor/musteriler')
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        with open('output.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Scraped properly.")
except Exception as e:
    print('Error:', e)
