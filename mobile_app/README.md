# NETRA Mobile App — Vercel Deployment

This folder contains the NETRA mobile PWA (Progressive Web App).
Deploy ONLY this `mobile_app/` folder to Vercel.

## Deploy to Vercel (Web UI — easiest)

1. Go to https://vercel.com → Sign up / Login (free)
2. Click **"Add New Project"**
3. Import from GitHub (push `mobile_app/` to a GitHub repo), OR
4. Use **Vercel CLI** (see below)

## Deploy via Vercel CLI

```powershell
# Install Vercel CLI (requires Node.js)
npm install -g vercel

# From inside the mobile_app/ folder:
cd mobile_app
vercel

# Follow prompts:
# - Link to existing project? No → create new
# - Project name: netra-surveillance
# - Which directory: ./ (current)
# - Override settings? No
```

Vercel will give you a URL like: `https://netra-surveillance.vercel.app`

## Alternative: Drag & Drop Deploy (no CLI needed)

1. Go to https://vercel.com/new
2. Choose "Deploy from file"  
3. Drag and drop the entire `mobile_app/` folder
4. Done!

## After Deployment

1. Open the Vercel URL on your **phone**
2. Go to Settings tab
3. Enter your Cloudflare tunnel URL
4. Tap "Enable Notifications" 
5. Add to home screen (iOS: Share → Add to Home Screen, Android: Menu → Install App)

## Files in this folder

| File | Purpose |
|---|---|
| `index.html` | Full mobile app (SPA) |
| `public/manifest.json` | PWA install metadata |
| `public/sw.js` | Service worker (push + offline) |
| `public/logo.png` | App icon (192px) |
| `public/icon-192.png` | PWA icon |
| `public/icon-512.png` | PWA splash icon |
| `vercel.json` | Vercel SPA routing config |
