import yaml, pathlib
path = pathlib.Path('.github/workflows/discord-notify.yml')
print('reading', path)
try:
    # ensure utf-8 when reading because the workflow contains emojis
    text = path.read_text(encoding='utf-8')
    data = yaml.safe_load(text)
    print('parsed ok')
except Exception as e:
    print('error', e)
