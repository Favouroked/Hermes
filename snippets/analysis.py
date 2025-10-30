from ollama import chat, ChatResponse
import time
import json
from bs4 import BeautifulSoup
import requests
from model import SessionLocal, JobAnalysis
from sqlalchemy import and_
import os
import webbrowser


def save_job_analysis(data: dict) -> int:
    with SessionLocal() as session:
        record = JobAnalysis(**data)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id


def retrieve_matching_links(links: list[str]):
    with SessionLocal() as session:
        return (
            session.query(JobAnalysis.link)
            .filter(JobAnalysis.link.in_(links), JobAnalysis.expired == False)
            .all()
        )


def validate_links(links: list[str]):
    existing_links = retrieve_matching_links(links)
    existing_links_set = set([l[0] for l in existing_links])
    return list(set(links) - existing_links_set)


models = ["gpt-oss:20b", "gemma3:12b"]


SYSTEM_PROMPT = """
You are a job search assistant. Your role is to analyze the text of a job page and extract the job details in JSON format. 
Your response must be a JSON object showing the info on the page in the format below:
```json
{
    "title": string, // The job title,
    "location": string | unknown (if not provided), // The location of the job
    "company": string | unknown (if not provided), // The company name.
    "salary": string | unknown (if not provided), // The salary range.
    "description": string | unknown (if not provided), // The job's description.
}
```
ONLY RETURN THE JSON OBJECT. DO NOT RETURN ANYTHING ELSE OR ADD ANY EXTRA TEXT OR SYMBOL. 
IMPORTANT: your response MUST be a valid json string. Always return a valid JSON string
"""


def analyze_html(link):
    r = requests.get(link)
    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text()
    print(f"Starting chat... {len(page_text)} characters [{link}]")
    start_time = time.time()
    response: ChatResponse = chat(
        model=models[0],
        messages=[
            {
                "role": "user",
                "content": f"{SYSTEM_PROMPT}\n\nAnalyze the page below:\n{page_text}",
            }
        ],
    )
    end_time = time.time()
    print(f"Chat execution time: {end_time - start_time:.2f} seconds")
    if json_response := response.message.content:
        data = json.loads(json_response)
        if str(data["title"]).lower() == "unknown":
            data["expired"] = True
        data["page_text"] = page_text
        data["link"] = link
        try:
            save_job_analysis(data)
        except Exception as e:
            print(f"Error saving job analysis: {e}")


def cover_letter_gen():
    with SessionLocal() as session:
        records = (
            session.query(JobAnalysis)
            .filter(
                and_(
                    JobAnalysis.title.notin_(["unprocessed", "unknown"]),
                    JobAnalysis.is_processed == False,
                    JobAnalysis.cover_letter == None,
                )
            )
            .all()
        )
        data_list = [
            {"id": record.id, "link": record.link, "page_text": record.page_text}
            for record in records
        ]
        print(f"Processing {len(data_list)} records")
        with open("../resume.txt") as resume_file:
            resume_text = resume_file.read()
        for data in data_list:
            try:
                start_time = time.time()
                page_text = data["page_text"]
                response: ChatResponse = chat(
                    model=models[0],
                    messages=[
                        {
                            "role": "user",
                            "content": f"This is my resume:\n{resume_text}\n\nYour job is to generate a cover letter. It must be in txt format. Sound natural like a human typed it manually in a textbox."
                            f"Do not include headers and placeholders. My name is Favour Okedele. Your final result must be a complete cover letter i can submit without editing. Analyze the job page below and generate a cover letter tailored to my resume:\n{page_text}",
                        }
                    ],
                )
                end_time = time.time()
                print(f"Chat execution time: {end_time - start_time:.2f} seconds")
                if llm_response := response.message.content:
                    try:
                        session.query(JobAnalysis).filter(
                            JobAnalysis.id == data["id"]
                        ).update({"cover_letter": llm_response})
                        session.commit()
                    except Exception as e:
                        print(f"Error saving job analysis: {e}")
                else:
                    print("No response from chat model")
            except Exception as e:
                print(f"[{data['id']}] Error processing link: {e}")


