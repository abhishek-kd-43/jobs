from PIL import Image, ImageDraw
img = Image.new('RGB', (16, 16), color = (232, 93, 4))
d = ImageDraw.Draw(img)
d.text((4, 0), "OJ", fill=(255, 255, 255))
img.save('favicon.ico')
