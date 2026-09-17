# 🛡️ NETRA — Cloudflare Zero Trust Tunnel Setup
## Permanent Public URL for Your Surveillance Backend

This guide gives your local PC a **permanent public HTTPS URL** 
(e.g. `https://netra.yourdomain.com`) so your Vercel mobile app 
can always reach the detection engine from anywhere.

---

## Prerequisites
- Free Cloudflare account: https://dash.cloudflare.com/sign-up
- A domain added to Cloudflare (even a free one from Freenom/Namecheap)
- `cloudflared` installed on your PC

---

## Step 1 — Install cloudflared

**Windows (download installer):**
```
https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi
```
Run the MSI installer. Then open a new PowerShell.

---

## Step 2 — Login to Cloudflare

```powershell
cloudflared tunnel login
```
- A browser window opens → log in to your Cloudflare account
- Select your domain → click **Authorize**

---

## Step 3 — Create the tunnel

```powershell
cloudflared tunnel create netra
```

This creates a tunnel named `netra` and saves a credentials JSON file.
Note the **Tunnel ID** shown (looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

---

## Step 4 — Create tunnel config file

Create the file: `C:\Users\<YourName>\.cloudflared\config.yml`

```yaml
tunnel: netra
credentials-file: C:\Users\<YourName>\.cloudflared\<TUNNEL-ID>.json

ingress:
  - hostname: netra.yourdomain.com
    service: http://localhost:5001
  - service: http_status:404
```

Replace `<YourName>`, `<TUNNEL-ID>`, and `yourdomain.com` with your values.

---

## Step 5 — Route DNS

```powershell
cloudflared tunnel route dns netra netra.yourdomain.com
```

This adds a CNAME record in your Cloudflare DNS automatically.

---

## Step 6 — Run as Windows Service (starts automatically on boot)

```powershell
cloudflared service install
```

Or run manually each time:
```powershell
cloudflared tunnel run netra
```

---

## Step 7 — Start NETRA

```powershell
cd "C:\Users\mishr\OneDrive\Desktop\testp\person-detection-in-survilliance-camera"
.\.venv\Scripts\activate
pip install -r requirements.txt
python livedetector.py
```

---

## Step 8 — Configure Mobile App

1. Open NETRA mobile app on your phone
2. Go to **Settings** tab
3. Enter your tunnel URL: `https://netra.yourdomain.com`
4. Tap **Save & Connect**
5. Tap **Enable Notifications** to subscribe to push alerts

---

## Verification

Test in your browser:
- `https://netra.yourdomain.com/api/status` → should return JSON
- `https://netra.yourdomain.com/video_feed` → should show live video

---

## Quick Start (no custom domain needed)

If you don't have a domain yet, use a **Quick Tunnel** (URL changes each session):

```powershell
cloudflared tunnel --url http://localhost:5001
```

Copy the printed URL (e.g. `https://random-words.trycloudflare.com`) 
and paste it in the mobile app Settings each time.
