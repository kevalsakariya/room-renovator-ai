import asyncio
import base64
import io
import json
import os
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageEnhance

load_dotenv()

router = APIRouter()
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Lazy-loaded local pipeline for local execution
_local_pipe = None
_local_pipe_device = None


def _is_local_available() -> bool:
    """Check if torch and diffusers packages are installed locally."""
    try:
        import diffusers  # noqa: F401
        import torch  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


import time

# Cache for Colab health check to avoid spamming the tunnel
_last_colab_check_time = 0.0
_last_colab_check_result = (False, "Not checked yet")


def _is_colab_configured() -> bool:
    """Check if a valid, non-placeholder Colab inference URL is set."""
    load_dotenv(override=True)
    colab_url = os.getenv("COLAB_INFERENCE_URL", "").strip().strip("'\"")
    return bool(colab_url and "your-temporary-address" not in colab_url)


def _check_colab_health(timeout: float = 2.5) -> tuple[bool, str]:
    """Actively ping Colab /health endpoint to verify if the tunnel is alive and responding."""
    load_dotenv(override=True)
    colab_url = os.getenv("COLAB_INFERENCE_URL", "").strip().strip("'\"")
    if not colab_url or "your-temporary-address" in colab_url:
        return False, "Colab URL not configured"

    health_url = colab_url.rsplit("/api/", 1)[0] + "/health"
    headers = {
        "User-Agent": "AI-Room-Makeover-Client/1.0",
        "ngrok-skip-browser-warning": "69420",
        "bypass-tunnel-reminder": "true",
    }
    req = Request(health_url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                gpu = data.get("gpu", "GPU")
                return True, f"Google Colab GPU Online ({gpu})"
    except Exception as exc:
        return False, f"Tunnel Unreachable ({exc})"
    return False, "Invalid response"


def _is_colab_live() -> tuple[bool, str]:
    global _last_colab_check_time, _last_colab_check_result
    now = time.time()
    if now - _last_colab_check_time < 6.0:
        return _last_colab_check_result
    _last_colab_check_result = _check_colab_health(timeout=2.5)
    _last_colab_check_time = now
    return _last_colab_check_result



def _get_local_pipeline():
    global _local_pipe, _local_pipe_device
    if _local_pipe is not None:
        return _local_pipe, _local_pipe_device

    try:
        import torch
        from diffusers import AutoPipelineForImage2Image
    except ImportError as err:
        raise HTTPException(
            status_code=500,
            detail=(
                "Local inference dependencies (torch, diffusers) are not installed. "
                "Install them or connect Google Colab GPU (see colab_room_redesign.ipynb)."
            ),
        ) from err

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32

    model_id = os.getenv("LOCAL_MODEL_ID", "stabilityai/sd-turbo").strip()

    print(f"Loading local model '{model_id}' on {device.upper()}...")
    try:
        pipe = AutoPipelineForImage2Image.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            variant="fp16" if device == "cuda" else None,
        ).to(device)
        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()
        _local_pipe = pipe
        _local_pipe_device = device
        print(f"Local model '{model_id}' ready on {device.upper()}.")
        return _local_pipe, _local_pipe_device
    except Exception as exc:
        print(f"Failed to load local model: {exc}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load local model '{model_id}': {str(exc)}",
        ) from exc


