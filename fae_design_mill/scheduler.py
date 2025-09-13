from __future__ import annotations
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

from .config import DEFAULT_SCHEDULE_HOUR, DEFAULT_PROVIDER, ASSETS_DIR
import uuid
from .repositories import (
    create_design_run,
    update_design_run_status,
    insert_prompt_record,
    insert_asset_record,
    log_cooldown,
    get_policy,
    recent_asset_hashes,
)
from .prompt.engine import build_prompt, novelty_check, mutate_prompt
from .prompt.hashers import phash_gray, dhash_gray
from .storage.files import save_prompt_json


def _load_provider():
    pol = get_policy() or {}
    provider_name = (pol.get("provider") or DEFAULT_PROVIDER or "null").lower()
    if provider_name == "null":
        from .providers.null_provider import NullProvider
        return NullProvider()
    if provider_name in ("openai", "openai_images"):
        from .providers.openai_images import OpenAIImageProvider
        return OpenAIImageProvider()
    raise RuntimeError(f"Unknown provider: {DEFAULT_PROVIDER}")


def _job_key_for(dt: datetime, manual: bool = True) -> str:
    if manual:
        return dt.strftime("%Y-%m-%dT%H%M%S")
    return dt.strftime("%Y-%m-%d")


def run_once(force_new: bool = False, random_seed: bool = False) -> Dict[str, str]:
    provider = _load_provider()
    now = datetime.utcnow()
    job_key = _job_key_for(now, manual=True)
    run_id = create_design_run(job_key=job_key, scheduled_for=now.isoformat())
    try:
        # Build prompt with retries if too similar
        policy = get_policy()
        attempts = 0
        max_retries = 4
        attempts = 0
        while True:
            prompt, hashes, used_item_ids = build_prompt(design_title="FAE Auto Design")
            # If requested, mutate proactively to push novelty
            if force_new:
                prompt = mutate_prompt(prompt)
            if random_seed:
                import random as _r
                prompt.setdefault("output", {})["seed"] = _r.randint(1, 2**31-1)
            ok, reason = novelty_check(hashes, policy)
            if ok:
                break
            attempts += 1
            if attempts > max_retries:
                update_design_run_status(run_id, "SKIPPED", f"Novelty failure: {reason}")
                return {"status": "SKIPPED", "reason": reason}
            # mutate and try again
            prompt = mutate_prompt(prompt)

        update_design_run_status(run_id, "PROMPTED")
        # Persist prompt and cooldown logs
        canon = json_canonical = None
        from .prompt.canonical import canonical_dump
        json_canonical = canonical_dump(prompt)
        prompt_rec_id = insert_prompt_record(
            run_id, prompt, json_canonical, hashes["simhash"], hashes["minhash"], novelty_score=0.6
        )
        log_cooldown(used_item_ids)
        # Save prompt to file
        save_prompt_json(prompt, f"run_{run_id}_prompt")

        # Image generation and de-dupe
        img_attempts = 0
        while True:
            result = provider.generate(prompt)
            dh = dhash_gray(result.image_gray)
            ph = phash_gray(result.image_gray)
            # compare to recent asset hashes
            dupe = False
            for ph_prev, dh_prev in recent_asset_hashes(200):
                if not ph_prev or not dh_prev:
                    continue
                # Hamming distance via int bit_count
                if ((int(ph_prev, 16) ^ int(ph, 16)).bit_count() <= int(policy.get("image_dupe_threshold", 5))):
                    dupe = True
                    break
            if dupe:
                img_attempts += 1
                if img_attempts > max_retries:
                    update_design_run_status(run_id, "SKIPPED", "Image duplicate threshold reached")
                    return {"status": "SKIPPED", "reason": "image dupe"}
                # mutate prompt then re-generate
                prompt = mutate_prompt(prompt)
                continue
            # Ensure a unique filename per run to avoid dashboard collisions/caching
            try:
                from pathlib import Path
                import os
                src = Path(result.file_path)
                unique_name = f"run_{run_id}_{uuid.uuid4().hex[:8]}.png"
                dst = ASSETS_DIR / unique_name
                if src.resolve() != dst.resolve():
                    try:
                        os.replace(str(src), str(dst))
                    except Exception:
                        import shutil
                        shutil.copyfile(str(src), str(dst))
                        try:
                            src.unlink()
                        except Exception:
                            pass
                final_path = str(dst)
            except Exception:
                final_path = result.file_path

            # Save asset record
            insert_asset_record(
                run_id,
                prompt_rec_id,
                provider=(policy.get("provider") or DEFAULT_PROVIDER),
                request_payload={"seed": prompt.get("output", {}).get("seed")},
                response_payload=result.response_payload or {},
                file_path=final_path,
                phash_hex=ph,
                dhash_hex=dh,
                width=result.width,
                height=result.height,
                dpi=prompt.get("print_spec", {}).get("dpi_target", 300),
            )
            break

        update_design_run_status(run_id, "GENERATED")
        return {"status": "GENERATED", "run_id": str(run_id), "file": final_path}
    except Exception as e:
        update_design_run_status(run_id, "FAILED", str(e))
        return {"status": "FAILED", "error": str(e)}


def run_scheduler():
    # Simple loop that waits until next schedule hour, runs once, repeats
    hour = DEFAULT_SCHEDULE_HOUR
    print(f"Scheduler started (hour={hour:02d}:00). Ctrl+C to stop.")
    try:
        while True:
            now = datetime.now()
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target = target + timedelta(days=1)
            delta = (target - now).total_seconds()
            mins = int(delta // 60)
            print(f"Sleeping {mins} min until {target.isoformat()}")
            time.sleep(max(5, delta))
            print("Running scheduled job...")
            print(run_once())
    except KeyboardInterrupt:
        print("Scheduler stopped.")
