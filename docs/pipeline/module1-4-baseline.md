# Project 3 — Modules 1–4 Baseline

This document freezes the verified local Python pipeline behavior before the hosted Module 5A.1 foundation is connected. The domain logic remains in Python and is not rewritten in Node.js.

## Verified pipeline

| Module | Responsibility | Verified evidence |
|---|---|---|
| Module 1 | CoinGecko primary ingestion with Binance secondary source for BTC, ETH, and USDT | Live single-run test fetched 5 readings and inserted 5 records. |
| Module 2 | Quality checks, polling-gap detection, source/schema checks, and quality flag persistence | Live run raised a gap flag when the interval exceeded the configured tolerance; clean runs also completed successfully. |
| Module 3 | Return-based statistical checks, IQR/z-score checks, and USDT peg deviation | Previous controlled tests produced IQR and statistical anomalies; USDT peg deviation was evaluated against the configured threshold. |
| Module 4 | Type-specific LLM narrative generation with Groq primary and OpenRouter fallback | Groq primary returned HTTP 200 and generated a narrative; forced Groq failure caused OpenRouter `stealth/ox-alpha` to return HTTP 200. Strict validation and provider metadata persistence passed. |

## Module 4 provider evidence

The verified primary model is `openai/gpt-oss-120b` through Groq. The verified fallback model is `stealth/ox-alpha` through OpenRouter. The fallback metadata row recorded `provider_used=openrouter`, `model_used=stealth/ox-alpha`, `fallback_used=1`, prompt tokens, completion tokens, and latency. No Anthropic credential is required.

## Hosted handoff boundary

The hosted foundation introduces a separate Python FastAPI service for pipeline-run lifecycle records and a React/Vite dashboard for operational inspection. It does not yet execute the existing local pipeline on a Render schedule, create alerts, or deliver notifications. Automatic alert delivery remains disabled until the idempotent alert layer is implemented in Module 5B.

## Evidence and limitations

The local pipeline was verified through PowerShell using Python 3.14, a real Groq-primary run, and a forced-fallback run with a temporary invalid Groq key. The invalid key was used only inside a temporary process and was never persisted. The hosted service foundation is compile-checked and documented, but Supabase, Render, and Vercel still require project-specific configuration before external deployment.
