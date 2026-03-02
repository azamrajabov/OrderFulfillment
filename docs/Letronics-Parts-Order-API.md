# Letronics - Parts Order API

**Commercial Parts Shipping API Design**

**UPDATED BY LETRONICS ON 03/01/2026**

---

## Revision History

| Rev. | Date       | Changes                              | Editor        |
|------|------------|--------------------------------------|---------------|
| 1.0  | 03/01/2026 | Document Created - Parts Order API   | Azam Rahabov  |

---

## Table of Contents

- [Introduction](#introduction)
- [API Base URL](#api-base-url)
- [Authentication](#authentication)
- [Request Parts Order](#request-parts-order)
  - [Sequence Diagram](#sequence-diagram---request-parts-order)
  - [Request Object](#request-object---request-parts-order)
  - [Response Object](#response-object---request-parts-order)
  - [Error Responses](#error-responses)
- [Order Flow](#order-flow)
- [Example Requests](#example-requests)
  - [cURL](#curl-example)
  - [Python](#python-example)
  - [Postman](#postman-setup)

---

## Introduction

This document describes the API for requesting parts orders through the Letronics Order Fulfillment system. Parts orders differ from camera orders in that they do not require VIN decoding or vehicle-related processing. Parts are identified by their **SKU** numbers which are matched against the Letronics inventory.

Once a parts order is submitted, it goes through the following stages:
1. **SKU Validation** - Each SKU is validated against inventory
2. **Address Validation** - Shipping address is validated via UPS Address Validation API
3. **Shipping Label Generation** - UPS shipping label is generated
4. **Order Created** - Order is saved with status "Unshipped" and listed on the Orders page

---

## API Base URL

| Environment | Base URL                                                        |
|-------------|-----------------------------------------------------------------|
| Production  | `https://ad0e2kb0yf.execute-api.us-east-1.amazonaws.com/Prod`  |

---

## Authentication

The `/request_order` endpoint is a **public POST endpoint** exposed externally for vendor integration. No authentication token is required for this endpoint.

**Headers:**

| Header         | Value              | Required |
|----------------|--------------------|----------|
| `Content-Type` | `application/json` | Yes      |

---

## Request Parts Order

Request Parts Order is triggered by the external system (Descartes Telematics) to ship replacement parts or accessories to a customer. The system validates each SKU against the inventory, validates the shipping address via UPS, generates a shipping label, and creates the order.

### Sequence Diagram - Request Parts Order

```
┌──────────────────┐                    ┌──────────────┐                ┌─────────┐
│    Commercial    │                    │              │                │         │
│    Telematics    │                    │  Letronics   │                │   UPS   │
│   (Descartes)    │                    │              │                │   API   │
└────────┬─────────┘                    └──────┬───────┘                └────┬────┘
         │                                     │                             │
         │  POST /request_order                │                             │
         │  (orderId, address, parts[sku])     │                             │
         │────────────────────────────────────>│                             │
         │                                     │                             │
         │                                     │  Validate SKUs              │
         │                                     │  against Inventory          │
         │                                     │──────┐                      │
         │                                     │      │                      │
         │                                     │<─────┘                      │
         │                                     │                             │
         │                                     │  Validate Address (XAV)     │
         │                                     │────────────────────────────>│
         │                                     │                             │
         │                                     │  Address Classification     │
         │                                     │<────────────────────────────│
         │                                     │                             │
         │                                     │  Create Shipment            │
         │                                     │────────────────────────────>│
         │                                     │                             │
         │                                     │  Tracking# + Label          │
         │                                     │<────────────────────────────│
         │                                     │                             │
         │                                     │  Save Order to DB           │
         │                                     │──────┐                      │
         │                                     │      │                      │
         │                                     │<─────┘                      │
         │                                     │                             │
         │  200 { orderId, orderStatus }       │                             │
         │<────────────────────────────────────│                             │
         │                                     │                             │
```

### Request Object - Request Parts Order

**Endpoint:** `POST /request_order`

**Content-Type:** `application/json`

```json
{
  "orderId": "b2fcf908-7147-47f8-bb9a-5875ba515082",
  "address": {
    "business": "ACME Corp",
    "name": "John Doe",
    "addressLine1": "6909 Harry Hines Blvd",
    "addressLine2": "",
    "city": "Dallas",
    "state": "TX",
    "zipCode": 75235
  },
  "parts": [
    {
      "sku": "9001410,9001412,9001325"
    }
  ]
}
```

**Request Fields:**

| Field                    | Type     | Required | Description                                                    |
|--------------------------|----------|----------|----------------------------------------------------------------|
| `orderId`                | string   | Yes      | Unique order identifier (UUID format)                          |
| `address`                | object   | Yes      | Shipping address object                                        |
| `address.business`       | string   | Yes      | Business/company name                                          |
| `address.name`           | string   | Yes      | Recipient name                                                 |
| `address.addressLine1`   | string   | Yes      | Street address line 1                                          |
| `address.addressLine2`   | string   | No       | Street address line 2 (suite, apt, etc.)                       |
| `address.city`           | string   | Yes      | City                                                           |
| `address.state`          | string   | Yes      | State (2-letter code, e.g., "TX")                              |
| `address.zipCode`        | integer  | Yes      | ZIP code                                                       |
| `parts`                  | array    | Yes      | Array of part objects                                          |
| `parts[].sku`            | string   | Yes      | Comma-separated SKU numbers (e.g., `"9001410,9001412"`)        |

> **Note:** Multiple SKUs can be included in a single `sku` string separated by commas. Each SKU is individually validated against the inventory database.

### Response Object - Request Parts Order

**Success Response (HTTP 200):**

```json
{
  "orderId": "b2fcf908-7147-47f8-bb9a-5875ba515082",
  "orderStatus": "Requested"
}
```

### Error Responses

**Order Already Exists (HTTP 200):**

If an order with the same `orderId` already exists in the system:

```json
{
  "orderStatus": "Order Already Exists"
}
```

**Validation Failed (HTTP 200):**

If SKU validation fails, required address fields are missing, or address validation fails via UPS:

```json
{
  "orderStatus": "Failed"
}
```

**Common failure reasons:**
- Missing required fields (`orderId`, `address.business`, `address.name`, `address.addressLine1`, `address.zipCode`, `address.state`)
- SKU not found in inventory
- Invalid shipping address (UPS address validation failure)
- UPS shipping label generation failure

---

## Order Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PARTS ORDER LIFECYCLE                              │
│                                                                             │
│  ┌──────────┐     ┌───────────┐     ┌──────────┐     ┌───────────┐         │
│  │ Request  │────>│ Unshipped │────>│ Shipped  │────>│ Delivered │         │
│  │ Order    │     │           │     │          │     │           │         │
│  └──────────┘     └───────────┘     └──────────┘     └───────────┘         │
│       │                │                                                    │
│       │                │            ┌──────────┐                            │
│       │                └───────────>│ Delayed  │                            │
│       │                             └──────────┘                            │
│       │                                                                     │
│       v                                                                     │
│  ┌──────────┐     ┌───────────┐                                             │
│  │ Failed   │────>│ Reprocess │──── (back to Unshipped)                     │
│  │          │     │           │                                              │
│  └──────────┘     └───────────┘                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Status      | Description                                                           |
|-------------|-----------------------------------------------------------------------|
| Requested   | Order received and being processed                                    |
| Unshipped   | Order created with shipping label, awaiting shipment                  |
| Failed      | Order creation failed (invalid address, SKU not found, etc.)          |
| Shipped     | Package has been shipped via UPS                                      |
| Delayed     | Shipment has been delayed                                             |
| Delivered   | Package delivered to recipient                                        |

---

## Example Requests

### cURL Example

**Request Parts Order:**

```bash
curl -X POST \
  'https://ad0e2kb0yf.execute-api.us-east-1.amazonaws.com/Prod/request_order' \
  -H 'Content-Type: application/json' \
  -d '{
    "orderId": "b2fcf908-7147-47f8-bb9a-5875ba515082",
    "address": {
      "business": "ACME Corp",
      "name": "John Doe",
      "addressLine1": "6909 Harry Hines Blvd",
      "addressLine2": "",
      "city": "Dallas",
      "state": "TX",
      "zipCode": 75235
    },
    "parts": [
      {
        "sku": "9001410,9001412,9001325"
      }
    ]
  }'
```

**Check Order Status:**

```bash
curl -X GET \
  'https://ad0e2kb0yf.execute-api.us-east-1.amazonaws.com/Prod/order_status?order_id=b2fcf908-7147-47f8-bb9a-5875ba515082'
```

### Python Example

```python
import requests
import uuid

url = "https://ad0e2kb0yf.execute-api.us-east-1.amazonaws.com/Prod/request_order"

payload = {
    "orderId": str(uuid.uuid4()),
    "address": {
        "business": "ACME Corp",
        "name": "John Doe",
        "addressLine1": "6909 Harry Hines Blvd",
        "addressLine2": "",
        "city": "Dallas",
        "state": "TX",
        "zipCode": 75235
    },
    "parts": [
        {
            "sku": "9001410,9001412,9001325"
        }
    ]
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.json())

# Expected Output:
# 200
# {"orderId": "...", "orderStatus": "Requested"}
```

### Postman Setup

1. **Method:** `POST`
2. **URL:** `https://ad0e2kb0yf.execute-api.us-east-1.amazonaws.com/Prod/request_order`
3. **Headers:**
   - `Content-Type`: `application/json`
4. **Body** (raw JSON):

```json
{
  "orderId": "0b74dc86-2ad7-41df-8d3b-73d58cf86e6d5",
  "address": {
    "business": "LQTEST1225",
    "name": "LQTEST1225",
    "addressLine1": "6909 Harry Hines Blvd",
    "addressLine2": "",
    "city": "Dallas",
    "state": "TX",
    "zipCode": 75235
  },
  "parts": [
    {
      "sku": "9001410,9001412,9001325"
    }
  ]
}
```

---

## Internal Processing Details

### SKU Validation

Each SKU in the comma-separated `sku` string is individually validated against the inventory database. The system looks up each SKU and retrieves the following fields:

- `Id` - Internal inventory ID
- `model` - Part model number
- `name` - Part name
- `type` - Part type (e.g., Cable, Part)
- `SKU` - SKU number

If any SKU is not found in inventory, the entire order is rejected with `{"orderStatus": "Failed"}`.

### Address Validation

Shipping addresses are validated using the **UPS Address Validation API (XAV)** before generating a shipping label. The validation checks:

- Address completeness
- Address classification (residential vs commercial)
- ZIP code accuracy

If address validation fails, the order is saved with status **"Failed"** and can be reprocessed with a corrected address through the Reprocess Orders page.

### Shipping Label

Upon successful validation, a **UPS shipping label** is generated and stored in S3. The label is accessible through the Letronics order management web interface under the "Print Label" action.
