"""
LeadGenius AI - スクリーンショット & 変化検知モジュール
====================================================

機能:
  1. スクリーンショット自動保存（Firecrawl screenshot / Scrapling DynamicFetcher）
  2. デザイン変化検知（カラー/フォント/レイアウトの差分比較）
  3. 変化検知時の自動通知（Discord / Slack Webhook）

統合方法:
  design_researcher_v2.py の DesignResearchPipelineV2 にインポートして使用

環境変数:
    FIRECRAWL_API_KEY      : Firecrawl API キー
    DISCORD_WEBHOOK_URL    : Discord通知（オプション）
    SLACK_WEBHOOK_URL      : Slack通知（オプション）
"""

import json
import os
import base64
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import requests

try:
    from scrapling.fetchers import DynamicFetcher
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

log = logging.getLogger("design_v2.screenshot")


# =============================================================================
# 1. スクリーンショット撮影
# =============================================================================

class ScreenshotCapture:
    """Firecrawl + Scrapling でスクリーンショットを撮影・保存"""

    def __init__(
        self,
        firecrawl_key: str = "",
        output_dir: str = "./design_stock_v2/screenshots",
    ):
        self.firecrawl_key = firecrawl_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture(self, url: str, entry_id: str) -> dict:
        """
        URLのスクリーンショットを撮影

        Returns:
            {
                "success": bool,
                "path": "screenshots/abc123_20260306.png",
                "thumbnail_path": "screenshots/abc123_20260306_thumb.png",
                "method": "firecrawl" | "scrapling",
                "timestamp": "2026-03-06T12:00:00",
                "file_size_kb": 245,
            }
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{entry_id}_{timestamp}.png"
        filepath = self.output_dir / filename

        # Firecrawl で撮影（優先）
        if self.firecrawl_key:
            result = self._capture_firecrawl(url, filepath)
            if result["success"]:
                result["thumbnail_path"] = self._create_thumbnail(filepath, entry_id, timestamp)
                return result

        # Scrapling フォールバック
        if HAS_SCRAPLING:
            result = self._capture_scrapling(url, filepath)
            if result["success"]:
                result["thumbnail_path"] = self._create_thumbnail(filepath, entry_id, timestamp)
                return result

        return {"success": False, "error": "No capture method available"}

    def _capture_firecrawl(self, url: str, filepath: Path) -> dict:
        """Firecrawl API でフルページスクリーンショット"""
        try:
            resp = requests.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={
                    "Authorization": f"Bearer {self.firecrawl_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "formats": [{"type": "screenshot", "fullPage": True}],
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                screenshot_data = data.get("data", {}).get("screenshot", "")
                if screenshot_data:
                    # v2: URL または base64
                    if screenshot_data.startswith("http"):
                        img_resp = requests.get(screenshot_data, timeout=30)
                        img_resp.raise_for_status()
                        img_bytes = img_resp.content
                    else:
                        if screenshot_data.startswith("data:image"):
                            screenshot_data = screenshot_data.split(",", 1)[1]
                        img_bytes = base64.b64decode(screenshot_data)
                    filepath.write_bytes(img_bytes)

                    size_kb = len(img_bytes) / 1024
                    log.info(f"    📸 Firecrawl: {filepath.name} ({size_kb:.0f}KB)")

                    return {
                        "success": True,
                        "path": str(filepath.relative_to(filepath.parent.parent)),
                        "method": "firecrawl",
                        "timestamp": datetime.now().isoformat(),
                        "file_size_kb": round(size_kb),
                    }

        except Exception as e:
            log.warning(f"    📸 Firecrawl失敗: {e}")

        return {"success": False}

    def _capture_scrapling(self, url: str, filepath: Path) -> dict:
        """Scrapling DynamicFetcher でスクリーンショット"""
        try:
            page = DynamicFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
                timeout=30,
            )

            # Playwright の screenshot 機能を使用
            # DynamicFetcher はPlaywrightベースなので、ページオブジェクトから取得
            # フォールバック: HTMLからヘッダ部分の情報だけ記録
            html = page.css("html").get("") or ""
            if html:
                # HTMLハッシュをメタデータとして保存（スクリーンショット代替）
                html_hash = hashlib.md5(html[:5000].encode()).hexdigest()

                # 簡易的にHTMLの先頭をテキストとして保存
                meta_path = filepath.with_suffix(".meta.json")
                meta = {
                    "url": url,
                    "html_hash": html_hash,
                    "html_length": len(html),
                    "captured_at": datetime.now().isoformat(),
                    "method": "scrapling_meta",
                }
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

                log.info(f"    📸 Scrapling(meta): {meta_path.name}")
                return {
                    "success": True,
                    "path": str(meta_path.relative_to(meta_path.parent.parent)),
                    "method": "scrapling_meta",
                    "timestamp": datetime.now().isoformat(),
                    "file_size_kb": 0,
                    "html_hash": html_hash,
                }

        except Exception as e:
            log.warning(f"    📸 Scrapling失敗: {e}")

        return {"success": False}

    def _create_thumbnail(self, filepath: Path, entry_id: str, timestamp: str) -> str:
        """サムネイル生成（PILが使える場合）"""
        try:
            from PIL import Image
            if filepath.exists() and filepath.suffix == ".png":
                img = Image.open(filepath)
                img.thumbnail((400, 300))
                thumb_path = filepath.parent / f"{entry_id}_{timestamp}_thumb.png"
                img.save(thumb_path, "PNG", optimize=True)
                return str(thumb_path.relative_to(thumb_path.parent.parent))
        except ImportError:
            pass
        except Exception as e:
            log.debug(f"    サムネイル生成スキップ: {e}")
        return ""

    def get_history(self, entry_id: str) -> list[dict]:
        """エントリのスクリーンショット履歴を取得"""
        history = []
        for f in sorted(self.output_dir.glob(f"{entry_id}_*")):
            if f.suffix in (".png", ".jpg"):
                history.append({
                    "path": str(f.relative_to(f.parent.parent)),
                    "filename": f.name,
                    "size_kb": round(f.stat().st_size / 1024),
                    "captured_at": f.stem.split("_", 1)[1] if "_" in f.stem else "",
                })
            elif f.suffix == ".json" and "meta" in f.name:
                meta = json.loads(f.read_text())
                history.append({
                    "path": str(f.relative_to(f.parent.parent)),
                    "filename": f.name,
                    "captured_at": meta.get("captured_at", ""),
                    "html_hash": meta.get("html_hash", ""),
                })
        return history


# =============================================================================
# 2. デザイン変化検知
# =============================================================================

@dataclass
class DesignDiff:
    """デザイン変更の差分データ"""
    url: str = ""
    entry_id: str = ""
    detected_at: str = ""
    change_level: str = ""              # "major" | "minor" | "none"
    change_score: float = 0.0           # 0-100 (変化度合い)
    summary: str = ""

    # 個別の変更
    color_changes: list = field(default_factory=list)
    font_changes: list = field(default_factory=list)
    layout_changes: list = field(default_factory=list)
    other_changes: list = field(default_factory=list)

    # 前後のデータ
    previous_aesthetic: str = ""
    current_aesthetic: str = ""
    previous_score: float = 0.0
    current_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


CHANGE_ANALYSIS_PROMPT = """あなたはWebデザインの変化を検知する専門家です。
同じWebサイトの2つの時点のデザインデータを比較し、変化を分析してください。

