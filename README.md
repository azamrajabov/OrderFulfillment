# Order Fulfillment

AWS SAM serverless order fulfillment application.

## Stack

- Python 3.12 Lambda
- DynamoDB (4 tables)
- S3 (2 buckets)
- API Gateway
- AWS Cognito (authentication)
- UPS API (shipping)

## Setup

### Prerequisites
- AWS SAM CLI
- Python 3.12
- AWS credentials configured

### Cognito Setup
If API Gateway URL changes, update callback URLs in the Cognito User Pool app client hosted UI settings.

### S3 Shipping Labels
The shipping labels S3 bucket needs public access configured manually.

### VPC
Lambda requires VPC configuration. See: https://www.youtube.com/watch?v=9OXJFtGd0OY

## Deployment

### CI/CD
- Push to `feature/**` branches deploys to a dev stack
- Push to `main` deploys to testing, then production (with manual approval)

### Stack Names
- Dev: `order-fulfillment-app-serverless-dev`
- Prod: `order-fulfillment-app-serverless-prod`

### GitHub Secrets Required
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `COGNITO_APP_CLIENT_ID_DEV`
- `COGNITO_APP_CLIENT_ID_PROD`

### AWS Resources Required
- Secrets Manager: `prod/order-fulfillment/secrets` (with `UPS_CLIENT_ID`, `UPS_CLIENT_SECRET`, `UPS_ACCOUNT_NUMBER`)
- Cognito User Pool with domain `order-fulfillment.auth.us-east-1.amazoncognito.com`
