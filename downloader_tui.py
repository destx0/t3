#!/usr/bin/env python3
import requests
import json
import html
import re
import time
from pathlib import Path
from collections import Counter
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from InquirerPy import inquirer
from InquirerPy.separator import Separator

from src.exam_targets import EXAM_TARGETS

# Configuration
AUTH_CODE = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3Rlc3Rib29rLmNvbSIsInN1YiI6IjY1ZjZiZDk4MmRhZTFmNmIyYmRkNjJiNCIsImF1ZCI6IlRCIiwiZXhwIjoiMjAyNS0xMi0yNlQxNDoxNDoxOS4zNjM2MTkxNzdaIiwiaWF0IjoiMjAyNS0xMS0yNlQxNDoxNDoxOS4zNjM2MTkxNzdaIiwibmFtZSI6IkRldmFuc2ggSXNod2FyIiwiZW1haWwiOiJpc2h3YXIwMHVwQGdtYWlsLmNvbSIsIm9yZ0lkIjoiIiwiaXNMTVNVc2VyIjpmYWxzZSwicm9sZXMiOiJzdHVkZW50In0.S_uw-UjIpdwBHNg2DWQX_nF1ONCHEJc4lRfhDQ6dAaavd1ezcBUd7DyMQg0mn8GsmHHoAQynftAxuJ5tl9k0rd79PVu192FrYRoJtf3rU3mWyjs0FZKJ5BzITE2I5FhKusYWSGF7ug9r4AKEBfAiuheupPdXSQKjRh4ZJqCvJ-E"

console = Console()
current_exam = None


def clean_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_base_dir():
    return Path(EXAM_TARGETS[current_exam]["dir"])


def get_tests_file():
    return get_base_dir() / "tests_list.json"


def show_header():
    console.clear()
    title = "PYQ Downloader"
    if current_exam:
        title += f" | {current_exam}"
    console.print(Panel.fit(f"[bold cyan]{title}[/bold cyan]", border_style="cyan"))
    console.print()


def select_exam():
    global current_exam
    show_header()

    console.print(f"[dim]{len(EXAM_TARGETS)} exams available[/dim]\n")

    choices = sorted(EXAM_TARGETS.keys())

    selected = inquirer.fuzzy(
        message="Search and select exam:",
        choices=choices,
        pointer=">",
        max_height="70%",
    ).execute()

    current_exam = selected
    return selected


def fetch_all_tests(start_year=2010, end_year=2025):
    """Fetch all tests for current exam from API"""
    target_id = EXAM_TARGETS[current_exam]["id"]
    all_tests = []
    year_counts = Counter()
    years = list(range(start_year, end_year + 1))

    console.print(f"Fetching tests for {current_exam} ({start_year}-{end_year})...")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching years...", total=len(years))

        for year in years:
            progress.update(task, description=f"Fetching {year}...")

            url = f"https://api.testbook.com/api/v1/previous-year-papers/target/{target_id}?id={target_id}&skip=0&limit=2000&year={year}&stage=&type=%5BTarget%20Page%5D%20getPypTargetTests&language=English"

            try:
                resp = requests.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if (
                        data.get("success")
                        and "data" in data
                        and "yearWiseTests" in data["data"]
                    ):
                        for year_data in data["data"]["yearWiseTests"]:
                            curr_year = year_data.get("year")
                            tests = year_data.get("tests", [])
                            year_counts[curr_year] += len(tests)

                            for test in tests:
                                all_tests.append(
                                    {
                                        "year": curr_year,
                                        "id": test.get("id"),
                                        "title": test.get("title"),
                                    }
                                )
            except Exception as e:
                console.print(f"[red]Error fetching {year}: {e}[/red]")

            progress.advance(task)
            time.sleep(0.3)

    # Save to file
    base_dir = get_base_dir()
    base_dir.mkdir(parents=True, exist_ok=True)

    with open(get_tests_file(), "w", encoding="utf-8") as f:
        json.dump(all_tests, f, indent=2, ensure_ascii=False)

    return all_tests, year_counts