## 前回のデザインデータ
{previous_json}

## 今回のデザインデータ
{current_json}

以下のJSON形式のみ出力してください:
{{
    "change_level": "major" | "minor" | "none",
    "change_score": 0-100（0=変化なし, 100=完全リデザイン）,
    "summary": "変化の要約を1-2文で",
    "color_changes": ["変更内容1", "変更内容2"],
    "font_changes": ["変更内容"],
    "layout_changes": ["変更内容"],
    "other_changes": ["変更内容"],
    "current_aesthetic": "現在のデザインスタイル名",
    "current_score": 現在のデザイン品質スコア(0-100)
}}"""


class DesignChangeDetector:
    """ストック済みサイトのデザイン変化を検知"""

    def __init__(
        self,
        gemini_key: str = "",
        firecrawl_key: str = "",
        gemini_model: str = "gemini-2.0-flash",
        stock_dir: str = "./design_stock_v2",
    ):
        self.gemini_key = gemini_key
        self.firecrawl_key = firecrawl_key
        self.model = gemini_model
        self.stock_dir = Path(stock_dir)
        self.history_dir = self.stock_dir / "change_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

        if gemini_key and HAS_GENAI:
            self.gemini = genai.Client(api_key=gemini_key)
        else:
            self.gemini = None

    def check_site(self, entry_id: str) -> Optional[DesignDiff]:
        """1サイトの変化をチェック"""
        # 前回のデータを読み込み
        detail_path = self.stock_dir / f"{entry_id}.json"
        if not detail_path.exists():
            return None

        previous = json.loads(detail_path.read_text())
        url = previous.get("url", "")
        if not url:
            return None

        log.info(f"  変化チェック: {previous.get('domain', url)}")

        # 現在のデータを取得（Firecrawl Branding）
        current_branding = self._fetch_current_branding(url)
        if not current_branding:
            log.info(f"    → データ取得失敗、スキップ")
            return None

        # 前回のブランディングデータ
        previous_branding = {
            "colors": previous.get("brand_colors", {}),
            "fonts": previous.get("brand_fonts", []),
            "typography": previous.get("brand_typography", {}),
            "aesthetic": previous.get("aesthetic", ""),
            "design_score": previous.get("design_score", 0),
        }

        # 簡易比較（カラーハッシュ）
        prev_hash = hashlib.md5(json.dumps(previous_branding, sort_keys=True).encode()).hexdigest()
        curr_hash = hashlib.md5(json.dumps(current_branding, sort_keys=True).encode()).hexdigest()

        if prev_hash == curr_hash:
            log.info(f"    → 変化なし")
            return DesignDiff(
                url=url, entry_id=entry_id,
                detected_at=datetime.now().isoformat(),
                change_level="none", change_score=0,
                summary="変化なし",
            )

        # Gemini で詳細な変化分析
        diff = self._analyze_changes(url, entry_id, previous_branding, current_branding, previous)

        if diff and diff.change_level != "none":
            # 変化履歴を保存
            self._save_history(diff)

            # 元データを更新
            if diff.change_level == "major":
                self._update_entry(entry_id, current_branding, diff)

        return diff

    def _fetch_current_branding(self, url: str) -> dict:
        """現在のブランディングデータを取得"""
        if not self.firecrawl_key:
            return {}

        try:
            resp = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {self.firecrawl_key}",
                    "Content-Type": "application/json",
                },
                json={"url": url, "formats": ["branding"]},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("data", {}).get("branding", {})
        except Exception as e:
            log.warning(f"    Firecrawl取得失敗: {e}")

        return {}

    def _analyze_changes(
        self, url: str, entry_id: str,
        previous: dict, current: dict, full_previous: dict,
    ) -> Optional[DesignDiff]:
        """Gemini で変化を詳細分析"""
        if not self.gemini:
            # Geminiなしの場合は簡易比較
            return self._simple_diff(url, entry_id, previous, current, full_previous)

        prompt = CHANGE_ANALYSIS_PROMPT.format(
            previous_json=json.dumps(previous, ensure_ascii=False, indent=2)[:2000],
            current_json=json.dumps(current, ensure_ascii=False, indent=2)[:2000],
        )

        try:
            resp = self.gemini.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1024),
            )
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            analysis = json.loads(text)

            diff = DesignDiff(
                url=url,
                entry_id=entry_id,
                detected_at=datetime.now().isoformat(),
                change_level=analysis.get("change_level", "minor"),
                change_score=analysis.get("change_score", 0),
                summary=analysis.get("summary", ""),
                color_changes=analysis.get("color_changes", []),
                font_changes=analysis.get("font_changes", []),
                layout_changes=analysis.get("layout_changes", []),
                other_changes=analysis.get("other_changes", []),
                previous_aesthetic=full_previous.get("aesthetic", ""),
                current_aesthetic=analysis.get("current_aesthetic", ""),
                previous_score=full_previous.get("design_score", 0),
                current_score=analysis.get("current_score", 0),
            )

            level_emoji = {"major": "🔴", "minor": "🟡", "none": "🟢"}
            log.info(f"    {level_emoji.get(diff.change_level, '❓')} {diff.change_level} (スコア: {diff.change_score}) {diff.summary}")

            return diff

        except Exception as e:
            log.warning(f"    Gemini分析失敗: {e}")
            return self._simple_diff(url, entry_id, previous, current, full_previous)

    def _simple_diff(
        self, url: str, entry_id: str,
        previous: dict, current: dict, full_previous: dict,
    ) -> DesignDiff:
        """Geminiなしの簡易差分比較"""
        changes = []

        # カラー比較
        prev_colors = previous.get("colors", {})
        curr_colors = current.get("colors", {})
        color_changes = []
        for key in set(list(prev_colors.keys()) + list(curr_colors.keys())):
            if isinstance(prev_colors.get(key), str) and isinstance(curr_colors.get(key), str):
                if prev_colors.get(key, "").lower() != curr_colors.get(key, "").lower():
                    color_changes.append(f"{key}: {prev_colors.get(key)} → {curr_colors.get(key)}")

        # フォント比較
        prev_fonts = set(str(f) for f in previous.get("fonts", []))
        curr_fonts = set(str(f) for f in current.get("fonts", []))
        font_changes = []
        if prev_fonts != curr_fonts:
            added = curr_fonts - prev_fonts
            removed = prev_fonts - curr_fonts
            if added:
                font_changes.append(f"追加: {', '.join(added)}")
            if removed:
                font_changes.append(f"削除: {', '.join(removed)}")

        total_changes = len(color_changes) + len(font_changes)
        change_score = min(total_changes * 15, 100)
        level = "none" if total_changes == 0 else ("major" if change_score >= 50 else "minor")

        return DesignDiff(
            url=url, entry_id=entry_id,
            detected_at=datetime.now().isoformat(),
            change_level=level,
            change_score=change_score,
            summary=f"{total_changes}箇所の変更を検知" if total_changes else "変化なし",
            color_changes=color_changes,
            font_changes=font_changes,
            previous_aesthetic=full_previous.get("aesthetic", ""),
            previous_score=full_previous.get("design_score", 0),
        )

    def _save_history(self, diff: DesignDiff):
        """変化履歴を保存"""
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        path = self.history_dir / f"{diff.entry_id}_{date_str}.json"
        path.write_text(json.dumps(diff.to_dict(), ensure_ascii=False, indent=2))

    def _update_entry(self, entry_id: str, new_branding: dict, diff: DesignDiff):
        """メジャーチェンジ時にストックデータを更新"""
        detail_path = self.stock_dir / f"{entry_id}.json"
        if not detail_path.exists():
            return

        entry = json.loads(detail_path.read_text())
        entry["brand_colors"] = new_branding.get("colors", entry.get("brand_colors", {}))
        entry["brand_fonts"] = new_branding.get("fonts", entry.get("brand_fonts", []))
        entry["brand_typography"] = new_branding.get("typography", entry.get("brand_typography", {}))

        if diff.current_aesthetic:
            entry["aesthetic"] = diff.current_aesthetic
        if diff.current_score > 0:
            entry["design_score"] = diff.current_score

        entry["last_change_detected"] = diff.detected_at
        entry["change_history"] = entry.get("change_history", [])
        entry["change_history"].append({
            "date": diff.detected_at,
            "level": diff.change_level,
            "score": diff.change_score,
            "summary": diff.summary,
        })

        detail_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
        log.info(f"    → エントリ更新済み")

    def check_all(self, max_checks: int = 20) -> list[DesignDiff]:
        """ストック済みサイト全体の変化チェック"""
        index_path = self.stock_dir / "index.json"
        if not index_path.exists():
            return []

        index = json.loads(index_path.read_text())
        entries = list(index.get("entries", {}).items())

        # スコア上位からチェック（重要なサイト優先）
        entries.sort(key=lambda x: x[1].get("design_score", 0), reverse=True)

        diffs = []
        for i, (entry_id, meta) in enumerate(entries[:max_checks]):
            diff = self.check_site(entry_id)
            if diff:
                diffs.append(diff)
            time.sleep(2)  # レート制限

        return diffs


# =============================================================================
# 3. 通知
# =============================================================================

class ChangeNotifier:
    """変化検知時の通知送信"""

    def __init__(self):
        self.discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.slack_url = os.getenv("SLACK_WEBHOOK_URL", "")

    def notify(self, diffs: list[DesignDiff]):
        """変化があったサイトを通知"""
        significant = [d for d in diffs if d.change_level in ("major", "minor")]
        if not significant:
            return

        major = [d for d in significant if d.change_level == "major"]
        minor = [d for d in significant if d.change_level == "minor"]

        lines = [f"🎨 **デザイン変化検知** ({len(significant)}件)"]
        lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        if major:
            lines.append(f"🔴 **メジャーチェンジ** ({len(major)}件)")
            for d in major[:5]:
                lines.append(f"  • {d.url}")
                lines.append(f"    {d.summary}")
                if d.previous_aesthetic and d.current_aesthetic:
                    lines.append(f"    {d.previous_aesthetic} → {d.current_aesthetic}")
            lines.append("")

        if minor:
            lines.append(f"🟡 **マイナーチェンジ** ({len(minor)}件)")
            for d in minor[:5]:
                lines.append(f"  • {d.url} - {d.summary}")

        message = "\n".join(lines)

        if self.discord_url:
            self._send_discord(message)
        if self.slack_url:
            self._send_slack(message)

    def _send_discord(self, message: str):
        try:
            requests.post(
                self.discord_url,
                json={"content": message[:2000]},
                timeout=10,
            )
            log.info("  📨 Discord通知送信")
        except Exception as e:
            log.warning(f"  Discord通知失敗: {e}")

    def _send_slack(self, message: str):
        try:
            # Slack用にMarkdownを調整
            slack_msg = message.replace("**", "*")
            requests.post(
                self.slack_url,
                json={"text": slack_msg[:3000]},
                timeout=10,
            )
            log.info("  📨 Slack通知送信")
        except Exception as e:
            log.warning(f"  Slack通知失敗: {e}")


# =============================================================================
# 統合: パイプラインに組み込むためのFacade
# =============================================================================

class DesignMonitor:
    """
    スクリーンショット + 変化検知の統合インターフェース
    DesignResearchPipelineV2 から呼び出す用
    """

    def __init__(
        self,
        firecrawl_key: str = "",
        gemini_key: str = "",
        gemini_model: str = "gemini-2.0-flash",
        stock_dir: str = "./design_stock_v2",
    ):
        self.screenshot = ScreenshotCapture(
            firecrawl_key=firecrawl_key,
            output_dir=f"{stock_dir}/screenshots",
        )
        self.detector = DesignChangeDetector(
            gemini_key=gemini_key,
            firecrawl_key=firecrawl_key,
            gemini_model=gemini_model,
            stock_dir=stock_dir,
        )
        self.notifier = ChangeNotifier()

    def capture_screenshot(self, url: str, entry_id: str) -> dict:
        """新規サイトのスクリーンショット撮影"""
        return self.screenshot.capture(url, entry_id)

    def run_change_detection(self, max_checks: int = 20) -> list[DesignDiff]:
        """全ストックサイトの変化チェック + 通知"""
        log.info("\n🔄 デザイン変化検知")
        diffs = self.detector.check_all(max_checks)

        changed = [d for d in diffs if d.change_level != "none"]
        log.info(f"  → チェック: {len(diffs)}件 / 変化: {len(changed)}件")

        if changed:
            self.notifier.notify(diffs)

            # 変化したサイトのスクリーンショットを更新
            for d in changed:
                log.info(f"  📸 スクリーンショット更新: {d.url}")
                self.screenshot.capture(d.url, d.entry_id)

        return diffs

    def get_change_summary(self, stock_dir: str = None) -> dict:
        """変化履歴のサマリーを生成"""
        history_dir = Path(stock_dir or self.detector.stock_dir) / "change_history"
        if not history_dir.exists():
            return {"total_checks": 0, "changes_detected": 0}

        files = list(history_dir.glob("*.json"))
        changes = []
        for f in files:
            try:
                changes.append(json.loads(f.read_text()))
            except:
                pass

        major = sum(1 for c in changes if c.get("change_level") == "major")
        minor = sum(1 for c in changes if c.get("change_level") == "minor")

        return {
            "total_checks": len(files),
            "changes_detected": major + minor,
            "major_changes": major,
            "minor_changes": minor,
            "recent_changes": sorted(
                [c for c in changes if c.get("change_level") != "none"],
                key=lambda x: x.get("detected_at", ""),
                reverse=True,
            )[:10],
        }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="デザイン変化検知ツール")
    parser.add_argument("--check", action="store_true", help="全サイトの変化チェック")
    parser.add_argument("--screenshot", type=str, help="指定URLのスクリーンショット撮影")
    parser.add_argument("--max-checks", type=int, default=20)
    parser.add_argument("--stock-dir", default="./design_stock_v2")
    args = parser.parse_args()

    monitor = DesignMonitor(
        firecrawl_key=os.getenv("FIRECRAWL_API_KEY", ""),
        gemini_key=os.getenv("GEMINI_API_KEY", ""),
        stock_dir=args.stock_dir,
    )

    if args.screenshot:
        entry_id = hashlib.md5(args.screenshot.encode()).hexdigest()[:12]
        result = monitor.capture_screenshot(args.screenshot, entry_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.check:
        diffs = monitor.run_change_detection(args.max_checks)
        changed = [d for d in diffs if d.change_level != "none"]
        print(f"\n📊 結果: {len(diffs)}チェック / {len(changed)}変化検知")
        for d in changed:
            print(f"  {'🔴' if d.change_level == 'major' else '🟡'} {d.url}: {d.summary}")
    else:
        parser.print_help()
