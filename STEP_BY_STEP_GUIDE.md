# Real Estate Property Portal — Complete Step-by-Step Build Guide

MCA Main Project — Devaraj M S

This walks through the entire project from scratch: what each piece is, why
it exists, and the actual code. Read this fully before your viva — you should
be able to explain any file here without looking at it.

---

## Step 0 — Prerequisites

```bash
python3 --version   # 3.10+ recommended
pip3 --version
```

Install these Python packages (full list in `requirements.txt`):
- **Flask** — the web framework serving pages and handling requests
- **Flask-SQLAlchemy** — ORM, lets us define database tables as Python classes
- **Flask-Login** — session management (who's logged in, role checks)
- **boto3** — AWS SDK, used to upload property images to S3
- **Gunicorn** — production WSGI server (replaces Flask's built-in dev server on EC2)
- **PyMySQL** — MySQL driver, used when the database is RDS instead of local SQLite

---

## Step 1 — Project Structure

Before writing code, decide the folder layout. This separation matters: it's
what lets the same codebase run locally (SQLite + local file storage) and on
AWS (RDS + S3) with zero code changes — only environment variables change.

```
real-estate-portal/
├── app/
│   ├── __init__.py     # App factory: creates the Flask app, registers all routes
│   ├── config.py       # All environment-dependent settings in ONE place
│   ├── models.py       # Database schema as Python classes (SQLAlchemy ORM)
│   ├── storage.py       # Image upload logic — local disk OR S3, switched by config
│   ├── templates/       # HTML pages (Jinja2 templates)
│   └── static/          # CSS + locally-uploaded images
├── run.py               # Entry point — what you actually execute
├── seed.py              # Fills the database with demo data for testing/viva
├── requirements.txt
└── .env.example         # Documents every environment variable the app needs
```

**Why an "app factory" pattern (`create_app()` function) instead of a global
`app = Flask(__name__)`?** It lets you create multiple app instances with
different configs — e.g., one for testing, one for production — and avoids
circular import issues once the project grows. This is the standard
production pattern, not just a style choice.

---

## Step 2 — Configuration (`app/config.py`)

Everything that differs between your laptop and AWS lives here, read from
environment variables with sensible local defaults:

```python
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Local dev: SQLite file. On AWS: RDS endpoint via DATABASE_URL env var.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'realestate.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # USE_S3 flag switches image storage between local disk and S3 — no code change needed.
    USE_S3 = os.environ.get("USE_S3", "false").lower() == "true"
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    S3_REGION = os.environ.get("AWS_REGION", "ap-south-1")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

    LOG_FILE = os.environ.get("LOG_FILE", os.path.join(BASE_DIR, "app.log"))
```

**Why this matters for your viva:** this is "12-factor app" configuration —
config comes from the environment, never hardcoded. It's exactly why the same
code deploys to EC2 without edits: you just set `DATABASE_URL` and `USE_S3`
as environment variables on the instance.

---

## Step 3 — Database Schema (`app/models.py`)

Five tables, designed around the features list:

```python
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")  # customer|agent|admin
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Property(db.Model):
    __tablename__ = "properties"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    property_type = db.Column(db.String(50))    # Apartment, Villa, Plot, Commercial
    listing_type = db.Column(db.String(20))     # Sale | Rent
    price = db.Column(db.Numeric(12, 2), nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    locality = db.Column(db.String(120))
    bedrooms = db.Column(db.Integer, default=0)
    bathrooms = db.Column(db.Integer, default=0)
    area_sqft = db.Column(db.Integer)
    status = db.Column(db.String(20), default="pending")  # pending|approved|rejected
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)


class PropertyImage(db.Model):
    __tablename__ = "property_images"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)  # local path OR S3 URL
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="requested")  # requested|confirmed|declined|completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**ER relationships to draw in your diagram:**
- `User (1) → (many) Property` — one agent lists many properties
- `Property (1) → (many) PropertyImage` — one property has many images
- `Property (1) → (many) Booking` and `User (1) → (many) Booking` — a booking
  links one customer to one property
- `Property (1) → (many) Review` and `User (1) → (many) Review` — same pattern

**Why `password_hash` and not `password`?** Never store plaintext passwords.
`generate_password_hash` uses a salted hash (Werkzeug's default is
`scrypt`) — even if the database leaks, passwords aren't recoverable.

---

## Step 4 — Image Storage Abstraction (`app/storage.py`)

This is the AWS integration piece — the same function call either saves to
disk or uploads to S3, decided by one config flag:

```python
import os, uuid
from werkzeug.utils import secure_filename
from flask import current_app

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

def save_property_image(file_storage):
    if not file_storage or file_storage.filename == "":
        raise ValueError("No file provided")
    if not allowed_file(file_storage.filename):
        raise ValueError("File type not allowed. Use png, jpg, jpeg, or webp.")

    filename = _unique_filename(secure_filename(file_storage.filename))

    if current_app.config["USE_S3"]:
        return _upload_to_s3(file_storage, filename)
    else:
        return _save_locally(file_storage, filename)

def _upload_to_s3(file_storage, filename):
    bucket = current_app.config["S3_BUCKET"]
    region = current_app.config["S3_REGION"]
    s3 = boto3.client("s3", region_name=region)   # <- no credentials here!
    key = f"property-images/{filename}"
    s3.upload_fileobj(file_storage, bucket, key,
                       ExtraArgs={"ContentType": file_storage.content_type})
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
```

**Interview-critical detail:** notice `boto3.client("s3", region_name=region)`
has no access key or secret anywhere. On EC2, boto3 automatically picks up
temporary credentials from the instance's attached **IAM role**. This is why
Step 1 of AWS deployment is always IAM — you're setting up *how* the app is
allowed to talk to S3, before the app can actually do it securely.

---

## Step 5 — Application Routes (`app/__init__.py`)

This is the biggest file — it wires models, storage, and templates together
into working pages. Structured by feature:

### 5a. App factory and login setup
```python
from flask import Flask
from flask_login import LoginManager
from app.config import Config
from app.models import db, User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    # ... routes registered below, see full file in the code zip
```

### 5b. Role-based access control
Every protected route uses a small decorator instead of repeating the same
check everywhere:
```python
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Usage:
@app.route("/admin")
@login_required
@role_required("admin")
def admin_panel():
    ...
```
This is what stops a customer from hitting `/admin` directly by typing the
URL — tested and confirmed returning `403 Forbidden`.

### 5c. Search/filter logic (property listings)
```python
@app.route("/")
def index():
    query = Property.query.filter_by(status="approved")
    city = request.args.get("city")
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    # ... more filters chained the same way (price range, bedrooms, type)
    properties = query.order_by(Property.created_at.desc()).all()
    return render_template("index.html", properties=properties)
```
Only `status="approved"` properties show publicly — this enforces the admin
moderation workflow at the query level, not just in the UI.

### 5d. Booking creation
```python
@app.route("/property/<int:property_id>/book", methods=["POST"])
@login_required
@role_required("customer")
def book_property(property_id):
    booking = Booking(
        property_id=property_id,
        customer_id=current_user.id,
        visit_date=datetime.strptime(request.form["visit_date"], "%Y-%m-%d").date(),
        message=request.form.get("message", ""),
    )
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for("property_detail", property_id=property_id))
```

**Full file (routes for agent dashboard, admin panel, reviews, auth) is in
the project zip** — the pattern repeats: check role → validate input → touch
the database → redirect with a flash message.

---

## Step 6 — Templates (`app/templates/`)

Jinja2 templates all extend a shared `base.html` (navbar, flash messages,
Bootstrap). One example — the booking form on the property detail page:

```html
{% if current_user.is_authenticated and current_user.role == 'customer' %}
<form method="POST" action="{{ url_for('book_property', property_id=property.id) }}">
    <input type="date" name="visit_date" min="{{ today }}" required>
    <textarea name="message" placeholder="Any questions for the agent?"></textarea>
    <button type="submit">Send Booking Request</button>
</form>
{% else %}
<p>Please <a href="{{ url_for('login') }}">log in</a> as a customer to book.</p>
{% endif %}
```

Every template does this same thing: **check `current_user.role` before
showing role-specific actions.** The full set (11 templates — home, login,
register, property detail, agent dashboard, property form, bookings,
customer dashboard, admin panel, error page) is in the zip.

---

## Step 7 — Entry Point (`run.py`)

```python
from app import create_app
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
```

`host="0.0.0.0"` (not `127.0.0.1`) matters on EC2 — it means the app accepts
connections from any network interface, not just localhost, which is
required for the ALB to reach it.

---

## Step 8 — Demo Data (`seed.py`)

Creates one admin, two agents, one customer, and four sample properties (one
left `pending` on purpose, so you can demo the admin approval flow live).
Run once:
```bash
python seed.py
```

---

## Step 9 — Run and Test Locally

```bash
pip install -r requirements.txt
python seed.py
python run.py
```

Visit `http://localhost:5000`. Test this sequence for your own confidence
before your viva:
1. Browse listings as a guest → search by city/price
2. Log in as `agent1@estate.com` / `agent123` → add a new property with images
3. Log in as `admin@estate.com` / `admin123` → approve that property
4. Log in as `customer@estate.com` / `customer123` → book a visit, leave a review
5. Log back in as the agent → confirm the booking

This exact flow is what you should demo live in your viva — it touches every
feature on your resume bullet list.

---

## Step 10 — Deploy to AWS

Full walkthrough (IAM → VPC → RDS → S3 → EC2 → Auto Scaling → ALB → Route 53
→ CloudWatch) is in `AWS_DEPLOYMENT_GUIDE.md` in the project zip — it's long
enough to warrant its own document. Read it alongside this guide.

**Order matters and mirrors dependency, not the resume bullet order:**
IAM (permissions) → VPC (network) → RDS (data layer) → S3 (storage) → EC2
(compute) → Auto Scaling (resilience) → ALB (traffic entry) → Route 53
(DNS) → CloudWatch (observe everything after it's running).

---

## Quick Reference: Feature → Code Mapping

| Resume Feature | File(s) |
|---|---|
| Property Listings | `models.py` (Property), `__init__.py` (`index()`) |
| Property Search | `__init__.py` (`index()` query filters) |
| Property Images | `storage.py`, `models.py` (PropertyImage) |
| Agent Dashboard | `__init__.py` (`agent_dashboard`, `new_property`) |
| Customer Login | `models.py` (User), `__init__.py` (`login`, `register`) |
| Booking Requests | `models.py` (Booking), `__init__.py` (`book_property`) |
| Property Reviews | `models.py` (Review), `__init__.py` (`add_review`) |
| Admin Panel | `__init__.py` (`admin_panel`, `moderate_property`) |
