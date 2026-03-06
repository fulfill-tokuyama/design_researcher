"""
デザイン調査スケジューラー v2
cron / systemd / 常駐プロセス / Vercel Cron 対応
"""

import os
import sys
import time
import json
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path

# スクリプトのディレクトリをモジュール検索パスに追加
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("scheduler_v2.log", encoding="utf-8")],
)
log = logging.getLogger("scheduler_v2")


class DailyScheduler:
    def __init__(self, hour: int = 3, minute: int = 0, config_path: str = "config.json"):
        self.hour = hour
        self.minute = minute
        self.config_path = config_path
        self.running = True
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))

    def _next_run(self) -> datetime:
        now = datetime.now()
        nxt = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        return nxt

    def _execute(self):
        log.info("🚀 スケジュール実行開始")
        try:
            from design_researcher_v2 import DesignResearchPipelineV2, load_config
            cfg = load_config(self.config_path)
            result = DesignResearchPipelineV2(cfg).run()
            log.info(f"✅ 完了: {result.get('stocked', 0)}件追加")
            self._notify(result)
        except Exception as e:
            log.error(f"❌ エラー: {e}", exc_info=True)

    def _notify(self, result: dict):
        """Discord / Slack Webhook 通知（オプション）"""
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return
        try:
            import requests
            payload = {
                "content": (
                    f"📊 **デザイン調査完了**\n"
                    f"新規ストック: {result.get('stocked', 0)}件\n"
                    f"平均スコア: {result.get('avg_score', 0)}\n"
                    f"API使用: Serper {result['api_usage']['serper_queries']}q / "
                    f"Firecrawl {result['api_usage']['firecrawl_scrapes']}s\n"
                    f"所要時間: {result.get('elapsed_sec', 0)}秒"
                )
            }
            requests.post(webhook_url, json=payload, timeout=10)
        except Exception:
            pass

    def start(self):
        log.info(f"🕐 スケジューラー起動 - 毎日 {self.hour:02d}:{self.minute:02d}")
        while self.running:
            nxt = self._next_run()
            wait = (nxt - datetime.now()).total_seconds()
            log.info(f"⏰ 次回: {nxt.strftime('%Y-%m-%d %H:%M')} ({wait/3600:.1f}h後)")
            while wait > 0 and self.running:
                time.sleep(min(60, wait))
                wait = (nxt - datetime.now()).total_seconds()
            if self.running:
                self._execute()


def setup_cron(hour=3, minute=0):
    script_dir = Path(__file__).parent.absolute()
    py = sys.executable
    env_vars = " ".join(
        f"{k}={os.getenv(k, 'YOUR_KEY')}"
        for k in ["GEMINI_API_KEY", "SERPER_API_KEY", "FIRECRAWL_API_KEY"]
        if os.getenv(k)
    )
    line = f"{minute} {hour} * * * cd {script_dir} && {env_vars} {py} design_researcher_v2.py >> cron.log 2>&1"
    print(f"\n📋 crontab に追加:\n  {line}\n")
    print("  crontab -e で上記を追加してください")


def setup_systemd(hour=3, minute=0):
    d = Path(__file__).parent.absolute()
    py = sys.executable
    user = os.getenv("USER", "ubuntu")
    env_lines = "\n".join(
        f"Environment={k}={os.getenv(k, 'YOUR_KEY')}"
        for k in ["GEMINI_API_KEY", "SERPER_API_KEY", "FIRECRAWL_API_KEY"]
    )

    svc = f"""[Unit]
Description=Design Research v2
After=network-online.target

[Service]
Type=oneshot
User={user}
WorkingDirectory={d}
{env_lines}
ExecStart={py} {d}/design_researcher_v2.py
TimeoutStartSec=3600

[Install]
WantedBy=multi-user.target
"""
    tmr = f"""[Unit]
Description=Daily Design Research

[Timer]
OnCalendar=*-*-* {hour:02d}:{minute:02d}:00
Persistent=true

[Install]
WantedBy=timers.target
"""
    (d / "design-research-v2.service").write_text(svc)
    (d / "design-research-v2.timer").write_text(tmr)
    print(f"📋 ファイル生成完了:")
    print(f"  sudo cp {d}/design-research-v2.* /etc/systemd/system/")
    print(f"  sudo systemctl daemon-reload")
    print(f"  sudo systemctl enable --now design-research-v2.timer")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--setup-cron", action="store_true")
    p.add_argument("--setup-systemd", action="store_true")
    p.add_argument("--run-now", action="store_true")
    p.add_argument("--hour", type=int, default=3)
    p.add_argument("--minute", type=int, default=0)
    p.add_argument("--config", default="config.json")
    args = p.parse_args()

    if args.setup_cron:
        setup_cron(args.hour, args.minute)
    elif args.setup_systemd:
        setup_systemd(args.hour, args.minute)
    elif args.run_now:
        from design_researcher_v2 import DesignResearchPipelineV2, load_config
        DesignResearchPipelineV2(load_config(args.config)).run()
    else:
        DailyScheduler(args.hour, args.minute, args.config).start()
