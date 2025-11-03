import asyncio
import json
from typing import Optional

from ulid import ULID

try:
    from pyppeteer import launch
except ImportError:
    raise SystemExit(
        "pyppeteer is not installed. Install it with:\n\n    pip install pyppeteer\n"
    )


async def wait_for_user_command(
    prompt: str = 'Type "continue" to capture, or "reload" to reload, or "quit" to exit: ',
) -> str:
    # Avoid blocking the event loop while waiting for terminal input
    cmd: str = await asyncio.to_thread(input, prompt)
    return cmd.strip().lower()


def save_html(html: str):
    file_path = f"search_pages/{ULID()}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)


async def new_browser_page(browser, url):
    try:
        page = await browser.newPage()
        await page.goto(url, waitUntil="load")

        print("\nA Chromium window has been opened for the specified URL.")
        print("Manipulate the page manually in the browser window.")
        print("Press [Enter] to capture the current HTML.")
        print(
            'You can also type "reload" to reload the page, or "exit" to exit without saving.\n'
        )
        print("When done, type 'q' to capture current HTML and continue")

        while True:
            cmd = await wait_for_user_command()
            if cmd == "q":
                break
            if cmd == "":
                captured_html = await page.content()
                save_html(captured_html)
                continue
            if cmd == "reload":
                await page.reload({"waitUntil": "load"})
                print("Page reloaded.")
                continue
            if cmd == "exit":
                print("Exiting without saving.")
                return 0
            print("Unrecognized command.")

        final_html = await page.content()
        save_html(final_html)
        print("HTML saved, exiting....")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


async def crawl(
    urls: list[str], executable_path: Optional[str], user_data_dir: Optional[str] = None
) -> int:
    launch_kwargs: dict = {
        "headless": False,  # open a visible browser window
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    }
    if executable_path:
        launch_kwargs["executablePath"] = executable_path
    if user_data_dir:
        launch_kwargs["userDataDir"] = user_data_dir

    browser = await launch(**launch_kwargs)
    try:
        for url in urls:
            await new_browser_page(browser, url)
    finally:
        await browser.close()


async def main():
    sample_executable_path = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    with open("../searches.json") as f:
        searches = json.loads(f.read())
    prob = ["wellfound", "linkedin", "ycombinator"]
    exclude = ["Lever", "Greenhouse"]
    urls = [
        query["google_search_url"]
        for query in searches["queries"]
        if query["site"] not in exclude
    ]
    await crawl(urls, sample_executable_path)


if __name__ == "__main__":

    raise SystemExit(asyncio.run(main()))
