# Optional ToAPIs provider

This provider adds two reviewed text-to-video presets to the existing SDK. Other providers and defaults remain available.

```sh
pip install -e '.[dev]'
```

Set `TOAPIS_API_KEY` privately. Optional `TOAPIS_BASE_URL` must be `https://toapis.com` or `https://toapis.cn`, without `/v1`. `TOAPIS_STATE_DIR` selects the local durable task directory; keep it outside version control. The provider queries the same Key's `/v1/pricing` before creation and stops on an unusable price. Token-based estimation is a conservative budget check, not a locked price. Per-job configured ceiling is at most USD 0.80 and does not guarantee the final token-metered amount.

```python
import asyncio
from video_gen import VideoClient

async def main():
    async with VideoClient() as client:
        task = await client.generate(
            "toapis", model="seedance-2-5", prompt="An unbranded blue bottle, slow camera push-in",
            duration=4, resolution="480p", aspect_ratio="16:9",
            extra={"run_id":"reviewed-demo-1", "max_usd":"0.80"},
        )
        result = await task.wait()
        await task.download("demo.mp4")
        billing = result.raw.get("billing") or {}
        if billing.get("status") == "settled":
            print({k: billing.get(k) for k in ("status", "cost_usd", "credits")})

asyncio.run(main())
```

Alternative preset: `model="kling-v3", duration=5, resolution="720p"`, standard mode, audio off. Seedance uses 480p/4s, audio off. Only 16:9 is reviewed. No reference image, seed, negative prompt or arbitrary extra fields are mapped. The explicit rejection is intentional.

Creation POSTs are not retried. The durable record is written before submission; repeating the same request and run ID resumes its task ID. A record with no task ID requires reconciliation rather than another POST. A new run ID explicitly authorizes a new paid task. Do not erase state to retry an uncertain submission. The server task status `in_progress` maps to SDK running. HTTPS result downloads do not carry the API Key. Cancellation is not implemented; local interruption does not imply remote cancellation or refund.

Validation: 20 tests passed, including original tests and native-provider protocol/price/resume/error cases. On 2026-10-22, two live native SDK generate/wait/download runs completed and same-run task reuse was verified. Browser UI, image input, cancellation and refund behavior were not accepted. Real output examples and dated case prices are maintained separately from the upstream contribution.
