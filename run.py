"""Entry point – run with:  python run.py  or  flask run"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
