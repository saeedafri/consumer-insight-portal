"""Downloads DB-IP's free "IP to City Lite" file at image build (deploy/Dockerfile), for the Logs page's Top visitors:
the city of a visitor's address is then looked up on our own server (api/metrics.py place_of), no address sent anywhere.
DB-IP publishes a new file each month; this tries this month's, then last month's. Licence: CC BY 4.0, credited on the
Logs page. A failed download never fails the build: visitors are then shown without a place.
    python deploy/geo-download.py /srv/cip/geo/dbip-city-lite.mmdb"""
import datetime
import gzip
import os
import shutil
import sys
import urllib.request

target = sys.argv[1]
today = datetime.date.today()
last_month = today.replace(day=1) - datetime.timedelta(days=1)
for month in (today, last_month):
    url = f"https://download.db-ip.com/free/dbip-city-lite-{month:%Y-%m}.mmdb.gz"
    asking = urllib.request.Request(url, headers={"User-Agent": "cip-image-build"})   # DB-IP refuses Python's default
    try:
        with urllib.request.urlopen(asking, timeout=120) as answer, open(target + ".part", "wb") as out:
            shutil.copyfileobj(gzip.GzipFile(fileobj=answer), out)
        os.replace(target + ".part", target)   # whole files only: a broken download leaves no half file
        print(f"geo-download: {url}")
        break
    except OSError as problem:
        print(f"geo-download: {url} not used ({problem})")
