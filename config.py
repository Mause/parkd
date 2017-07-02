try:
    auth = json.load(open('auth.json'))
    access_token = '{app_id}|{app_secret}'.format_map(auth)
except FileNotFoundError:
    access_token = os.environ.get('ACCESS_TOKEN')
