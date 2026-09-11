import sys
import subprocess

try:
    import playwright
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1000, 'height': 800})
    # We will just load the CSS and the HTML snippet
    with open('static/fin2.css', 'r') as f:
        css = f.read()
    with open('templates/dashboard/xp_statement.html', 'r') as f:
        html = f.read()
    
    # Create a mock page
    full_html = f"""
    <!DOCTYPE html>
    <html><head><style>{css}</style></head>
    <body>
    <main>
    <section class="panel">
    <form>
    {html}
    </form>
    </section>
    </main>
    </body></html>
    """
    page.set_content(full_html)
    page.screenshot(path="table_screenshot.png", full_page=True)
    
    # Evaluate widths
    table_wrap_width = page.evaluate("document.querySelector('.table-wrap').scrollWidth")
    table_width = page.evaluate("document.querySelector('.table-wrap table').offsetWidth")
    viewport_width = page.evaluate("window.innerWidth")
    
    print(f"Viewport width: {viewport_width}")
    print(f"Table-wrap scrollWidth: {table_wrap_width}")
    print(f"Table offsetWidth: {table_width}")
    browser.close()
