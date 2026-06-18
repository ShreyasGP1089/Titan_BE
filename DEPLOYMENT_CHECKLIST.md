# Deployment Checklist

Quick checklist to track deployment progress.

---

## Pre-Deployment

- [x] LoRA adapter files present (35 MB + 11 MB)
- [x] Adapter path correct: `training/outputs/qwen25_1_5b_lora_hf/`
- [x] Local server uses Qwen2.5-1.5B-Instruct
- [x] Local server loads LoRA (REQUIRED, not optional)
- [x] Health endpoint exists (`/health`)
- [x] Parse query endpoint exists (`/parse-query`)
- [x] Parse query returns structured JSON (not string)
- [x] Backend uses HTTP client (no direct model loading)
- [x] `requirements_local_server.txt` exists
- [x] `requirements_render.txt` exists (NO PyTorch)
- [x] Test script exists (`test_local_model.py`)
- [x] Verification script passes (`./verify_ready.sh`)

---

## Local Testing

- [ ] Dependencies installed: `pip install -r requirements_local_server.txt`
- [ ] Local server starts: `python3 local_model_server.py`
- [ ] LoRA adapter loads successfully
- [ ] Server shows "Model ready on MPS/CUDA/CPU"
- [ ] Health check passes: `curl http://localhost:8001/health`
- [ ] Health response shows `"adapter_loaded": true`
- [ ] All 5 tests pass: `python3 test_local_model.py`

**Test Results:**
- [ ] Test 1: Health Check ✓
- [ ] Test 2: Direct HTTP Generation ✓
- [ ] Test 3: LocalModelClient ✓
- [ ] Test 4: Parse Query Endpoint ✓
- [ ] Test 5: Client Parse Query ✓

---

## ngrok Setup

- [ ] ngrok installed: `brew install ngrok` (or download)
- [ ] ngrok started: `ngrok http 8001`
- [ ] HTTPS URL obtained (e.g., `https://xxxx.ngrok-free.app`)
- [ ] ngrok health check passes: `curl https://YOUR-URL/health`
- [ ] ngrok parse query works: `curl -X POST https://YOUR-URL/parse-query -H "Content-Type: application/json" -d '{"query": "test"}'`

**Your ngrok URL:**
```
[Write your ngrok URL here]
```

---

## Render Configuration

### Environment Variables Set:
- [ ] `LOCAL_MODEL_URL` = your ngrok URL
- [ ] `MODEL_REQUEST_TIMEOUT` = 120
- [ ] `POSTGRES_HOST` = your postgres host
- [ ] `POSTGRES_PORT` = 5432
- [ ] `POSTGRES_DB` = your database name
- [ ] `POSTGRES_USER` = your username
- [ ] `POSTGRES_PASSWORD` = your password
- [ ] `API_KEY` = your API key
- [ ] `EMBEDDING_MODEL` = sentence-transformers/all-MiniLM-L6-v2

### Build Configuration:
- [ ] Using `backend/requirements_render.txt` (NOT requirements_local_server.txt)
- [ ] Build command correct
- [ ] Start command correct
- [ ] Python version 3.11

---

## Deployment

- [ ] Code committed: `git add . && git commit -m "Split architecture"`
- [ ] Code pushed: `git push origin main`
- [ ] Render deployment started
- [ ] Render build successful
- [ ] Render deployment live
- [ ] Memory usage < 512 MB ✓

---

## Production Verification

- [ ] Render health check: `curl https://your-app.onrender.com/health`
- [ ] Render connects to local server successfully
- [ ] Test query parsing: `curl -X POST https://your-app.onrender.com/api/chat -H "Content-Type: application/json" -H "X-API-Key: your-key" -d '{"query": "running shoes under 5000"}'`
- [ ] Response contains parsed intent
- [ ] Response contains products
- [ ] Response contains recommendations
- [ ] End-to-end flow works (frontend → Render → ngrok → Mac → back)

---

## Post-Deployment

- [ ] Monitor Render memory usage
- [ ] Monitor ngrok request count
- [ ] Check response times
- [ ] Verify LoRA adapter being used (not base model)
- [ ] Test multiple queries
- [ ] Test both "search" and "task" intents

---

## Known Limitations

- ⚠️ ngrok free tier: 40 requests/minute
- ⚠️ ngrok tunnel expires after 8 hours (need to restart)
- ⚠️ Mac must stay on and running local server
- ⚠️ Network must be stable for Mac → ngrok connection

---

## Rollback Plan

If deployment fails:

1. Check logs:
   - [ ] Local server logs
   - [ ] Render logs
   - [ ] ngrok dashboard

2. Verify connections:
   - [ ] Local server running
   - [ ] ngrok tunnel active
   - [ ] Render can reach ngrok URL

3. Test components individually:
   - [ ] Test local server: `curl http://localhost:8001/health`
   - [ ] Test ngrok: `curl https://YOUR-URL/health`
   - [ ] Test Render: Check Render logs

---

## Success Criteria

Deployment is successful when:

- ✅ Local server loads LoRA adapter (REQUIRED)
- ✅ Health endpoint returns 200 with `"adapter_loaded": true`
- ✅ Parse query returns structured JSON (not string)
- ✅ Render backend < 512 MB RAM
- ✅ End-to-end query works (frontend → Render → Mac → back)
- ✅ No errors in Render logs
- ✅ Responses contain products and recommendations

---

## Commands Quick Reference

```bash
# Verify everything is ready
./verify_ready.sh

# Install local server dependencies
pip install -r requirements_local_server.txt

# Start local server
python3 local_model_server.py

# Run tests (in another terminal)
python3 test_local_model.py

# Start ngrok (in another terminal)
ngrok http 8001

# Test local health
curl http://localhost:8001/health

# Test ngrok health
curl https://YOUR-NGROK-URL/health

# Deploy to Render
git add . && git commit -m "Ready to deploy" && git push origin main
```

---

## Contacts & Resources

- **ngrok Dashboard:** https://dashboard.ngrok.com
- **Render Dashboard:** https://dashboard.render.com
- **Documentation:** `TEST_AND_DEPLOY.md`
- **Architecture:** `SPLIT_ARCHITECTURE.md`

---

**Last Updated:** June 18, 2026  
**Status:** Pre-Deployment Complete ✅  
**Next Step:** Local Testing
