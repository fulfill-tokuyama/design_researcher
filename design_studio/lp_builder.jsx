import { useState, useRef, useEffect, useCallback } from "react";

const API = "https://api.anthropic.com/v1/messages";
const MDL = "claude-sonnet-4-20250514";

// ─── Section definitions ───
const SECTION_DEFS = [
  { id: "hero", label: "ヒーロー", icon: "🏔️", desc: "ファーストビュー。キャッチコピー + CTA" },
  { id: "problem", label: "課題提起", icon: "⚡", desc: "ターゲットの痛みを言語化" },
  { id: "solution", label: "解決策", icon: "💡", desc: "サービスの価値提案" },
  { id: "features", label: "特徴/機能", icon: "🔧", desc: "3-4つの主要機能" },
  { id: "howto", label: "導入ステップ", icon: "📋", desc: "3ステップの導入フロー" },
  { id: "trust", label: "信頼/実績", icon: "🏆", desc: "数字・導入事例・お客様の声" },
  { id: "pricing", label: "料金/CTA", icon: "💰", desc: "プラン or 無料お試しCTA" },
  { id: "footer", label: "フッター", icon: "📎", desc: "企業情報・リンク" },
];

// ─── Prompts ───
const DESIGN_SYSTEM_PROMPT = `You are an elite Japanese web designer. You create HTML/CSS sections for landing pages.
RULES:
- Output ONLY the HTML for the requested section. No <!DOCTYPE>, <html>, <head>, or <body> tags.
- Use inline <style> at the top of each section for its CSS.
- All text in Japanese (日本語).
- Use Google Fonts via @import in the style block.
- Modern CSS: flexbox, grid, clamp(), custom properties.
- Responsive design. Beautiful animations.
- Make it look like a premium design agency created it.
- NEVER use generic fonts like Arial/Inter. Pick distinctive fonts.
- Output raw HTML only. No markdown. No backticks.`;

const sectionPrompt = (section, biz, designDNA, prevSections) => {
  const context = prevSections.length > 0
    ? `\n\nPREVIOUS SECTIONS (maintain visual consistency - use same fonts, colors, spacing):\n${prevSections.map(s => `[${s.id}]: fonts=${s.fonts || 'not set'}, primary_color=${s.primaryColor || 'not set'}`).join("\n")}`
    : "";

  return `${DESIGN_SYSTEM_PROMPT}

DESIGN DNA: ${designDNA || "Premium, modern, bold typography with generous whitespace. Dark hero transitioning to light sections."}

BUSINESS: ${biz}
${context}
Create the "${section.label}" section (${section.desc}).
Section ID: ${section.id}
Wrap everything in a <section id="${section.id}"> tag.`;
};

const REFINE_PROMPT = (sectionId, currentHtml, instruction) =>
  `${DESIGN_SYSTEM_PROMPT}

Here is the current HTML for the "${sectionId}" section:
${currentHtml}

USER'S EDIT REQUEST: ${instruction}

Modify the section according to the request. Keep the same <section id="${sectionId}"> wrapper.
Output ONLY the modified HTML. No explanation.`;

// ─── Theme ───
const T = {
  bg: "#05050a",
  panel: "#0c0c14",
  card: "#111119",
  cardHover: "#16161f",
  bd: "#1f1f32",
  bdFocus: "#e67e22",
  tx: "#eaeaf4",
  mt: "#6a6a8c",
  ac: "#e67e22",
  ac2: "#f39c12",
  acSoft: "rgba(230,126,34,0.1)",
  gr: "linear-gradient(135deg, #e67e22 0%, #f1c40f 100%)",
  ok: "#2ecc71",
  err: "#e74c3c",
};

const font = "'DM Sans','Noto Sans JP',sans-serif";
const mono = "'DM Mono',monospace";

// ─── Utility ───
const cls = (...args) => args.filter(Boolean).join(" ");

function IconBtn({ children, onClick, disabled, title, active, small }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        padding: small ? "4px 8px" : "6px 10px",
        borderRadius: 6,
        border: `1px solid ${active ? T.ac : T.bd}`,
        background: active ? T.acSoft : "transparent",
        color: active ? T.ac : T.mt,
        fontSize: small ? 12 : 13,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        transition: "all .15s",
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      {children}
    </button>
  );
}

