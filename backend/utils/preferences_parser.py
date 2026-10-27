"""
preferences_parser.py
Universal Dynamic Interior Design Engine.
Dynamically analyzes ANY freeform user instruction without relying on rigid static categories.
"""

import re
from typing import Dict, Any


def clean_conversational_text(text: str) -> str:
    """Strip conversational filler phrases so diffusion models receive pure descriptive tags."""
    cleaned = text.strip()
    patterns = [
        r"^(please\s+)?(can\s+you\s+)?(i\s+want\s+to\s+add\s+|i\s+want\s+to\s+have\s+|i\s+would\s+like\s+to\s+add\s+|i\s+would\s+like\s+|i\s+need\s+to\s+add\s+|i\s+need\s+|we\s+want\s+to\s+add\s+|we\s+need\s+|please\s+add\s+|add\s+|put\s+in\s+|put\s+|install\s+|create\s+|build\s+)",
        r"^(make\s+sure\s+to\s+include\s+|make\s+sure\s+there\s+is\s+|include\s+|provide\s+|give\s+me\s+)",
        r"^(the\s+|a\s+|an\s+|some\s+)",
    ]
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.strip(" .,;!")


def _extract_intent_details(cleaned: str, lower: str) -> dict:
    """Dynamically determine the architectural category, scale, and focus of ANY request."""
    # Detect addition / structural / physical changes
    physical_indicators = [
        "table", "desk", "unit", "sofa", "couch", "chair", "bed", "shelf", "shelves", "bookshelf",
        "cabinet", "wardrobe", "closet", "tv", "screen", "plant", "plants", "greenery", "fireplace",
        "aquarium", "counter", "bar", "island", "partition", "door", "window", "lighting", "lamp",
        "chandelier", "mirror", "rug", "carpet", "curtain", "drapes", "art", "painting", "wall",
        "swing", "rack", "bench", "nook", "corner", "console", "stand", "credenza", "setup", "tree"
    ]
    is_physical = any(w in lower for w in physical_indicators) or any(w in lower for w in ["add", "install", "put", "build", "place", "mount", "set up"])

    # Determine focus theme dynamically based on input
    if any(k in lower for k in ["tv", "media", "screen", "theatre", "theater", "console", "audio", "speaker"]):
        focus = "Media & Entertainment"
        budget = "$350 – $1,200"
    elif any(k in lower for k in ["study", "desk", "work", "office", "computer", "laptop", "child", "kid"]):
        focus = "Ergonomic Workspace & Study"
        budget = "$280 – $850"
    elif any(k in lower for k in ["plant", "green", "botanical", "garden", "nature", "tree", "flower"]):
        focus = "Biophilic Greenery & Planters"
        budget = "$120 – $380"
    elif any(k in lower for k in ["light", "lamp", "chandelier", "pendant", "neon", "led", "sconce"]):
        focus = "Architectural Illumination"
        budget = "$180 – $650"
    elif any(k in lower for k in ["bed", "sleep", "mattress", "headboard", "bunk"]):
        focus = "Master Suite & Resting Zone"
        budget = "$550 – $1,600"
    elif any(k in lower for k in ["sofa", "seating", "couch", "lounge", "chair", "recliner"]):
        focus = "Social Lounge & Seating"
        budget = "$500 – $1,800"
    elif any(k in lower for k in ["storage", "shelf", "bookshelf", "closet", "wardrobe", "cabinet"]):
        focus = "Custom Storage & Joinery"
        budget = "$300 – $950"
    elif any(k in lower for k in ["kitchen", "dining", "bar", "coffee", "wine", "island"]):
        focus = "Dining & Hospitality Zone"
        budget = "$400 – $1,400"
    elif any(k in lower for k in ["fireplace", "chimney", "hearth"]):
        focus = "Warm Hearth & Fireplace Accent"
        budget = "$600 – $2,200"
    elif any(k in lower for k in ["gym", "workout", "fitness", "yoga"]):
        focus = "Wellness & Workout Area"
        budget = "$300 – $1,100"
    else:
        focus = "Bespoke Architectural Feature"
        budget = "$250 – $900"

    return {
        "is_physical": is_physical,
        "focus": focus,
        "budget": budget,
    }


