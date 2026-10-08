import requests
import base64
import urllib.parse
import sys

def fetch_and_process():
    try:
        data = requests.get("https://snowd.com/api/locations.php", timeout=10).json()
        if data.get('success') != 1 or 'data' not in data:
            return []
        
        results = []
        for loc in data['data']:
            if not isinstance(loc, dict):
                continue
            
            accs = loc.get('accs')
            country = loc.get('country')
            if not accs or not country:
                continue
            
            parts = accs.split('@', 1)
            if len(parts) != 2:
                continue
            
            decoded = base64.b64decode(parts[0]).decode('utf-8')
            combined = f"{decoded}@{parts[1]}"
            encoded = base64.b64encode(combined.encode('utf-8')).decode('utf-8')
            
            results.append(f"ss://{encoded}#{urllib.parse.quote(country)}")
        return results
    except Exception:
        return []

if __name__ == "__main__":
    for result in fetch_and_process():
        print(result)