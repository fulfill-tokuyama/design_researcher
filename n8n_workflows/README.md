# n8n ワークフロー集

LeadGenius Design Suite の全自動化を実現する4つのn8nワークフロー。

## インポート方法

1. n8n を開く
2. 左メニュー「Workflows」→「Add Workflow」
3. 右上「...」→「Import from File」
4. 各JSONファイルを選択
5. `/path/to/` を実環境のパスに置換
6. 環境変数をn8nの「Credentials」または「Variables」に設定

## ワークフロー一覧

### 01: 🎨 デザイン自動調査 + 通知

**毎日AM3:00** に自動実行。

```
⏰ Schedule (AM3:00)
  → 🐍 design_researcher_v2.py 実行
  → 📂 index.json 読み込み
  → 🔢 結果パース（新着数・TOP5・トレンドタグ）
  → 🔀 ニュースあり？
     YES → 💬 Discord + 📱 LINE 通知
     NO  → スキップ
```

**通知サンプル:**
```
🎨 デザイン調査完了 (2026/3/7)

📊 サマリー
新規: 5件 / 総ストック: 127件
平均スコア: 78.2 / 変化検知: 1件
📸 スクリーンショット: 5枚

🏆 本日の新着
[92] ミニマル・テック - stripe.com
[88] ダーク・エレガント - linear.app

🔥 トレンドタグ
ミニマル(23) | ダーク(18) | グラデーション(15) | 余白(12)
```

---

### 02: ✨ 高スコアデザイン → LP自動生成

**毎日AM6:00**（調査の3時間後）に実行。

```
⏰ Schedule (AM6:00)
  → 📂 ストック読み込み
  → 🔢 本日の高スコア(≥85)を抽出
  → 🔀 該当あり？
     YES → 🔥 Firecrawl でデザインDNA再取得
          → 🤖 Claude でLP生成（HTML完全版）
          → 💾 HTMLファイル保存
          → 📊 Google Sheets に記録
          → 💬 Discord「LP案が生成されました！」
     NO  → スキップ
```

**ポイント:** 朝起きたらDiscordに「昨日見つけたstripe.com風のLP案です」と届いている状態。

---

### 03: 📧 リード収集 → メール → フォローアップ

**毎週月曜AM9:00** に実行。

```
⏰ Schedule (毎週月曜 AM9:00)
  → 🐍 pipeline.py 実行（Scrapling + Gemini）
  → 📂 結果読み込み
  → 🔢 HOT(≥70) / WARM(40-69) に分類
  → 🔀 HOTリードあり？
     YES → 📧 Resend でメール送信（各リードに個別）
          → 📅 Google Calendar に3日後フォローアップ登録
          → 📊 Google Sheets にリード記録
          → 💬 Discord 通知
     NO  → スキップ
```

**自動化される作業:**
- ターゲット企業のWeb情報収集
- AIスコアリング（0-100）
- パーソナライズドメール文面生成＆送信
- フォローアップ日のカレンダー自動登録
- 全リードのSpreadsheet管理

---

### 04: 🎯 AIO Insight ゼロミーティングセールス

**Webhook駆動**（フォーム送信時に即時実行）。

```
🌐 Webhook: LP のフォーム送信を受信
  → 📋 フォームデータ正規化
  → 🔥 Firecrawl: 見込み客のWebサイトを分析
  → 🤖 Gemini: LLMO診断レポート自動生成
       - AI可視性スコア
       - コンテンツ品質スコア
       - 技術SEOスコア
       - 優先度付き改善提案
  → 📧 Resend: 診断レポートをメール自動返信
  → 📊 Google Sheets: AIOリードとして記録
  → 💬 Discord: 「新規リード！LLMOスコア: 45/100」
  → 🔙 フォーム応答「診断レポートをお送りしました」
```

**これがゼロミーティングセールスの核心:**
1. 見込み客がLPのフォームに企業URL入力
2. 数秒で自動LLMO診断 → 結果メール送信
3. TAKASHIはDiscordで通知を見るだけ
4. 見込み客は「うちのサイト、AI検索でこんなに弱いのか...」と課題を自覚
5. 有料コンサルティングへの自然な導線

## 環境変数

n8n の Variables または .env に設定:

| 変数名 | 用途 | 取得先 |
|--------|------|--------|
| `GEMINI_API_KEY` | KW生成・診断・スコアリング | aistudio.google.com |
| `SERPER_API_KEY` | Google検索 | serper.dev |
| `FIRECRAWL_API_KEY` | デザインDNA・スクショ | firecrawl.dev |
| `RESEND_API_KEY` | メール送信 | resend.com |
| `SENDER_EMAIL` | 送信元アドレス | — |
| `ANTHROPIC_API_KEY` | LP生成（Claude） | console.anthropic.com |
| `DISCORD_WEBHOOK_URL` | Discord通知 | Discord設定 |
| `LINE_NOTIFY_TOKEN` | LINE通知 | notify-bot.line.me |

## 導入順序（推奨）

```
Week 1: 01（デザイン調査）をインポート → 毎日の自動収集を開始
Week 2: 02（LP自動生成）を追加 → おしゃれなLP案が毎日届く
Week 3: 04（ゼロミーティング）を追加 → AIO InsightのLPにWebhook接続
Week 4: 03（リード収集）を追加 → 関西不動産への自動アプローチ開始
```
