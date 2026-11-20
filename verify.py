from __future__ import annotations

import base64
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image
import numpy as np

from art import LATVERIA_PALETTE_HEX, hex_to_rgb
from build import (
    CSS_LIMIT,
    DOOMSDAY_COLORS,
    EXPECTED_COLOR_ROLES,
    PROTECTED_APP_VARIABLES,
    SHORT_VARIABLES,
    VARIANTS,
    ThemeVariant,
    build_theme,
    validate_build_invariants,
)

ROOT = Path(__file__).parent


def verify_built_payload(variant: ThemeVariant, payload: dict) -> None:
    assert payload.get("version") == 1, f"Invalid version in {variant.id}"
    assert payload.get("name") == variant.name, f"Invalid name in {variant.id}"
    assert payload.get("appearance") == "dark", f"Appearance is not dark in {variant.id}"

    colors = payload.get("colors", {})
    assert len(colors) == EXPECTED_COLOR_ROLES, f"Unexpected color role count in {variant.id}"
    for k, v in DOOMSDAY_COLORS.items():
        assert colors.get(k) == v, f"Color mismatch for role {k} in {variant.id}"

    css = payload.get("css", "")
    assert len(css) <= CSS_LIMIT, f"CSS length {len(css)} exceeds {CSS_LIMIT} in {variant.id}"

    for placeholder in ("__ART__", "__ART_WIDTH__", "__PLUS_PRESSED__"):
        assert placeholder not in css, f"Unresolved placeholder {placeholder} in {variant.id}"

    for long_dm_var in SHORT_VARIABLES:
        assert long_dm_var not in css, f"Unshortened variable {long_dm_var} found in {variant.id}"

    for nyx_leak in ("#8a7fe8", "#b4aaff", "#07061c", "--nyx-"):
        assert nyx_leak not in css, f"Nyx theme leak '{nyx_leak}' found in {variant.id}"

    raw_css = "\n".join((ROOT / source).read_text(encoding="utf-8") for source in variant.sources)
    for protected_var in PROTECTED_APP_VARIABLES:
        if protected_var in raw_css:
            assert protected_var in css, f"Protected variable {protected_var} altered in {variant.id}"

    match = re.search(r"url\((data:image/webp;base64,[^)]+)\)", css)
    assert match is not None, f"Embedded data URI missing in {variant.id}"
    raw_webp = base64.b64decode(match.group(1).split(",", 1)[1])
    decoded_img = Image.open(io.BytesIO(raw_webp)).convert("RGB")
    assert decoded_img.size == (480, 270), f"Decoded image size {decoded_img.size} is not 480x270"

    canonical_img = Image.open(ROOT / "assets" / "throne.png").convert("RGB")
    decoded_arr = np.asarray(decoded_img)
    canonical_arr = np.asarray(canonical_img)
    assert np.array_equal(decoded_arr, canonical_arr), "Decoded pixels differ from throne.png"

    allowed_colors = {hex_to_rgb(h) for h in LATVERIA_PALETTE_HEX}
    unique_pixels = {
        tuple(int(v) for v in rgb)
        for rgb in np.unique(decoded_arr.reshape(-1, 3), axis=0)
    }
    bad_colors = unique_pixels - allowed_colors
    assert not bad_colors, f"Pixel colors outside LATVERIA_PALETTE_HEX: {bad_colors}"


def verify_negative_invariants() -> None:
    bad_colors_count = dict(DOOMSDAY_COLORS)
    bad_colors_count.pop("canvas")
    try:
        validate_build_invariants(bad_colors_count, SHORT_VARIABLES)
        raise AssertionError("Validation did not fail on color role count mismatch")
    except ValueError:
        pass

    bad_colors_hex = dict(DOOMSDAY_COLORS)
    bad_colors_hex["canvas"] = "not-a-hex"
    try:
        validate_build_invariants(bad_colors_hex, SHORT_VARIABLES)
        raise AssertionError("Validation did not fail on invalid hex color")
    except ValueError:
        pass

    try:
        validate_build_invariants(DOOMSDAY_COLORS, {"--dm-rim": "--w"})
        raise AssertionError("Validation did not fail on reserved variable collision")
    except ValueError:
        pass

    try:
        validate_build_invariants(DOOMSDAY_COLORS, {"--dm-rim": "--glass-opacity"})
        raise AssertionError("Validation did not fail on protected app variable collision")
    except ValueError:
        pass

    try:
        validate_build_invariants(DOOMSDAY_COLORS, {"--dm-rim": "--r", "--dm-rim-soft": "--r"})
        raise AssertionError("Validation did not fail on duplicate short aliases")
    except ValueError:
        pass


class _ResultAttrParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.result: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "body":
            return
        for name, value in attrs:
            if name == "data-result":
                self.result = value
                break


