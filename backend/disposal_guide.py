"""
Disposal guidance shown to the user after classification.
Keyed by the internal class name used in config.CLASS_NAMES.
If you rename classes in config.py, update the keys here to match.
"""

DISPOSAL_GUIDES = {
    "recyclable": {
        "label": "Recyclable",
        "summary": "This can go into your recycling stream after a quick prep step.",
        "bin_color": "#2E6F40",
        "icon": "recycle",
        "steps": [
            {
                "title": "Empty and rinse",
                "detail": "Tip out any leftover liquid or food and give it a quick rinse. Wet or dirty items can contaminate an entire batch of recycling.",
            },
            {
                "title": "Remove non-recyclable parts",
                "detail": "Take off caps, straws, pumps, or anything made of a different material if your local facility asks for materials to be separated.",
            },
            {
                "title": "Dry it off",
                "detail": "Let it air-dry for a few seconds. Damp items can stick to paper and cardboard and ruin them.",
            },
            {
                "title": "Check the local recycling symbol",
                "detail": "Look for the resin code or your municipality's accepted-materials list — some areas don't accept every plastic type.",
            },
            {
                "title": "Place in the recycling bin",
                "detail": "Use your blue/marked recycling bin. Don't bag loose recyclables in plastic bags unless your local program says to.",
            },
        ],
        "avoid": [
            "Don't put greasy or food-stained items (like a used pizza box's greasy section) in recycling — tear off the dirty part first.",
            "Don't crush items so flat that sorting machines can't recognize their shape (for cans/bottles, light crushing is usually fine).",
        ],
    },
    "non_recyclable": {
        "label": "Non-Recyclable (General Waste)",
        "summary": "This isn't accepted by standard recycling streams — here's how to dispose of it responsibly.",
        "bin_color": "#6B6357",
        "icon": "trash",
        "steps": [
            {
                "title": "Confirm it's really non-recyclable",
                "detail": "Some items look like trash but have take-back programs (e.g. soft plastics, batteries hidden inside toys). When in doubt, check locally before binning.",
            },
            {
                "title": "Reduce volume where possible",
                "detail": "Flatten or compact the item if it's safe to do so, to save landfill space and bin room.",
            },
            {
                "title": "Bag it securely",
                "detail": "Use a general waste bag to prevent sharp or messy items from causing issues during collection.",
            },
            {
                "title": "Place in general waste bin",
                "detail": "Use your standard household/municipal waste bin, not the recycling bin — mixing them can contaminate recyclables.",
            },
            {
                "title": "Consider reuse first",
                "detail": "Before throwing away, ask if the item (or its container) could be reused, donated, or repurposed instead.",
            },
        ],
        "avoid": [
            "Don't put this in the recycling bin — contamination can cause an entire truckload to be sent to landfill.",
            "Don't burn waste at home — it releases harmful pollutants.",
        ],
    },
    "ewaste": {
        "label": "E-Waste",
        "summary": "Electronic waste needs special handling — never put this in regular trash or recycling.",
        "bin_color": "#B5651D",
        "icon": "cpu",
        "steps": [
            {
                "title": "Back up and wipe personal data",
                "detail": "For phones, laptops, drives, or memory cards: back up anything important, then factory-reset or securely wipe the device to protect your data.",
            },
            {
                "title": "Remove batteries if possible",
                "detail": "Loose batteries (especially lithium-ion) should usually be taken separately to a battery drop-off point — they're a fire risk if crushed in regular waste.",
            },
            {
                "title": "Do NOT put it in household trash or recycling",
                "detail": "E-waste contains heavy metals (lead, mercury, cadmium) that can contaminate soil and water if landfilled, and it can damage recycling sorting equipment.",
            },
            {
                "title": "Find a certified e-waste collection point",
                "detail": "Look for authorized e-waste recyclers, manufacturer take-back programs, or municipal e-waste collection drives/kiosks in your area.",
            },
            {
                "title": "Drop it off (or arrange pickup)",
                "detail": "Many electronics retailers and city sanitation departments run periodic e-waste collection drives — check your local municipal corporation's website or app.",
            },
        ],
        "avoid": [
            "Don't disassemble devices yourself unless you know what you're doing — some components (like CRT screens or batteries) can be hazardous.",
            "Don't leave e-waste with informal/unlicensed collectors — improper handling causes serious pollution and health hazards for waste workers.",
        ],
    },
}


def get_guide(class_name: str):
    """Return the disposal guide dict for a predicted class, with a safe fallback."""
    return DISPOSAL_GUIDES.get(
        class_name,
        {
            "label": class_name.replace("_", " ").title(),
            "summary": "Please check your local waste management guidelines for this item.",
            "bin_color": "#444444",
            "icon": "help-circle",
            "steps": [],
            "avoid": [],
        },
    )