def parse_user_preferences(
    instructions: str,
    room_type: str = "living",
    style: str = "modern",
    background_color: str = "#ffffff",
    foreground_color: str = "#000000",
) -> Dict[str, Any]:
    """
    Dynamically analyze ANY user instruction and return:
      - prompt_tag: high-impact visual phrase for diffusion models
      - optimal_strength: dynamically computed img2img strength (0.78-0.82 for additions)
      - custom_report_markdown: customized architectural brief addressing the exact request
      - preview_overlay_label: dynamic badge text for preview mode image
    """
    raw = (instructions or "").strip()
    if not raw:
        return {
            "has_preferences": False,
            "raw": "",
            "cleaned": "",
            "prompt_tag": "",
            "optimal_strength": 0.58,
            "is_furniture_addition": False,
            "custom_report_markdown": "",
            "preview_overlay_label": "",
            "category": "none",
        }

    lower = raw.lower()
    cleaned = clean_conversational_text(raw)
    feature_name = cleaned if len(cleaned) > 1 else raw
    s_name = style.strip().capitalize() or "Modern"
    r_name = room_type.strip().capitalize() or "Room"

    intent = _extract_intent_details(feature_name, lower)
    is_physical = intent["is_physical"]
    focus_theme = intent["focus"]
    est_budget = intent["budget"]

    # 1. Dynamically Craft the High-Weight Diffusion Prompt Token
    # This transforms ANY user text into a rich visual scene token the AI model can paint
    prompt_tag = (
        f"featuring a bespoke, beautifully integrated {feature_name}, "
        f"flawlessly designed in {s_name.lower()} architectural style, "
        f"harmonized with the {r_name.lower()} layout and curated interior finishes"
    )

    # 2. Dynamic Latent Strength
    # Adding physical objects/furniture requires high strength (0.80) so diffusion manifests the new elements
    # Subtle ambient/color changes require moderate strength (0.64)
    optimal_strength = 0.80 if is_physical else 0.64

    # 3. Dynamic Badge Label
    display_title = feature_name[:36].strip().upper()
    preview_label = f"📐 PLAN: INTEGRATED {display_title}"

    # 4. Dynamically Synthesize the Architectural & Interior Design Plan
    # Tailored specifically to whatever the user requested!
    custom_report = f"""#### 🎯 Bespoke Feature Integration: {feature_name.title()}
*Directly addressing client specification: "{raw}"*

- **Spatial Flow & Strategic Placement:** Seamlessly positions the requested **{feature_name}** into the {r_name.lower()} floorplan, maintaining optimal 36-inch clearance walkways and functional ergonomic circulation.
- **Architectural Harmony & Finishes:** Styled to match the `{s_name}` aesthetic, coordinating primary surfaces with `{background_color}` and framing accent details with `{foreground_color}`.
- **Ergonomics, Scale & Utility:** Proportioned to complement the existing room volume while fulfilling daily functional needs for `{focus_theme}`.
- **Dedicated Illumination:** Tailored lighting strategy with ambient backlight or directional task fixtures to naturally accentuate the {feature_name}.

**Estimated Scope & Investment for Custom Request:**
- Custom fabrication / procurement of {feature_name}: **{est_budget}**
- Professional installation, cable concealment & staging: **$120 – $280**
"""

    return {
        "has_preferences": True,
        "raw": raw,
        "cleaned": cleaned,
        "prompt_tag": prompt_tag,
        "optimal_strength": optimal_strength,
        "is_furniture_addition": is_physical,
        "custom_report_markdown": custom_report,
        "preview_overlay_label": preview_label,
        "category": focus_theme.lower().replace(" ", "_"),
    }
