from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True for local dev only. On EC2, this is run behind Gunicorn (see deployment guide).
    app.run(host="0.0.0.0", port=5000, debug=False)
