"""Liquid Glass 前端设计与无障碍契约。"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

WEBUI_ROOT = Path("src/webUI")
TEMPLATE_ROOT = WEBUI_ROOT / "templates"
STATIC_ROOT = WEBUI_ROOT / "static"
LIQUID_CSS = STATIC_ROOT / "css" / "liquid-glass.css"
ICON_SPRITE = STATIC_ROOT / "icons.svg"
LANDSCAPE_BACKGROUND = STATIC_ROOT / "images" / "liquid-landscape.webp"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_liquid_glass_assets_are_loaded_on_app_and_login_pages():
    for template_name in ("base.html", "login.html"):
        template = _read(TEMPLATE_ROOT / template_name)
        assert "/static/css/style.css?v=1" in template
        assert "/static/css/liquid-glass.css?v=1" in template
        assert '<link rel="preload" href="/static/images/liquid-landscape.webp"' in template

    css = _read(LIQUID_CSS)
    assert "--liquid-regular" in css
    assert "backdrop-filter:" in css
    assert "@supports not ((backdrop-filter:" in css
    assert "../images/liquid-landscape.webp" in css
    assert LANDSCAPE_BACKGROUND.stat().st_size > 0


def test_svg_sprite_and_template_macro_cover_structural_icons():
    macro = _read(TEMPLATE_ROOT / "partials" / "icon.html")
    sprite = _read(ICON_SPRITE)

    assert "/static/icons.svg#icon-{{ name }}" in macro
    for icon_name in (
        "settings",
        "tasks",
        "chart",
        "logs",
        "user",
        "refresh",
        "save",
        "close",
    ):
        assert f'id="icon-{icon_name}"' in sprite

    structural_sources = [
        *TEMPLATE_ROOT.glob("*.html"),
        TEMPLATE_ROOT / "partials" / "sidebar.html",
        *sorted((STATIC_ROOT / "js").glob("*.js")),
    ]
    structural_emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    for path in structural_sources:
        assert structural_emoji.search(_read(path)) is None, f"仍有结构性 Emoji: {path}"


def test_mobile_navigation_has_four_routes_and_safe_area_spacing():
    base = _read(TEMPLATE_ROOT / "base.html")
    css = _read(LIQUID_CSS)

    mobile_nav = re.search(
        r'<nav class="mobile-bottom-nav".*?</nav>',
        base,
        flags=re.DOTALL,
    )
    assert mobile_nav is not None
    assert re.findall(r'href="(/[^"]+)"', mobile_nav.group(0)) == [
        "/config",
        "/tasks",
        "/data",
        "/logs",
    ]
    assert 'aria-current="page"' in mobile_nav.group(0)
    assert "env(safe-area-inset-bottom)" in css
    assert "--mobile-nav-height" in css
    assert "min-height: 44px" in css


def test_liquid_glass_preserves_shell_positioning():
    css = _read(LIQUID_CSS)

    for selector, position in (
        (".sidebar", "fixed"),
        (".page-topbar", "sticky"),
        (".config-module-nav", "sticky"),
        (".task-toolbar", "sticky"),
        ("body.page-data .tabs-scroll-wrap", "sticky"),
        (".mobile-bottom-nav", "fixed"),
    ):
        assert re.search(
            rf"{re.escape(selector)}[^{{]*\{{[^}}]*position:\s*{position};",
            css,
            flags=re.DOTALL,
        ), f"{selector} 应保持 {position} 定位"


def test_surface_radius_and_log_viewer_use_shared_layout_tokens():
    css = _read(LIQUID_CSS)

    for token in (
        "--liquid-radius-control:",
        "--liquid-radius-card:",
        "--liquid-radius-panel:",
        "--liquid-radius-sheet:",
    ):
        assert token in css

    assert ":is(" in css
    assert "border-radius: var(--liquid-radius-card)" in css
    assert "--liquid-content: rgba(255, 255, 255, 0.92);" in css
    assert "--liquid-data: rgba(255, 255, 255, 0.9);" in css
    assert "--liquid-data: rgba(24, 23, 36, 0.88);" in css
    assert "body.page-logs .content-body" in css
    assert "max-width: 1320px" in css
    assert "body.page-logs .logs-container" in css


def test_motion_transparency_and_keyboard_accessibility_have_fallbacks():
    css = _read(LIQUID_CSS)
    common_js = _read(STATIC_ROOT / "js" / "common.js")
    data_js = _read(STATIC_ROOT / "js" / "data.js")

    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (prefers-reduced-transparency: reduce)" in css
    assert "@media (forced-colors: active)" in css
    assert ":focus-visible" in css
    assert "aria-live" in common_js
    assert "openAccessibleModal" in common_js
    assert "closeAccessibleModal" in common_js
    assert "event.key !== 'Tab'" in common_js
    assert "拖拽或使用方向键调整顺序" in data_js
    assert "ArrowUp" in data_js and "ArrowDown" in data_js


def test_data_cards_use_translucent_glass_and_pointer_hover_magnification():
    css = _read(LIQUID_CSS)
    data_template = _read(TEMPLATE_ROOT / "data.html")

    assert "--liquid-data:" in css
    assert "--liquid-data-hover:" in css
    assert "--liquid-data-sheen:" in css
    assert re.search(
        r"\.data-card::after\s*\{[^}]+border-radius:\s*var\(--data-card-radius\);",
        css,
        flags=re.DOTALL,
    )
    assert re.search(
        r"body\.page-data \.data-card\s*\{[^}]+--data-card-radius:\s*var\(--liquid-radius-card\);",
        css,
        flags=re.DOTALL,
    )
    assert re.search(
        r"body\.page-data \.data-card\s*\{[^}]+backdrop-filter:\s*none;[^}]+-webkit-backdrop-filter:\s*none;",
        css,
        flags=re.DOTALL,
    )
    assert "@media (hover: hover) and (pointer: fine)" in css
    assert re.search(
        r"\.data-card:not\([^}]+:hover\s*\{[^}]+scale3d\(1\.025,\s*1\.025,\s*1\)",
        css,
        flags=re.DOTALL,
    )
    assert ".data-card:not(.data-card-dragging):not(.data-card-chosen):hover::after" in css
    assert ".data-card:hover::before" in css
    assert '{% block body_class %} class="page-data"{% endblock %}' in data_template
    assert ".data-card.weibo-feed-card:nth-child(odd)" in css
    assert "body.page-data .content-body > .card" in css
    assert "body.page-data .table-container" in css


def test_tabs_and_modals_expose_semantic_state():
    config = _read(TEMPLATE_ROOT / "config.html")
    tasks = _read(TEMPLATE_ROOT / "tasks.html")
    data = _read(TEMPLATE_ROOT / "data.html")
    base = _read(TEMPLATE_ROOT / "base.html")

    for template in (config, tasks, data):
        assert 'role="tablist"' in template
        assert 'aria-selected="true"' in template
        assert 'aria-selected="false"' in template

    for template in (base, tasks):
        assert 'role="dialog"' in template
        assert 'aria-modal="true"' in template
        assert 'aria-hidden="true"' in template


def test_all_frontend_templates_render_with_the_icon_macro():
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_ROOT),
        autoescape=select_autoescape(("html",)),
    )

    for template_name in (
        "base.html",
        "login.html",
        "config.html",
        "tasks.html",
        "data.html",
        "logs.html",
    ):
        rendered = environment.get_template(template_name).render(
            page_title="测试页面",
            active_nav="config",
        )
        assert "icon-" in rendered
        assert "ui-icon" in rendered
