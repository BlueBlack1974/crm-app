from app import create_app
app = create_app()
with app.app_context():
    env = app.jinja_env
    import os
    templates_dir = os.path.join(app.root_path, 'templates')
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                path = os.path.relpath(os.path.join(root, file), templates_dir).replace('\\', '/')
                try:
                    source, filename, uptodate = env.loader.get_source(env, path)
                    env.parse(source)
                except Exception as e:
                    if 'TemplateSyntaxError' in str(type(e)):
                        print(f'ERROR IN {path} LINE {getattr(e, "lineno", "?")}: {e}')
