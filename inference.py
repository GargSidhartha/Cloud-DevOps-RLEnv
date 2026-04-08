import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Tuple

from openai import OpenAI
from pydantic import ValidationError

from env import CloudDevOpsEnv
from models import CloudAction

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "google/gemma-4-31B-it")
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("API_KEY")

BENCHMARK = "CloudDevOpsEnv"
MAX_STEPS = 15
MAX_TOTAL_REWARD = 1.0
SCORE_MIN = 0.001
SCORE_MAX = 0.999
SUCCESS_SCORE_THRESHOLD = 0.8


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: Any, reward: float, done: bool, error: Any) -> None:
    action_dict = action.model_dump() if hasattr(action, "model_dump") else str(action)
    if isinstance(action_dict, dict):
        action_str = json.dumps(action_dict, separators=(",", ":"))
    else:
        action_str = str(action_dict)
    action_str = action_str.replace("\n", " ").replace("\r", " ")

    error_str = "null" if not error else str(error).replace("\n", " ").replace("\r", " ")
    done_str = str(done).lower()
    print(
        f"[STEP] step={step} action={action_str} reward={reward:.2f} done={done_str} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    success_str = str(success).lower()
    print(
        f"[END] success={success_str} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def get_model_action(
    client: OpenAI,
    step: int,
    last_obs: str,
    last_error: str,
    history: List[Dict[str, str]],
) -> Tuple[CloudAction, str]:
    """Prompt the LLM and parse its response into a CloudAction."""
    system_prompt = (
        "You are an expert AI DevOps Engineer diagnosing a cloud infrastructure issue. "
        "You must respond ONLY with a raw JSON object matching this schema:\n"
        "{\n"
        '  "command": "list_resources" | "describe_resource" | "view_logs" | "update_security_group" | "restart_service" | "submit_solution",\n'
        '  "resource_id": "string (optional)",\n'
        '  "parameters": {"key": "value"} (optional)\n'
        "}\n"
        "Do not include markdown blocks like ```json. Just output the JSON."
    )

    user_prompt = f"Step {step}.\nLast Observation:\n{last_obs}\n"
    if last_error:
        user_prompt += f"\nLast Error:\n{last_error}\n"
    user_prompt += "\nWhat is your next action JSON?"

    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
            max_tokens=200,
        )
        raw_text = (response.choices[0].message.content or "").strip()

        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        action_dict = json.loads(raw_text)
        return CloudAction(**action_dict), raw_text
    except (json.JSONDecodeError, ValidationError) as exc:
        print(f"[DEBUG] Model parse failed: {exc}", file=sys.stderr, flush=True)
        return CloudAction(command="list_resources"), "failed_parse"
    except Exception as exc:
        print(f"[DEBUG] API request failed: {exc}", file=sys.stderr, flush=True)
        return CloudAction(command="list_resources"), "api_error"


async def run_task(task_name: str, client: OpenAI) -> None:
    env = CloudDevOpsEnv(task_name=task_name)

    history: List[Dict[str, str]] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset()
        last_obs = result.observation.output
        last_error = result.observation.error or ""

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            action, raw_response = get_model_action(
                client, step, last_obs, last_error, history
            )

            result = await env.step(action)
            obs = result.observation
            reward = result.reward or 0.0
            done = result.done
            error = obs.error

            rewards.append(reward)
            steps_taken = step
            last_obs = obs.output
            last_error = error or ""

            log_step(step=step, action=action, reward=reward, done=done, error=error)

            history.append({"role": "assistant", "content": raw_response})
            history.append(
                {
                    "role": "user",
                    "content": f"Observation: {last_obs}\nError: {last_error}",
                }
            )

            if done:
                break

        score = sum(rewards)
        # Keep score strictly in (0,1) after formatting to avoid validator endpoint failures.
        score = max(SCORE_MIN, min(score, SCORE_MAX))
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        try:
            await env.close()
        except Exception as exc:
            print(f"[DEBUG] env.close() failed: {exc}", file=sys.stderr, flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


async def main() -> None:
    if not HF_TOKEN:
        print(
            "[WARN] HF_TOKEN (or API_KEY fallback) is not set. API calls will fail in remote evaluation.",
            file=sys.stderr,
            flush=True,
        )

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    tasks = ["easy", "medium", "hard"]
    for task in tasks:
        await run_task(task, client)


if __name__ == "__main__":
    asyncio.run(main())