def _run_local_inference(image_bytes: bytes, prompt: str, strength: float = 0.55) -> bytes:
    pipe, device = _get_local_pipeline()

    with Image.open(io.BytesIO(image_bytes)) as src:
        image = src.convert("RGB")

    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
    width = max(8, (image.width // 8) * 8)
    height = max(8, (image.height // 8) * 8)
    image = image.resize((width, height), Image.Resampling.LANCZOS)

    pipe_name = getattr(pipe, "_model_id", getattr(pipe, "name_or_path", "sd-turbo"))
    is_turbo = "turbo" in str(pipe_name).lower()
    steps = 1 if is_turbo else 20
    guidance = 0.0 if is_turbo else 7.5

    result = pipe(
        prompt=prompt,
        image=image,
        strength=strength,
        num_inference_steps=steps,
        guidance_scale=guidance,
    ).images[0]

    out_buffer = io.BytesIO()
    result.save(out_buffer, format="PNG")
    return out_buffer.getvalue()


def _hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    clean = hex_code.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
    if len(clean) != 6:
        return (200, 200, 200)
    try:
        return (
            int(clean[0:2], 16),
            int(clean[2:4], 16),
            int(clean[4:6], 16),
        )
    except ValueError:
        return (200, 200, 200)


def _hex_to_color_name(hex_code: str) -> str:
    """Convert a hex color code to a descriptive English color name for AI prompts.

    Diffusion models understand color names, NOT hex codes like #f4ede4.
    This maps the user's chosen color to the closest named color the model recognizes.
    """
    r, g, b = _hex_to_rgb(hex_code)

    # Normalize to 0-1
    rn, gn, bn = r / 255, g / 255, b / 255
    max_c = max(rn, gn, bn)
    min_c = min(rn, gn, bn)
    lum = (max_c + min_c) / 2
    sat = 0.0
    if max_c != min_c:
        d = max_c - min_c
        sat = d / (2 - max_c - min_c) if lum > 0.5 else d / (max_c + min_c)

    # Achromatic (grey-scale) detection
    if sat < 0.10:
        if lum < 0.12:
            return "matte black"
        if lum < 0.25:
            return "charcoal grey"
        if lum < 0.42:
            return "dark grey"
        if lum < 0.58:
            return "medium grey"
        if lum < 0.75:
            return "light grey"
        if lum < 0.88:
            return "off-white"
        return "crisp white"

    # Hue calculation
    if max_c == rn:
        hue = (gn - bn) / (max_c - min_c) % 6
    elif max_c == gn:
        hue = (bn - rn) / (max_c - min_c) + 2
    else:
        hue = (rn - gn) / (max_c - min_c) + 4
    hue = (hue / 6) * 360  # 0-360

    # Lightness prefix
    if lum < 0.20:
        prefix = "deep "
    elif lum < 0.38:
        prefix = "dark "
    elif lum > 0.78:
        prefix = "light "
    elif lum > 0.62:
        prefix = "soft "
    else:
        prefix = ""

    # Saturation qualifier
    if sat < 0.30:
        prefix = "muted " + prefix
    elif sat > 0.80:
        prefix = "vibrant " + prefix

    # Base hue name
    if hue < 15 or hue >= 345:
        base = "red"
    elif hue < 30:
        base = "red-orange"
    elif hue < 45:
        base = "orange"
    elif hue < 60:
        base = "amber"
    elif hue < 80:
        base = "yellow"
    elif hue < 100:
        base = "yellow-green"
    elif hue < 135:
        base = "green"
    elif hue < 160:
        base = "emerald green"
    elif hue < 185:
        base = "teal"
    elif hue < 210:
        base = "cyan"
    elif hue < 235:
        base = "sky blue"
    elif hue < 255:
        base = "blue"
    elif hue < 275:
        base = "indigo"
    elif hue < 295:
        base = "purple"
    elif hue < 315:
        base = "violet"
    elif hue < 330:
        base = "magenta"
    else:
        base = "rose"

    # Special warm/neutral overrides
    if 25 <= hue <= 55 and sat < 0.40 and lum > 0.55:
        return f"{prefix}warm beige"
    if 20 <= hue <= 50 and sat < 0.55 and lum < 0.40:
        return f"{prefix}warm brown"
    if 180 <= hue <= 240 and sat < 0.25:
        return f"{prefix}slate blue-grey"

    return f"{prefix}{base}".strip()


def _apply_duotone_colorize(gray_img: "Image.Image", dark_rgb: tuple, light_rgb: tuple) -> "Image.Image":
    """Map each pixel's luminance to a color between dark_rgb (shadows) and light_rgb (highlights).

    This is the core technique for realistic room color mapping:
    - Bright pixels (walls, ceilings, light surfaces) → light_rgb (background color)
    - Dark pixels (furniture, floors, shadows) → dark_rgb (foreground/accent color)
    - Mid-tones smoothly interpolate between both
    """
    # Build a 256-entry lookup table that maps each brightness level to an RGB color
    lut_r = []
    lut_g = []
    lut_b = []
    for i in range(256):
        t = i / 255.0  # 0.0 = pure shadow, 1.0 = pure highlight
        # Apply a slight S-curve to make the midtones richer
        t = t * t * (3 - 2 * t)  # smoothstep
        lut_r.append(int(dark_rgb[0] + t * (light_rgb[0] - dark_rgb[0])))
        lut_g.append(int(dark_rgb[1] + t * (light_rgb[1] - dark_rgb[1])))
        lut_b.append(int(dark_rgb[2] + t * (light_rgb[2] - dark_rgb[2])))

    # Apply LUT to each channel independently using point()
    r_ch = gray_img.point(lut_r)
    g_ch = gray_img.point(lut_g)
    b_ch = gray_img.point(lut_b)

    return Image.merge("RGB", (r_ch, g_ch, b_ch))


def _run_preview_mode(
    image_bytes: bytes,
    background_color: str,
    foreground_color: str,
    style: str,
    instructions: str = "",
) -> bytes:
    """Apply a realistic room color palette preview using luminance-zone duotone colorization.

    Algorithm:
      1. Fully desaturate the source so original colors don't compete.
      2. Map bright zones (walls, ceilings) → user's background/wall color.
         Map dark zones (furniture, floors, shadows) → user's accent/foreground color.
      3. Blend colorized layer at high strength (78%) with desaturated original.
      4. Apply style-specific grading + user instruction keyword effects.
    """
    with Image.open(io.BytesIO(image_bytes)) as src:
        img = src.convert("RGB")

    # Resize to comfortable display dimensions (multiple of 8)
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    w = max(8, (img.width // 8) * 8)
    h = max(8, (img.height // 8) * 8)
    img = img.resize((w, h), Image.Resampling.LANCZOS)

    bg_rgb = _hex_to_rgb(background_color)   # Wall / light surface color
    fg_rgb = _hex_to_rgb(foreground_color)   # Furniture / accent / dark zone color

    # ── Step 1: Fully desaturate the original ──
    # Remove the original room's colors entirely so the user's palette dominates.
    # We keep a small amount (15%) to preserve natural texture shading cues.
    gray = img.convert("L")
    desaturated = ImageEnhance.Color(img).enhance(0.15)  # near-greyscale base

    # Sharpen the greyscale map so room edges (furniture outlines, wall seams)
    # carry into the colorized version with clean borders.
    gray_sharp = ImageEnhance.Sharpness(gray).enhance(1.4)

    # ── Step 2: Duotone colorize — bright → bg_color, dark → fg_color ──
    colorized = _apply_duotone_colorize(gray_sharp, dark_rgb=fg_rgb, light_rgb=bg_rgb)

    # ── Step 3: Blend at 78% colorized — strong whole-room color shift ──
    # Using desaturated base (not original) means the user's palette wins everywhere:
    # walls, ceilings, floor, furniture, bedsheets — all shift to the chosen colors.
    blended = Image.blend(desaturated, colorized, alpha=0.78)

    # ── Step 4: Saturation & contrast boost so colors are vivid ──
    result = ImageEnhance.Color(blended).enhance(1.40)
    result = ImageEnhance.Contrast(result).enhance(1.20)
    result = ImageEnhance.Sharpness(result).enhance(1.15)

    # ── Step 5: Style-specific finishing adjustments ──
    s_lower = style.strip().lower()
    if s_lower in ("modern", "minimalist"):
        result = ImageEnhance.Sharpness(result).enhance(1.25)
        result = ImageEnhance.Contrast(result).enhance(1.12)
        result = ImageEnhance.Brightness(result).enhance(1.04)
    elif s_lower in ("rustic", "bohemian"):
        result = ImageEnhance.Color(result).enhance(1.18)
        result = ImageEnhance.Brightness(result).enhance(1.06)
        result = ImageEnhance.Contrast(result).enhance(0.96)
    elif s_lower == "classic":
        result = ImageEnhance.Color(result).enhance(0.82)
        result = ImageEnhance.Contrast(result).enhance(1.14)
        result = ImageEnhance.Sharpness(result).enhance(1.18)
    else:
        result = ImageEnhance.Sharpness(result).enhance(1.12)
        result = ImageEnhance.Brightness(result).enhance(1.03)

    # ── Step 6: Parse user's Additional Styling Preferences ──
    # Translate freeform text keywords into actual image adjustments.
    instr = instructions.strip().lower() if instructions else ""
    if instr:
        print(f"   📝 Applying instruction keywords: '{instr[:80]}'")

        # Brightness keywords
        if any(k in instr for k in ("bright", "airy", "light room", "sunlit", "day light", "daylight")):
            result = ImageEnhance.Brightness(result).enhance(1.18)
            result = ImageEnhance.Color(result).enhance(0.92)  # bright rooms look a bit washed
        elif any(k in instr for k in ("dark", "moody", "dramatic", "night", "dim")):
            result = ImageEnhance.Brightness(result).enhance(0.80)
            result = ImageEnhance.Contrast(result).enhance(1.20)
            result = ImageEnhance.Color(result).enhance(1.10)

        # Warmth keywords
        if any(k in instr for k in ("warm", "cozy", "cosy", "golden", "amber", "sunset")):
            # Shift toward warm tones: boost red/yellow, pull back blue
            r, g, b = result.split()
            r = ImageEnhance.Brightness(r).enhance(1.12)
            b = ImageEnhance.Brightness(b).enhance(0.88)
            result = Image.merge("RGB", (r, g, b))
            result = ImageEnhance.Color(result).enhance(1.15)
        elif any(k in instr for k in ("cool", "cold", "nordic", "scandinavian", "icy")):
            # Shift toward cool tones
            r, g, b = result.split()
            r = ImageEnhance.Brightness(r).enhance(0.90)
            b = ImageEnhance.Brightness(b).enhance(1.10)
            result = Image.merge("RGB", (r, g, b))

        # Saturation keywords
        if any(k in instr for k in ("vibrant", "colorful", "bold", "saturated", "pop")):
            result = ImageEnhance.Color(result).enhance(1.35)
        elif any(k in instr for k in ("muted", "neutral", "subtle", "pastel", "soft")):
            result = ImageEnhance.Color(result).enhance(0.78)
            result = ImageEnhance.Brightness(result).enhance(1.05)

        # Sharpness keywords
        if any(k in instr for k in ("sharp", "crisp", "detailed", "clean")):
            result = ImageEnhance.Sharpness(result).enhance(1.40)
        elif any(k in instr for k in ("soft", "dreamy", "blur", "hazy", "foggy")):
            result = ImageEnhance.Sharpness(result).enhance(0.65)

        # Contrast keywords
        if any(k in instr for k in ("high contrast", "punchy", "bold contrast")):
            result = ImageEnhance.Contrast(result).enhance(1.30)
        elif any(k in instr for k in ("low contrast", "flat", "matte finish")):
            result = ImageEnhance.Contrast(result).enhance(0.85)

    # ── Step 7: Color swatch legend — bottom-left corner ──
    swatch_size = 22
    swatch_gap  = 6
    swatch_x    = 14
    swatch_y    = h - 2 * (swatch_size + swatch_gap) - 12

    legend        = Image.new("RGBA", result.size, (0, 0, 0, 0))
    legend_draw   = ImageDraw.Draw(legend)

    # Panel background
    panel_pad = 6
    panel_x1 = swatch_x - panel_pad
    panel_y1 = swatch_y - panel_pad
    panel_x2 = swatch_x + swatch_size + panel_pad
    panel_y2 = swatch_y + 2 * swatch_size + swatch_gap + panel_pad
    legend_draw.rounded_rectangle(
        [panel_x1, panel_y1, panel_x2, panel_y2],
        radius=6, fill=(15, 23, 42, 180),
    )

    # Background color swatch (wall color)
    legend_draw.rounded_rectangle(
        [swatch_x, swatch_y, swatch_x + swatch_size, swatch_y + swatch_size],
        radius=4, fill=(*bg_rgb, 240), outline=(255, 255, 255, 180), width=2,
    )
    # Foreground / accent color swatch
    fg_swatch_y = swatch_y + swatch_size + swatch_gap
    legend_draw.rounded_rectangle(
        [swatch_x, fg_swatch_y, swatch_x + swatch_size, fg_swatch_y + swatch_size],
        radius=4, fill=(*fg_rgb, 240), outline=(255, 255, 255, 180), width=2,
    )

    result = Image.alpha_composite(result.convert("RGBA"), legend).convert("RGB")

    # ── Step 8: Watermark banner — bottom-right ──
    banner_w = min(210, max(130, w - 24))
    banner_h = 28
    bx = max(8, w - banner_w - 12)
    by = max(8, h - banner_h - 12)

    watermark      = Image.new("RGBA", result.size, (0, 0, 0, 0))
    watermark_draw = ImageDraw.Draw(watermark)
    watermark_draw.rounded_rectangle(
        [bx, by, bx + banner_w, by + banner_h],
        radius=7, fill=(10, 17, 35, 210),
    )
    watermark_draw.text((bx + 10, by + 7), "AI MAKEOVER PREVIEW", fill=(248, 250, 252, 240))
    result = Image.alpha_composite(result.convert("RGBA"), watermark).convert("RGB")

    out_buffer = io.BytesIO()
    result.save(out_buffer, format="PNG")
    return out_buffer.getvalue()


def _request_colab(payload: dict[str, str | float | int]) -> dict[str, str]:
    inference_url = os.getenv("COLAB_INFERENCE_URL", "").strip().strip("'\"")
    inference_token = os.getenv("COLAB_INFERENCE_TOKEN", "").strip().strip("'\"")

    if not inference_url or "your-temporary-address" in inference_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "Colab inference URL is not configured. Start the Colab notebook "
                "and set COLAB_INFERENCE_URL in backend/.env."
            ),
        )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AI-Room-Makeover-Client/1.0",
        "ngrok-skip-browser-warning": "69420",
        "bypass-tunnel-reminder": "true",
    }
    if inference_token:
        headers["Authorization"] = f"Bearer {inference_token}"

    print(f"📡 Sending image request to Colab GPU ({inference_url})...")

    request = Request(
        inference_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    raw_body = ""
    try:
        with urlopen(request, timeout=300) as response:
            raw_body = response.read().decode("utf-8")
            status_code = getattr(response, "status", 200)
            print(f"📥 Colab HTTP Response received! Status: {status_code} | Raw body size: {len(raw_body) / 1024:.1f} KB")
            result = json.loads(raw_body)
    except HTTPError as exc:
        err_msg = ""
        try:
            err_msg = exc.read().decode("utf-8")[:250]
        except Exception:
            pass
        print(f"❌ Colab HTTPError {exc.code}: {exc.reason} | {err_msg}")
        if exc.code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail="Colab rejected the inference token. Check COLAB_INFERENCE_TOKEN in backend/.env matches the token in Colab.",
            ) from exc
        if exc.code == 431:
            raise HTTPException(
                status_code=502,
                detail="Proxy returned 431 (Header Too Large).",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"Colab returned HTTP {exc.code}: {exc.reason}. Response: {err_msg}",
        ) from exc
    except (URLError, TimeoutError) as exc:
        print(f"❌ Colab Connection Error: {exc}")
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot reach Colab endpoint ({exc}). Ensure the Google Colab notebook is running "
                "and COLAB_INFERENCE_URL in backend/.env matches the latest printed tunnel URL."
            ),
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"❌ Colab Returned Non-JSON: {raw_body[:300]}")
        raise HTTPException(
            status_code=502,
            detail=(
                "Colab tunnel returned an HTML page instead of JSON. "
                "The tunnel may be offline or requiring verification. Check the Colab tab."
            ),
        ) from exc

    if not isinstance(result, dict) or not result.get("image_base64"):
        print(f"❌ Colab response dictionary did not contain 'image_base64'. Keys present: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        raise HTTPException(
            status_code=502,
            detail="Colab response did not contain a generated image.",
        )

    b64_str = result["image_base64"]
    approx_kb = len(b64_str) * 3 / 4 / 1024
    print(f"✅ Successfully received AI redesigned image from Colab GPU! (Base64 length: {len(b64_str):,} chars, ~{approx_kb:.1f} KB)")
    return result




def _generate_design_report(
    room_type: str,
    design_type: str,
    style: str,
    background_color: str,
    foreground_color: str,
    instructions: str,
    mode_used: str,
) -> str:
    """Generate a rich, structured architectural design report in Markdown format."""
    r_name = room_type.strip().capitalize() or "Room"
    d_name = design_type.strip().capitalize() or "Interior"
    s_name = style.strip().capitalize() or "Modern"

    custom_section = ""
    if instructions.strip():
        custom_section = f"- **Client Specifications:** Implemented requested preference: *\"{instructions.strip()}\"*."

    preview_notice = ""
    if "Preview" in mode_used:
        preview_notice = (
            "\n\n> 💡 **GPU Status Note:** Displaying Smart Makeover Preview. "
            "To activate full Stable Diffusion generative rendering, start the Google Colab GPU notebook "
            "(`colab_room_redesign.ipynb`) or install PyTorch locally."
        )

    return f"""### 🏡 Architectural & Interior Makeover Plan

**Space Type:** {r_name} ({d_name})  
**Aesthetic Style:** {s_name}  
**Inference Engine:** {mode_used}

---

#### 🎨 Color & Material Palette
- **Primary Backdrop (`{background_color}`):** Curated for primary wall surfacing, perimeter finishes, and large architectural planes to set a luminous {s_name.lower()} mood.
- **Accent Harmony (`{foreground_color}`):** Focused on statement furniture, architectural frames, luminaire details, and bespoke textiles.
- **Material Textures:** Warm organic woods, matte architectural ceramics, textured linen, and subtle brushed metals aligned with {s_name.lower()} principles.

#### 🪑 Spatial Flow & Furnishing Strategy
- **Zoning & Ergonomics:** Preserves structural walls while streamlining visual balance and functional walkways.
- **Focal Elements:** Integrated low-profile {s_name.lower()} centerpieces tailored to elevate standard {r_name.lower()} layouts.
{custom_section}

#### 💡 Lighting & Ambiance
- **Layered Illumination:** Warm 2700K ambient ceiling channels combined with sculptural accent fixtures and directional task lamps.
- **Natural Light Diffusion:** Minimalist sheer window treatments to maximize daytime illumination.

#### 📊 Estimated Project Scope & Investment
- **Estimated Budget Range:** $1,800 – $4,500 (flexible based on material selections).
- **Projected Turnaround:** 2 to 4 weeks for procurement, painting, and staging.{preview_notice}"""


@router.get("/status")
def get_status():
    """Return backend connection status and available inference modes with live Colab check."""
    load_dotenv(override=True)
    local_available = _is_local_available()
    colab_ready = _is_colab_configured()
    colab_url = os.getenv("COLAB_INFERENCE_URL", "").strip().strip("'\"")

    if colab_ready:
        is_live, colab_label = _is_colab_live()
        if is_live:
            active_mode = "colab"
            mode_label = colab_label
        else:
            active_mode = "colab_offline"
            mode_label = "⚠️ Colab Offline (Update URL in .env)"
    elif local_available:
        active_mode = "local"
        mode_label = "Local PyTorch"
    else:
        active_mode = "preview"
        mode_label = "Instant Smart Preview"

    return {
        "status": "ready",
        "active_mode": active_mode,
        "mode_label": mode_label,
        "colab_configured": colab_ready,
        "colab_live": _is_colab_live()[0] if colab_ready else False,
        "local_pytorch_available": local_available,
        "colab_url": colab_url,
    }


@router.get("/colab-ping")
def ping_colab():
    """Manually test connection to the configured Colab URL."""
    load_dotenv(override=True)
    url = os.getenv("COLAB_INFERENCE_URL", "").strip().strip("'\"")
    is_live, msg = _check_colab_health(timeout=3.5)
    return {
        "configured_url": url,
        "is_live": is_live,
        "message": msg,
    }



@router.post("/try-on")
async def try_on(
    place_image: UploadFile = File(...),
    design_type: str = Form("interior"),
    room_type: str = Form("living"),
    style: str = Form("modern"),
    background_color: str = Form("#ffffff"),
    foreground_color: str = Form("#000000"),
    instructions: str = Form(""),
):
    content_type = (place_image.content_type or "").lower()
    filename = (place_image.filename or "").lower()
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    valid_mimes = {"image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp"}

    if content_type not in valid_mimes and not filename.endswith(valid_exts):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type ({content_type or filename}). Please upload a JPEG, PNG, or WEBP image.",
        )

    place_bytes = await place_image.read()
    if not place_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(place_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Image exceeds the 10 MB size limit.",
        )

    # Validate that image is readable by PIL
    try:
        with Image.open(io.BytesIO(place_bytes)) as test_img:
            test_img.verify()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid, readable image.",
        ) from exc

    # Convert hex color codes to descriptive names the AI model can understand.
    # Diffusion models do NOT understand '#f4ede4' but DO understand 'warm beige'.
    bg_color_name = _hex_to_color_name(background_color)
    fg_color_name = _hex_to_color_name(foreground_color)

    print(f"🎨 Color translation: {background_color} → '{bg_color_name}' | {foreground_color} → '{fg_color_name}'")

    extra = f" {instructions.strip()}" if instructions.strip() else ""
    prompt = (
        f"A photorealistic {design_type} redesign of a {room_type}, "
        f"{style} style interior design. "
        f"Primary wall and surface color: {bg_color_name}. "
        f"Furniture and accent color: {fg_color_name}. "
        f"High quality, well-lit, professional interior photography.{extra}"
    ).strip()

    load_dotenv(override=True)
    use_local_env = os.getenv("USE_LOCAL_MODEL", "auto").strip().lower()
    has_colab = _is_colab_configured()
    has_local = _is_local_available()

    # Determine inference route
    if use_local_env in ("true", "1", "yes") and has_local:
        route = "local"
    elif has_colab and use_local_env not in ("true", "1", "yes"):
        route = "colab"
    elif has_local:
        route = "local"
    else:
        route = "preview"

    print("\n" + "=" * 55)
    print("🚀 INCOMING MAKEOVER REQUEST:")
    print(f"   Selected Engine Route: {route.upper()}")
    print(f"   Configured Colab URL: {os.getenv('COLAB_INFERENCE_URL', '').strip()}")
    print("=" * 55)


    mode_used = ""
    generated_image_bytes = None

    if route == "colab":
        mode_used = "Google Colab GPU"
        try:
            response = await asyncio.to_thread(
                _request_colab,
                {
                    "image_base64": base64.b64encode(place_bytes).decode("ascii"),
                    "prompt": prompt,
                    "strength": 0.65,
                    "steps": 4,
                },
            )
            generated_image_bytes = base64.b64decode(
                response["image_base64"],
                validate=True,
            )
            with Image.open(io.BytesIO(generated_image_bytes)) as gen_img:
                print(f"🖼️ Verified AI image from Colab: {gen_img.size[0]}x{gen_img.size[1]} | Format: {gen_img.format} | Size: {len(generated_image_bytes) / 1024:.1f} KB")
        except HTTPException:
            raise

        except Exception as exc:
            print(f"❌ Colab generation failed: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Colab generation failed: {str(exc)}",
            ) from exc

    elif route == "local":
        mode_used = f"Local PC ({_local_pipe_device or 'PyTorch'})"
        try:
            generated_image_bytes = await asyncio.to_thread(
                _run_local_inference,
                place_bytes,
                prompt,
                0.55,
            )
        except Exception as exc:
            print(f"Local inference failed ({exc}), falling back to preview mode.")
            mode_used = "Instant Smart Preview (Local Fallback)"
            generated_image_bytes = await asyncio.to_thread(
                _run_preview_mode,
                place_bytes,
                background_color,
                foreground_color,
                style,
                instructions,
            )

    else:
        if use_local_env in ("true", "1", "yes") and not has_local:
            mode_used = "Instant Smart Preview (PyTorch Not Installed)"
        elif not has_colab:
            mode_used = "Instant Smart Preview (Colab Not Connected)"
        else:
            mode_used = "Instant Smart Preview"

        generated_image_bytes = await asyncio.to_thread(
            _run_preview_mode,
            place_bytes,
            background_color,
            foreground_color,
            style,
            instructions,
        )

    image_url = f"data:image/png;base64,{base64.b64encode(generated_image_bytes).decode('ascii')}"
    text_response = _generate_design_report(
        room_type=room_type,
        design_type=design_type,
        style=style,
        background_color=background_color,
        foreground_color=foreground_color,
        instructions=instructions,
        mode_used=mode_used,
    )

    return JSONResponse(
        content={
            "image": image_url,
            "text": text_response,
            "mode": mode_used,
        }
    )

