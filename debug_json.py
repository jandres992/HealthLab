import urllib.request
import json
url = "https://www.datos.gov.co/resource/gdxc-w37w.json?$limit=1"
with urllib.request.urlopen(url) as response:
    print(json.loads(response.read().decode('utf-8')))
