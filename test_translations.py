from app import create_app
from flask_babel import gettext
from flask import session

app = create_app()

with app.test_request_context():
    session['language'] = 'tr'
    with app.app_context():
        import flask_babel
        # Zorla dili tr olarak çevir
        flask_babel.refresh()
        print('Language is set to TR')
        print('Total Appointments ->', gettext('Total Appointments'))
