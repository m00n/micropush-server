import math
import os
from pathlib import Path
import arrow

from PIL import Image
from flask import Flask
from flask import request
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Sequence
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text
from sqlalchemy import types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from flask_httpauth import HTTPBasicAuth


Model = declarative_base()

Session = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
    )
)


class Arrow(types.TypeDecorator):
    impl = types.INTEGER

    def process_bind_param(self, value, dialect):
        """
        :type value: arrow.arrow.Arrow
        """
        if value is not None:
            return value.to("utc").timestamp

    def process_result_value(self, value, dialect):
        if value is not None:
            return arrow.get(value)


class User(Model):
    __tablename__ = "user"

    user_id = Column(
        Integer,
        Sequence('user_id_seq'),
        primary_key=True
    )

    name = Column(String(64), nullable=False)
    password = Column(String(128), nullable=False)

    devices = relationship("Device")
    fcm_registrations = relationship("FCMRegistration")


class Notification(Model):
    __tablename__ = "notification"

    notification_id = Column(
        Integer,
        Sequence('notification_id_seq'),
        primary_key=True
    )
    user_id = Column(ForeignKey("user.user_id"), nullable=False)
    icon_id = Column(ForeignKey("icon.icon_id"))

    title = Column(String(256), nullable=False)
    message = Column(String(512), nullable=False)
    full_message = Column(Text)
    timestamp = Column(Arrow, nullable=False, default=arrow.utcnow)
    group = Column(String(48))

    user = relationship("User")


class FCMRegistration(Model):
    __tablename__ = "fcm"

    fcm_registration_id = Column(
        Integer,
        Sequence('fcm_registration_id_seq'),
        primary_key=True
    )
    user_id = Column(ForeignKey("user.user_id"), nullable=False)
    device_id = Column(ForeignKey("device.device_id"), nullable=False)

    token = Column(String(256), nullable=False)

    created_on = Column(Arrow, nullable=False, default=arrow.utcnow)

    user = relationship("User")
    device = relationship("Device", uselist=False)


class Device(Model):
    __tablename__ = "device"

    device_id = Column(
        Integer,
        Sequence('device_id_seq'),
        primary_key=True
    )

    user_id = Column(ForeignKey("user.user_id"), nullable=False)

    uuid = Column(String(128), nullable=False)
    model = Column(String(128), nullable=False, default="<unknown>")
    alias = Column(String(32))

    last_seen_on = Column(Arrow, nullable=False, default=arrow.utcnow)

    user = relationship("User")
    registration = relationship("FCMRegistration", uselist=False)


class Icon(Model):
    __tablename__ = "icon"

    icon_id = Column(
        Integer,
        Sequence('icon_id_seq'),
        primary_key=True
    )
    user_id = Column(ForeignKey("user.user_id"), nullable=False)
    name = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=0)

    user = relationship("User")

    @staticmethod
    def check_file(fd):
        try:
            Image.open(fd)
        except OSError as exc:
            if exc.args[0].startswith("cannot identify image file"):
                return False
            else:
                raise
        else:
            return True

    def path(self, base) -> Path:
        subdir = str(math.floor(self.icon_id // 1000))
        return base / subdir / "{}.png".format(self.icon_id)

    def get_write_stream(self, base: Path):
        try:
            os.mkdir(self.path(base).parent)
        except FileExistsError:
            pass

        self.version += 1

        return open(self.path(base), "wb")