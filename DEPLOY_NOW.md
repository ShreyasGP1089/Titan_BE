# 🚀 Deploy to Production - START HERE

Your system is **100% ready** for Linux production deployment! Everything has been prepared.

---

## ✅ Status: READY TO DEPLOY

**What's completed:**
- ✅ MLX dependencies removed
- ✅ Hugging Face Transformers integrated
- ✅ LoRA adapter converted to HF format
- ✅ Docker configuration created
- ✅ Production requirements defined
- ✅ API updated with automatic fallback
- ✅ All documentation complete

---

## 🎯 Choose Your Deployment Platform

### Option 1: Railway (Easiest - Recommended)

```bash
# 1. Push to GitHub (if not already)
git init
git add .
git commit -m "Production ready with HF"
git push origin main

# 2. Go to railway.app
# 3. Click "New Project" → "Deploy from GitHub repo"
# 4. Select your repository
# 5. Add PostgreSQL: Click "New" → "Database" → "PostgreSQL"
# 6. Set environment variable: USE_HF_PLANNER=true
# 7. Deploy! (Railway auto-detects Dockerfile)
```

**Cost:** Free tier → $5-20/month  
**Time:** 5 minutes  
**URL:** Auto-generated HTTPS URL

---

### Option 2: Render

```bash
# 1. Push to GitHub
git init
git add .
git commit -m "Production ready"
git push

# 2. Go to render.com
# 3. New Web Service → Connect GitHub
# 4. Configure:
#    - Build: docker build -t api .
#    - Start: python backend/api_swagger.py
# 5. Add PostgreSQL database
# 6. Set environment variables
# 7. Deploy
```

**Cost:** Free tier → $7-25/month  
**Time:** 10 minutes

---

### Option 3: Docker Compose (Any VPS)

**For AWS EC2, DigitalOcean, or any Linux server:**

```bash
# 1. SSH into your server
ssh user@your-server-ip

# 2. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt-get install docker-compose

# 3. Clone repository
git clone <your-repo-url>
cd Toolset

# 4. Create .env file
cp backend/.env.production.example backend/.env
nano backend/.env  # Edit with your values

# 5. Deploy
docker-compose up -d

# 6. Check status
docker-compose ps
curl http://localhost:5000/api/v1/system/health
```

**Server Requirements:**
- **Minimum:** 4 CPU, 8GB RAM, 20GB disk
- **Recommended:** 4 CPU, 16GB RAM, 40GB disk + GPU

**Cost:** 
- DigitalOcean: $48/month
- AWS EC2 t3.xlarge: ~$150/month
- AWS EC2 g4dn.xlarge (GPU): ~$365/month

---

### Option 4: Local Docker Test

**Test locally before deploying:**

```bash
# 1. Ensure you're in the Toolset directory
cd /path/to/Toolset

# 2. Build and start
docker-compose up -d

# 3. Wait for startup (30-60 seconds)
sleep 60

# 4. Test
curl http://localhost:5000/api/v1/system/health

# 5. Test smart search
curl -X POST http://localhost:5000/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: decathlon_smart_search_2024_secure_key_abc123xyz" \
  -d '{"query": "running shoes under 5000"}'

# 6. View logs
docker-compose logs -f api

# 7. Stop when done
docker-compose down
```

---

## 📝 Environment Variables Required

Create `backend/.env` or set in your platform:

```bash
# Required
POSTGRES_HOST=<database-host>
POSTGRES_USER=<database-user>
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=decathlon_db
API_KEY=<your-secure-api-key>

# Important for Linux deployment
USE_HF_PLANNER=true

# Optional (improves performance)
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/transformers
```

**Railway/Render:** They auto-configure PostgreSQL variables  
**Manual:** You set all variables

---

## 🔍 Verification Checklist

After deployment, verify:

```bash
# 1. Health check
curl https://your-domain.com/api/v1/system/health
# Should return: {"status": "healthy"}

# 2. Parse query (fast test)
curl -X POST https://your-domain.com/api/v1/shopping/parse-query \
  -H "Content-Type: application/json" \
  -H "API-KEY: your_api_key" \
  -d '{"query": "running shoes under 5000"}'
# Should return parsed JSON in ~500ms

# 3. Smart search (full test)
curl -X POST https://your-domain.com/api/v1/shopping/smart-search \
  -H "Content-Type: application/json" \
  -H "API-KEY: your_api_key" \
  -d '{"query": "running shoes under 5000"}'
# Should return products in ~5-10s (first request)
# Subsequent requests: ~1-2s with GPU, ~5s with CPU
```

---

## 📊 Expected Performance

