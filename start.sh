#!/bin/bash

# راه‌اندازی Cloudflare Warp
warp-svc &
sleep 3
warp-cli --accept-tos register
warp-cli --accept-tos connect
sleep 5

echo "Warp status:"
warp-cli status

# اجرای ربات
python bot.py
