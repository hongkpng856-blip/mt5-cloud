#!/usr/bin/env python3
"""生成 icon-bot（Lucide bot icon）風格嘅 PNG — tkinter 警告視窗用
完全照住 Lucide bot.svg 線條風格：圓角方形頭框 + 天線 + 耳線 + 眼線（emerald 色）
viewBox 24x24 → 96x96（×4），stroke-width=2 → 6px
"""
import os
from PIL import Image, ImageDraw

EMERALD = (16, 185, 129)   # #10b981
W = 6                       # stroke 寬度（96px 版）

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guard_icon_bot.png')

S = 96
img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 照 Lucide bot.svg（24x24 → 96x96，×4）：
# 1. 天線 M12 8V4H8 → (48,32)→(48,16)→(32,16)
d.line([48, 32, 48, 16], fill=EMERALD, width=W)
d.line([48, 16, 32, 16], fill=EMERALD, width=W)
# 2. 頭部 rect(4,8,16,12 rx=2) → (16,32)-(80,80) rx=8
d.rounded_rectangle([16, 32, 80, 80], radius=8, outline=EMERALD, width=W)
# 3. 左耳 M2 14h2 → (8,56)-(16,56)
d.line([8, 56, 16, 56], fill=EMERALD, width=W)
# 4. 右耳 M20 14h2 → (80,56)-(88,56)
d.line([80, 56, 88, 56], fill=EMERALD, width=W)
# 5. 左眼 M9 13v2 → (36,52)-(36,60)
d.line([36, 52, 36, 60], fill=EMERALD, width=W)
# 6. 右眼 M15 13v2 → (60,52)-(60,60)
d.line([60, 52, 60, 60], fill=EMERALD, width=W)

img.save(OUT)
print(f"✅ icon-bot（Lucide 線條風格）已生成: {OUT} ({os.path.getsize(OUT)} bytes)")
