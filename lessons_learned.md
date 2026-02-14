# Lessons Learned - LEELOO Spotify Integration (Feb 14, 2026)

## Session Summary
Successfully deployed production relay server, implemented Spotify OAuth, and integrated "Currently Playing" feature with proper album art sizing.

---

## Key Lessons

### 1. **DNS Propagation Takes Time**
- DNS changes at Namecheap typically take 5-10 minutes
- Always wait for propagation before testing SSL certificates
- Use `dig` or online tools to verify DNS before proceeding

### 2. **WebSocket Connections Need Keepalive**
- Long-running WebSocket connections drop without periodic pings
- Implement `ping_interval` and `ping_timeout` in websockets library
- OAuth flows that wait for callbacks need robust connection handling

### 3. **Token Refresh is Critical for Spotify API**
- Access tokens expire after 1 hour (3600 seconds)
- Always implement automatic token refresh using refresh_token
- Handle 401 responses by refreshing token and retrying request
- Keep refresh_token even if not returned in refresh response

### 4. **OAuth State Parameter Must Match Device ID**
- The `state` parameter in OAuth URL identifies which device is authorizing
- Device must maintain WebSocket connection with same ID while user authorizes
- Connection drops = missed callback = failed authorization

### 5. **Image Sizing Must Be Centralized**
**Problem:** Multiple scripts created album art at different sizes, causing inconsistent display
**Solution:** 
- Create single source of truth: `leeloo_album_art.py`
- All scripts import from centralized utility
- Standard size: 243×304 (244px art + 60px bar)
- Never create images ad-hoc in individual scripts

### 6. **Cache Invalidation is Hard**
- Old cached files persist even after code changes
- Always clear cache when changing image dimensions
- Main loop must be restarted to load new code
- Check file timestamps to debug which code version created files

### 7. **Process Management Requires Restarts**
- Long-running processes (gadget_main.py) don't auto-reload code
- Check PID and start time to verify which version is running
- Use `sudo pkill -f` to kill by command name, not just PID
- Always verify process restarted before testing changes

### 8. **QR Code UX: Don't Compete with Main UI**
**Original approach:** Full-screen QR code takeover
**Better approach:** Show QR code in album art area only
- Preserves main UI (weather, time, contacts)
- User knows where to scan
- Less jarring experience

### 9. **Spotify API Scopes Are Specific**
- `user-read-currently-playing` - Get what's playing right now
- `user-read-playback-state` - Get full playback state (includes paused)
- Request minimal scopes needed for feature

### 10. **Priority Logic for Music Display**
**Implementation:**
1. Shared music (from crew) - shows for 30 minutes
2. Currently playing (from Spotify) - shows when nothing shared
3. Source flag (`source` field) determines display label:
   - `"currently_playing"` → "pushed by: You"
   - `"shared"` → "pushed by: [Name]"

---

## Technical Patterns

### Centralized Utilities Pattern
```python
# ❌ BAD: Each script creates images differently
def download_album_art_script1():
    img.resize((640, 640))  # Wrong size

def download_album_art_script2():
    img.resize((300, 300))  # Different wrong size

# ✅ GOOD: Single source of truth
from leeloo_album_art import download_and_create_album_art
album_art = download_and_create_album_art(url, uri, dir, source)
```

### Token Refresh Pattern
```python
response = requests.get(api_url, headers={"Authorization": f"Bearer {token}"})

if response.status_code == 401:
    # Token expired, refresh it
    new_token = refresh_access_token()
    # Retry with new token
    response = requests.get(api_url, headers={"Authorization": f"Bearer {new_token}"})
```

### WebSocket Keepalive Pattern
```python
async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
    while True:
        try:
            message = await asyncio.wait_for(ws.recv(), timeout=30)
            # Process message
        except asyncio.TimeoutError:
            # Send ping to keep connection alive
            await ws.send(json.dumps({"type": "ping"}))
```

---

## Architecture Decisions

### Why Relay Server?
- Raspberry Pi can't expose ports to internet (behind NAT)
- Spotify OAuth requires publicly accessible callback URL
- Relay server acts as middleman:
  1. Device connects via WebSocket
  2. OAuth callback received at public URL
  3. Tokens sent to device via existing WebSocket

### Why 243×304 for Album Art?
- Display layout reserves 243px width for album art column
- 304px height = 244px art + 60px bar (scancode or "Now Playing")
- Matches existing placeholder dimensions exactly
- Consistent with shared music scancode format

### Why 30-Minute Priority for Shared Music?
- Shared music is intentional social action (more important)
- Currently playing is passive background info
- 30 minutes gives time to listen and engage
- After expiry, reverts to showing currently playing

---

## Debugging Techniques Used

1. **Check file timestamps** - `stat filename` to see when created
2. **Verify process age** - `ps aux` shows start time, identify old code
3. **Check image dimensions** - `file image.jpg` shows actual size
4. **Test imports** - Run utility standalone to verify it works
5. **Check API responses** - Print status codes and raw JSON
6. **Trace execution** - `grep -n` to find which functions are called
7. **Verify cache state** - List cached files to see what exists

---

## Production Deployment Checklist

- [ ] DNS configured and propagated
- [ ] SSL certificate obtained and auto-renewing
- [ ] PM2 configured for auto-restart on crash/reboot
- [ ] Firewall configured (only 22, 80, 443 open)
- [ ] Environment variables secured (not in Git)
- [ ] WebSocket keepalive implemented
- [ ] Token refresh implemented
- [ ] Cache clearing mechanism in place
- [ ] Process restart procedure documented
- [ ] Health check endpoint working

---

## Files Created This Session

### Production Server
- `/root/leeloo-relay/server.js` - WebSocket relay server
- `/root/leeloo-relay/.env` - Spotify credentials (secured)
- `/etc/nginx/sites-available/leeloobot.xyz` - Nginx config

### Pi Scripts
- `leeloo_album_art.py` - Centralized album art utility ⭐
- `leeloo_music_manager.py` - Currently playing integration
- `spotify_auth_qr.py` - QR code OAuth flow
- `spotify_tokens.json` - Cached Spotify tokens

### Documentation
- `RELAY_DEPLOYMENT_SUCCESS.md` - Complete deployment log
- `lessons_learned.md` - This file

---

## Key Metrics

- **Deployment time**: ~25 minutes (DNS to working relay)
- **OAuth flow time**: ~10 seconds (scan to tokens saved)
- **Music update interval**: 30 seconds
- **Shared music priority**: 30 minutes
- **Token lifespan**: 1 hour (auto-refresh)

---

## What Worked Well

1. ✅ Centralized album art utility prevents size inconsistencies
2. ✅ QR code in album art area preserves main UI
3. ✅ Automatic token refresh prevents auth failures
4. ✅ Priority system gives shared music preference
5. ✅ WebSocket keepalive prevents connection drops
6. ✅ PM2 process management ensures uptime

## What to Improve

1. 🔄 Add visual indicator when token is expired
2. 🔄 Implement token expiry tracking (don't wait for 401)
3. 🔄 Add retry logic for network failures
4. 🔄 Cache album art for offline display
5. 🔄 Add album art for shared music with scancodes

---

Made with ♪ by squid-baby & Claude Sonnet 4.5
