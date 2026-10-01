from PIL import Image, ImageDraw

DARK_BG = (15, 23, 42, 255)      # #0F172A
TEAL = (14, 165, 233, 255)        # #0EA5E9
ORANGE = (249, 115, 22, 255)      # #F97316
WHITE = (255, 255, 255, 255)

# 1. Logo Principal (1024x1024)
logo = Image.new('RGBA', (1024, 1024), DARK_BG)
draw = ImageDraw.Draw(logo)
draw.ellipse([520, 260, 740, 480], fill=ORANGE)
draw.ellipse([260, 460, 520, 720], fill=TEAL)
draw.ellipse([420, 360, 760, 700], fill=TEAL)
draw.rectangle([390, 520, 680, 720], fill=TEAL)
draw.arc([220, 220, 804, 804], start=200, end=340, fill=WHITE, width=16)
logo.save('climapp_logo.png')

# 2. Ícono PWA (512x512)
icon = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
icon_draw = ImageDraw.Draw(icon)
icon_draw.rounded_rectangle([0, 0, 512, 512], radius=110, fill=DARK_BG)
icon_draw.ellipse([260, 110, 390, 240], fill=ORANGE)
icon_draw.ellipse([120, 220, 270, 370], fill=TEAL)
icon_draw.ellipse([200, 170, 380, 350], fill=TEAL)
icon_draw.rectangle([195, 260, 330, 370], fill=TEAL)
icon.save('climapp_icon.png')

print("Imágenes creadas: climapp_logo.png y climapp_icon.png")