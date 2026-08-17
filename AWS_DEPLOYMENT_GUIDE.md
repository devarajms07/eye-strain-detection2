# AWS Deployment Guide — Real Estate Property Portal

This maps the Flask app to your resume's AWS service list. Follow in order —
each step builds on the last. Written for the CLF-C02 concepts you're already
studying, so this doubles as hands-on exam reinforcement.

**Estimated cost:** stay within Free Tier limits (t2.micro/t3.micro, db.t3.micro,
5GB S3) and this should cost close to $0/month for a demo period. Watch NAT
Gateway and ALB — they are NOT free tier eligible and bill hourly even when idle.
Tear down resources after your demo/viva if you're cost-conscious.

---

## Architecture Overview

```
                            Route 53 (DNS)
                                  |
                                  v
                    Application Load Balancer (public subnet)
                                  |
                    -------------+-------------
                    |                         |
              EC2 Instance A            EC2 Instance B   <- Auto Scaling Group
           (private subnet, App)     (private subnet, App)
                    |                         |
                    -------------+-------------
                                  |
                                  v
                      RDS MySQL (private subnet)
                                  |
                    S3 Bucket (property images, public subnet-independent)
                                  |
                          CloudWatch (logs + metrics + alarms)

        IAM roles attached to EC2 instances grant S3 + CloudWatch access
        (no hardcoded credentials anywhere in the app)
```

---

## Step 1 — IAM (do this first)

1. Create an **IAM role** (not a user) named `EstatePortal-EC2-Role` with:
   - `AmazonS3FullAccess` (or better: a custom policy scoped to just your bucket)
   - `CloudWatchAgentServerPolicy`
2. This role gets attached to EC2 instances later — so the app authenticates to
   AWS via the instance's IAM role, never via access keys in code. This is why
   `storage.py` calls `boto3.client("s3", region_name=...)` with no credentials
   — boto3 automatically picks up the instance role.
