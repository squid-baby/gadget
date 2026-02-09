# LEELOO Display UI

A retro terminal-style music sharing device UI for Raspberry Pi with a Waveshare 3.5" LCD display.

---

## Current Version: Python/Pillow + Frame Animations (Active)

The production Python version running on Raspberry Pi with smooth frame expansion animations.

### Quick Start (Raspberry Pi)

```bash
# Copy files to Pi
scp -r * pi@gadget.local:/home/pi/

# SSH into Pi
ssh pi@gadget.local

# Run the main UI
python3 gadget_main.py

# Or run the animation demo
python3 demo_weather_typewriter.py
```

### Display Layout (480x320px)

```
┌─────────────────────┬─────────────────┐
│  ┌─────────────────┐│                 │
│  │ weather         ││                 │
│  │ 72°F  ☀9  🌧1   ││                 │
│  └─────────────────┘│                 │
│  ┌─────────────────┐│   Album Art     │
│  │ time            ││   (240x240px)   │
│  │ 2:47 PM · Feb 4 ││                 │
│  └─────────────────┘│                 │
│  ┌─────────────────┐│                 │
│  │ messages        ││                 │
│  │ Amy, Ben        ││                 │
│  └─────────────────┘│                 │
│  ┌─────────────────┐│                 │
│  │ album           ││                 │
│  │ Cinnamon Chasers││                 │
│  │ "Doorways"      ││                 │
│  │ pushed by Amy   ││                 │
│  └─────────────────┘│                 │
└─────────────────────┴─────────────────┘
       ~215px                ~265px
```

### Frame Expansion Animations

Each info panel can expand to full height with smooth animations:

- **Weather**: Expands to show detailed forecast with typewriter effect
- **Time**: Expands to show calendar/schedule
- **Messages**: Expands to show full message threads
- **Album**: Expands to show track details and artist info

#### Animation System

The frame animator uses:
- **Row-by-row file I/O** to avoid screen tearing (critical fix!)
- **24fps** pre-processed frames with cubic ease-in-out
- **1.5 second** expand/collapse duration
- **Typewriter effect** for content reveal

### Architecture

```
leeloo_ui_manager.py    # Event-driven state machine (THE PRO SOLUTION)
├── UIState enum        # NORMAL, EXPANDING, EXPANDED, COLLAPSING
├── LeelooUIManager     # Single owner of framebuffer
│   ├── expand_weather()
│   ├── expand_time()
│   ├── expand_messages()
│   └── expand_album()
└── FrameAnimator       # Handles expand/collapse animations

gadget_main.py          # Main loop (updates display every second)
gadget_display.py       # LeelooDisplay class (renders PIL images)
display/
├── frame_animator.py   # Frame expansion animation system
└── fast_fb.py          # Fast framebuffer utilities (numpy)
```

### Key Technical Fixes

#### Screen Tearing Solution

The Waveshare 3.5" LCD (ILI9486) has no vsync. We fixed tearing by:

1. **`fbcon=map:0`** in `/boot/firmware/cmdline.txt` - Stops Linux console from fighting for fb1
2. **Row-by-row file I/O** instead of numpy memmap - Matches working GIF demo approach
3. **Single process architecture** - UI manager owns the framebuffer exclusively

#### Critical Files Changed

```bash
# /boot/firmware/cmdline.txt - Changed fbcon=map:01 to fbcon=map:0
# This keeps the console on fb0 (HDMI) and leaves fb1 (LCD) for our exclusive use
```

### Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Navy | `#1A1D2E` | Background |
| Green | `#719253` | Album box border |
| Purple | `#9C93DD` | Time box border |
| Lavender | `#A7AFD4` | Messages box border |
| Tan | `#C2995E` | Weather box border |
| Rose | `#D6697F` | "pushed by" accent |
| White | `#FFFFFF` | Text |

### Animation Timings

| Effect | Duration |
|--------|----------|
| Frame expand/collapse | 1.5s (36 frames @ 24fps) |
| Typewriter text | 30ms per character |
| Line pause | 100ms between lines |
| Content display | 10 seconds default |

### Running Demos

```bash
# Stop the main service first
sudo systemctl stop gadget.service

# Run the weather expansion demo
python3 demo_weather_typewriter.py

# Run the UI manager demo
python3 leeloo_ui_manager.py

# Run the reaction GIF demo
python3 demo_message_expand.py

# Re-enable the main service
sudo systemctl start gadget.service
```

### File Structure

```
TipTop UI/
├── gadget_main.py           # Main loop service
├── gadget_display.py        # LeelooDisplay renderer
├── leeloo_ui_manager.py     # Event-driven UI state machine
├── demo_weather_typewriter.py   # Weather expansion demo
├── demo_message_expand.py   # Reaction GIF demo
├── display/
│   ├── __init__.py
│   ├── frame_animator.py    # Expand/collapse animations
│   └── fast_fb.py           # Fast framebuffer (numpy)
├── doorways-album.jpg       # Album artwork
└── README.md
```

---

## React Version (Development Preview)

The React version is used for desktop prototyping only.

### Quick Start

```bash
cd Retro-Music-Panel
npm install
npm run dev
# Open http://localhost:3000
```

---

## Deployment to Raspberry Pi

### 1. Configure Display Driver

The Waveshare 3.5" LCD uses the `fb_ili9486` driver via `dtoverlay=waveshare35a`.

### 2. Fix Console Mapping

Edit `/boot/firmware/cmdline.txt` and change:
```
fbcon=map:01  →  fbcon=map:0
```

This prevents the Linux console from writing to the LCD (fb1).

### 3. Install as Service

```bash
sudo systemctl enable gadget.service
sudo systemctl start gadget.service
```

### 4. Troubleshooting

**Screen tearing during animations?**
- Make sure `fbcon=map:0` is set
- Stop any other processes writing to fb1
- Use `sudo systemctl stop gadget.service` before running demos

**Boot screen showing through UI?**
- This is fbcon fighting for the display
- The `fbcon=map:0` fix should resolve this

**Animation too slow?**
- Pre-processing should complete in ~280ms
- Playback should hit 24fps
- Check for other CPU-intensive processes

---

## Questions?

Refer to the design decisions document for the full spec.
