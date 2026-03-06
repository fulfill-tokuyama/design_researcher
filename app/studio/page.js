"use client";
import { useState, useRef, useEffect, useMemo } from "react";

const API_URL = "/api/claude";
const MODEL = "claude-sonnet-4-20250514";

// ─── LP Generation Prompt ───
const GEN_PROMPT = `You are a world-class web designer. Create a COMPLETE, production-ready single-page HTML file for a landing page.

DESIGN DNA (extracted from reference sites):
{design_dna}

BUSINESS:
{biz}

RULES:
- Complete HTML with embedded CSS and minimal JS. No frameworks.
- INSPIRED by the design DNA, NOT a copy. Create something ORIGINAL with same aesthetic DNA.
- Google Fonts via <link>. Fully responsive. Smooth scroll + CSS animations.
- ALL text in Japanese (日本語).
- Sections: Hero, Problem, Solution/Features, How It Works, Trust/Testimonials, CTA, Footer.
- STUNNING quality — top design agency level.
- Modern CSS: grid, flexbox, clamp(), custom properties.
- Output: ONLY the HTML. No explanation. No backticks.`;

// ─── Theme: Warm dark editorial ───
const C = {
  bg: "#08080c", s1: "#10101a", s2: "#161622", bd: "#222238",
  tx: "#e8e8f4", mt: "#7878a0", ac: "#f97316", ac2: "#fb923c",
  glow: "rgba(249,115,22,0.12)", gr: "linear-gradient(135deg,#f97316,#f59e0b,#eab308)",
  ok: "#22c55e", warn: "#eab308", err: "#ef4444",
};

const pill = (active) => ({
  padding: "6px 16px", borderRadius: 99, fontSize: 12, fontWeight: 600, cursor: "default",
  border: `1px solid ${active ? C.ac : C.bd}`,
  background: active ? C.glow : "transparent",
  color: active ? C.ac : C.mt,
  transition: "all .3s",
});