def load_tests():
    tests_file = get_tests_file()
    if tests_file.exists():
        with open(tests_file, "r") as f:
            return json.load(f)
    return None


def download_paper(test_id, progress=None, task=None):
    """Download paper with retry logic"""
    url = f"https://api-new.testbook.com/api/v2/tests/{test_id}?auth_code={AUTH_CODE}&X-Tb-Client=web,1.2&language=English&attemptNo=1"
    
    max_retries = 5
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:  # Rate limited
                delay = base_delay * (2 ** attempt)  # Progressive: 2, 4, 8, 16, 32
                if progress and task:
                    progress.update(task, description=f"[red]Rate limit, wait {delay}s[/red]")
                time.sleep(delay)
            else:
                return None
        except Exception:
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
    
    return None


def download_answers(test_id, progress=None, task=None):
    """Download answers with retry logic and progressive delay"""
    url = f"https://api-new.testbook.com/api/v2/tests/{test_id}/answers?auth_code={AUTH_CODE}&X-Tb-Client=web,1.2&language=English&attemptNo=1"
    
    max_retries = 5
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:  # Rate limited
                delay = base_delay * (2 ** attempt)  # Progressive: 2, 4, 8, 16, 32
                if progress and task:
                    progress.update(task, description=f"[red]Rate limit, wait {delay}s[/red]")
                time.sleep(delay)
            else:
                return None
        except Exception:
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
    
    return None


def process_paper(paper_data, answers_data, include_correct_answer):
    paper_info = paper_data.get("data", {})
    title = paper_info.get("title", "Unknown")
    answers = answers_data.get("data", {}) if answers_data else {}

    cleaned_questions = []
    for section in paper_info.get("sections", []):
        for q in section.get("questions", []):
            q_id = q.get("_id")
            en_data = q.get("en", {})

            question_text = clean_html(en_data.get("value", ""))
            options = [
                clean_html(opt.get("value", "")) for opt in en_data.get("options", [])
            ]

            answer_info = answers.get(q_id, {})
            correct_option = answer_info.get("correctOption", "")

            q_data = {
                "id": q_id,
                "question": question_text,
                "options": options,
                "correct_option": correct_option,
            }

            if include_correct_answer and correct_option and options:
                try:
                    idx = int(correct_option) - 1
                    if 0 <= idx < len(options):
                        q_data["correct_answer"] = options[idx]
                except:
                    pass

            cleaned_questions.append(q_data)

    return {"title": title, "questions": cleaned_questions}


def select_years(tests):
    years = sorted(set(t["year"] for t in tests), reverse=True)

    choices = []
    for y in years:
        count = len([t for t in tests if t["year"] == y])
        choices.append({"name": f"{y} ({count} papers)", "value": y, "enabled": True})

    selected = inquirer.checkbox(
        message="Select years (space to toggle, enter to confirm):",
        choices=choices,
        pointer=">",
    ).execute()

    return selected if selected else years


def ask_output_options():
    include_answer = inquirer.confirm(
        message="Include correct_answer text in output?", default=True
    ).execute()

    return include_answer


