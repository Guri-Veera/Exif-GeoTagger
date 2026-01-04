from PIL import Image, ImageDraw, ImageFont
import textwrap
from functools import lru_cache

@lru_cache(maxsize=32)
def get_font(path: str, size: int):
    return ImageFont.truetype(path, size)

def create_location_card(imgW, imgH, map_img, headerAddrLine, addrLine, locText, dateText):
    # ---------------- PASS 1: Initial geometry ----------------
    cardW = int(0.9 * imgW)
    initialCardH = int(0.25 * min(imgW, imgH))

    title_font = get_font(r"../assets/Inter_18pt-Bold.ttf", size=int(0.14 * initialCardH))
    normal_font = get_font(r"../assets/Inter_18pt-Regular.ttf", size=int(0.10 * initialCardH))

    mapDim_est = initialCardH
    left_margin = 0.05 * cardW
    right_margin = 0.1 * cardW

    # ---------------- PASS 2: Loose wrapping for height estimate ----------------
    loose_char_limit = 80

    wrapped_header_loose = "\n".join(
        textwrap.wrap(headerAddrLine, width=int(loose_char_limit * 0.8))
    )
    wrapped_address_loose = "\n".join(
        textwrap.wrap(addrLine, width=loose_char_limit)
    )
    wrapped_loc_loose = locText

    text_blocks_loose = [
        (wrapped_header_loose, title_font),
        (wrapped_address_loose, normal_font),
        (wrapped_loc_loose, normal_font),
        (dateText, normal_font)
    ]

    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    spacing = 0.05 * initialCardH
    total_text_height = 0

    for text, font in text_blocks_loose:
        bbox = temp_draw.multiline_textbbox((0, 0), text, font=font)
        total_text_height += (bbox[3] - bbox[1]) + spacing

    padding_y = 0.3 * initialCardH

    # ---------------- PASS 3: Final geometry ----------------
    cardH = int(min(mapDim_est, total_text_height + padding_y))
    mapDim = cardH

    # ---------------- PASS 4: Final wrapping ----------------
    textW = cardW - mapDim - left_margin - right_margin
    char_limit = max(10, int(textW / (int(0.1 * initialCardH) * 0.5)))

    wrapped_header = "\n".join(
        textwrap.wrap(headerAddrLine, width=int(char_limit * 0.8))
    )
    wrapped_address = "\n".join(
        textwrap.wrap(addrLine, width=char_limit)
    )
    wrapped_loc = locText

    text_blocks = [
        (wrapped_header, title_font),
        (wrapped_address, normal_font),
        (wrapped_loc, normal_font),
        (dateText, normal_font)
    ]

    # ---------------- PASS 5: Draw card ----------------
    card = Image.new("RGBA", (cardW, cardH), (0, 0, 0, 0))
    textBox = ImageDraw.Draw(card)

    # Background
    textBox.rounded_rectangle(
        (1.1 * cardH, 0, cardW, cardH),
        radius=32,
        fill=(43, 43, 43, 230)
    )

    # Re-measure FINAL wrapped text height
    final_text_height = 0
    for text, font in text_blocks:
        bbox = textBox.multiline_textbbox((0, 0), text, font=font)
        final_text_height += (bbox[3] - bbox[1]) + spacing

    current_y = (cardH - final_text_height) // 2
    text_x = 1.25 * mapDim

    for text, font in text_blocks:
        textBox.multiline_text((text_x, current_y), text, fill="white", font=font)
        bbox = textBox.multiline_textbbox((text_x, current_y), text, font=font)
        current_y += (bbox[3] - bbox[1]) + spacing

    # ---------------- Map masking & paste ----------------
    map_img = map_img.resize((mapDim, mapDim))

    map_mask = Image.new('L', (mapDim * 4, mapDim * 4), 0)
    draw_mask = ImageDraw.Draw(map_mask)
    draw_mask.rounded_rectangle(
        (0, 0, mapDim * 4, mapDim * 4),
        radius=32 * 4,
        fill=255
    )
    map_mask = map_mask.resize(map_img.size, Image.Resampling.LANCZOS)
    map_img.putalpha(map_mask)

    card.paste(map_img, (0, 0), mask=map_img)

    return card