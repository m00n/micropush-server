from pathlib import Path

import arrow

from flask import Blueprint, jsonify
from flask import abort
from flask import g
from flask import request
from flask import send_file
from flask import url_for
from flask import current_app
from sqlalchemy.orm.exc import NoResultFound

from common import auth, push_service
from model import User, Device, FCMRegistration, Notification, Icon

api = Blueprint("api", __name__)


@api.before_request
def before_request():
    pass


@api.route('/messages/<int:notification_id>/text')
@auth.login_required
def full_message(notification_id):
    print(notification_id)
    notification = g.session.query(Notification).get(notification_id)
    if notification is None:
        return abort(404)

    print(notification.user, g.user)
    if notification.user != g.user:
        return abort(403)

    return jsonify({
        "message": notification.full_message
    })


@api.route("/send", methods=["POST"])
@auth.login_required
def send_notification():
    title = request.form["title"]
    message = request.form["message"]
    source = request.form.get("source", "api")
    group = request.form.get("group", None)
    full_message = request.form.get("full_message", None)
    icon = request.form.get("icon", 0)

    to = request.form.get("to")
    if to is not None:
        to = to.split(",")

    if to:
        registrations = g.session.query(Device).join(FCMRegistration).filter(Device.alias.in_(to)).all()
    else:
        registrations = g.session.query(FCMRegistration).filter(FCMRegistration.user == g.user).all()
    registration_ids = [r.token for r in registrations]

    if not registrations:
        return jsonify(dict(error="No devices")), 500

    notification = Notification(
        user=g.user,
        title=title,
        message=message,
        full_message=full_message,
        group=group
    )
    g.session.add(notification)
    g.session.commit()

    payload = {
        "title": title,
        "message": message,
        "source": source,
        "timestamp": arrow.utcnow().timestamp,
        "group": group,
        "full_message": bool(full_message),
        "notification_id": notification.notification_id,
        "icon": icon
    }
    result = push_service.notify_multiple_devices(registration_ids=registration_ids, data_message=payload)

    registrations_updated = 0
    for registration, response in zip(registrations, result[0]["results"]):
        print(registration, response)
        if "registration_id" in response:
            token = response["registration_id"]
            if token != registration.token:
                registration.token = token
                registrations_updated += 1

        if "error" in response and response["error"] == "NotRegistered":
            g.session.delete(registration)

    g.session.commit()

    print(result)

    return jsonify({
        "devices": len(registrations),
        "tokens_updated": registrations_updated,
        "success": result[0]["success"],
        "failure": result[0]["failure"],
        "notification_id": notification.notification_id,
    })


def get_device():
    try:
        uuid = request.get_json()["uuid"]
    except KeyError:
        return None

    try:
        return g.session.query(Device).filter_by(uuid=uuid).one()
    except NoResultFound:
        return None


@api.route("/register", methods=["POST"])
@auth.login_required
def register_device():
    data = request.get_json()

    try:
        uuid = data["uuid"]
        name = data["name"]
        token = data["token"]
    except KeyError:
        return abort(400)

    try:
        device = g.session.query(Device).filter_by(uuid=uuid).one()
    except NoResultFound:
        device = Device(uuid=uuid, model=name, user=g.user)
        g.session.add(device)

    if device.registration:
        registration = device.registration
    else:
        registration = FCMRegistration(device=device, user=g.user, token=token)

    g.session.add(registration)
    g.session.commit()

    return jsonify({
        "status": "registered"
    })


@api.route('/unregister', methods=['POST'])
def unregister_device():
    token = request.form["token"]

    try:
        registration = g.session.query(FCMRegistration).filter_by(token=token).one()
    except NoResultFound:
        return abort(404)

    g.session.delete(registration)
    g.session.commit()
    return jsonify({
        "status": "ok"
    })


@api.route("/verfify", methods=["POST"])
def verify():
    return jsonify({
        "status": "ok"
    })


@api.route("/icons/<int:icon_id>", methods=["GET"])
@auth.login_required
def get_icon(icon_id):
    icon = g.session.query(Icon).get(icon_id)

    if icon is None:
        return abort(404)

    print(icon.user, g.user, icon.path(get_upload_directory()), )
    if icon.user != g.user:
        return abort(403)

    return send_file(str(icon.path(get_upload_directory())), mimetype="image/png")


@api.route("/icons/", methods=["GET", "POST"])
@auth.login_required
def icons():
    def icon_to_dict(icon):
        return {
            "icon_id": icon.icon_id,
            "name": icon.name,
            "version": icon.version,
            "url": url_for("api.get_icon", icon_id=icon.icon_id, _external=True)
        }

    if request.method == "GET":
        icons = g.session.query(Icon).filter(Icon.user == g.user).all()
        return jsonify({icon.icon_id: icon_to_dict(icon) for icon in icons})

    elif request.method == "POST":
        name = request.form["name"]
        upload = request.files["file"]

        if not Icon.check_file(upload.stream):
            return abort(400)

        upload.stream.seek(0)

        icon = Icon(user=g.user, name=name)
        g.session.add(icon)
        g.session.commit()

        with icon.get_write_stream(get_upload_directory()) as fd:
            upload.save(fd)

        return jsonify(icon_to_dict(icon))


def get_upload_directory():
    return Path(current_app.config["UPLOAD_DIRECTORY"])
