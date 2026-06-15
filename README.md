# Amazon Prism — AI-Powered Returns & Sustainable Resale

**HackOn with Amazon 6.0 | Second Life Commerce**
**Team:** Master Branch
**Theme:** AI-Powered Returns & Sustainable Resale

Amazon Prism is an AI-powered returns intelligence platform that helps Amazon, sellers, and customers give every returned product its best possible second life.

Instead of treating returns as a cost center, Prism evaluates each returned item using AI vision, calculates its financial recovery value, and routes it to the most suitable outcome: **resale, refurbishment, exchange, donation, recycling, returnless handling, or manual review**.

---

## Problem Statement

E-commerce returns create a massive operational, financial, and environmental problem.

Returned products often move through expensive reverse logistics pipelines involving pickup, shipping, inspection, repacking, storage, liquidation, or disposal. Many usable products lose value simply because there is no fast, intelligent system to evaluate their condition and decide the best next action at item level.

This affects:

* **Amazon Operations:** high return volume, manual inspection bottlenecks, and lost recovery value.
* **Third-Party Sellers:** limited visibility and control over returned inventory, especially for FBM returns.
* **Customers:** lack of trust in renewed or refurbished products.
* **Environment:** usable products being wasted, liquidated, or landfilled.

---

## Our Solution: Amazon Prism

Amazon Prism acts as an intelligent decision layer for returns.

It answers one key question:

> What should happen to this exact returned product next?

Prism uses product images, AI condition grading, financial viability scoring, and fulfillment-aware routing to decide whether the item should be resold, refurbished, donated, recycled, exchanged, or sent for manual review.

---

## Key Features

### 1. AI Product Condition Grading

Users upload or capture product images. Prism analyzes the item using an AI vision pipeline and generates:

* Product grade: A / B / C / D
* Product health score: 1–100
* Damage summary
* Packaging condition
* Usage level
* Missing-parts detection
* Buyer-facing condition summary

The AI pipeline is designed with:

* **Amazon Bedrock Nova Lite** as the primary vision model
* **Gemini 2.5 Flash** as fallback
* Manual review fallback when AI confidence is low or providers are unavailable

---

### 2. PRECHECK and FINAL CHECK Workflow

Prism separates return intelligence into two stages.

#### Customer PRECHECK

The customer starts a return and uploads or captures product images.

Prism performs an early AI PRECHECK to:

* Create the return case
* Estimate product condition
* Validate return reason
* Predict the likely recovery path
* Reduce blind reverse-logistics decisions

#### Vendor / Amazon Admin FINAL CHECK

The final inspection happens when the item is received.

* **FBM returns:** vendor performs FINAL CHECK
* **FBA returns:** Amazon Administration performs FINAL CHECK

This ensures the final disposition is based on received-condition evidence.

---

### 3. Financial Viability Scoring

Prism does not route products based only on condition. It also checks whether recovery is economically sensible.

It calculates:

```text
Expected Resale Price = Original Price × Grade Factor × Demand Multiplier

Total Recovery Cost = Reverse Logistics + Inspection + Repacking + Relisting + Refurbishment

Net Recovery Value = Expected Resale Price - Total Recovery Cost
```

This helps determine whether the product is worth reselling, refurbishing, donating, recycling, or handling through another route.

---

### 4. Intelligent Multi-Path Routing

Prism considers multiple signals:

* AI grade
* Health score
* Net recovery value
* Return reason
* Demand level
* Fulfillment type: FBA or FBM
* Inspection stage: PRECHECK or FINAL_CHECK

Based on these signals, it routes products to outcomes such as:

* Resell
* Refurbish
* Exchange
* Donate
* Recycle
* P2P resale
* Returnless handling
* Vendor review
* Amazon admin final check
* Manual review

---

### 5. Product Health Card

Each eligible item gets a **Prism Verified Product Health Card**.

The card contains:

* Grade
* Health score
* Condition summary
* Damage details
* Confidence level
* Recommended route
* Green impact message

This builds buyer trust in renewed and refurbished products.

---

### 6. Vendor Final Disposition Approval

