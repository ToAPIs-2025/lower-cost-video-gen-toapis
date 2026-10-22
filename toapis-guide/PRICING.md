# API pricing · 2026-10-22

| Model / 模型 | Preset / 参数 | API pricing | Case / 本次案例 |
|---|---|---|---|
| kling-v3 | duration=5, mode=std, aspect_ratio=16:9, audio=False | $0.06/s | $0.3 actual; 5.04s; $0.059524/s observed |
| seedance-2-5 | duration=4, resolution=480p, aspect_ratio=16:9, generate_audio=False, output_format=mp4 | $1/M tokens | $0.3883 actual; 4.04s; $0.096114/s observed |

Token-metered rates use actual tokens; the observed $/s is this case’s settled cost divided by decoded MP4 duration, not a fixed future rate. Quotes are same-Key prices dated 2026-10-22, not confirmed charges. The client rechecks pricing before a paid submission.
