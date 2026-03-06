"""
LeadGenius AI - Gemini API連携モジュール
収集したリードデータのスコアリングとパーソナライズドメール生成

環境変数:
    GEMINI_API_KEY: Google Gemini APIキー
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

# Gemini SDK (pip install google-genai)
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("⚠️ google-genai がインストールされていません: pip install google-genai")


# =============================================================================
# リードスコアリング
# =============================================================================

SCORING_PROMPT = """あなたはB2B営業のエキスパートです。
以下の不動産会社のリード情報を分析し、AI/DXソリューション（LLMO対策・AI検索最適化サービス）の
導入可能性をスコアリングしてください。

## 評価基準
- 企業規模（従業員数・設立年数）
- デジタル成熟度（Webサイトの有無・質）
- AI/DXニーズの推定度合い
- アプローチのしやすさ（メール・電話の取得状況）

## リード情報
{lead_json}

## 出力フォーマット（JSON）
{{
    "score": 0-100の整数,
    "reasoning": "スコアの根拠（2-3文）",
    "recommended_approach": "推奨アプローチ方法",
    "pain_points": ["推定される課題1", "推定される課題2"],
    "talking_points": ["商談で使えるポイント1", "商談で使えるポイント2"]
}}

JSONのみを出力してください。"""


EMAIL_PROMPT = """あなたはB2Bセールスのメールライターです。
以下の不動産会社に対して、AI検索最適化（LLMO/AIO）サービスの初回アプローチメールを作成してください。

## サービス概要
- サービス名: AIO Insight（AI検索最適化診断・対策サービス）
- 提供元: Fulfill株式会社
- 価値提案: AI検索（ChatGPT、Gemini、Perplexity等）で自社が推薦される状態を作る
- 初回特典: 無料LLMO診断レポート

## リード情報
{lead_json}

## スコアリング分析
{scoring_json}

## メール要件
- 件名: 開封率を最大化する件名
- 本文: 200-300文字程度
- トーン: 丁寧だが堅すぎない、具体的な価値提案を含む
- CTA: 無料診断レポートの申し込みへ誘導
- パーソナライズ: リード情報を活用して個別感を出す

## 出力フォーマット（JSON）
{{
    "subject": "メール件名",
    "body": "メール本文",
    "follow_up_timing": "フォローアップ推奨タイミング",
    "follow_up_subject": "フォローアップメール件名"
}}

JSONのみを出力してください。"""


class LeadEnricher:
    """Gemini APIを使ったリードデータの拡充"""
    
    def __init__(self, api_key: str = None):
        if not HAS_GENAI:
            raise ImportError("google-genai パッケージが必要です")
        
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"  # コスト効率重視
    
    def _call_gemini(self, prompt: str) -> dict:
        """Gemini APIを呼び出してJSONレスポンスを取得"""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # 安定した出力のため低めに設定
                    max_output_tokens=1024,
                ),
            )
            
            text = response.text.strip()
            # コードブロックの除去
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            
            return json.loads(text)
        
        except json.JSONDecodeError as e:
            print(f"⚠️ JSONパースエラー: {e}")
            return {}
        except Exception as e:
            print(f"⚠️ Gemini API エラー: {e}")
            return {}
    
    def score_lead(self, lead_dict: dict) -> dict:
        """リードをスコアリング"""
        prompt = SCORING_PROMPT.format(lead_json=json.dumps(lead_dict, ensure_ascii=False, indent=2))
        result = self._call_gemini(prompt)
        
        if result and "score" in result:
            lead_dict["score"] = result["score"]
            lead_dict["scoring_detail"] = result
        
        return result
    
    def generate_email(self, lead_dict: dict, scoring_result: dict = None) -> dict:
        """パーソナライズドメールを生成"""
        if not scoring_result:
            scoring_result = self.score_lead(lead_dict)
        
        prompt = EMAIL_PROMPT.format(
            lead_json=json.dumps(lead_dict, ensure_ascii=False, indent=2),
            scoring_json=json.dumps(scoring_result, ensure_ascii=False, indent=2),
        )
        
        return self._call_gemini(prompt)
    
    def process_leads(self, leads: list[dict], min_score: int = 40) -> list[dict]:
        """
        リードリストを一括処理
        
        Args:
            leads: リードデータのリスト
            min_score: メール生成の最低スコア閾値
        
        Returns:
            スコアリング・メール付きのリードリスト
        """
        processed = []
        
        for i, lead in enumerate(leads):
            print(f"  [{i+1}/{len(leads)}] {lead.get('company_name', 'Unknown')}...")
            
            # スコアリング
            scoring = self.score_lead(lead)
            lead["scoring"] = scoring
            
            # スコアが閾値以上ならメール生成
            score = scoring.get("score", 0)
            if score >= min_score:
                email = self.generate_email(lead, scoring)
                lead["generated_email"] = email
                print(f"    ✅ スコア: {score} → メール生成済")
            else:
                print(f"    ⏭️  スコア: {score} → スキップ（閾値: {min_score}）")
            
            processed.append(lead)
        
        return processed


# =============================================================================
# 使用例
# =============================================================================

if __name__ == "__main__":
    # テスト用のサンプルリードデータ
    sample_lead = {
        "company_name": "サンプル不動産株式会社",
        "representative": "山田太郎",
        "address": "大阪府大阪市中央区本町1-1-1",
        "phone": "06-1234-5678",
        "email": "info@sample-fudousan.co.jp",
        "website": "https://www.sample-fudousan.co.jp",
        "business_type": "不動産売買・賃貸仲介",
        "area": "関西",
        "license_number": "大阪府知事(3)第12345号",
        "employee_count": "15名",
        "established": "2010年",
    }
    
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        enricher = LeadEnricher(api_key)
        
        print("🧠 リードスコアリング中...")
        scoring = enricher.score_lead(sample_lead)
        print(json.dumps(scoring, ensure_ascii=False, indent=2))
        
        print("\n📧 メール生成中...")
        email = enricher.generate_email(sample_lead, scoring)
        print(json.dumps(email, ensure_ascii=False, indent=2))
    else:
        print("GEMINI_API_KEY を設定してください")
        print("export GEMINI_API_KEY='your-api-key'")
