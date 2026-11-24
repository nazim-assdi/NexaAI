from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
SIZE = 1024

base = Image.new("RGBA", (SIZE, SIZE), (4, 13, 27, 255))
px = base.load()
for y in range(SIZE):
    t = y / (SIZE - 1)
    color = (5 + int(2*t), 16 + int(8*t), 32 + int(15*t), 255)
    for x in range(SIZE):
        px[x, y] = color

glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse((180, 170, 850, 850), fill=(0, 225, 229, 76))
base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(130)))

decor = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(decor)
draw.arc((84, 84, 940, 940), 205, 337, fill=(0, 211, 235, 205), width=17)
draw.arc((84, 84, 940, 940), 26, 158, fill=(35, 115, 190, 190), width=14)
for x, y in [(185,355),(839,355),(218,735),(805,735),(512,160),(512,864)]:
    draw.ellipse((x-19,y-19,x+19,y+19), fill=(6,24,43,255), outline=(24,225,238,255), width=8)
    draw.ellipse((x-6,y-6,x+6,y+6), fill=(185,255,255,255))

ribbon=[(226,766),(226,275),(315,246),(706,629),(706,250),(807,250),(807,730),(719,769),(328,394),(328,766)]
shadow=Image.new("RGBA",(SIZE,SIZE),(0,0,0,0))
ImageDraw.Draw(shadow).polygon([(x+12,y+22) for x,y in ribbon],fill=(0,0,0,175))
base=Image.alpha_composite(base,shadow.filter(ImageFilter.GaussianBlur(30)))

mask=Image.new("L",(SIZE,SIZE),0)
ImageDraw.Draw(mask).polygon(ribbon,fill=255)
gradient=Image.new("RGBA",(SIZE,SIZE),(0,0,0,0))
gp=gradient.load()
for y in range(SIZE):
    for x in range(SIZE):
        if x<512:
            v=max(0.0,min(1.0,(x+y*0.18)/720))
            c=(int(8+8*v),int(125+105*v),int(175+70*v),255)
        else:
            v=max(0.0,min(1.0,(x-390)/520))
            c=(int(115+115*v),int(165+80*v),int(195+60*v),255)
        gp[x,y]=c
gradient.putalpha(mask)
base=Image.alpha_composite(base,gradient)

bevel=Image.new("RGBA",(SIZE,SIZE),(0,0,0,0))
bd=ImageDraw.Draw(bevel)
bd.line([(242,730),(242,302),(313,281),(691,649),(691,273)],fill=(194,255,255,230),width=10,joint="curve")
bd.line([(790,280),(790,713),(722,742),(341,376),(341,747)],fill=(5,48,85,220),width=11,joint="curve")
base=Image.alpha_composite(base,bevel.filter(ImageFilter.GaussianBlur(2)))

circuit=Image.new("RGBA",(SIZE,SIZE),(0,0,0,0))
cd=ImageDraw.Draw(circuit)
cd.line([(190,512),(360,512),(414,458),(610,458),(664,512),(834,512)],fill=(8,226,239,210),width=14,joint="curve")
cd.line([(190,545),(360,545),(414,599),(610,599),(664,545),(834,545)],fill=(151,237,245,190),width=8,joint="curve")
cd.ellipse((446,446,578,578),fill=(0,199,228,110),outline=(167,255,255,255),width=9)
cd.ellipse((475,475,549,549),fill=(111,250,255,255))
base=Image.alpha_composite(base,circuit.filter(ImageFilter.GaussianBlur(1)))

rounded=Image.new("L",(SIZE,SIZE),0)
ImageDraw.Draw(rounded).rounded_rectangle((8,8,SIZE-8,SIZE-8),radius=178,fill=255)
base.putalpha(Image.composite(base.getchannel("A"),Image.new("L",(SIZE,SIZE),0),rounded))
base.resize((512,512),Image.Resampling.LANCZOS).save(ASSETS/"nexa-ai-icon.png",optimize=True)
base.save(ASSETS/"nexa-ai.ico",format="ICO",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(f"Created NTech NexaAI icon: {ASSETS/'nexa-ai.ico'}")
