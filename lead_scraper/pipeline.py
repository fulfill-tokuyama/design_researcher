"""
LeadGenius AI - 統合パイプライン
Scrapling(収集) → Gemini(分析・メール生成) → Resend(送信) → Calendar(フォローアップ)

環境変数:
    GEMINI_API_KEY:  Google Gemini APIキー
    RESEND_API_KEY:  Resend APIキー
    SENDER_EMAIL:    送信元メールアドレス

使用方法:
    python pipeline.py --targets targets.json
    python pipeline.py --targets targets.json --dry-run
    python pipeline.py --targets targets.json --min-score 60
"""

import json
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

# .env をプロジェクトルートから読み込み
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from lead_spider import CompanyWebsiteSpider, LeadManager, LeadData
from lead_enricher import LeadEnricher

# Resend (pip install resend)
try:
    import resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False


# =============================================================================
# パイプライン設定
# =============================================================================

class PipelineConfig:
    """パイプライン設定"""
    min_score: int = 40           # メール送信の最低スコア
    send_delay: float = 5.0       # メール送信間隔（秒）
    dry_run: bool = False         # True: メール送信しない
    output_dir: str = "./pipeline_output"
    max_emails_per_run: int = 20  # 1回の実行での最大送信数
    
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


# =============================================================================
# メール送信
# =============================================================================

class EmailSender:
    """Resend APIでメール送信"""
    
    def __init__(self, api_key: str, sender_email: str):
        if not HAS_RESEND:
            raise ImportError("resend パッケージが必要です: pip install resend")
        resend.api_key = api_key
        self.sender_email = sender_email
    
    def send(self, to_email: str, subject: str, body: str) -> dict:
        """メール送信"""
        try:
            # プレーンテキストをHTML化（改行対応）
            html_body = body.replace('\n', '<br>')
            html_body = f"""
            <div style="font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; 
                        font-size: 14px; line-height: 1.8; color: #333;">
                {html_body}
            </div>
            """
            
            result = resend.Emails.send({
                "from": self.sender_email,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            })
            return {"success": True, "id": result.get("id", "")}
        
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# メインパイプライン
# =============================================================================

