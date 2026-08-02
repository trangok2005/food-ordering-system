from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import cloudinary
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_USERNAME = os.getenv("DATABASE_USERNAME")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_PORT = os.getenv("DATABASE_PORT")


db = SQLAlchemy()
login = LoginManager()

def create_app():

    app = Flask(__name__)
    app.secret_key = 'trangdeptraicomotkohaip@ok'

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{os.environ['DATABASE_USERNAME']}:{os.environ['DATABASE_PASSWORD']}"
        f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}/{os.environ['DATABASE_NAME']}?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
    app.config["PAGE_SIZE"] = 9

    db.init_app(app)
    login.init_app(app)

    return app



