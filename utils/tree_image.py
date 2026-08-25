from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import math


# ==================================================
# COLOURS / STYLE
# ==================================================

GOLD = (212, 175, 55)

NODE_BG = (
    20,
    20,
    20,
    235,
)

TEXT_COLOR = GOLD

LINE_COLOR = (
    212,
    175,
    55,
    210,
)


# ==================================================
# FONT SIZES
# ==================================================

BASE_FONT_SIZE = 42
SMALL_FONT_SIZE = 30
TITLE_FONT_SIZE = 54


# ==================================================
# NODE SETTINGS
# ==================================================

NODE_PADDING_X = 70
NODE_PADDING_Y = 44

NODE_GAP = 45
ROW_GAP = 190

# Distance between you and spouse
CENTER_GAP = 280


# ==================================================
# FONT
# ==================================================

def auto_font(
    size,
    bold=False,
):
    """
    Use DejaVu Sans when available.

    Falls back to Pillow's built-in font.
    """

    try:

        filename = (
            "DejaVuSans-Bold.ttf"
            if bold
            else "DejaVuSans.ttf"
        )

        return ImageFont.truetype(
            filename,
            size=size,
        )

    except OSError:

        try:

            return ImageFont.load_default(
                size=size
            )

        except TypeError:

            return ImageFont.load_default()


# ==================================================
# TEXT MEASUREMENT
# ==================================================

def measure_text(
    draw,
    text,
    font,
    spacing=6,
):

    bbox = draw.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        spacing=spacing,
        align="center",
    )

    return (
        bbox[2] - bbox[0],
        bbox[3] - bbox[1],
    )


# ==================================================
# NODE SIZE
# ==================================================

def get_node_size(
    draw,
    text,
    font,
):

    text_width, text_height = (
        measure_text(
            draw,
            text,
            font,
        )
    )

    node_width = (
        text_width
        + NODE_PADDING_X
    )

    node_height = (
        text_height
        + NODE_PADDING_Y
    )

    return (
        node_width,
        node_height,
    )


# ==================================================
# DRAW NODE
# ==================================================

def draw_node(
    draw,
    x,
    y,
    text,
    font,
    accent_width=4,
):

    text_width, text_height = (
        measure_text(
            draw,
            text,
            font,
        )
    )

    node_width = (
        text_width
        + NODE_PADDING_X
    )

    node_height = (
        text_height
        + NODE_PADDING_Y
    )

    x1 = int(
        x
        - node_width / 2
    )

    y1 = int(
        y
        - node_height / 2
    )

    x2 = int(
        x
        + node_width / 2
    )

    y2 = int(
        y
        + node_height / 2
    )

    # --------------------------------------------------
    # NODE BOX
    # --------------------------------------------------

    draw.rounded_rectangle(
        (
            x1,
            y1,
            x2,
            y2,
        ),
        radius=25,
        outline=GOLD,
        fill=NODE_BG,
        width=accent_width,
    )

    # --------------------------------------------------
    # NODE TEXT
    # --------------------------------------------------

    draw.multiline_text(
        (
            x,
            y,
        ),
        text,
        font=font,
        fill=TEXT_COLOR,
        anchor="mm",
        align="center",
        spacing=6,
    )

    return {
        "x": x,
        "y": y,
        "left": x1,
        "right": x2,
        "top": y1,
        "bottom": y2,
        "width": node_width,
        "height": node_height,
    }


# ==================================================
# CONNECTION LINE
# ==================================================

def draw_connection(
    draw,
    start,
    end,
    width=5,
):

    draw.line(
        (
            int(start[0]),
            int(start[1]),
            int(end[0]),
            int(end[1]),
        ),
        fill=LINE_COLOR,
        width=width,
    )


# ==================================================
# NORMALISE PERSON LIST
# ==================================================

def normalise_people(
    value,
):

    if not value:
        return []

    if isinstance(
        value,
        str,
    ):

        return [
            value
        ]

    return list(
        value
    )


# ==================================================
# BUILD RELATIONSHIP NODES
# ==================================================

