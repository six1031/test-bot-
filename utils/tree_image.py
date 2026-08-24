from PIL import Image, ImageDraw, ImageFont
from io import BytesIO


# --------------------------------------------------
# BASE SETTINGS
# --------------------------------------------------

BASE_WIDTH = 2400
BASE_HEIGHT = 1600

GOLD = (212, 175, 55)
NODE_BG = (20, 20, 20)
TEXT_COLOR = GOLD

BASE_FONT_SIZE = 48

NODE_PADDING_X = 60
NODE_PADDING_Y = 40


# --------------------------------------------------
# FONT
# --------------------------------------------------

def auto_font(label, base_size):
    """Use a readable built-in font."""

    try:
        return ImageFont.load_default(size=base_size)
    except TypeError:
        return ImageFont.load_default()


# --------------------------------------------------
# TEXT MEASUREMENT
# --------------------------------------------------

def measure_text(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


# --------------------------------------------------
# DRAW NODE
# --------------------------------------------------

def draw_node(draw, x, y, text, font):

    tw, th = measure_text(draw, text, font)

    node_w = tw + NODE_PADDING_X
    node_h = th + NODE_PADDING_Y

    x1 = x - node_w // 2
    y1 = y - node_h // 2
    x2 = x + node_w // 2
    y2 = y + node_h // 2

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=25,
        outline=GOLD,
        fill=NODE_BG,
        width=4,
    )

    draw.text(
        (x - tw / 2, y - th / 2),
        text,
        font=font,
        fill=TEXT_COLOR
    )


# --------------------------------------------------
# GENERATE TREE IMAGE
# --------------------------------------------------

def generate_tree_image(
    user_name,
    spouse_name,
    caregivers,
    littles,
    middles,
    siblings,
    handler,
    pets,
):

    # --------------------------------------------------
    # BUILD NODE LIST
    # --------------------------------------------------

    nodes = []

    nodes.append(("YOU: " + user_name, "center"))

    if spouse_name:
        nodes.append(("Spouse: " + spouse_name, "center"))

    for name in caregivers:
        nodes.append(("Caregiver: " + name, "care"))

    for name in siblings:
        nodes.append(("Sibling: " + name, "sib"))

    if handler:
        nodes.append(("Handler: " + handler, "handler"))

    for name in pets:
        nodes.append(("Pet: " + name, "pet"))

    for name in littles:
        nodes.append(("Little: " + name, "little"))

    for name in middles:
        nodes.append(("Middle: " + name, "middle"))

    # --------------------------------------------------
    # DYNAMIC CANVAS SIZE / AUTO ZOOM
    # --------------------------------------------------

    total_nodes = len(nodes)

    row_counts = {}

    for label, group in nodes:
        row_counts[group] = row_counts.get(group, 0) + 1

    max_people_in_row = max(
        row_counts.values(),
        default=1
    )

    active_rows = len(row_counts)

    width = max(
        1400,
        min(
            2400,
            900 + (max_people_in_row * 320)
        )
    )

    height = max(
        1000,
        min(
            1600,
            700 + (active_rows * 120)
        )
    )

    # --------------------------------------------------
    # LOAD BACKGROUND
    # --------------------------------------------------

    background = Image.open(
        "utils/tree_bg.jpg"
    ).convert("RGB")

    background = background.resize(
        (width, height)
    )

    img = background.copy()

    # --------------------------------------------------
    # DARK OVERLAY
    # --------------------------------------------------

    overlay = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 60)
    )

    img = Image.alpha_composite(
        img.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(img)

    # --------------------------------------------------
    # LAYOUT ROWS
    # --------------------------------------------------

    rows = {
        "care": [],
        "sib": [],
        "handler": [],
        "pet": [],
        "center": [],
        "little": [],
        "middle": [],
    }

    for label, group in nodes:
        rows[group].append(label)

    # --------------------------------------------------
    # Y POSITIONS
    # --------------------------------------------------

    y_positions = {
        "care": height * 0.20,
        "sib": height * 0.35,
        "handler": height * 0.45,
        "pet": height * 0.55,
        "center": height * 0.50,
        "little": height * 0.65,
        "middle": height * 0.75,
    }

    # --------------------------------------------------
    # DRAW NODES
    # --------------------------------------------------

    for group, labels in rows.items():

        if not labels:
            continue

        y = int(y_positions[group])

        # Build fonts and calculate the real width
        # of every name box first.
        fonts = []
        node_widths = []

        for label in labels:

            font = auto_font(
                label,
                BASE_FONT_SIZE
            )

            fonts.append(font)

            text_width, text_height = measure_text(
                draw,
                label,
                font
            )

            node_width = (
                text_width + NODE_PADDING_X
            )

            node_widths.append(
                node_width
            )

        # Space between the edges of each box
        box_gap = 35

        # Calculate total width of this row
        total_row_width = (
            sum(node_widths)
            + box_gap * (len(labels) - 1)
        )

        # Start the whole row in the centre
        current_x = (
            width - total_row_width
        ) // 2

        # Draw every node
        for label, font, node_width in zip(
            labels,
            fonts,
            node_widths
        ):

            # X position is the centre of this box
            x = (
                current_x
                + node_width // 2
            )

            draw_node(
                draw,
                x,
                y,
                label,
                font
            )

            # Move to the next box
            current_x += (
                node_width
                + box_gap
            )
    # --------------------------------------------------
    # SAVE IMAGE
    # --------------------------------------------------

    buffer = BytesIO()

    # JPEG does not support RGBA.
    # Convert the final image back to RGB.

    img = img.convert("RGB")

    img.save(
        buffer,
        format="JPEG",
        quality=95
    )

    buffer.seek(0)

    return buffer
