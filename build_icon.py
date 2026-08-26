from PIL import Image, ImageDraw


def main() -> None:
    size = 256
    image = Image.new("RGBA", (size, size), "#0B1220")
    draw = ImageDraw.Draw(image)
    for y in range(size):
        mix = y / (size - 1)
        color = (
            int(18 + (43 - 18) * mix),
            int(63 + (127 - 63) * mix),
            int(112 + (255 - 112) * mix),
            255,
        )
        draw.line((0, y, size, y), fill=color)
    draw.rounded_rectangle((18, 18, 238, 238), radius=48, outline=(255, 255, 255, 70), width=5)
    draw.polygon([(92, 62), (92, 166), (180, 114)], fill="#FFFFFF")
    draw.rounded_rectangle((52, 181, 204, 198), radius=8, fill="#FFFFFF")
    draw.rounded_rectangle((76, 207, 180, 222), radius=7, fill="#FFD966")
    image.save("app.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()