export default function DesignStudioV2() {
  useEffect(() => {
    if (!document.getElementById("dsv2-fonts")) {
      const s = document.createElement("style"); s.id = "dsv2-fonts";
      s.textContent = `
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&family=Noto+Sans+JP:wght@400;500;700&display=swap');
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes fadeIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
      `;
      document.head.appendChild(s);
    }
  }, []);

  // ─── State ───
  const [urls, setUrls] = useState([]);
  const [urlInput, setUrlInput] = useState("");
  const [biz, setBiz] = useState(
    "サービス名: AIO Insight\n提供: Fulfill株式会社\n内容: AI検索最適化（LLMO/AIO）診断・対策\nターゲット: 中小企業経営者（関西）\nCTA: 無料LLMO診断レポート申し込み"
  );
  const [step, setStep] = useState(0); // 0=idle 1=analyzing 2=generating 3=done
  const [pct, setPct] = useState(0);
  const [status, setStatus] = useState("");
  const [designDNA, setDesignDNA] = useState(null); // combined branding analysis
  const [html, setHtml] = useState("");
  const [tab, setTab] = useState("preview");
  const [err, setErr] = useState("");
  const iframeRef = useRef(null);

  const addUrl = () => {
    const u = urlInput.trim();
    if (!u) return;
    try { new URL(u); } catch { setErr("有効なURLを入力"); return; }
    if (urls.length >= 5) { setErr("最大5件"); return; }
    if (urls.includes(u)) return;
    setUrls(p => [...p, u]);
    setUrlInput("");
    setErr("");
  };

  // ─── Analyze via Claude (web search for each URL) ───
  const analyzeUrls = async () => {
    if (!urls.length) { setErr("URLを入力してください"); return; }
    setErr(""); setDesignDNA(null); setHtml(""); setStep(1); setPct(10);

    try {
      // Analyze all URLs together
      setStatus("参考サイトのデザインを分析中...");
      const urlList = urls.map((u, i) => `${i + 1}. ${u}`).join("\n");

      const resp = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODEL, max_tokens: 4096,
          tools: [{ type: "web_search_20250305", name: "web_search" }],
          messages: [{
            role: "user",
            content: `Analyze the design of these websites in detail. For each site, extract: exact color palette (hex codes), font families and weights, layout structure, animation/effects, background treatments, spacing philosophy, and standout design elements. Be very specific with CSS values.\n\nSites:\n${urlList}\n\nFinally, synthesize the COMMON design DNA across all sites into a unified design system recommendation. Return as structured JSON with: colors (with hex), typography, layout, effects, aesthetic_name, design_principles.`
          }],
        }),
      });
      const data = await resp.json();
      const analysisText = data.content?.filter(b => b.type === "text").map(b => b.text).join("\n") || "";

      setPct(50);
      setStatus("デザインDNAを構造化中...");

      // Parse into structured DNA
      const parseResp = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODEL, max_tokens: 2048,
          messages: [{
            role: "user",
            content: `Based on this design analysis, extract a structured JSON design system. Return ONLY JSON, no backticks:\n\n${analysisText}\n\nJSON format:\n{"aesthetic":"style name","overview":"2 sentences","colors":{"primary":"#hex","secondary":"#hex","accent":"#hex","background":"#hex","text":"#hex"},"typography":{"heading_font":"name","body_font":"name","heading_weight":"weight"},"layout":{"sections":[],"grid_style":"desc","spacing":"desc"},"effects":{"animations":[],"backgrounds":"desc"},"standout":["5 elements"],"principles":["3-5 principles"]}`
          }],
        }),
      });
      const parseData = await parseResp.json();
      let dnaText = parseData.content?.find(b => b.type === "text")?.text || "";
      dnaText = dnaText.replace(/```json\s*/g, "").replace(/```/g, "").trim();
      const dna = JSON.parse(dnaText);
      setDesignDNA(dna);

      // Generate LP
      setStep(2); setPct(70);
      setStatus("ランディングページを生成中...");

      const genResp = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODEL, max_tokens: 8000,
          messages: [{
            role: "user",
            content: GEN_PROMPT.replace("{design_dna}", JSON.stringify(dna, null, 2)).replace("{biz}", biz),
          }],
        }),
      });
      const genData = await genResp.json();
      let genHtml = genData.content?.find(b => b.type === "text")?.text || "";
      genHtml = genHtml.replace(/```html\s*/g, "").replace(/```/g, "").trim();
      setHtml(genHtml);

      setStep(3); setPct(100); setStatus("完了");
    } catch (e) {
      setErr(`エラー: ${e.message}`);
      setStep(0); setPct(0);
    }
  };

  useEffect(() => {
    if (html && iframeRef.current && tab === "preview") {
      const doc = iframeRef.current.contentDocument;
      doc.open(); doc.write(html); doc.close();
    }
  }, [html, tab]);

  const busy = step === 1 || step === 2;
  const font = "'DM Sans','Noto Sans JP',sans-serif";
  const mono = "'DM Mono',monospace";

  // Color swatches
  const Swatch = ({ color, label }) => (
    <div style={{ textAlign: "center" }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8, background: color,
        border: `2px solid ${C.bd}`, margin: "0 auto",
      }} />
      <div style={{ fontSize: 9, color: C.mt, marginTop: 4, fontFamily: mono }}>{color}</div>
      <div style={{ fontSize: 9, color: C.mt }}>{label}</div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.tx, fontFamily: font }}>
      <style>{`*{box-sizing:border-box;margin:0}`}</style>

      {/* ── Header ── */}
      <header style={{
        padding: "16px 32px", borderBottom: `1px solid ${C.bd}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: C.gr,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 800, color: "#fff",
          }}>D</div>
          <span style={{
            fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em",
            background: C.gr, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>Design Studio v2</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <span style={pill(true)}>Serper</span>
          <span style={pill(true)}>Firecrawl</span>
          <span style={pill(true)}>Gemini</span>
        </div>
      </header>

      <main style={{ maxWidth: 920, margin: "0 auto", padding: "32px 20px" }}>

        {/* ── Hero ── */}
        <div style={{ textAlign: "center", padding: "32px 0 24px" }}>
          <h1 style={{ fontSize: "clamp(24px,3.5vw,38px)", fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1.25 }}>
            参考サイト → <span style={{ background: C.gr, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>デザインDNA抽出</span> → LP生成
          </h1>
          <p style={{ fontSize: 14, color: C.mt, marginTop: 12, lineHeight: 1.7 }}>
            Serper検索 + Firecrawl Branding + Claude分析 の3段構成で高精度なデザイン分析を実現
          </p>
        </div>

        {/* ── Step indicators ── */}
        <div style={{ display: "flex", gap: 8, justifyContent: "center", margin: "20px 0 28px", flexWrap: "wrap" }}>
          {[
            { n: 1, icon: "🔍", label: "分析" },
            { n: 2, icon: "✨", label: "生成" },
            { n: 3, icon: "🎉", label: "完了" },
          ].map(s => (
            <div key={s.n} style={pill(step >= s.n)}>
              {s.icon} {s.label}
            </div>
          ))}
        </div>

        {/* ── Input ── */}
        <div style={{
          background: C.s1, borderRadius: 14, border: `1px solid ${C.bd}`, padding: 28, marginBottom: 20,
        }}>
          <label style={{ fontSize: 11, fontWeight: 700, color: C.mt, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            参考サイトURL（最大5件）
          </label>
          <div style={{ display: "flex", gap: 8, marginTop: 8, marginBottom: 8 }}>
            <input
              value={urlInput}
              onChange={e => setUrlInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && (e.preventDefault(), addUrl())}
              placeholder="https://stripe.com"
              disabled={busy}
              style={{
                flex: 1, padding: "10px 14px", borderRadius: 8,
                border: `1px solid ${C.bd}`, background: C.bg, color: C.tx,
                fontSize: 13, fontFamily: mono, outline: "none",
              }}
            />
            <button onClick={addUrl} disabled={busy} style={{
              padding: "10px 14px", borderRadius: 8, border: `1px solid ${C.bd}`,
              background: C.s2, color: C.mt, fontSize: 16, cursor: "pointer",
            }}>+</button>
          </div>
          <div style={{ minHeight: 20, marginBottom: 12 }}>
            {urls.map((u, i) => (
              <span key={i} style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                padding: "4px 10px", borderRadius: 6, marginRight: 6, marginBottom: 6,
                background: C.glow, border: `1px solid ${C.ac}33`,
                fontSize: 11, color: C.ac, fontFamily: mono,
              }}>
                {u.length > 35 ? u.slice(0, 35) + "…" : u}
                <button onClick={() => setUrls(p => p.filter((_, j) => j !== i))} style={{
                  background: "none", border: "none", color: C.ac, cursor: "pointer", fontSize: 13, padding: 0, opacity: 0.6,
                }}>×</button>
              </span>
            ))}
          </div>

          <label style={{ fontSize: 11, fontWeight: 700, color: C.mt, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: 12, display: "block" }}>
            ビジネス情報
          </label>
          <textarea
            value={biz} onChange={e => setBiz(e.target.value)} disabled={busy}
            style={{
              width: "100%", marginTop: 8, padding: "10px 14px", borderRadius: 8,
              border: `1px solid ${C.bd}`, background: C.bg, color: C.tx,
              fontSize: 13, fontFamily: font, lineHeight: 1.6, resize: "vertical",
              minHeight: 70, outline: "none", boxSizing: "border-box",
            }}
          />

          {err && <p style={{ color: C.err, fontSize: 12, marginTop: 8 }}>{err}</p>}

          <button
            onClick={analyzeUrls}
            disabled={busy || !urls.length}
            style={{
              width: "100%", marginTop: 16, padding: "14px", borderRadius: 10,
              border: "none", background: busy || !urls.length ? C.bd : C.gr,
              color: busy || !urls.length ? C.mt : "#fff",
              fontSize: 15, fontWeight: 700, cursor: busy ? "not-allowed" : "pointer",
            }}
          >
            {busy ? "処理中…" : "🚀 分析 → LP生成"}
          </button>

          {busy && (
            <div style={{ animation: "fadeIn .3s" }}>
              <div style={{ height: 3, background: C.bd, borderRadius: 2, marginTop: 14, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${pct}%`, background: C.gr, transition: "width .5s" }} />
              </div>
              <p style={{ fontSize: 12, color: C.mt, marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{
                  display: "inline-block", width: 12, height: 12,
                  border: `2px solid ${C.bd}`, borderTopColor: C.ac,
                  borderRadius: "50%", animation: "spin .8s linear infinite",
                }} />
                {status}
              </p>
            </div>
          )}
        </div>

        {/* ── Design DNA ── */}
        {designDNA && (
          <div style={{
            background: C.s1, borderRadius: 14, border: `1px solid ${C.bd}`,
            overflow: "hidden", marginBottom: 20, animation: "fadeIn .4s",
          }}>
            <div style={{
              padding: "16px 22px", borderBottom: `1px solid ${C.bd}`,
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{ fontSize: 14, fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}>
                🎨 デザインDNA
              </span>
              <span style={{
                fontSize: 11, padding: "3px 10px", borderRadius: 99,
                background: `${C.ok}22`, color: C.ok, fontWeight: 600,
              }}>{designDNA.aesthetic}</span>
            </div>
            <div style={{ padding: 22 }}>
              <p style={{ fontSize: 13, color: C.mt, lineHeight: 1.7, marginBottom: 16 }}>
                {designDNA.overview}
              </p>

              {/* Colors */}
              {designDNA.colors && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 10, color: C.mt, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>カラーパレット</div>
                  <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                    {Object.entries(designDNA.colors).filter(([, v]) => v?.startsWith?.("#")).map(([k, v]) => (
                      <Swatch key={k} color={v} label={k} />
                    ))}
                  </div>
                </div>
              )}

              {/* Typography + Layout */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10, marginBottom: 16 }}>
                {[
                  ["見出しフォント", designDNA.typography?.heading_font],
                  ["本文フォント", designDNA.typography?.body_font],
                  ["レイアウト", designDNA.layout?.grid_style],
                  ["スペーシング", designDNA.layout?.spacing],
                ].filter(([, v]) => v).map(([l, v]) => (
                  <div key={l} style={{ padding: 12, borderRadius: 8, background: C.bg, border: `1px solid ${C.bd}` }}>
                    <div style={{ fontSize: 9, color: C.mt, textTransform: "uppercase" }}>{l}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* Standout */}
              {designDNA.standout?.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {designDNA.standout.map((el, i) => (
                    <span key={i} style={{
                      padding: "4px 10px", borderRadius: 99, background: C.bg,
                      border: `1px solid ${C.bd}`, fontSize: 11, color: C.tx,
                    }}>{el}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Generated LP ── */}
        {html && (
          <div style={{
            background: C.s1, borderRadius: 14, border: `1px solid ${C.bd}`,
            overflow: "hidden", animation: "fadeIn .4s",
          }}>
            <div style={{
              padding: "16px 22px", borderBottom: `1px solid ${C.bd}`,
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span style={{ fontSize: 14, fontWeight: 700 }}>✨ 生成LP</span>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", borderBottom: `1px solid ${C.bd}` }}>
              {["preview", "code"].map(t => (
                <button key={t} onClick={() => setTab(t)} style={{
                  padding: "10px 18px", fontSize: 12, fontWeight: 600,
                  color: tab === t ? C.ac : C.mt, background: "none", border: "none",
                  borderBottom: `2px solid ${tab === t ? C.ac : "transparent"}`, cursor: "pointer",
                }}>
                  {t === "preview" ? "プレビュー" : "コード"}
                </button>
              ))}
            </div>

            <div style={{ padding: 20 }}>
              {tab === "preview" ? (
                <iframe ref={iframeRef} style={{
                  width: "100%", height: 550, border: "none", borderRadius: 10, background: "#fff",
                }} title="preview" sandbox="allow-scripts allow-same-origin" />
              ) : (
                <div style={{ position: "relative" }}>
                  <button onClick={() => navigator.clipboard.writeText(html)} style={{
                    position: "absolute", top: 8, right: 8,
                    padding: "4px 12px", borderRadius: 6, border: `1px solid ${C.bd}`,
                    background: C.bg, color: C.mt, fontSize: 11, cursor: "pointer", fontWeight: 600,
                  }}>コピー</button>
                  <pre style={{
                    padding: 16, background: C.bg, borderRadius: 8,
                    fontSize: 11, lineHeight: 1.5, fontFamily: mono, color: C.mt,
                    overflow: "auto", maxHeight: 380, whiteSpace: "pre-wrap", wordBreak: "break-all",
                  }}>{html}</pre>
                </div>
              )}

              <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => {
                  const b = new Blob([html], { type: "text/html" });
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(b); a.download = "landing-page.html"; a.click();
                }} style={{
                  padding: "10px 20px", borderRadius: 10, border: "none",
                  background: C.gr, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer",
                }}>📥 ダウンロード</button>
                <button onClick={() => { const w = window.open(); w.document.write(html); w.document.close(); }} style={{
                  padding: "10px 20px", borderRadius: 10, border: `1px solid ${C.bd}`,
                  background: C.s2, color: C.tx, fontSize: 13, fontWeight: 600, cursor: "pointer",
                }}>🔗 新しいタブ</button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
