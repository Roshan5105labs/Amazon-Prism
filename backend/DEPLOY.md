# Amazon Prism — AWS Deployment (Free Tier)

The app is container-ready. Deploy = create 4 AWS resources, then point the
service at them with environment variables. No code changes needed.

## 0. One IAM user for everything
IAM → Users → Create user → Attach policies: `AmazonS3FullAccess`,
`AmazonBedrockFullAccess`. Create an access key (type: Application).
Save the **Access key** and **Secret** — used for both S3 and Bedrock.

## 1. S3 (media storage)
S3 → Create bucket, e.g. `amazon-prism-media`, region `us-east-1`.
(Block-public-access can stay on; the app serves media via the API.)

## 2. Bedrock (the AI grader — Nova Lite, image + video)
Bedrock → Model access → enable **Amazon Nova Lite** in `us-east-1`.
This first call also unlocks part of the onboarding AWS credits.

## 3. RDS (PostgreSQL database)
RDS → Create database → PostgreSQL → **Free tier** template →
instance `db.t4g.micro` → set master user/password + DB name `amazon_prism` →
Public access: Yes (for the demo) → create. Copy the **endpoint**.
Tables auto-create on first boot (no migration needed on a fresh DB).

## 4. App Runner (runs the container, gives a public HTTPS URL)
Push this repo to GitHub, then App Runner → Create service → Source: GitHub
(or container/ECR) → Build: use the included `Dockerfile` → Port `8000`.
Set these environment variables:

```
DATABASE_URL=postgresql://<user>:<pass>@<rds-endpoint>:5432/amazon_prism
VISION_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
AWS_ACCESS_KEY_ID=<IAM access key>          # boto3 / Bedrock auth
AWS_SECRET_ACCESS_KEY=<IAM secret>
MINIO_ENDPOINT=s3.us-east-1.amazonaws.com
MINIO_ACCESS_KEY=<IAM access key>           # same key, used by S3 client
MINIO_SECRET_KEY=<IAM secret>
MINIO_BUCKET=amazon-prism-media
MINIO_SECURE=true
MINIO_REGION=us-east-1
MINIO_PUBLIC_BASE_URL=https://amazon-prism-media.s3.us-east-1.amazonaws.com
ALLOWED_ORIGINS=https://<your-frontend-url>
```

Deploy → open `https://<service-url>/docs` (Swagger). Hit it once to warm it.

## 5. Frontend
Deploy the React app on AWS Amplify (or S3+CloudFront). Point it at the App
Runner URL, and put that Amplify URL into `ALLOWED_ORIGINS` above.

## Demo happy-path (in /docs)
1. POST a return case  2. upload PRECHECK media  3. POST run-ai-assessment?stage=PRECHECK
4. upload FINAL_CHECK media  5. POST run-ai-assessment?stage=FINAL_CHECK
6. GET health-card, listing-preview, green-credits, recommendations.

## Notes
- Video grading is inherently slow (~1–2 min upload+inference). The "under ~2s"
  number is image-only.
- If a Bedrock call ever fails, set `VISION_PROVIDER=gemini` + `GEMINI_API_KEY`
  as a proven fallback (same response contract).
- Local dev still works unchanged via docker-compose (Postgres + MinIO).