// ─── Main Component ───
export default function LPBuilder() {
  useEffect(() => {
    if (!document.getElementById("lpb-css")) {
      const s = document.createElement("style");
      s.id = "lpb-css";
      s.textContent = `
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400&family=Noto+Sans+JP:wght@400;500;700&display=swap');
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
        .lpb-section-card:hover{border-color:${T.bdFocus}!important}
        .lpb-drag-over{border-color:${T.ac}!important;background:${T.acSoft}!important}
      `;
      document.head.appendChild(s);
    }
  }, []);

  // ─── State ───
  const [biz, setBiz] = useState(
    "サービス名: AIO Insight\n提供: Fulfill株式会社\n内容: AI検索最適化（LLMO/AIO）診断・対策サービス\nターゲット: 中小企業経営者（関西エリア）\nCTA: 無料LLMO診断レポート申し込み"
  );
  const [designDNA, setDesignDNA] = useState("");
  const [sections, setSections] = useState(
    SECTION_DEFS.map((d) => ({ ...d, html: "", status: "pending", generating: false }))
  );
  const [activeSection, setActiveSection] = useState(null);
  const [editInstruction, setEditInstruction] = useState("");
  const [isRefining, setIsRefining] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [genAll, setGenAll] = useState(false);
  const previewRef = useRef(null);
  const [dragIdx, setDragIdx] = useState(null);

  // ─── API call ───
  const callClaude = async (prompt) => {
    const resp = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: MDL, max_tokens: 4000, messages: [{ role: "user", content: prompt }] }),
    });
    const data = await resp.json();
    let text = data.content?.find((b) => b.type === "text")?.text || "";
    return text.replace(/```html\s*/g, "").replace(/```/g, "").trim();
  };

  // ─── Generate single section ───
  const generateSection = useCallback(async (idx) => {
    setSections((prev) => prev.map((s, i) => (i === idx ? { ...s, generating: true, status: "generating" } : s)));

    try {
      const currentSections = sections.slice(0, idx).filter((s) => s.html);
      const prompt = sectionPrompt(sections[idx], biz, designDNA, currentSections);
      const html = await callClaude(prompt);

      setSections((prev) =>
        prev.map((s, i) => (i === idx ? { ...s, html, generating: false, status: "done" } : s))
      );
    } catch (e) {
      setSections((prev) =>
        prev.map((s, i) => (i === idx ? { ...s, generating: false, status: "error" } : s))
      );
    }
  }, [sections, biz, designDNA]);

  // ─── Generate all sections sequentially ───
  const generateAll = async () => {
    setGenAll(true);
    for (let i = 0; i < sections.length; i++) {
      if (sections[i].status === "done" && sections[i].html) continue;

      setSections((prev) => prev.map((s, j) => (j === i ? { ...s, generating: true, status: "generating" } : s)));

      try {
        // Get latest state for context
        const prevDone = [];
        setSections((prev) => {
          prev.slice(0, i).filter((s) => s.html).forEach((s) => prevDone.push(s));
          return prev;
        });

        const prompt = sectionPrompt(SECTION_DEFS[i], biz, designDNA, prevDone);
        const html = await callClaude(prompt);

        setSections((prev) =>
          prev.map((s, j) => (j === i ? { ...s, html, generating: false, status: "done" } : s))
        );
      } catch {
        setSections((prev) =>
          prev.map((s, j) => (j === i ? { ...s, generating: false, status: "error" } : s))
        );
      }
    }
    setGenAll(false);
  };

  // ─── Refine section ───
  const refineSection = async (idx) => {
    if (!editInstruction.trim()) return;
    setIsRefining(true);

    try {
      const prompt = REFINE_PROMPT(sections[idx].id, sections[idx].html, editInstruction);
      const html = await callClaude(prompt);
      setSections((prev) => prev.map((s, i) => (i === idx ? { ...s, html } : s)));
      setEditInstruction("");
    } catch (e) {
      console.error(e);
    }
    setIsRefining(false);
  };

  // ─── Drag & drop reorder ───
  const handleDragStart = (idx) => setDragIdx(idx);
  const handleDragOver = (e, idx) => { e.preventDefault(); };
  const handleDrop = (idx) => {
    if (dragIdx === null || dragIdx === idx) return;
    setSections((prev) => {
      const next = [...prev];
      const [removed] = next.splice(dragIdx, 1);
      next.splice(idx, 0, removed);
      return next;
    });
    setDragIdx(null);
  };

  // ─── Remove / duplicate section ───
  const removeSection = (idx) => setSections((prev) => prev.filter((_, i) => i !== idx));
  const duplicateSection = (idx) => {
    setSections((prev) => {
      const dup = { ...prev[idx], id: prev[idx].id + "_copy", label: prev[idx].label + " (コピー)" };
      const next = [...prev];
      next.splice(idx + 1, 0, dup);
      return next;
    });
  };

  // ─── Combine for preview / export ───
  const fullHtml = `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Landing Page</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:sans-serif;overflow-x:hidden}</style>
</head>
<body>
${sections.filter((s) => s.html).map((s) => s.html).join("\n\n")}
</body>
</html>`;

  useEffect(() => {
    if (showPreview && previewRef.current) {
      const doc = previewRef.current.contentDocument;
      doc.open(); doc.write(fullHtml); doc.close();
    }
  }, [showPreview, sections]);

  const doneCount = sections.filter((s) => s.html).length;

  return (
    <div style={{ minHeight: "100vh", background: T.bg, color: T.tx, fontFamily: font, display: "flex", flexDirection: "column" }}>
      {/* ── Header ── */}
      <header style={{
        padding: "12px 24px", borderBottom: `1px solid ${T.bd}`,
        display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: 7, background: T.gr, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, color: "#fff" }}>LP</div>
          <span style={{ fontSize: 15, fontWeight: 700, background: T.gr, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>LP Builder</span>
          <span style={{ fontSize: 11, color: T.mt, marginLeft: 4 }}>セクション編集モード</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: T.mt }}>{doneCount}/{sections.length} セクション</span>
          <IconBtn onClick={() => setShowPreview(!showPreview)} active={showPreview}>
            {showPreview ? "✏️ 編集" : "👁️ プレビュー"}
          </IconBtn>
          <IconBtn onClick={() => { const b = new Blob([fullHtml], { type: "text/html" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "landing-page.html"; a.click(); }} disabled={doneCount === 0}>
            📥 DL
          </IconBtn>
        </div>
      </header>

      {showPreview ? (
        /* ── Full Preview ── */
        <iframe ref={previewRef} style={{ flex: 1, border: "none", background: "#fff" }} title="preview" sandbox="allow-scripts allow-same-origin" />
      ) : (
        /* ── Editor ── */
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left: Settings + Section List */}
          <div style={{ width: 340, borderRight: `1px solid ${T.bd}`, display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0 }}>
            {/* Biz + Design DNA */}
            <div style={{ padding: 16, borderBottom: `1px solid ${T.bd}`, flexShrink: 0 }}>
              <label style={{ fontSize: 10, fontWeight: 700, color: T.mt, textTransform: "uppercase", letterSpacing: ".06em" }}>ビジネス情報</label>
              <textarea
                value={biz} onChange={(e) => setBiz(e.target.value)}
                style={{ width: "100%", marginTop: 6, padding: "8px 10px", borderRadius: 6, border: `1px solid ${T.bd}`, background: T.bg, color: T.tx, fontSize: 11, fontFamily: font, lineHeight: 1.5, resize: "vertical", minHeight: 60, outline: "none", boxSizing: "border-box" }}
              />
              <label style={{ fontSize: 10, fontWeight: 700, color: T.mt, textTransform: "uppercase", letterSpacing: ".06em", marginTop: 10, display: "block" }}>デザインDNA（任意）</label>
              <input
                value={designDNA} onChange={(e) => setDesignDNA(e.target.value)}
                placeholder="例: ダーク×ミニマル、Stripe風"
                style={{ width: "100%", marginTop: 6, padding: "8px 10px", borderRadius: 6, border: `1px solid ${T.bd}`, background: T.bg, color: T.tx, fontSize: 11, outline: "none", boxSizing: "border-box" }}
              />
              <button
                onClick={generateAll} disabled={genAll}
                style={{ width: "100%", marginTop: 10, padding: "10px", borderRadius: 8, border: "none", background: genAll ? T.bd : T.gr, color: genAll ? T.mt : "#fff", fontSize: 13, fontWeight: 700, cursor: genAll ? "not-allowed" : "pointer" }}
              >
                {genAll ? "⏳ 生成中…" : "🚀 全セクション生成"}
              </button>
            </div>

            {/* Section List */}
            <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
              {sections.map((s, i) => (
                <div
                  key={s.id + i}
                  className="lpb-section-card"
                  draggable
                  onDragStart={() => handleDragStart(i)}
                  onDragOver={(e) => handleDragOver(e, i)}
                  onDrop={() => handleDrop(i)}
                  onClick={() => setActiveSection(i)}
                  style={{
                    margin: "0 12px 6px", padding: "10px 12px", borderRadius: 8,
                    border: `1px solid ${activeSection === i ? T.ac : T.bd}`,
                    background: activeSection === i ? T.acSoft : T.card,
                    cursor: "pointer", transition: "all .15s", animation: "fadeIn .3s",
                    display: "flex", alignItems: "center", gap: 10,
                  }}
                >
                  <span style={{ cursor: "grab", color: T.mt, fontSize: 11 }}>⠿</span>
                  <span style={{ fontSize: 16 }}>{s.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.label}</div>
                    <div style={{ fontSize: 10, color: T.mt }}>{s.desc}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    {s.generating && <span style={{ width: 10, height: 10, border: `2px solid ${T.bd}`, borderTopColor: T.ac, borderRadius: "50%", animation: "spin .7s linear infinite", display: "inline-block" }} />}
                    {s.status === "done" && <span style={{ color: T.ok, fontSize: 14 }}>✓</span>}
                    {s.status === "error" && <span style={{ color: T.err, fontSize: 14 }}>✗</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Section Editor */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {activeSection !== null ? (
              <>
                {/* Section header */}
                <div style={{
                  padding: "12px 20px", borderBottom: `1px solid ${T.bd}`,
                  display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 18 }}>{sections[activeSection].icon}</span>
                    <span style={{ fontSize: 14, fontWeight: 700 }}>{sections[activeSection].label}</span>
                    {sections[activeSection].status === "done" && (
                      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 99, background: `${T.ok}22`, color: T.ok, fontWeight: 600 }}>生成済み</span>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    <IconBtn small onClick={() => generateSection(activeSection)} disabled={sections[activeSection].generating}>
                      {sections[activeSection].html ? "🔄 再生成" : "✨ 生成"}
                    </IconBtn>
                    <IconBtn small onClick={() => duplicateSection(activeSection)} title="複製">📋</IconBtn>
                    <IconBtn small onClick={() => { removeSection(activeSection); setActiveSection(null); }} title="削除">🗑️</IconBtn>
                  </div>
                </div>

                {/* Section preview */}
                <div style={{ flex: 1, overflow: "auto", position: "relative" }}>
                  {sections[activeSection].html ? (
                    <iframe
                      srcDoc={`<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:sans-serif}</style></head><body>${sections[activeSection].html}</body></html>`}
                      style={{ width: "100%", height: "100%", border: "none", background: "#fff" }}
                      title={sections[activeSection].id}
                      sandbox="allow-scripts allow-same-origin"
                    />
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: T.mt, fontSize: 14 }}>
                      {sections[activeSection].generating ? (
                        <div style={{ textAlign: "center" }}>
                          <div style={{ width: 24, height: 24, border: `3px solid ${T.bd}`, borderTopColor: T.ac, borderRadius: "50%", animation: "spin .8s linear infinite", margin: "0 auto 12px" }} />
                          生成中…
                        </div>
                      ) : (
                        <div style={{ textAlign: "center" }}>
                          <div style={{ fontSize: 32, marginBottom: 8 }}>{sections[activeSection].icon}</div>
                          「✨ 生成」をクリックしてこのセクションを作成
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Edit bar */}
                {sections[activeSection].html && (
                  <div style={{
                    padding: "10px 16px", borderTop: `1px solid ${T.bd}`,
                    display: "flex", gap: 8, flexShrink: 0, background: T.panel,
                  }}>
                    <input
                      value={editInstruction}
                      onChange={(e) => setEditInstruction(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); refineSection(activeSection); } }}
                      placeholder="修正指示を入力（例: 背景を暗くして、CTAボタンをもっと大きく）"
                      disabled={isRefining}
                      style={{
                        flex: 1, padding: "10px 14px", borderRadius: 8,
                        border: `1px solid ${T.bd}`, background: T.bg, color: T.tx,
                        fontSize: 12, outline: "none", fontFamily: font,
                      }}
                    />
                    <button
                      onClick={() => refineSection(activeSection)}
                      disabled={isRefining || !editInstruction.trim()}
                      style={{
                        padding: "10px 18px", borderRadius: 8, border: "none",
                        background: isRefining ? T.bd : T.gr, color: isRefining ? T.mt : "#fff",
                        fontSize: 12, fontWeight: 700, cursor: isRefining ? "not-allowed" : "pointer",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {isRefining ? "⏳" : "✏️ 修正"}
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: T.mt, fontSize: 14 }}>
                ← 左のセクションリストから編集するセクションを選択
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