For vendor-controlled returns, Prism does not blindly force an AI decision.

The vendor can review the AI recommendation and approve or decline final disposition options such as:

* Resale
* Refurbishment
* Donation
* Recycling

This gives sellers visibility and control over their returned inventory.

---

### 7. Prism Renewed Marketplace

Approved products are listed in a Prism Renewed-style marketplace view.

Each listing can show:

* Product image
* Product name
* Condition grade
* Health score
* Recommended price
* Prism Verified badge
* Product Health Card information

This helps buyers trust second-life products.

---

### 8. Amazon Administration Dashboard

The Amazon Administration portal provides operational visibility into returns.

It supports:

* FBA final check
* Return registry monitoring
* AI grading status
* Recovery route tracking
* Resale/refurbish/donation/recycle outcomes
* Sustainability and green-credit impact

---

## User Roles

### Customer

Customers can:

* Start a return
* Capture product images using camera
* Upload product images from gallery
* View returned product status
* See Prism Renewed products

### Vendor

Vendors can:

* View returned product queue
* Open AI Engine for FINAL CHECK
* Upload or capture final inspection images
* View AI recommendation
* Approve or decline final disposition
* Track resale/refurbish/donation/recycle decisions

### Amazon Administration

Amazon Admin can:

* Monitor all return cases
* Perform FBA final checks
* View return registry
* Track Prism routing decisions
* Monitor renewed listings and sustainability outcomes

---

## Tech Stack

### Frontend

* React
* Vite
* AWS Amplify Hosting
* Role-based UI for Customer, Vendor, and Amazon Administration

### Backend

* FastAPI
* Python
* SQLModel
* Pydantic
* Docker
* AWS Elastic Beanstalk

### Database

* PostgreSQL on Amazon RDS

### Object Storage

* Amazon S3 for product image storage

### AI / Vision

* Amazon Bedrock Nova Lite as primary AI vision grader
* Gemini 2.5 Flash as fallback
* Manual review fallback for provider throttling or low-confidence results

### Deployment

* Frontend: AWS Amplify
* Backend: AWS Elastic Beanstalk with Docker
* HTTPS bridge: Amazon CloudFront
* Database: Amazon RDS PostgreSQL
* Media: Amazon S3

---

## Architecture Overview

```text
Customer / Vendor / Amazon Admin
        |
        v
React Frontend on AWS Amplify
        |
        v
CloudFront HTTPS Proxy
        |
        v
FastAPI Backend on Elastic Beanstalk
        |
        |---- PostgreSQL on Amazon RDS
        |
        |---- Amazon S3 Media Storage
        |
        |---- Amazon Bedrock Nova Lite
        |
        |---- Gemini 2.5 Flash Fallback
        |
        v
Prism Decision Engine
        |
        v
Health Card + Routing + Listing Preview + Green Credits
```

---

## Main Workflow

```text
1. Customer starts return
2. Customer captures/uploads product image
3. Prism performs AI PRECHECK
4. Return case is created
5. Product is routed based on condition and viability
6. Vendor or Amazon Admin performs FINAL CHECK
7. Prism recommends final disposition
8. Responsible owner approves or declines
9. Eligible products become Prism Renewed listings
10. Buyer sees verified second-life product with Health Card
```

---

## Backend API Highlights

| Endpoint                                                      | Purpose                             |
| ------------------------------------------------------------- | ----------------------------------- |
| `GET /health`                                                 | Backend health check                |
| `POST /return-cases`                                          | Create return case                  |
| `POST /media/upload`                                          | Upload product images               |
| `POST /return-cases/{id}/run-ai-assessment?stage=PRECHECK`    | Run customer precheck               |
| `POST /return-cases/{id}/run-ai-assessment?stage=FINAL_CHECK` | Run vendor/admin final check        |
| `POST /return-cases/{id}/ai-assessment`                       | Manual/demo assessment fallback     |
| `GET /return-cases`                                           | Fetch return cases                  |
| `GET /return-cases/{id}`                                      | Fetch one return case               |
| `GET /return-cases/{id}/health-card`                          | Fetch Product Health Card           |
| `GET /return-cases/{id}/listing-preview`                      | Fetch Prism Renewed listing preview |
| `POST /return-cases/{id}/vendor-decision`                     | Vendor approval/decline workflow    |
| `GET /green-credits/summary`                                  | Sustainability impact summary       |