def enrich_unprocessed():
    with SessionLocal() as session:
        records = (
            session.query(JobAnalysis).filter(JobAnalysis.title == "unprocessed").all()
        )
        data_list = [
            {"id": record.id, "link": record.link, "page_text": record.page_text}
            for record in records
        ]
        for data in data_list:
            try:
                start_time = time.time()
                page_text = data["page_text"]
                response: ChatResponse = chat(
                    model=models[0],
                    messages=[
                        {
                            "role": "user",
                            "content": f"Analyze the page below:\n{page_text}\n\n{SYSTEM_PROMPT}",
                        }
                    ],
                )
                end_time = time.time()
                print(f"Chat execution time: {end_time - start_time:.2f} seconds")
                if json_response := response.message.content:
                    print(json_response)
                    json_data = json.loads(json_response)
                    if str(json_data["title"]).lower() == "unknown":
                        json_data["expired"] = True
                    try:
                        session.query(JobAnalysis).filter(
                            JobAnalysis.id == data["id"]
                        ).update(json_data)
                        session.commit()
                    except Exception as e:
                        print(f"Error saving job analysis: {e}")
                else:
                    print("No response from chat model")
            except Exception as e:
                print(f"[{data['id']}] Error processing link: {e}")


def process_links():
    with open("../auto_links.txt", "r") as f:
        links = f.readlines()
    for link in links:
        link = link.strip()
        try:
            r = requests.get(link, timeout=(10, 30))
            if r.status_code != 200:
                raise ValueError("Invalid status code")
            soup = BeautifulSoup(r.text, "html.parser")
            page_text = soup.get_text()
            data = {}
            data["page_text"] = page_text
            data["link"] = link
            data["title"] = "unprocessed"
            save_job_analysis(data)
        except Exception as e:
            print(f"Error processing link: {e}")
            with open("../error_links.txt", "a") as ef:
                ef.write(link)


def process_html(path: str):
    with open(path, "r") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    results = soup.select(".yuRUbf")
    print(f"Results: {len(results)}")
    links = [sr.select_one("a").get("href") for sr in results]
    valid_links = validate_links(links)
    prob = ["wellfound", "linkedin", "ycombinator"]
    problematic_links = [
        l for l in valid_links if prob[0] in l or prob[1] in l or prob[2] in l
    ]
    final_links = list(set(valid_links) - set(problematic_links))
    with open("../manual_links.txt", "a") as f:
        f.write("\n".join(problematic_links))
    # for link in final_links:
    #     analyze_html(link)
    with open("../auto_links.txt", "a") as af:
        af.write("\n".join(final_links))


def get_pages():
    pages = os.listdir("search_pages")
    return sorted([f"search_pages/{p}" for p in pages])


def start_processing():
    pages = get_pages()
    for p in pages:
        print(f"Processing {p}")
        process_html(p)
        os.remove(p)


import pyperclip


def process_jobs():
    with SessionLocal() as session:
        records = (
            session.query(JobAnalysis)
            .filter(
                and_(
                    JobAnalysis.title.notin_(["unprocessed", "unknown"]),
                    JobAnalysis.cover_letter.is_not(None),
                    JobAnalysis.is_processed == False,
                )
            )
            .all()
        )
        for record in records:
            link, cover_letter = str(record.link), str(record.cover_letter)
            webbrowser.open(link)
            pyperclip.copy(cover_letter)
            exit_loop = False
            while True:
                char_input = input("Enter command: ")
                char_input = char_input.strip().lower()
                if char_input == "c":
                    pyperclip.copy(cover_letter)
                    print("--> Cover letter copied to clipboard!")
                if char_input == "n":
                    notes = input("Enter notes: ")
                    session.query(JobAnalysis).filter(
                        JobAnalysis.id == record.id
                    ).update({"notes": notes})
                    session.commit()
                    print("--> Notes updated!")
                if char_input == "":
                    session.query(JobAnalysis).filter(
                        JobAnalysis.id == record.id
                    ).update({"is_processed": True})
                    session.commit()
                    print("--> Job marked as processed!")
                    break
                if char_input == "q":
                    print("--> Skipping job for now")
                    break
                if char_input == "e":
                    session.query(JobAnalysis).filter(
                        JobAnalysis.id == record.id
                    ).update({"expired": True})
                    session.commit()
                    print("--> Job marked as expired!")
                    break
                if char_input == "exit":
                    print("--> Exiting without saving.")
                    exit_loop = True
                    break
            if exit_loop:
                break


if __name__ == "__main__":
    process_jobs()
