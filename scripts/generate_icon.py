"""
Generates high-resolution brand icon for Project Sift:
- assets/sift_icon.png (512x512 PNG)
- assets/sift_icon.ico (multi-resolution Windows icon: 256, 128, 64, 48, 32, 16)
- src/dist/favicon.ico
"""

import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
os.makedirs(ASSETS_DIR, exist_ok=True)

size = 512
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 1. Dark Slate Rounded Background Tile
radius = 110
bg_color = (15, 23, 42, 255) # Slate 900
border_color = (51, 65, 85, 255) # Slate 700
draw.rounded_rectangle([16, 16, size - 16, size - 16], radius=radius, fill=bg_color, outline=border_color, width=8)

# 2. Geometric Sift Funnel / Filter Geometry (Cyan to Emerald)
# Top horizontal funnel bar
draw.polygon([(90, 110), (422, 110), (390, 150), (122, 150)], fill=(56, 189, 248, 255)) # Sky 400

# Middle funnel trapezoid
draw.polygon([(130, 165), (382, 165), (312, 260), (200, 260)], fill=(14, 165, 233, 255)) # Sky 500

# Sieve Mesh Lines in middle
for y in [185, 205, 225, 245]:
    draw.line([(150 + (y-165)*0.5, y), (362 - (y-165)*0.5, y)], fill=(186, 230, 253, 200), width=3)

# Lower column (triage funnel spout)
draw.rounded_rectangle([210, 275, 302, 360], radius=16, fill=(16, 185, 129, 255)) # Emerald 500

# Droplet / Delta indicator at bottom
draw.ellipse([230, 380, 282, 432], fill=(52, 211, 153, 255), outline=(16, 185, 129, 255), width=4)

# Margin delta badge glyph ("S")
try:
    font = ImageFont.truetype("arial.ttf", 46)
except Exception:
    font = None

if font:
    draw.text((256, 315), "S", fill=(255, 255, 255, 255), font=font, anchor="mm")
    draw.text((256, 404), "+", fill=(15, 23, 42, 255), font=font, anchor="mm")

# Save master PNG
png_path = os.path.join(ASSETS_DIR, "sift_icon.png")
img.save(png_path, "PNG")
print(f"[*] Generated master icon PNG: {png_path}")

# Generate multi-size ICO
ico_path = os.path.join(ASSETS_DIR, "sift_icon.ico")
icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
ico_images = [img.resize(s, Image.Resampling.LANCZOS) for s in icon_sizes]
ico_images[0].save(
    ico_path,
    format="ICO",
    sizes=icon_sizes,
    append_images=ico_images[1:],
)
print(f"[*] Generated multi-resolution Windows ICO: {ico_path}")

# Copy to src/dist/favicon.ico if src/dist exists
dist_favicon = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "dist", "favicon.ico"))
if os.path.isdir(os.path.dirname(dist_favicon)):
    ico_images[4].save(dist_favicon, format="ICO") # 32x32 favicon
    print(f"[*] Updated web favicon: {dist_favicon}")
