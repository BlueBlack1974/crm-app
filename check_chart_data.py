import urllib.request, re

req = urllib.request.Request('http://127.0.0.1:5000/rapor/musteriler')
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        pattern = r'<div id="chartData"(.*?)>.*?</div>'
        match = re.search(pattern, html, flags=re.DOTALL)
        if match:
            print('Found chartData HTML tag:')
            print(match.group(0))
        else:
            print('chartData not found in rendered HTML')
except Exception as e:
    print('Error:', e)
