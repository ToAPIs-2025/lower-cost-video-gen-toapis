# Video Gen Client: integration scope

原生可选 Provider：Seedance 2.5 与 Kling v3 两条 SDK 真实生成、等待及下载成功；20 项测试通过，同 run ID 复用同任务。仅限已审查的文生视频预设，画面输入、浏览器 UI、取消和退款未验收。

Native optional provider: two live SDK generate/wait/download runs with Seedance 2.5 and Kling v3; 20 tests passed and the same run ID resumes the same task. Reviewed text-to-video presets only. Image input, browser UI, cancellation and refunds are unverified.

## Contract

- HTTPS origin: `https://toapis.com`, Bearer API Key; no key forwarded to assets.
- Price: `GET /v1/pricing?model=...&type=image|video`, match every catalog condition; no quote means stop.
- Create: `POST /v1/images/generations` or `/v1/videos/generations`; persist submission state before POST and ID immediately afterward.
- Poll existing ID only; `in_progress` is running; `completed` is success; failed/cancelled/expired stop.
- Result: `result.data[0].url`; validate actual image/MP4 bytes.
- Cost: only settled billing is actual; a missing image bill is not zero.

## Native work remaining

Native provider lives at repository root `src/video_gen/providers/toapis.py`; setup in `docs/TOAPIS.md`. SDK and pytest verified. Additional models, image-to-video, web UI, remote cancellation and refunds require separate review.

## Acceptance / 待维护者确认

Target app version and supported model presets; existing supplier/referral ownership; key storage and deployment proxy policy; quote/approval display; create/poll/result/import; refresh/restart resumes same task; actual billing and error handling. Supply test credits by agreement, with no guaranteed quota, SLA or acceptance deadline.
