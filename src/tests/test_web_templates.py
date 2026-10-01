"""关键页面模板渲染与共享资源版本冒烟检查。"""

from src.web.templating import STATIC_ASSET_VERSION, templates


def test_all_frontend_templates_render_with_the_icon_macro():
    for template_name in (
        "base.html",
        "login.html",
        "config.html",
        "tasks.html",
        "data.html",
        "logs.html",
    ):
        rendered = templates.env.get_template(template_name).render(
            page_title="测试页面",
            active_nav="config",
            static_version=STATIC_ASSET_VERSION,
        )
        assert "icon-" in rendered
        assert "ui-icon" in rendered
        assert f"?v={STATIC_ASSET_VERSION}" in rendered
