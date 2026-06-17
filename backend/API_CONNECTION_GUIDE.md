# API Connection Guide for External Applications

## ✅ Authentication Setup Complete!

Your Smart Search API now has API key authentication enabled.

---

## 📋 Application Configuration

### Fill in your application's connection form with these values:

| Field | Value |
|-------|-------|
| **OpenAPI Version** | `3.0.0` |
| **API Title** | `Decathlon Smart Search API` |
| **API Version** | `1.0.0` |
| **Description** | `AI-powered shopping search API using fine-tuned Qwen 3:4B` |
| **Server URL** | `http://localhost:5000/api/v1` |
| **Server Description** | `Local development server` |
| **Path** | `/shopping/smart-search` |
| **HTTP Method** | `POST` |
| **Operation ID** | `smart_search` |

### Authentication Configuration:

| Field | Value |
|-------|-------|
| **Authorization Type** | `API Key` |
| **Auth Type (Location)** | `Header` |
| **Auth Key** | `API-KEY` ⚠️ **Must use hyphen, NOT underscore** |
| **Auth Value** | `decathlon_smart_search_2024_secure_key_abc123xyz` |
| **Header Name** | `API-KEY` |

---

## ⚠️ Important Note About Header Name

**The header MUST be `API-KEY` (with hyphen), NOT `API_KEY` (with underscore).**

**Why?** HTTP headers with underscores are dropped by most HTTP clients and servers. Use hyphens instead.

- ❌ Wrong: `API_KEY: value` (underscore - will be dropped)
- ✅ Correct: `API-KEY: value` (hyphen - works perfectly)

---

## 📄 Complete OpenAPI Configuration

If your application needs the full OpenAPI JSON, use this:

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "Decathlon Smart Search API",
    "version": "1.0.0",
    "description": "AI-powered shopping search API using fine-tuned Qwen 3:4B. Understands natural language queries and returns personalized product recommendations with semantic search."
  },
  "servers": [
    {
      "url": "http://localhost:5000/api/v1",
      "description": "Local development server"
    }
  ],
  "paths": {
    "/shopping/smart-search": {
      "post": {
        "summary": "Smart search with AI recommendations",
        "description": "Complete AI-powered search: parses natural language query, executes hybrid search, and returns products with personalized recommendations.",
        "operationId": "smart_search",
        "security": [
          {
            "apiKey": []
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                  "query": {
                    "type": "string",
                    "description": "Natural language search query (e.g. 'Horse riding boots for kids below 3000')"
                  }
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Search results with products and AI recommendations"
          },
          "401": {
            "description": "Unauthorized - API key missing"
          },
          "403": {
            "description": "Forbidden - Invalid API key"
          },
          "400": {
            "description": "Missing or invalid query parameter"
          },
          "503": {
            "description": "Fine-tuned model not available"
          }
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "apiKey": {
        "type": "apiKey",
        "in": "header",
        "name": "API-KEY",
        "description": "API key for authentication (use hyphen, not underscore)"
      }
    }
  }
}
```

This is also saved in: `backend/OPENAPI_CONFIG.json`

---

## 🧪 Testing the Connection

### Test 1: Using curl

```bash
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -d '{"query": "Horse riding boots for kids below 3000"}'
```

### Test 2: Using Python

```python
import requests

response = requests.post(
    'http://localhost:5000/api/v1/shopping/smart-search',
    headers={
        'Content-Type': 'application/json',
        'API-KEY': 'decathlon_smart_search_2024_secure_key_abc123xyz'
    },
    json={'query': 'Horse riding boots for kids below 3000'}
)

print(response.json())
```

### Test 3: Run the test script

```bash
cd backend
python3 test_api_auth.py
```

---

## 📊 Example Request & Response

### Request

```json
POST /api/v1/shopping/smart-search
Headers:
  Content-Type: application/json
  API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz

Body:
{
  "query": "Horse riding boots for kids below 3000"
}
```

### Response (200 OK)

```json
{
  "status": "success",
  "user_query": "Horse riding boots for kids below 3000",
  "parsed_query": {
    "intent": "search",
    "search_request": {
      "sport": "Horse Riding",
      "category": "Riding Boots",
      "keywords": ["boots", "kids"],
      "price_limit": 3000,
      "experience_level": null
    }
  },
  "intent": "search",
  "recommendations": "I found some great options for kids' riding boots...",
  "products": [
    {
      "product_id": "8765432",
      "name": "Fouganza Schooling Kids Boots",
      "brand": "Fouganza",
      "price": 2499.0,
      "rating": 4.6,
      "similarity": 0.92,
      "description": "...",
      "image_url": "...",
      "product_url": "..."
    }
  ],
  "metadata": {
    "model": "Qwen 3:4B Fine-tuned (MLX)",
    "search_type": "hybrid",
    "products_found": 10
  }
}
```

---

## 🔐 Changing the API Key

The API key is stored in `backend/.env`:

```bash
API_KEY=decathlon_smart_search_2024_secure_key_abc123xyz
```

To change it:

1. Edit `backend/.env`
2. Update the `API_KEY` value
3. Restart the API: `python3 api_swagger.py`
4. Update your application's "Auth Value" with the new key

---

## ❌ Common Errors

### 401 Unauthorized
**Cause**: Missing API key header  
**Fix**: Add `API-KEY` header to your request

### 403 Forbidden
**Cause**: Invalid API key  
**Fix**: Check that the API key matches the value in `backend/.env`

### 400 Bad Request
**Cause**: Missing or empty "query" field  
**Fix**: Include `{"query": "your search text"}` in the request body

### 503 Service Unavailable
**Cause**: Fine-tuned model not found  
**Fix**: Run `cd training && python3 train_mlx.py`

---

## ✅ Quick Checklist

Before connecting your application:

- [ ] API is running: `python3 api_swagger.py` (in `backend/` directory)
- [ ] Test authentication works: `python3 test_api_auth.py`
- [ ] Use header name: `API-KEY` (with hyphen)
- [ ] Use header value: `decathlon_smart_search_2024_secure_key_abc123xyz`
- [ ] Server URL: `http://localhost:5000/api/v1`
- [ ] Path: `/shopping/smart-search`
- [ ] Method: `POST`
- [ ] Body: `{"query": "your search text"}`

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:5000/docs (Swagger UI)
- **API Guide**: `backend/API_GUIDE.md`
- **Test Script**: `backend/test_api_auth.py`
- **OpenAPI Config**: `backend/OPENAPI_CONFIG.json`
- **Environment Config**: `backend/.env`

---

## 🎉 You're Ready!

Your API is configured and ready to connect. Fill in the values above in your application's configuration form.

**Key Points to Remember:**
1. Header name: `API-KEY` (hyphen, not underscore)
2. Header value: `decathlon_smart_search_2024_secure_key_abc123xyz`
3. Server URL: `http://localhost:5000/api/v1`
4. Make sure the API is running before connecting

Good luck! 🚀
