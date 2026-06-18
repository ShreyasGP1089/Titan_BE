# Deployment Checklist for Render

Use this checklist to deploy your AI Shopping Search backend to Render.

---

## ⚠️ PRE-DEPLOYMENT (CRITICAL)

### 1. Security - Rotate API Key
- [ ] The API key in `backend/.env` was exposed in git
- [ ] Generate a new secure API key:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- [ ] Update `backend/.env` locally (do NOT commit)
- [ ] Add new API key to Render environment variables

### 2. Database - Verify Neon PostgreSQL
- [ ] Neon database is running
- [ ] Products table has data: `SELECT COUNT(*) FROM products;`
- [ ] Embeddings are computed: `SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL;`
- [ ] Get connection string for Render

### 3. Code - Final Checks
- [ ] All changes committed to git
- [ ] `.gitignore` excludes `.env`
- [ ] `backend/requirements_production.txt` has correct dependencies
- [ ] `Dockerfile` uses gunicorn
- [ ] `USE_HF_PLANNER=true` in docker-compose.yml

---

## 📦 DEPLOYMENT STEPS

### Step 1: Create Render Account
1. Go to https://render.com
2. Sign up / Log in
3. Connect your GitHub account

### Step 2: Create New Web Service
1. Click "New" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Name**: `shopping-api` (or your choice)
   - **Environment**: Docker
   - **Branch**: `main`
   - **Instance Type**: Standard (512MB RAM minimum)

### Step 3: Set Environment Variables
In Render dashboard, add these environment variables:

```
DATABASE_URL = <your_neon_postgresql_url>
API_KEY = <your_new_secure_api_key>
USE_HF_PLANNER = true
PORT = 5000
FLASK_ENV = production
```

**How to get DATABASE_URL from Neon**:
1. Log into Neon dashboard
2. Go to your project → Connection Details
3. Copy the connection string (starts with `postgresql://`)

### Step 4: Deploy
1. Click "Create Web Service"
2. Render will automatically:
   - Clone your repository
   - Build Docker image
   - Start the service

**Deployment time**: ~10-15 minutes (first time)

### Step 5: Monitor Deployment
- [ ] Watch the "Logs" tab for build progress
- [ ] Look for: `✓ Model loaded and ready`
- [ ] Wait for: `Your service is live at https://...`

---

## ✅ POST-DEPLOYMENT TESTING

### Test 1: Health Check
```bash
curl https://YOUR-APP.onrender.com/api/v1/system/health
```

**Expected**:
```json
{
  "status": "healthy",
  "model": "Qwen 2.5 Coder 3B (Hugging Face)",
  "timestamp": "..."
}
```

### Test 2: Parse Query (with API key)
```bash
curl -X POST https://YOUR-APP.onrender.com/api/v1/shopping/parse-query \
  -H "API-KEY: YOUR_NEW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "yoga mat for beginners"}'
```

**Expected**:
```json
{
  "status": "success",
  "parsed_query": {
    "intent": "search",
    "search_request": {
      "sport": "Yoga",
      "keywords": ["mat", "beginners"],
      ...
    }
  }
}
```

### Test 3: Smart Search (with API key)
```bash
curl -X POST https://YOUR-APP.onrender.com/api/v1/shopping/smart-search \
  -H "API-KEY: YOUR_NEW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

**Expected**:
```json
{
  "status": "success",
  "user_query": "running shoes under 5000",
  "parsed_query": { ... },
  "products": [ ... ],
  "recommendations": "I found some great running shoes...",
  "metadata": {
    "model": "Qwen 2.5 Coder 3B (Hugging Face)",
    "products_found": 10
  }
}
```

### Test 4: Swagger Documentation
Visit in browser:
```
https://YOUR-APP.onrender.com/api/v1/docs
```

You should see interactive Swagger UI with all endpoints.

---

## 🐛 TROUBLESHOOTING

### Issue: "Application failed to respond"
**Cause**: Model loading timeout  
**Fix**: 
- Check logs for OOM errors
- Upgrade to Standard Plus instance (1GB RAM)
- Or reduce model size

### Issue: "502 Bad Gateway"
**Cause**: Gunicorn worker timeout during model loading  
**Fix**: First request takes 10-15s (model loads once, then cached)

### Issue: "Database connection error"
**Cause**: Wrong `DATABASE_URL`  
**Fix**: Verify connection string in Render environment variables

### Issue: "401 Unauthorized"
**Cause**: Missing or wrong `API-KEY` header  
**Fix**: Use `API-KEY` (with hyphen, not underscore)

---

## 📊 MONITORING

### Check Service Health
- **Render Dashboard** → Your Service → "Logs"
- Look for errors or warnings
- Monitor response times

### Key Metrics to Watch
- **Response Time**: Should be 2-5s (after initial load)
- **Memory Usage**: Should stay under 80% of instance RAM
- **Error Rate**: Should be < 1%

### Logs to Watch For
✅ Good:
```
INFO - ✓ Model loaded and ready
INFO - ✓ Successfully parsed: intent=search
INFO - ✓ Query processed successfully: 10 products found
```

⚠️ Warning:
```
WARNING - Using base model without fine-tuning
WARNING - JSON repair needed
```

❌ Error:
```
ERROR - Query parsing error
ERROR - Database connection failed
ERROR - Out of memory
```

---

## 🔧 MAINTENANCE

### Regular Tasks
- [ ] Monitor error logs weekly
- [ ] Check response times
- [ ] Update dependencies monthly (security patches)

### Optional Improvements
- [ ] Add LoRA fine-tuning (see `DEPLOYMENT_STATUS.md`)
- [ ] Enable caching layer (Redis)
- [ ] Add monitoring (Sentry, Datadog)
- [ ] Scale to multiple instances (load balancing)

---

## 📞 GETTING HELP

### Render Support
- Dashboard → Help → Submit Ticket
- Render Community Forum: https://community.render.com

### Debugging
1. **Check Logs**: Most issues show up in logs
2. **Test Locally**: Run `docker-compose up` to reproduce
3. **Verify Environment**: Double-check all environment variables
4. **Check Database**: Test connection from local machine

---

## ✅ SUCCESS CRITERIA

Your deployment is successful when:

- [x] Health endpoint returns 200 OK
- [x] Parse-query endpoint returns structured JSON
- [x] Smart-search endpoint returns products + recommendations
- [x] No errors in Render logs
- [x] Response time < 10s for first request, < 5s for subsequent
- [x] API key authentication works

---

## 🎉 CONGRATULATIONS!

If all tests pass, your AI Shopping Search API is live!

**Next Steps**:
1. Integrate with your frontend application
2. Monitor performance and errors
3. Consider adding LoRA fine-tuning for better accuracy (see `DEPLOYMENT_STATUS.md`)

**Your API is now ready for production traffic! 🚀**