def build_relation_nodes(
    caregivers=None,
    handlers=None,
    littles=None,
    middles=None,
    siblings=None,
    pets=None,
):

    # --------------------------------------------------
    # ABOVE THE PERSON
    # --------------------------------------------------

    top = []

    # --------------------------------------------------
    # BELOW THE PERSON
    # --------------------------------------------------

    bottom = []

    # --------------------------------------------------
    # CAREGIVERS
    # --------------------------------------------------

    for name in normalise_people(
        caregivers
    ):

        top.append(
            (
                f"CAREGIVER\n{name}",
                "caregiver",
            )
        )

    # --------------------------------------------------
    # HANDLERS
    # --------------------------------------------------

    for name in normalise_people(
        handlers
    ):

        top.append(
            (
                f"HANDLER\n{name}",
                "handler",
            )
        )

    # --------------------------------------------------
    # LITTLES
    # --------------------------------------------------

    for name in normalise_people(
        littles
    ):

        bottom.append(
            (
                f"LITTLE\n{name}",
                "little",
            )
        )

    # --------------------------------------------------
    # MIDDLES
    # --------------------------------------------------

    for name in normalise_people(
        middles
    ):

        bottom.append(
            (
                f"MIDDLE\n{name}",
                "middle",
            )
        )

    # --------------------------------------------------
    # PETS
    # --------------------------------------------------

    for name in normalise_people(
        pets
    ):

        bottom.append(
            (
                f"PET\n{name}",
                "pet",
            )
        )

    # --------------------------------------------------
    # SIBLINGS
    # --------------------------------------------------

    for name in normalise_people(
        siblings
    ):

        bottom.append(
            (
                f"SIBLING\n{name}",
                "sibling",
            )
        )

    return (
        top,
        bottom,
    )


# ==================================================
# ESTIMATE ROW COUNT
# ==================================================

def estimate_rows(
    item_count,
    max_per_row=3,
):

    if item_count <= 0:
        return 0

    return math.ceil(
        item_count
        / max_per_row
    )


# ==================================================
# LAYOUT RELATIONSHIP NODES
# ==================================================

def layout_relation_nodes(
    draw,
    items,
    region_left,
    region_right,
    start_y,
    direction,
):
    """
    direction = 1
        Rows move downward.

    direction = -1
        Rows move upward.
    """

    if not items:
        return []

    font = auto_font(
        BASE_FONT_SIZE,
        bold=True,
    )

    available_width = (
        region_right
        - region_left
    )

    rows = []

    current_row = []

    current_width = 0

    # --------------------------------------------------
    # BUILD ROWS THAT FIT THE AVAILABLE SPACE
    # --------------------------------------------------

    for text, kind in items:

        node_width, _ = (
            get_node_size(
                draw,
                text,
                font,
            )
        )

        proposed_width = (
            current_width
            + (
                NODE_GAP
                if current_row
                else 0
            )
            + node_width
        )

        if (
            current_row
            and proposed_width
            > available_width
        ):

            rows.append(
                current_row
            )

            current_row = []

            current_width = 0

        current_row.append(
            (
                text,
                kind,
                node_width,
            )
        )

        current_width += (
            (
                NODE_GAP
                if len(
                    current_row
                ) > 1
                else 0
            )
            + node_width
        )

    if current_row:

        rows.append(
            current_row
        )

    # --------------------------------------------------
    # POSITION EACH ROW
    # --------------------------------------------------

    positioned = []

    for row_index, row in enumerate(
        rows
    ):

        y = (
            start_y
            + (
                row_index
                * ROW_GAP
                * direction
            )
        )

        total_width = (
            sum(
                node_width
                for (
                    _,
                    _,
                    node_width,
                )
                in row
            )
            + (
                NODE_GAP
                * (
                    len(row)
                    - 1
                )
            )
        )

        current_x = (
            region_left
            + (
                available_width
                - total_width
            ) / 2
        )

        for (
            text,
            kind,
            node_width,
        ) in row:

            x = (
                current_x
                + node_width / 2
            )

            positioned.append(
                {
                    "text": text,
                    "kind": kind,
                    "x": x,
                    "y": y,
                    "font": font,
                }
            )

            current_x += (
                node_width
                + NODE_GAP
            )

    return positioned


# ==================================================
# GENERATE TREE IMAGE
# ==================================================

