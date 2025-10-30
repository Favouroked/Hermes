from src.web.lever import LeverBrowser
import asyncio
import traceback

LINK = "https://jobs.lever.co/cognitiv/b355e50a-4058-4608-ad19-d8880308cc71/apply"


async def _demo():
    try:
        lever = LeverBrowser(LINK)
        with open("form.html") as f:
            html = f.read()
        questions_html = lever.get_questions_html(html)
        with open("answers.txt", "a") as f:
            for question in questions_html[1:]:
                try:
                    answer = lever.answer_question(question)
                    print(answer)
                    f.write(answer)
                except Exception as e:
                    print(e)
                    f.write(f"{question}: {e}")
    except:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(_demo())
