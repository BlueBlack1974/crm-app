import urllib.request

req = urllib.request.Request('http://127.0.0.1:5000/rapor/musteriler')
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        lines = html.split('\n')
        for i, line in enumerate(lines):
            if 'chartData' in line:
                print(f"Found 'chartData' on line {i+1}:")
                for j in range(max(0, i-2), min(len(lines), i+8)):
                    print(lines[j].strip())
                print('---')
except Exception as e:
    print('Error:', e)
