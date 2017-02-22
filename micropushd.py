import os

import click
import flask
import sqlalchemy
import werkzeug.security
from flask import Flask, g
from flask import request

from flask_httpauth import HTTPBasicAuth
from sqlalchemy.orm.exc import NoResultFound

from api import api
from common import auth, push_service
from model import Session, User, Model

app = Flask(__name__)


@auth.verify_password
def verify_pw(username, password):
    print(">>>", username, password)
    g.user = None
    try:
        g.user = user = g.session.query(User).filter_by(name=username).one()
    except NoResultFound:
        return False

    return werkzeug.security.check_password_hash(user.password, password)


@app.before_request
def before_request():
    g.session = Session()
    g.user = None


@app.after_request
def shutdown_session(r):
    g.session.close()

    return r


@app.route("/")
def index():
    return "test"


@app.cli.command()
def setup():
    click.echo("Setting up micropushd")

    Model.metadata.create_all()
    click.echo("Tables created")

    click.echo("Creating admin user")
    username = click.prompt("Username")
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    if not password or not username:
        click.echo("Password or username can't be empty")
        return

    session = Session()

    user = User(
        name=username,
        password=werkzeug.security.generate_password_hash(password),
    )

    session.add(user)
    session.commit()

    click.echo("User {!r} created".format(username))


def init_app(config):
    app.config.from_json(config)

    # Bind database
    Model.metadata.bind = sqlalchemy.create_engine(app.config["DB"])

    # FCM Api Key
    push_service.set_api_key(app.config["FCM_KEY"])

    # Blueprints
    app.register_blueprint(api, url_prefix="/api/v1")

    return app


init_app(os.getenv("MICROPUSH_CONFIG"))


if __name__ == "__main__":
    app.run(host="", port=8090)
