"""Common utilities for Gemini seed generation scripts."""

import json
import os
import sys
from pathlib import Path
from typing import Any, TypeVar
from dotenv import load_dotenv
from rich.console import Console
from pydantic import BaseModel

load_dotenv()

console = Console()
T = TypeVar("T", bound=BaseModel)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")


class QuotaTracker:
    """Tracks API requests made in the current process to help user monitor Free Tier limits."""
    def __init__(self, free_tier_daily_limit: int = 20):
        self.requests_made = 0
        self.daily_limit = free_tier_daily_limit

    def record_request(self):
        self.requests_made += 1

    def print_status(self):
        pct = (self.requests_made / self.daily_limit) * 100
        console.print(
            f"[dim]📊 Quota Tracker: [bold]{self.requests_made}[/bold] / {self.daily_limit} "
            f"requests used ({pct:.1f}% of free daily allocation).[/dim]"
        )


tracker = QuotaTracker()


def get_gemini_client():
    """Initialize and validate Google GenAI client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error: GEMINI_API_KEY is not set in environment or .env file.[/bold red]")
        sys.exit(1)

    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        console.print(f"[bold red]Error initializing Google GenAI client: {e}[/bold red]")
        sys.exit(1)


import re
import time


def generate_structured_data(
    client: Any,
    prompt: str,
    response_schema: type[T],
    model: str = GEMINI_MODEL,
    max_retries: int = 4,
) -> T:
    """Generate structured Pydantic object using Gemini with backoff and automatic model fallback."""
    tracker.record_request()
    seen = set()
    candidate_models = []
    for m in [model, "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite"]:
        if m and m not in seen:
            candidate_models.append(m)
            seen.add(m)

    for current_model in candidate_models:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": response_schema,
                        "temperature": 0.7,
                    },
                )
                return response.parsed
            except Exception as e:
                err_msg = str(e)
                # If daily quota is hit for this model, switch immediately to next candidate model
                if "PerDay" in err_msg or "Daily" in err_msg:
                    console.print(
                        f"[yellow]⚠️ Cuota diaria alcanzada para {current_model}. Probando modelo de respaldo...[/yellow]"
                    )
                    break

                if "503" in err_msg or "UNAVAILABLE" in err_msg or "high demand" in err_msg.lower():
                    delay = 5.0 * attempt
                    if attempt < max_retries:
                        console.print(
                            f"[yellow]⚠️ Servidor temporalmente ocupado (503 {current_model}). "
                            f"Pausando {delay:.1f}s antes de reintentar ({attempt}/{max_retries})...[/yellow]"
                        )
                        time.sleep(delay)
                        continue

                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    delay = 12.0
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg, re.IGNORECASE)
                    if match:
                        delay = max(float(match.group(1)) + 1.5, 12.0)
                    else:
                        delay = 12.0 * attempt

                    if attempt < max_retries:
                        console.print(
                            f"[yellow]⚠️ Límite de tasa de Gemini ({current_model}). "
                            f"Pausando {delay:.1f}s antes de reintentar ({attempt}/{max_retries})...[/yellow]"
                        )
                        time.sleep(delay)
                        continue
                console.print(f"[bold red]Gemini API generation failed with {current_model}: {e}[/bold red]")
                if current_model == candidate_models[-1]:
                    raise e
                break
    raise RuntimeError("All candidate Gemini models failed generation.")


def save_json_file(data: Any, filepath: Path, dry_run: bool = False, delay_seconds: float = 3.0):
    """Save serializable data to formatted JSON file with pacing delay to stay within rate limits."""
    if dry_run:
        console.print(f"[yellow][DRY RUN] Would write to: {filepath}[/yellow]")
    else:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        console.print(f"[green]✓ Wrote {len(data) if isinstance(data, list) else len(data.keys())} items to [bold]{filepath}[/bold][/green]")

    if delay_seconds > 0:
        time.sleep(delay_seconds)
