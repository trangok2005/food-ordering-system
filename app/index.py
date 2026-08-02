from flask import request, jsonify, session, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from app import utils, login, create_app


@login.user_loader
def load_user(user_id):
    return #dao.get_user_by_id(user_id)


def register_routers(app):
    login.login_view = 'login_view'

    @app.route('/')
    def index():
        return render_template('index.html')


    @app.route('/login')
    def login_view():
        return render_template('login.html')

    @app.route('/login', methods=['POST'])
    def login_process():
       return

    @app.route('/register')
    def register_view():
        return render_template('register.html')

    @app.route('/register', methods=['POST'])
    def register_process():
        return

    @app.route('/logout')
    def logout_process():
        logout_user()
        return redirect('/login')


app = create_app()
register_routers(app=app)

if __name__ == '__main__':
    app.run(debug=True)