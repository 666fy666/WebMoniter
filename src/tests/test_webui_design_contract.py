"""Liquid Glass 前端设计与无障碍契约。"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.web.templating import STATIC_ASSET_VERSION

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
        assert "/static/css/style.css?v={{ static_version }}" in template
        assert "/static/css/liquid-glass.css?v={{ static_version }}" in template
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
    assert 'id="mobileMenuBtn"' in mobile_nav.group(0)
    assert 'aria-current="page"' in mobile_nav.group(0)
    assert "env(safe-area-inset-bottom)" in css
    assert "--mobile-nav-height" in css
    assert "min-height: 44px" in css


def test_shell_removes_page_topbar_and_uses_sidebar_collapse_handle():
    base = _read(TEMPLATE_ROOT / "base.html")
    sidebar = _read(TEMPLATE_ROOT / "partials" / "sidebar.html")
    style_css = _read(STATIC_ROOT / "css" / "style.css")
    common_js = _read(STATIC_ROOT / "js" / "common.js")

    assert "page-topbar" not in base
    assert 'class="page-title-group"' not in base
    assert 'class="sr-only"' in base
    assert 'id="sidebarCollapseHandle"' in sidebar
    assert "sidebar-collapse-handle" in style_css
    assert "sidebarCollapseHandle" in common_js
    assert "applyDesktopCollapsedState" in common_js


def test_liquid_glass_preserves_shell_positioning():
    css = _read(LIQUID_CSS)

    for selector, position in (
        (".sidebar", "fixed"),
        (".config-module-nav", "sticky"),
        (".task-toolbar", "sticky"),
        ("body.page-data .tabs-scroll-wrap", "sticky"),
        (".mobile-bottom-nav", "fixed"),
        (".theme-toggle-fab", "fixed"),
        (".data-card-drag-handle", "absolute"),
    ):
        assert re.search(
            rf"{re.escape(selector)}[^{{]*\{{[^}}]*position:\s*{position};",
            css,
            flags=re.DOTALL,
        ), f"{selector} 应保持 {position} 定位"

    assert ".data-card > :not(.data-card-drag-handle)" in css
    assert ".btn:not(.theme-toggle-fab)" in css


def test_back_to_top_keeps_fixed_position_and_hidden_state():
    style_css = _read(STATIC_ROOT / "css" / "style.css")
    liquid_css = _read(LIQUID_CSS)
    liquid_rules = re.findall(r"([^{}]+)\{([^{}]*)\}", liquid_css)

    assert re.search(
        r"\.back-to-top\s*\{[^}]*position:\s*fixed;[^}]*display:\s*none;",
        style_css,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.back-to-top\.show\s*\{[^}]*display:\s*flex;",
        style_css,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.back-to-top\s*\{[^}]*overflow:\s*clip;",
        liquid_css,
        flags=re.DOTALL,
    )
    assert not any(
        ".back-to-top" in selector
        and not selector.strip().endswith("> *")
        and re.search(r"position:\s*relative;", declarations)
        for selector, declarations in liquid_rules
    )
    assert not any(
        ".back-to-top" in selector
        and re.search(r"display:\s*inline-grid;", declarations)
        for selector, declarations in liquid_rules
    )


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
    assert "body.page-config.is-config-text-view #textView" in css
    assert "body.page-config.is-config-text-view #yamlEditor" in css
    assert 'class="page-config"' in _read(TEMPLATE_ROOT / "config.html")
    assert "setConfigView" in _read(STATIC_ROOT / "js" / "config.js")


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


def test_frontend_controls_and_dynamic_config_fields_have_accessible_names():
    config = _read(TEMPLATE_ROOT / "config.html")
    tasks = _read(TEMPLATE_ROOT / "tasks.html")
    config_js = _read(STATIC_ROOT / "js" / "config.js")

    assert 'id="configModuleSearch"' in config
    assert 'aria-label="搜索监控任务配置"' in config
    assert 'id="taskSearch"' in tasks
    assert 'aria-label="搜索任务名称或 ID"' in tasks
    assert "function ensureConfigControlAccessibleNames" in config_js
    assert "control.setAttribute('aria-labelledby', labelCell.id)" in config_js
    assert "new MutationObserver" in config_js


def test_external_template_links_are_isolated_and_scripts_share_cache_version():
    template_paths = [
        *TEMPLATE_ROOT.glob("*.html"),
        TEMPLATE_ROOT / "partials" / "sidebar.html",
    ]
    for path in template_paths:
        source = _read(path)
        for match in re.finditer(r'<a\b[^>]*target="_blank"[^>]*>', source):
            tag = match.group(0)
            assert 'rel="noopener noreferrer"' in tag, f"外链缺少隔离属性: {path}"

    for path, script_name in (
        (TEMPLATE_ROOT / "base.html", "common.js"),
        (TEMPLATE_ROOT / "login.html", "common.js"),
        (TEMPLATE_ROOT / "login.html", "login.js"),
        (TEMPLATE_ROOT / "tasks.html", "tasks.js"),
        (TEMPLATE_ROOT / "logs.html", "logs.js"),
        (TEMPLATE_ROOT / "data.html", "data.js"),
    ):
        assert f"/static/js/{script_name}?v={{{{ static_version }}}}" in _read(path)

    assert STATIC_ASSET_VERSION == "1"

    interactive_sources = [*template_paths, *sorted((STATIC_ROOT / "js").glob("*.js"))]
    for path in interactive_sources:
        assert not re.search(r"\bon(?:click|change|input)\s*=", _read(path)), (
            f"仍有内联事件处理器: {path}"
        )


def test_high_risk_visual_tokens_and_controls_keep_accessibility_contract():
    css = _read(STATIC_ROOT / "css" / "style.css")

    for declaration in (
        "--primary-color: #be185d;",
        "--text-muted: #626b7b;",
        "--success-color: #15803d;",
        "--warning-color: #92400e;",
        "--error-color: #b91c1c;",
        "--info-color: #1d4ed8;",
        "--z-lightbox: 3000;",
        "--z-toast: 3100;",
    ):
        assert declaration in css

    assert "transition: all" not in css
    assert "content: '🔐'" not in css
    assert "z-index: var(--z-lightbox)" in css
    assert "z-index: var(--z-toast)" in css
    toast_close = re.search(r"\.toast-close\s*\{(?P<body>[^}]+)\}", css)
    assert toast_close is not None
    assert "width: 44px" in toast_close.group("body")
    assert "height: 44px" in toast_close.group("body")


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
        assert 'aria-orientation="horizontal"' in template
        assert 'aria-selected="true"' in template
        assert 'aria-selected="false"' in template

    for template in (base, tasks):
        assert 'role="dialog"' in template
        assert 'aria-modal="true"' in template
        assert 'aria-hidden="true"' in template


def test_tab_keyboard_navigation_and_touch_targets_are_consistent():
    common_js = _read(STATIC_ROOT / "js" / "common.js")
    liquid_css = _read(LIQUID_CSS)

    assert "function initTablistKeyboardNavigation" in common_js
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in common_js
    assert "initTablistKeyboardNavigation();" in common_js
    assert re.search(
        r"\.password-input-wrap \.password-toggle\s*\{[^}]*width:\s*44px;[^}]*height:\s*44px;",
        liquid_css,
        flags=re.DOTALL,
    )
    assert '{% block body_class %} class="page-tasks"{% endblock %}' in _read(
        TEMPLATE_ROOT / "tasks.html"
    )


def test_custom_cursor_and_pointer_reactions_keep_safe_fallbacks():
    common_js = _read(STATIC_ROOT / "js" / "common.js")
    liquid_css = _read(LIQUID_CSS)

    assert "function initCustomCursorExperience" in common_js
    assert "CUSTOM_CURSOR_HOVER_SELECTOR" in common_js
    assert "CUSTOM_CURSOR_TEXT_SELECTOR" in common_js
    assert "CURSOR_MAGNET_SELECTOR" in common_js
    assert "requestAnimationFrame(animate)" in common_js
    assert "initCustomCursorExperience();" in common_js
    assert "(hover: hover) and (pointer: fine)" in common_js
    assert "(forced-colors: active)" in common_js

    for selector in (
        ".custom-cursor-ring",
        ".custom-cursor-dot",
        ".custom-cursor-ring.is-hover",
        ".custom-cursor-ring.is-text",
        ".card.cursor-reactive-card:hover",
    ):
        assert selector in liquid_css
    assert "--cursor-pull-x" in liquid_css
    assert "--cursor-tilt-x" in liquid_css
    assert "cursor: revert !important" in liquid_css
    assert re.search(
        r"\.custom-cursor-ring\s*\{[^}]*width:\s*28px;[^}]*height:\s*28px;"
        r"[^}]*backdrop-filter:\s*blur\(1px\)",
        liquid_css,
        flags=re.DOTALL,
    )
    assert re.search(
        r"\.custom-cursor-ring\.is-hover\s*\{[^}]*scale:\s*1\.35;",
        liquid_css,
        flags=re.DOTALL,
    )


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
            static_version=STATIC_ASSET_VERSION,
        )
        assert "icon-" in rendered
        assert "ui-icon" in rendered
