# Real Estate Property Portal

MCA Final Year Project — Devaraj M S

A multi-role real estate listing platform built with Flask, designed to
deploy on AWS using IAM, EC2, VPC, S3, RDS, ALB, Auto Scaling, Route 53, and
CloudWatch.

## Features
- Property listings with search/filter (city, type, price, bedrooms)
- Property image uploads (local disk in dev, S3 in production)
- Agent dashboard — add/manage listings, respond to booking requests
- Customer accounts — book property visits, leave reviews
- Admin panel — approve/reject listings, view platform stats
- Role-based access control (customer / agent / admin)

## Tech Stack
- **Backend:** Flask, Flask-SQLAlchemy, Flask-Login
- **Database:** SQLite (dev) → MySQL on RDS (production)
- **Storage:** Local disk (dev) → S3 via boto3 (production)
- **Frontend:** Jinja2 templates + Bootstrap 5
- **Deployment:** EC2 + Gunicorn behind an Application Load Balancer, Auto
  Scaling Group, Route 53 DNS, CloudWatch monitoring

## Quick Start (Local)

```bash
pip install -r requirements.txt
cp .env.example .env      # edit if needed; defaults work for local dev
python seed.py             # creates DB + demo data
python run.py
```

Visit http://localhost:5000

| Role     | Email                | Password    |
|----------|-----------------------|-------------|
| Admin    | admin@estate.com      | admin123    |
| Agent    | agent1@estate.com     | agent123    |
| Agent    | agent2@estate.com     | agent123    |
| Customer | customer@estate.com   | customer123 |

## Project Structure

```
real-estate-portal/
├── app/
│   ├── __init__.py       # Flask app factory + all routes
│   ├── config.py         # Environment-based configuration
│   ├── models.py         # SQLAlchemy models (User, Property, Booking, Review, PropertyImage)
│   ├── storage.py        # S3 / local image upload abstraction (boto3)
│   ├── templates/        # Jinja2 templates
│   └── static/           # CSS + local image uploads
├── run.py                # App entry point
├── seed.py                # Demo data seeder
├── requirements.txt
├── .env.example
└── AWS_DEPLOYMENT_GUIDE.md   # Full step-by-step AWS deployment walkthrough
```

## Deploying to AWS

See `AWS_DEPLOYMENT_GUIDE.md` for the complete walkthrough mapping every
service in the architecture (IAM → VPC → RDS → S3 → EC2 → Auto Scaling → ALB
→ Route 53 → CloudWatch), including security group rules, IAM role setup,
and what to screenshot for your project report.

## Database Schema

- **User** — customer / agent / admin, with hashed passwords
- **Property** — listing details, owned by an agent, moderated by admin
- **PropertyImage** — one-to-many images per property
- **Booking** — customer visit requests, with status tracking
- **Review** — customer ratings/comments per property
