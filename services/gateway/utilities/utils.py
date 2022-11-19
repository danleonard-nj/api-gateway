
def validate_leading_slash(url):
    if not url[0] == '/':
        raise Exception(f'{url} must begin with a leading slash')