def download_and_clean(tests, include_answer):
    """Download papers and clean them, also save raw responses"""
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn, TextColumn, 
        TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn
    )
    from rich.live import Live
    from rich.table import Table
    
    base_dir = get_base_dir()
    output_dir = base_dir / "cleaned"
    raw_dir = base_dir / "raw"
    success = 0
    failed = 0
    total = len(tests)
    current_status = "Starting..."

    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40, complete_style="green", finished_style="bright_green"),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        expand=False,
    ) as progress:
        task = progress.add_task("Downloading", total=total)

        for idx, test in enumerate(tests, 1):
            tid = test["id"]
            title = test.get("title", "Unknown")
            year = test["year"]

            progress.update(task, description=f"[cyan]Paper {idx}[/cyan]")

            paper = download_paper(tid, progress=progress, task=task)
            if not paper:
                failed += 1
                progress.advance(task)
                continue

            progress.update(task, description=f"[yellow]Answers {idx}[/yellow]")
            answers = download_answers(tid, progress=progress, task=task)

            try:
                safe_title = "".join(
                    c for c in title if c.isalnum() or c in (" ", "-", "_")
                )[:80]
                
                raw_year_dir = raw_dir / str(year)
                raw_year_dir.mkdir(parents=True, exist_ok=True)
                
                with open(raw_year_dir / f"{tid}_{safe_title}_paper.json", "w", encoding="utf-8") as f:
                    json.dump(paper, f, indent=2, ensure_ascii=False)
                
                if answers:
                    with open(raw_year_dir / f"{tid}_{safe_title}_answers.json", "w", encoding="utf-8") as f:
                        json.dump(answers, f, indent=2, ensure_ascii=False)

                cleaned = process_paper(paper, answers, include_answer)

                year_dir = output_dir / str(year)
                year_dir.mkdir(parents=True, exist_ok=True)

                filename = f"{tid}_{safe_title}.json"

                with open(year_dir / filename, "w", encoding="utf-8") as f:
                    json.dump(cleaned, f, indent=2, ensure_ascii=False)

                success += 1
            except Exception:
                failed += 1

            progress.advance(task)
            time.sleep(0.3)

    return success, failed


def main():
    """Run the complete flow: select exam -> fetch -> select years -> download"""
    global current_exam

    try:
        while True:
            # Step 1: Select exam (starts with search)
            select_exam()

            # Step 2: Fetch tests (auto)
            show_header()
            tests_file = get_tests_file()

            if tests_file.exists():
                tests = load_tests()
                console.print(f"[green]Found cached test list with {len(tests)} tests[/green]")
                console.print()
                refetch = inquirer.confirm(
                    message="Re-fetch from API?", default=False
                ).execute()
                if refetch:
                    tests, _ = fetch_all_tests()
                    tests = load_tests()
            else:
                console.print("[yellow]Fetching test list from API...[/yellow]")
                tests, _ = fetch_all_tests()
                tests = load_tests()

            if not tests:
                console.print("[red]No tests found![/red]")
                time.sleep(2)
                continue

            # Show stats
            show_header()
            table = Table(title=f"{current_exam} - Available Papers", show_header=True)
            table.add_column("Year")
            table.add_column("Papers", justify="right")

            years = sorted(set(t["year"] for t in tests), reverse=True)
            for y in years:
                count = len([t for t in tests if t["year"] == y])
                table.add_row(str(y), str(count))

            console.print(table)
            console.print()

            # Step 3: Select years
            selected_years = select_years(tests)
            if not selected_years:
                console.print("[yellow]No years selected, restarting...[/yellow]")
                time.sleep(1)
                continue

            # Step 4: Ask about correct_answer
            include_answer = ask_output_options()

            # Step 5: Download and clean
            filtered = [t for t in tests if t["year"] in selected_years]

            console.print()
            console.print(f"[cyan]Downloading & cleaning {len(filtered)} papers...[/cyan]")
            console.print()

            success, failed = download_and_clean(filtered, include_answer)

            console.print()
            console.print(
                Panel(
                    f"[green]Success: {success}[/green]  [red]Failed: {failed}[/red]\n"
                    f"[dim]Cleaned: {get_base_dir() / 'cleaned'}[/dim]\n"
                    f"[dim]Raw: {get_base_dir() / 'raw'}[/dim]",
                    title="Results",
                )
            )

            # Ask to continue or exit
            again = inquirer.confirm(
                message="Download another exam?", default=True
            ).execute()
            if not again:
                break

        console.print("\nGoodbye!\n")
    except KeyboardInterrupt:
        console.print("\nGoodbye!\n")


if __name__ == "__main__":
    main()