3. Create a separate **IAM user** only if you need to run AWS CLI commands from
   your laptop for setup (with `AdministratorAccess` for course purposes, but
   note in production you'd scope this down).

## Step 2 — VPC (networking foundation)

1. Create a VPC: `10.0.0.0/16`
2. Create 4 subnets across 2 Availability Zones for redundancy:
   - `10.0.1.0/24` — public subnet AZ-a (for ALB)
   - `10.0.2.0/24` — public subnet AZ-b (for ALB)
   - `10.0.3.0/24` — private subnet AZ-a (for EC2 + RDS)
   - `10.0.4.0/24` — private subnet AZ-b (for EC2 + RDS)
3. Create an **Internet Gateway**, attach to the VPC, and route `0.0.0.0/0` to
   it from the public subnets' route table.
4. (Optional, costs money) Create a **NAT Gateway** in a public subnet if your
   private-subnet EC2 instances need outbound internet (e.g., `pip install` at
   boot, S3 access without a VPC endpoint). For a free-tier demo, you can
   instead put EC2 in the public subnets directly with a security group that
   only allows the ALB in — simpler and cheaper for a student project.
5. Security Groups (this is your CLF-C02 material directly):
   - `alb-sg`: inbound 80/443 from `0.0.0.0/0`
   - `ec2-sg`: inbound 5000 (or 80 via Gunicorn+Nginx) from `alb-sg` only
   - `rds-sg`: inbound 3306 from `ec2-sg` only — never open to `0.0.0.0/0`

## Step 3 — RDS (database)

1. Create an RDS MySQL instance (`db.t3.micro`, free tier):
   - DB name: `realestate`
   - Place in the private subnets, using an RDS **subnet group** spanning both
     private subnets
   - Attach `rds-sg`
   - Enable automated backups
2. Note the endpoint, e.g. `estate-db.xxxxxx.ap-south-1.rds.amazonaws.com`
3. Once EC2 is up, set the app's `DATABASE_URL` environment variable:
   ```
   DATABASE_URL=mysql+pymysql://admin:YOUR_PASSWORD@estate-db.xxxxxx.ap-south-1.rds.amazonaws.com:3306/realestate
   ```
4. Run `python seed.py` once (or a migration) from an EC2 instance to create
   tables in RDS — the app's `db.create_all()` on startup will also handle
   table creation automatically.

## Step 4 — S3 (image storage)

1. Create an S3 bucket, e.g. `estate-portal-images-<your-initials>`
2. Block public access at the bucket level, but add a **bucket policy** that
   allows `s3:GetObject` publicly on the `property-images/*` prefix only (so
   images render in browsers without exposing the whole bucket) — or better,
   serve images through **CloudFront** in front of S3 for production-grade
   delivery (optional stretch goal).
3. Set environment variables on EC2:
   ```
   USE_S3=true
   S3_BUCKET=estate-portal-images-<your-initials>
   AWS_REGION=ap-south-1
   ```
4. No code changes needed — `storage.py` already switches to S3 uploads via
   this flag.

## Step 5 — EC2 (compute)

1. Launch an EC2 instance (`t3.micro`, Amazon Linux 2023 or Ubuntu 24.04) in a
   private subnet, attach `ec2-sg` and the `EstatePortal-EC2-Role` IAM role.
2. User-data script (paste into "Advanced details" at launch) to bootstrap:
   ```bash
   #!/bin/bash
   apt update -y
   apt install -y python3-pip python3-venv git nginx
   git clone <your-github-repo-url> /home/ubuntu/app
   cd /home/ubuntu/app
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   export DATABASE_URL="mysql+pymysql://admin:PASSWORD@<rds-endpoint>:3306/realestate"
   export USE_S3=true
   export S3_BUCKET="estate-portal-images-<your-initials>"
   export AWS_REGION="ap-south-1"
   nohup gunicorn -w 3 -b 0.0.0.0:5000 run:app &
   ```
3. Better practice: bake these into a **Launch Template** (not a one-off
   instance) so the Auto Scaling Group can reuse it.

## Step 6 — Auto Scaling Group

1. Create a Launch Template from your working EC2 config above.
2. Create an Auto Scaling Group using that template:
   - Min: 2, Desired: 2, Max: 4
   - Spread across your two private subnets (AZ-a and AZ-b)
   - Attach to the target group created in Step 7
   - Scaling policy: target tracking on average CPU utilization (e.g., 50%)

## Step 7 — Application Load Balancer

1. Create an ALB in the **public** subnets, attach `alb-sg`.
2. Create a Target Group (port 5000, HTTP health check on `/`).
3. Create a Listener on port 80 forwarding to the target group.
4. Point the Auto Scaling Group at this target group so new instances
   register automatically.
5. (Optional) Add an HTTPS listener on 443 with an ACM certificate for TLS.

## Step 8 — Route 53

1. If you own a domain, create a **Hosted Zone** in Route 53.
2. Add an **A record (Alias)** pointing your domain (e.g.,
   `estateportal.yourdomain.com`) to the ALB's DNS name.
3. No domain? Skip this — you can demo directly via the ALB's public DNS name.

## Step 9 — CloudWatch (monitoring)

1. Install the **CloudWatch agent** on your EC2 instances (via user-data) to
   ship `app.log` (the file `LOG_FILE` points to) to CloudWatch Logs.
2. Create **CloudWatch Alarms**:
   - EC2 CPUUtilization > 70% for 5 min → triggers Auto Scaling
   - ALB 5xx error count > 10 in 5 min → notify via SNS (optional)
   - RDS FreeStorageSpace < 2GB → notify
3. Build a simple **CloudWatch Dashboard** with widgets for EC2 CPU, ALB
   request count, and RDS connections — great screenshot for your project
   report/viva.

---

## Local Development (before touching AWS)

```bash
pip install -r requirements.txt
python seed.py          # creates local SQLite DB with demo data
python run.py            # runs on http://localhost:5000
```

Demo logins after seeding:
| Role     | Email                | Password    |
|----------|-----------------------|-------------|
| Admin    | admin@estate.com      | admin123    |
| Agent    | agent1@estate.com     | agent123    |
| Customer | customer@estate.com   | customer123 |

## What to Screenshot for Your Project Report

- VPC diagram (subnets, route tables) from the AWS Console's VPC Resource Map
- Security Group inbound rules for `alb-sg`, `ec2-sg`, `rds-sg`
- Auto Scaling Group activity history (shows a scale-out event if you load-test it)
- ALB target group health checks (all targets healthy)
- CloudWatch dashboard/alarms
- The running app itself (listings page, agent dashboard, admin panel)

## Talking Points for Interviews / Viva

- **Why private subnets for EC2/RDS?** Defense in depth — only the ALB is
  internet-facing; app servers and database are unreachable directly from
  the internet, reducing attack surface.
- **Why IAM roles instead of access keys?** Roles are temporary, auto-rotated
  credentials scoped to the instance — no secrets to leak in code or git history.
- **Why ALB over NLB here?** ALB operates at Layer 7 (HTTP), giving path-based
  routing and easy integration with Auto Scaling + health checks for a web
  app. NLB (Layer 4) would be used for TCP-level, ultra-low-latency workloads.
- **Why Auto Scaling?** Handles unpredictable traffic (e.g., property listing
  going viral) without manual intervention, and improves availability by
  replacing unhealthy instances automatically.