def generate_tree_image(
    user_name,
    spouse_name,
    caregivers,
    littles,
    middles,
    siblings,
    handler,
    pets,

    # --------------------------------------------------
    # NEW:
    # The spouse's own relationships.
    #
    # These are optional for now so the existing
    # /tree command will still work until we update it.
    # --------------------------------------------------

    spouse_data=None,

    # --------------------------------------------------
    # NEW:
    # Used when the spouse is ALSO your Little/Pet/etc.
    #
    # Example:
    #
    # SPOUSE
    # Alex
    # ALSO YOUR LITTLE
    # --------------------------------------------------

    spouse_extra_roles=None,
):

    spouse_data = (
        spouse_data
        or {}
    )

    spouse_extra_roles = (
        spouse_extra_roles
        or []
    )

    # ==================================================
    # YOUR RELATIONSHIPS
    # ==================================================

    root_top, root_bottom = (
        build_relation_nodes(
            caregivers=caregivers,
            handlers=handler,
            littles=littles,
            middles=middles,
            siblings=siblings,
            pets=pets,
        )
    )

    # ==================================================
    # SPOUSE RELATIONSHIPS
    # ==================================================

    spouse_top, spouse_bottom = (
        build_relation_nodes(

            caregivers=(
                spouse_data.get(
                    "caregivers",
                    [],
                )
            ),

            handlers=(
                spouse_data.get(
                    "handlers",
                    spouse_data.get(
                        "handler",
                        [],
                    ),
                )
            ),

            littles=(
                spouse_data.get(
                    "littles",
                    [],
                )
            ),

            middles=(
                spouse_data.get(
                    "middles",
                    [],
                )
            ),

            siblings=(
                spouse_data.get(
                    "siblings",
                    [],
                )
            ),

            pets=(
                spouse_data.get(
                    "pets",
                    [],
                )
            ),
        )
    )

    # ==================================================
    # DOES THE TREE HAVE A SPOUSE?
    # ==================================================

    has_spouse = bool(
        spouse_name
    )

    # ==================================================
    # DYNAMIC WIDTH
    # ==================================================

    widest_side_count = max(
        len(root_top),
        len(root_bottom),
        len(spouse_top),
        len(spouse_bottom),
        1,
    )

    if has_spouse:

        width = max(
            2600,
            min(
                3600,
                (
                    2500
                    + max(
                        0,
                        widest_side_count - 4,
                    )
                    * 180
                ),
            ),
        )

    else:

        width = max(
            1700,
            min(
                2600,
                (
                    1600
                    + max(
                        0,
                        widest_side_count - 4,
                    )
                    * 160
                ),
            ),
        )

    # ==================================================
    # DYNAMIC HEIGHT
    # ==================================================

    root_top_rows = (
        estimate_rows(
            len(root_top)
        )
    )

    spouse_top_rows = (
        estimate_rows(
            len(spouse_top)
        )
    )

    root_bottom_rows = (
        estimate_rows(
            len(root_bottom)
        )
    )

    spouse_bottom_rows = (
        estimate_rows(
            len(spouse_bottom)
        )
    )

    top_rows = max(
        root_top_rows,
        spouse_top_rows,
        1,
    )

    bottom_rows = max(
        root_bottom_rows,
        spouse_bottom_rows,
        1,
    )

    center_y = (
        410
        + (
            max(
                0,
                top_rows - 1,
            )
            * ROW_GAP
        )
    )

    bottom_start_y = (
        center_y
        + 390
    )

    height = max(
        1450,
        int(
            bottom_start_y
            + (
                max(
                    0,
                    bottom_rows - 1,
                )
                * ROW_GAP
            )
            + 220
        ),
    )

    # ==================================================
    # LOAD BACKGROUND
    # ==================================================

    background = Image.open(
        "utils/tree_bg.jpg"
    ).convert(
        "RGB"
    )

    background = (
        background.resize(
            (
                width,
                height,
            )
        )
    )

    img = (
        background
        .copy()
        .convert(
            "RGBA"
        )
    )

    # ==================================================
    # DARK OVERLAY
    # ==================================================

    overlay = Image.new(
        "RGBA",
        (
            width,
            height,
        ),
        (
            0,
            0,
            0,
            70,
        ),
    )

    img = Image.alpha_composite(
        img,
        overlay,
    )

    draw = ImageDraw.Draw(
        img
    )

    # ==================================================
    # TITLE
    # ==================================================

    title_font = auto_font(
        TITLE_FONT_SIZE,
        bold=True,
    )

    draw.text(
        (
            width / 2,
            70,
        ),
        "RELATIONSHIP TREE",
        font=title_font,
        fill=TEXT_COLOR,
        anchor="ma",
    )

    # ==================================================
    # MAIN PERSON POSITIONS
    # ==================================================

    if has_spouse:

        # --------------------------------------------------
        # YOU ON THE LEFT
        # --------------------------------------------------

        user_x = (
            width / 2
            - CENTER_GAP
        )

        # --------------------------------------------------
        # SPOUSE ON THE RIGHT
        # --------------------------------------------------

        spouse_x = (
            width / 2
            + CENTER_GAP
        )

        # --------------------------------------------------
        # YOUR SIDE OF THE TREE
        # --------------------------------------------------

        left_region = (
            100,
            width / 2 - 80,
        )

        # --------------------------------------------------
        # SPOUSE SIDE OF THE TREE
        # --------------------------------------------------

        right_region = (
            width / 2 + 80,
            width - 100,
        )

    else:

        user_x = (
            width / 2
        )

        spouse_x = None

        left_region = (
            120,
            width - 120,
        )

        right_region = None

    # ==================================================
    # MAIN NODE TEXT
    # ==================================================

    user_text = (
        f"YOU\n{user_name}"
    )

    spouse_text = None

    if spouse_name:

        extra_role_text = ""

        if spouse_extra_roles:

            extra_role_text = (
                "\nALSO YOUR "
                + " / ".join(
                    role.upper()
                    for role
                    in spouse_extra_roles
                )
            )

        spouse_text = (
            f"SPOUSE\n"
            f"{spouse_name}"
            f"{extra_role_text}"
        )

    # ==================================================
    # MAIN NODE FONT
    # ==================================================

    main_font = auto_font(
        BASE_FONT_SIZE + 4,
        bold=True,
    )

    # ==================================================
    # MAIN NODE SIZES
    # ==================================================

    user_width, user_height = (
        get_node_size(
            draw,
            user_text,
            main_font,
        )
    )

    spouse_width = 0
    spouse_height = 0

    if spouse_text:

        (
            spouse_width,
            spouse_height,
        ) = get_node_size(
            draw,
            spouse_text,
            main_font,
        )

    # ==================================================
    # TOP POSITIONS
    #
    # CG + HANDLER
    # ==================================================

    top_start_y = (
        center_y
        - 350
    )

    root_top_positions = (
        layout_relation_nodes(
            draw,
            root_top,
            left_region[0],
            left_region[1],
            top_start_y,
            -1,
        )
    )

    # ==================================================
    # BOTTOM POSITIONS
    #
    # LITTLE + PET + MIDDLE + SIBLING
    # ==================================================

    root_bottom_positions = (
        layout_relation_nodes(
            draw,
            root_bottom,
            left_region[0],
            left_region[1],
            bottom_start_y,
            1,
        )
    )

    spouse_top_positions = []

    spouse_bottom_positions = []

    if (
        has_spouse
        and right_region
    ):

        spouse_top_positions = (
            layout_relation_nodes(
                draw,
                spouse_top,
                right_region[0],
                right_region[1],
                top_start_y,
                -1,
            )
        )

        spouse_bottom_positions = (
            layout_relation_nodes(
                draw,
                spouse_bottom,
                right_region[0],
                right_region[1],
                bottom_start_y,
                1,
            )
        )

    # ==================================================
    # DRAW ALL CONNECTION LINES FIRST
    #
    # Drawing them before boxes means the lines disappear
    # neatly underneath the person boxes.
    # ==================================================

    # --------------------------------------------------
    # YOUR TOP CONNECTION POINT
    # --------------------------------------------------

    user_top_anchor = (
        user_x,
        center_y
        - user_height / 2,
    )

    # --------------------------------------------------
    # YOUR BOTTOM CONNECTION POINT
    # --------------------------------------------------

    user_bottom_anchor = (
        user_x,
        center_y
        + user_height / 2,
    )

    # --------------------------------------------------
    # YOUR CG / HANDLER LINES
    # --------------------------------------------------

    for item in root_top_positions:

        draw_connection(
            draw,
            user_top_anchor,
            (
                item["x"],
                item["y"],
            ),
        )

    # --------------------------------------------------
    # YOUR LITTLE / PET LINES
    # --------------------------------------------------

    for item in root_bottom_positions:

        draw_connection(
            draw,
            user_bottom_anchor,
            (
                item["x"],
                item["y"],
            ),
        )

    # ==================================================
    # SPOUSE CONNECTIONS
    # ==================================================

    if has_spouse:

        spouse_top_anchor = (
            spouse_x,
            center_y
            - spouse_height / 2,
        )

        spouse_bottom_anchor = (
            spouse_x,
            center_y
            + spouse_height / 2,
        )

        # --------------------------------------------------
        # SPOUSE CG / HANDLER
        # --------------------------------------------------

        for item in spouse_top_positions:

            draw_connection(
                draw,
                spouse_top_anchor,
                (
                    item["x"],
                    item["y"],
                ),
            )

        # --------------------------------------------------
        # SPOUSE LITTLE / PET
        # --------------------------------------------------

        for item in spouse_bottom_positions:

            draw_connection(
                draw,
                spouse_bottom_anchor,
                (
                    item["x"],
                    item["y"],
                ),
            )

        # ==================================================
        # MARRIAGE LINE
        # ==================================================

        marriage_start = (
            user_x
            + user_width / 2,
            center_y,
        )

        marriage_end = (
            spouse_x
            - spouse_width / 2,
            center_y,
        )

        draw_connection(
            draw,
            marriage_start,
            marriage_end,
            width=7,
        )

        # --------------------------------------------------
        # MARRIED LABEL
        # --------------------------------------------------

        marriage_font = auto_font(
            SMALL_FONT_SIZE,
            bold=True,
        )

        marriage_mid_x = (
            marriage_start[0]
            + marriage_end[0]
        ) / 2

        marriage_label = (
            "MARRIED"
        )

        (
            label_width,
            label_height,
        ) = measure_text(
            draw,
            marriage_label,
            marriage_font,
        )

        label_padding_x = 18
        label_padding_y = 10

        draw.rounded_rectangle(
            (
                marriage_mid_x
                - label_width / 2
                - label_padding_x,

                center_y
                - 65
                - label_height / 2
                - label_padding_y,

                marriage_mid_x
                + label_width / 2
                + label_padding_x,

                center_y
                - 65
                + label_height / 2
                + label_padding_y,
            ),
            radius=14,
            fill=NODE_BG,
            outline=GOLD,
            width=3,
        )

        draw.text(
            (
                marriage_mid_x,
                center_y - 65,
            ),
            marriage_label,
            font=marriage_font,
            fill=TEXT_COLOR,
            anchor="mm",
        )

    # ==================================================
    # DRAW RELATIONSHIP NODES
    # ==================================================

    all_relationship_nodes = (
        root_top_positions
        + root_bottom_positions
        + spouse_top_positions
        + spouse_bottom_positions
    )

    for item in all_relationship_nodes:

        draw_node(
            draw,
            item["x"],
            item["y"],
            item["text"],
            item["font"],
        )

    # ==================================================
    # DRAW YOU
    # ==================================================

    draw_node(
        draw,
        user_x,
        center_y,
        user_text,
        main_font,
        accent_width=6,
    )

    # ==================================================
    # DRAW SPOUSE
    # ==================================================

    if spouse_text:

        draw_node(
            draw,
            spouse_x,
            center_y,
            spouse_text,
            main_font,
            accent_width=6,
        )

    # ==================================================
    # SIDE LABELS
    # ==================================================

    if has_spouse:

        section_font = auto_font(
            SMALL_FONT_SIZE + 6,
            bold=True,
        )

        # Different colours from the gold relationship tags
        section_text_color = (
            255,
            255,
            255,
        )

        section_fill = (
            120,
            85,
            150,
            235,
        )

        section_outline = (
            220,
            190,
            255,
            255,
        )

        # --------------------------------------------------
        # DRAW SECTION HEADER
        # --------------------------------------------------

        def draw_section_label(
            x,
            y,
            text,
        ):

            text_width, text_height = (
                measure_text(
                    draw,
                    text,
                    section_font,
                )
            )

            padding_x = 34
            padding_y = 20

            x1 = (
                x
                - text_width / 2
                - padding_x
            )

            y1 = (
                y
                - text_height / 2
                - padding_y
            )

            x2 = (
                x
                + text_width / 2
                + padding_x
            )

            y2 = (
                y
                + text_height / 2
                + padding_y
            )

            draw.rounded_rectangle(
                (
                    x1,
                    y1,
                    x2,
                    y2,
                ),
                radius=20,
                fill=section_fill,
                outline=section_outline,
                width=5,
            )

            draw.text(
                (
                    x,
                    y,
                ),
                text,
                font=section_font,
                fill=section_text_color,
                anchor="mm",
            )

        # --------------------------------------------------
        # YOUR SIDE
        # --------------------------------------------------

        draw_section_label(
            user_x,
            center_y + 165,
            f"{user_name}'S RELATIONSHIPS",
        )

        # --------------------------------------------------
        # SPOUSE SIDE
        # --------------------------------------------------

        draw_section_label(
            spouse_x,
            center_y + 165,
            f"{spouse_name}'S RELATIONSHIPS",
        )
    # ==================================================
    # SAVE IMAGE
    # ==================================================

    buffer = BytesIO()

    # JPEG cannot save RGBA directly.

    img = img.convert(
        "RGB"
    )

    img.save(
        buffer,
        format="JPEG",
        quality=95,
    )

    buffer.seek(0)

    return buffer
