#!/usr/bin/env python3
"""
Cria um ícone .ico para o aplicativo Elysius Whitelist.
Execute este script para gerar o icon.ico antes do build.
"""

from PIL import Image, ImageDraw, ImageFont

def create_icon():
    """Cria o ícone do aplicativo em múltiplos tamanhos."""
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Cores do tema Elysius (azul/dourado mitológico)
        bg_color = "#1e3a8a"  # Azul escuro
        border_color = "#fbbf24"  # Dourado
        text_color = "#fcd34d"  # Dourado claro

        # Desenhar círculo de fundo
        margin = max(1, size // 16)
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=bg_color,
            outline=border_color,
            width=max(1, size // 16),
        )

        # Adicionar "E" no centro
        try:
            font_size = int(size * 0.5)
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        text = "E"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - size // 10
        draw.text((x, y), text, fill=text_color, font=font)

        images.append(img)

    # Salvar como .ico com múltiplos tamanhos
    images[0].save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )

    print("icon.ico criado com sucesso!")
    print(f"Tamanhos incluidos: {sizes}")


if __name__ == "__main__":
    create_icon()