class LeadGeniusPipeline:
    """
    LeadGenius AI 統合パイプライン
    
    フロー:
        1. Scrapling で企業Webサイトからリード情報を収集
        2. Gemini API でスコアリング＋メール生成
        3. Resend でメール送信
        4. 結果をJSON/CSVにエクスポート
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
    
    def run(self, target_urls: list[str]):
        """パイプライン実行"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print("=" * 60)
        print("🚀 LeadGenius AI パイプライン開始")
        print(f"   実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   対象URL数: {len(target_urls)}")
        print(f"   最低スコア: {self.config.min_score}")
        print(f"   Dry Run: {self.config.dry_run}")
        print("=" * 60)
        
        # ----- Step 1: スクレイピング -----
        print("\n📡 Step 1: Webスクレイピング")
        leads = self._step_scrape(target_urls)
        
        if not leads:
            print("⚠️ リードが収集できませんでした。終了します。")
            return
        
        # ----- Step 2: Gemini スコアリング＋メール生成 -----
        print(f"\n🧠 Step 2: AI分析＋メール生成（{len(leads)}件）")
        enriched = self._step_enrich(leads)
        
        # ----- Step 3: メール送信 -----
        qualified = [l for l in enriched if l.get("scoring", {}).get("score", 0) >= self.config.min_score]
        print(f"\n📧 Step 3: メール送信（対象: {len(qualified)}件）")
        
        if qualified and not self.config.dry_run:
            self._step_send_emails(qualified)
        elif self.config.dry_run:
            print("   [Dry Run] メール送信をスキップ")
        
        # ----- Step 4: 結果エクスポート -----
        print(f"\n💾 Step 4: 結果エクスポート")
        self._step_export(enriched, timestamp)
        
        # ----- サマリー -----
        self._print_summary(enriched)
    
    def _step_scrape(self, target_urls: list[str]) -> list[dict]:
        """Step 1: スクレイピング"""
        spider = CompanyWebsiteSpider(target_urls=target_urls)
        result = spider.start()
        
        leads = [lead.to_dict() for lead in spider.leads]
        print(f"   ✅ {len(leads)}件のリードを収集")
        return leads
    
    def _step_enrich(self, leads: list[dict]) -> list[dict]:
        """Step 2: Gemini APIでスコアリング＋メール生成"""
        import os
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("   ⚠️ GEMINI_API_KEY未設定 → スコアリングスキップ")
            return leads
        
        try:
            enricher = LeadEnricher(api_key)
            return enricher.process_leads(leads, min_score=self.config.min_score)
        except Exception as e:
            print(f"   ⚠️ AI分析エラー: {e}")
            return leads
    
    def _step_send_emails(self, qualified_leads: list[dict]):
        """Step 3: メール送信"""
        import os
        resend_key = os.getenv("RESEND_API_KEY")
        sender = os.getenv("SENDER_EMAIL")
        
        if not resend_key or not sender:
            print("   ⚠️ RESEND_API_KEY / SENDER_EMAIL 未設定 → 送信スキップ")
            return
        
        sender_client = EmailSender(resend_key, sender)
        sent = 0
        
        for lead in qualified_leads[:self.config.max_emails_per_run]:
            email_data = lead.get("generated_email", {})
            to_email = lead.get("email", "")
            
            if not to_email or not email_data:
                continue
            
            subject = email_data.get("subject", "")
            body = email_data.get("body", "")
            
            if not subject or not body:
                continue
            
            result = sender_client.send(to_email, subject, body)
            
            if result["success"]:
                sent += 1
                lead["email_sent"] = True
                lead["email_sent_at"] = datetime.now().isoformat()
                print(f"   ✅ 送信: {lead.get('company_name', '')} → {to_email}")
            else:
                lead["email_sent"] = False
                lead["email_error"] = result.get("error", "")
                print(f"   ❌ 失敗: {lead.get('company_name', '')} - {result.get('error', '')}")
            
            # レート制限対策
            time.sleep(self.config.send_delay)
        
        print(f"   📤 {sent}件送信完了")
    
    def _step_export(self, leads: list[dict], timestamp: str):
        """Step 4: 結果のエクスポート"""
        # JSON出力
        json_path = self.output_dir / f"pipeline_result_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "pipeline_run": timestamp,
                "config": {
                    "min_score": self.config.min_score,
                    "dry_run": self.config.dry_run,
                },
                "total": len(leads),
                "leads": leads,
            }, f, ensure_ascii=False, indent=2)
        
        print(f"   ✅ {json_path}")
        
        # 高スコアリードのみ別ファイル
        high_score = [l for l in leads if l.get("scoring", {}).get("score", 0) >= 60]
        if high_score:
            hot_path = self.output_dir / f"hot_leads_{timestamp}.json"
            with open(hot_path, 'w', encoding='utf-8') as f:
                json.dump(high_score, f, ensure_ascii=False, indent=2)
            print(f"   🔥 高スコアリード: {hot_path} ({len(high_score)}件)")
    
    def _print_summary(self, leads: list[dict]):
        """実行結果サマリー"""
        total = len(leads)
        scored = [l for l in leads if "scoring" in l]
        qualified = [l for l in scored if l.get("scoring", {}).get("score", 0) >= self.config.min_score]
        sent = [l for l in leads if l.get("email_sent")]
        
        avg_score = (
            sum(l["scoring"]["score"] for l in scored if "score" in l.get("scoring", {}))
            / len(scored) if scored else 0
        )
        
        print("\n" + "=" * 60)
        print("📊 パイプライン実行結果")
        print("=" * 60)
        print(f"  収集リード:       {total}件")
        print(f"  スコアリング済:   {len(scored)}件")
        print(f"  平均スコア:       {avg_score:.1f}")
        print(f"  有望リード:       {len(qualified)}件（≥{self.config.min_score}）")
        print(f"  メール送信:       {len(sent)}件")
        print("=" * 60)
        
        if qualified:
            print("\n🏆 上位リード:")
            sorted_leads = sorted(
                qualified,
                key=lambda x: x.get("scoring", {}).get("score", 0),
                reverse=True
            )
            for i, lead in enumerate(sorted_leads[:5]):
                score = lead.get("scoring", {}).get("score", 0)
                name = lead.get("company_name", "Unknown")
                print(f"  {i+1}. [{score}点] {name}")


# =============================================================================
# CLI エントリーポイント
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="LeadGenius AI パイプライン")
    parser.add_argument(
        "--targets", "-t",
        required=True,
        help="ターゲットURLのJSONファイルパス（配列形式）"
    )
    parser.add_argument(
        "--min-score", "-s",
        type=int, default=40,
        help="メール送信の最低スコア（デフォルト: 40）"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="メール送信しない（テスト用）"
    )
    parser.add_argument(
        "--output", "-o",
        default="./pipeline_output",
        help="出力ディレクトリ（デフォルト: ./pipeline_output）"
    )
    
    args = parser.parse_args()
    
    # ターゲットURL読み込み
    targets_path = Path(args.targets)
    if not targets_path.exists():
        print(f"❌ ファイルが見つかりません: {targets_path}")
        return
    
    with open(targets_path, 'r', encoding='utf-8') as f:
        target_urls = json.load(f)
    
    if not isinstance(target_urls, list):
        print("❌ ターゲットファイルはURL配列のJSON形式である必要があります")
        return
    
    config = PipelineConfig(
        min_score=args.min_score,
        dry_run=args.dry_run,
        output_dir=args.output,
    )
    
    pipeline = LeadGeniusPipeline(config)
    pipeline.run(target_urls)


if __name__ == "__main__":
    main()