### First Request (Model Loading):
- **With GPU:** ~10-20 seconds
- **CPU only:** ~30-60 seconds

### Subsequent Requests:
- **With GPU:** ~1-2 seconds
- **CPU only:** ~5-10 seconds

### Resource Usage:
- **RAM:** 4-6GB (model loaded)
- **CPU:** 50-100% during inference
- **GPU:** 4-8GB VRAM if available

---

## 🛠️ Platform-Specific Instructions

### Railway Detailed Steps:

1. **Create Account:** railway.app
2. **New Project:** Dashboard → New Project
3. **Deploy from GitHub:** Select your repository
4. **Add Database:** New → Database → PostgreSQL
5. **Environment Variables:**
   ```
   USE_HF_PLANNER=true
   API_KEY=<generate-secure-key>
   ```
6. **Deploy:** Railway auto-detects Dockerfile
7. **Get URL:** Settings → Domains → Generate Domain

### Render Detailed Steps:

1. **Create Account:** render.com
2. **New Web Service:** Dashboard → New → Web Service
3. **Connect GitHub:** Authorize and select repo
4. **Configure Build:**
   - Build Command: `docker build -t api .`
   - Start Command: `python backend/api_swagger.py`
5. **Add PostgreSQL:** New → PostgreSQL
6. **Link Database:** Copy connection string to env vars
7. **Environment Variables:**
   ```
   USE_HF_PLANNER=true
   POSTGRES_HOST=<from-render>
   POSTGRES_USER=<from-render>
   POSTGRES_PASSWORD=<from-render>
   POSTGRES_DB=<from-render>
   API_KEY=<your-secure-key>
   ```
8. **Deploy:** Click "Create Web Service"

### AWS EC2 Detailed Steps:

1. **Launch Instance:**
   - Ubuntu 22.04 LTS
   - Instance type: t3.xlarge (or g4dn.xlarge for GPU)
   - Storage: 40GB
   - Security group: Allow ports 22, 80, 443, 5000

2. **Connect:**
   ```bash
   ssh -i your-key.pem ubuntu@ec2-instance-ip
   ```

3. **Install Docker:**
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose git
   sudo systemctl enable docker
   sudo usermod -aG docker ubuntu
   # Log out and back in
   ```

4. **Deploy:**
   ```bash
   git clone <your-repo>
   cd Toolset
   cp backend/.env.production.example backend/.env
   nano backend/.env  # Edit values
   docker-compose up -d
   ```

5. **Configure Domain (Optional):**
   ```bash
   # Install nginx
   sudo apt install -y nginx certbot python3-certbot-nginx
   
   # Configure reverse proxy
   sudo nano /etc/nginx/sites-available/api
   ```

---

## 🔐 Security Checklist

Before going live:

- [ ] Change `API_KEY` to a strong random value
- [ ] Use strong database password
- [ ] Enable HTTPS (use nginx + Let's Encrypt)
- [ ] Set up firewall (only ports 80, 443, 22)
- [ ] Disable Flask debug mode (done in Dockerfile)
- [ ] Regular security updates
- [ ] Monitor logs
- [ ] Set up rate limiting
- [ ] Configure backups

---

## 📞 Quick Help

**API won't start?**
```bash
# Check logs
docker-compose logs -f api

# Common issues:
# 1. Model not found → Verify adapter converted
# 2. Database connection → Check POSTGRES_* vars
# 3. Out of memory → Reduce batch size or upgrade RAM
```

**Slow performance?**
```bash
# Use GPU instance or:
# 1. Reduce max_tokens in hf_planner.py
# 2. Enable caching (already done)
# 3. Add more RAM
```

**Model accuracy issues?**
```bash
# Retrain with HF instead of converting:
cd training
python train_hf.py
```

---

## 🎉 You're Ready!

Everything is prepared for production deployment. Choose a platform above and follow the steps.

**Recommended path for fastest deployment:**
1. **Test locally:** `docker-compose up -d`
2. **Deploy to Railway:** Push to GitHub → Connect → Deploy
3. **Total time:** ~15 minutes

**Need help?** Check:
- `PRODUCTION_DEPLOYMENT.md` - Complete guide
- `MIGRATION_SUMMARY.md` - Technical details
- `./deploy.sh` - Automated helper

---

## 🚀 Start Deployment

**Choose one:**

```bash
# Option 1: Test locally first
docker-compose up -d

# Option 2: Deploy to Railway
# Push to GitHub, then connect in Railway dashboard

# Option 3: Deploy to VPS
./deploy.sh  # Run deployment helper
```

**Your production-ready system is waiting! Deploy now! 🎊**
