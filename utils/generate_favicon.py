from PIL import Image, ImageDraw, ImageFont
import os

# Crear una imagen para el favicon (32x32 píxeles)
img = Image.new('RGBA', (32, 32), color=(34, 34, 34, 255))
draw = ImageDraw.Draw(img)

# Dibujar círculo exterior
draw.ellipse([(2, 2), (30, 30)], outline=(255, 255, 255, 255), width=2)

# Dibujar círculo interior
draw.ellipse([(8, 8), (24, 24)], outline=(255, 255, 255, 255), width=2)

# Dibujar el número 2 en el centro (si la fuente está disponible)
try:
    # Intentar usar una fuente
    font = ImageFont.load_default()
    draw.text((13, 7), "2", fill=(255, 255, 255, 255), font=font)
except Exception as e:
    print(f"Error al dibujar texto: {e}")
    # Alternativa: dibujar un punto blanco
    draw.ellipse([(14, 14), (18, 18)], fill=(255, 255, 255, 255))

# Guardar como favicon.ico
output_path = os.path.join('static', 'favicon.ico')
img.save(output_path, format='ICO')
print(f"Favicon generado en {output_path}") 