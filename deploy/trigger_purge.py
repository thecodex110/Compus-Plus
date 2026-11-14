"""Knocks on the web service's clean-up URL. Run daily by the Render cron job (see render.yaml).

Needs APP_URL (https://your-app.onrender.com) and CRON_TOKEN in the environment.
Uses only the standard library, so the cron job has nothing to install.
"""
import os
import sys
import urllib.error
import urllib.request

url = os.environ['APP_URL'].rstrip('/') + '/internal/purge-print-files/'
request = urllib.request.Request(url, method='POST', headers={'Authorization': 'Bearer ' + os.environ['CRON_TOKEN']})
try:
    with urllib.request.urlopen(request, timeout=120) as response:
        print(response.status, response.read().decode())
except urllib.error.HTTPError as error:
    print('Clean-up failed: HTTP', error.code, '(is APP_URL right and is CRON_TOKEN the same on both services?)')
    sys.exit(1)
except urllib.error.URLError as error:
    print('Clean-up failed:', error.reason)
    sys.exit(1)