---

## Demo Flow

A recommended demo flow:

```text
1. Open Prism landing page
2. Choose Customer
3. Start a return
4. Capture/upload product image
5. Run Prism AI PRECHECK
6. View return status and AI health score
7. Open Vendor or Amazon Administration
8. Select returned product
9. Run FINAL CHECK
10. Approve final disposition
11. View Prism Renewed listing with health card
```

---

## Screenshots

Add your screenshots here.

```md
![Landing Page](./screenshots/landing.png)
![Customer Return](./screenshots/customer-return.png)
![AI Health Card](./screenshots/health-card.png)
![Vendor Queue](./screenshots/vendor-queue.png)
![Admin Dashboard](./screenshots/admin-dashboard.png)
![Prism Renewed Listing](./screenshots/prism-renewed.png)
```

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

---

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
```

For Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:5432/postgres?sslmode=require
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-s3-bucket-name
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
GEMINI_API_KEY=your-gemini-api-key
VISION_PROVIDER=gemini
ALLOWED_ORIGINS=http://localhost:5173
```

Run backend:

```bash
uvicorn app.main:app --reload
```

Backend docs:

```text
http://localhost:8000/docs
```

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Create `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_API=false
```

Frontend:

```text
http://localhost:5173
```

---

## Production Deployment

### Frontend

The frontend is deployed using AWS Amplify.

Recommended Amplify rewrite rules:

```json
[
  {
    "source": "/api/<*>",
    "target": "https://YOUR_CLOUDFRONT_BACKEND_DOMAIN/<*>",
    "status": "200",
    "condition": null
  },
  {
    "source": "/<*>",
    "target": "/index.html",
    "status": "404-200",
    "condition": null
  }
]
```

### Backend

The backend is deployed on AWS Elastic Beanstalk using Docker.

Production services:

```text
AWS Amplify → CloudFront → Elastic Beanstalk FastAPI → RDS + S3 + Bedrock/Gemini
```

---

## Environment Variables

Do not commit secrets to GitHub.

Use `.env.example` for safe placeholders.

```env
DATABASE_URL=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
S3_BUCKET_NAME=
BEDROCK_MODEL_ID=
GEMINI_API_KEY=
VISION_PROVIDER=
ALLOWED_ORIGINS=
```

---

## Sustainability Impact

Prism supports sustainability by:

* Reducing unnecessary landfill disposal
* Increasing resale and refurbishment recovery
* Routing usable low-recovery products to donation
* Routing damaged products to recycling
* Awarding Green Credits for sustainable choices
* Helping prevent future returns through return-reason insights

---

## Future Scope

Planned improvements:

* Asynchronous AI processing using Amazon SQS
* Worker-based Bedrock processing pipeline
* Expanded Product Health Card standard
* Seller notification workflows using SNS/SES
* CloudFront-backed media delivery
* Return prevention nudges on product pages
* Prism Verified buyer-facing marketplace
* B2B API for retailers, OEMs, warranty providers, and e-waste programs

---

## Team

**Team Name:** Master Branch
**Hackathon:** HackOn with Amazon 6.0
**Theme:** Second Life Commerce: AI-Powered Returns & Sustainable Resale

| Name            | Role               |
| --------------- | ------------------ |
| S Roshan Pranao | Backend Developer  |
| Mani Shankar B  | Frontend Developer |

---

## Links

| Resource          | Link                                               |
| ----------------- | -------------------------------------------------- |
| Live App          | `https://YOUR_LIVE_APP_URL`                        |
| Demo Video        | `https://YOUR_DEMO_VIDEO_URL`                      |
| GitHub Repository | `https://github.com/YOUR_USERNAME/YOUR_REPOSITORY` |

---

## Tagline

> Amazon Prism — A second life for every return.
