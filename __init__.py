import os
import json
from aqt import mw, gui_hooks
from aqt.deckbrowser import DeckBrowser
from aqt.reviewer import Reviewer
from aqt.overview import Overview
from aqt.toolbar import Toolbar, BottomBar
from aqt.qt import QWidget, QHBoxLayout, QPushButton, Qt, QToolBar
from . import patcher
from . import settings
from . import config
from . import menu_buttons
from . import heatmap
from . import welcome_dialog # ADDED

addon_path = os.path.dirname(__file__)
addon_package = mw.addonManager.addonFromModule(__name__)
user_files_root = f"/_addons/{addon_package}/user_files"
web_assets_root = f"/_addons/{addon_package}/web"

def inject_menu_files(web_content, context):
    conf = config.get_config()
    should_hide = conf.get("hideNativeHeaderAndBottomBar", False)
    is_deck_browser = isinstance(context, DeckBrowser)
    is_reviewer = isinstance(context, Reviewer)
    is_overview = isinstance(context, Overview)
    is_top_toolbar = isinstance(context, Toolbar)
    is_bottom_toolbar = isinstance(context, BottomBar)
    is_reviewer_bottom_bar = type(context).__name__ == "ReviewerBottomBar"
    if is_deck_browser or is_reviewer or is_overview:
        web_content.head += patcher.generate_dynamic_css(conf)
    if is_deck_browser:
        css_path = os.path.join(addon_path, "web", "menu.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            print(f"Onigiri Error: Could not find menu.css at {css_path}")
        heatmap_css_path = os.path.join(addon_path, "web", "heatmap.css")
        try:
            with open(heatmap_css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            print(f"Onigiri Error: Could not find heatmap.css at {heatmap_css_path}")
        web_content.head += patcher.generate_profile_bar_fix_css()
        web_content.head += patcher.generate_deck_browser_backgrounds(addon_path)
        web_content.head += patcher.generate_icon_css(addon_package, conf)
        web_content.head += patcher.generate_conditional_css(conf)
        web_content.head += patcher.generate_icon_size_css()
        web_content.head += f'<script src="{web_assets_root}/injector.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/heatmap.js"></script>'
    elif is_reviewer:
        web_content.head += patcher.generate_reviewer_background_css(addon_path)

        # Add top bar background CSS
        web_content.head += patcher.generate_reviewer_top_bar_background_css(addon_path)

        # Get top bar HTML and structural CSS
        top_bar_html, top_bar_css = patcher.generate_reviewer_top_bar_html_and_css()
        web_content.head += top_bar_css

        # FIX: Escape backticks for JS template literal to avoid f-string syntax error in Python < 3.12
        escaped_top_bar_html = top_bar_html.replace("`", "\\`")

        # Injector script to add both background div and top bar div
        js_injector = f"""
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                // Add background div
                if (!document.getElementById('onigiri-background-div')) {{
                    const bgDiv = document.createElement('div');
                    bgDiv.id = 'onigiri-background-div';
                    document.body.prepend(bgDiv);
                }}

                // Add top bar HTML
                const topBarHtml = `{escaped_top_bar_html}`;
                if (topBarHtml.trim() && !document.getElementById('onigiri-reviewer-header')) {{
                    document.body.insertAdjacentHTML('afterbegin', topBarHtml);
                }}
            }});
        </script>
        """
        web_content.head += js_injector
    elif is_overview:
        web_content.head += patcher.generate_overview_background_css(addon_path)

        # Add top bar structural CSS
        _top_bar_html, top_bar_css = patcher.generate_reviewer_top_bar_html_and_css()
        web_content.head += top_bar_css

        css_path = os.path.join(addon_path, "web", "overview.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            print(f"Onigiri Error: Could not find overview.css at {css_path}")
    if is_reviewer_bottom_bar:
        web_content.head += patcher.generate_reviewer_bottom_bar_background_css(addon_path)
    elif (is_top_toolbar or is_bottom_toolbar):
        if not should_hide:
            web_content.head += patcher.generate_toolbar_background_css(addon_path)

# --- NEW FUNCTION ---
def maybe_show_welcome_popup():
    """Shows the welcome pop-up if it hasn't been disabled by the user."""
    conf = config.get_config()
    if conf.get("showWelcomePopup", True):
        welcome_dialog.show_welcome_dialog()

def initial_setup():
    patcher.take_control_of_deck_browser_hook()
    patcher.apply_patches()
    patcher.patch_overview()
    patcher.patch_congrats_page()
    menu_buttons.setup_onigiri_menu(addon_path)
    maybe_show_welcome_popup() # ADDED

def on_deck_browser_did_render(deck_browser: DeckBrowser):
    conf = config.get_config()
    grid_layout = conf.get("onigiriWidgetLayout", {}).get("grid", {})
    if "heatmap" in grid_layout:
        try:
            heatmap_data, heatmap_config = heatmap.get_heatmap_and_config()
            js = f"OnigiriHeatmap.render('onigiri-heatmap-container', {json.dumps(heatmap_data)}, {json.dumps(heatmap_config)});"
            deck_browser.web.eval(js)
        except Exception as e:
            print(f"Onigiri heatmap failed to render: {e}")

gui_hooks.main_window_did_init.append(initial_setup)
gui_hooks.webview_will_set_content.append(inject_menu_files)
gui_hooks.deck_browser_will_render_content.append(patcher.render_custom_main_screen)
gui_hooks.deck_browser_did_render.append(on_deck_browser_did_render)
gui_hooks.webview_did_receive_js_message.append(patcher.on_webview_js_message)
mw.addonManager.setWebExports(__name__, r"((user_files|web)/.*|onigiri_logo\.png)")