def verify_chromium_stylesheet(variant: ThemeVariant, css: str) -> None:
    chromium_bin = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium") or "/usr/bin/chromium"
    if not Path(chromium_bin).exists():
        print(f"Skipping Chromium parse check ({chromium_bin} not found)")
        return

    is_plus = variant.id.endswith("-plus")
    html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<title>Theme Test</title>
</head>
<body>
  <div data-slot="sidebar-wrapper">
    <div data-slot="sidebar-container">
      <div data-app-sidebar>
        <div data-sidebar-row="draft-1">
          <div class="z-10">
            <div class="h-5"><span class="font-normal">Thread</span></div>
            <div class="mt-1">Title</div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div data-chat-canvas>
    <div data-workspace-area="conversation">
      <div class="messages-timeline-scroll"></div>
      <div data-chat-composer-form>
        <div data-slot="composer-host"></div>
      </div>
    </div>
  </div>
  <div data-environment-identification="pill"></div>
  <div data-slot="popover-popup">
    <div>
      <div data-model-picker-content>
        <div class="flex-1">
          <div class="shrink-0"><input type="text"></div>
        </div>
      </div>
      <div data-model-picker-sidebar>
        <button aria-pressed="true">Claude</button>
      </div>
      <div data-model-picker-effort>
        <div role="radiogroup">
          <button aria-checked="true">High</button>
        </div>
      </div>
      <svg class="lucide-star fill-current"></svg>
    </div>
  </div>
<script>
  try {{
    const cssText = {json.dumps(css)};
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(cssText);
    document.adoptedStyleSheets = [sheet];
    const rulesCount = sheet.cssRules.length;
    const pillColor = getComputedStyle(document.querySelector('[data-environment-identification="pill"]')).color;
    const wrapperBg = getComputedStyle(document.querySelector('[data-slot="sidebar-wrapper"]'), '::before').backgroundImage;
    const starColor = getComputedStyle(document.querySelector('.lucide-star.fill-current')).color;
    const sidebarOrder = getComputedStyle(document.querySelector('[data-model-picker-sidebar]')).order;
    const radio = document.querySelector('[data-model-picker-effort] [role="radiogroup"]');
    const radioAfterBg = getComputedStyle(radio, '::after').backgroundImage;
    const sidebarPressedBg = getComputedStyle(document.querySelector('[data-model-picker-sidebar] [aria-pressed="true"]')).backgroundImage;
    const checks = [
      rulesCount > 0,
      pillColor === 'rgb(240, 217, 138)',
      wrapperBg.includes('data:image/webp;base64'),
    ];
    if ({json.dumps(is_plus)}) {{
      checks.push(
        starColor === 'rgb(240, 203, 84)',
        sidebarOrder === '-1',
        radioAfterBg.includes('data:image/webp;base64'),
        sidebarPressedBg.includes('16, 185, 129'),
      );
    }}
    document.body.setAttribute('data-result', JSON.stringify({{
      ok: checks.every(Boolean),
      rulesCount,
      pillColor,
      starColor,
      sidebarOrder,
      hasWrapperWebp: wrapperBg.includes('data:image/webp;base64'),
      hasEffortWebp: radioAfterBg.includes('data:image/webp;base64'),
      sidebarPressedBg,
    }}));
  }} catch (err) {{
    document.body.setAttribute('data-result', JSON.stringify({{ ok: false, error: err.message }}));
  }}
</script>
</body>
</html>"""

    with tempfile.TemporaryDirectory(dir="/tmp") as tmp_dir:
        html_file = Path(tmp_dir) / "test.html"
        html_file.write_text(html_content, encoding="utf-8")
        user_data_dir = Path(tmp_dir) / "chrome-profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        env["TMPDIR"] = "/tmp"

        cmd = [
            chromium_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={user_data_dir}",
            "--dump-dom",
            f"file://{html_file.resolve()}",
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        parser = _ResultAttrParser()
        parser.feed(proc.stdout)
        parser.close()
        assert parser.result is not None, (
            f"Chromium script did not emit data-result for {variant.id}"
        )
        parsed = json.loads(parser.result)
        assert parsed.get("ok") is True, f"Chromium check failed for {variant.id}: {parsed}"


def main() -> None:
    verify_negative_invariants()

    for variant in VARIANTS:
        built = build_theme(variant, ROOT, DOOMSDAY_COLORS)
        payload = built.to_payload()
        verify_built_payload(variant, payload)
        verify_chromium_stylesheet(variant, built.css)

        disk_file = ROOT / f"{variant.id}.json"
        assert disk_file.exists(), f"Missing built file on disk: {disk_file.name}"
        disk_payload = json.loads(disk_file.read_text(encoding="utf-8"))
        assert disk_payload == payload, f"{disk_file.name} on disk is stale relative to build.py"
        print(f"Verified {disk_file.name} ({len(built.css)} css chars)")

    print("All verification invariants passed.")


if __name__ == "__main__":
    main()
