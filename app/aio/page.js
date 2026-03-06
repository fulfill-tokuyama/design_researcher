"use client";
import { useEffect, useState, useRef } from "react";

// ─── Design System ───
const C = {
  bg: "#030712",
  s1: "#0a1628",
  s2: "#111d33",
  card: "rgba(255,255,255,0.03)",
  bd: "rgba(255,255,255,0.08)",
  tx: "#f1f5f9",
  mt: "#94a3b8",
  ac: "#3b82f6",
  ac2: "#60a5fa",
  acGlow: "rgba(59,130,246,0.15)",
  gr: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #06b6d4 100%)",
  grText: "linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #22d3ee 100%)",
  ok: "#10b981",
  warn: "#f59e0b",
  err: "#ef4444",
};

const font = "'Inter','Noto Sans JP',system-ui,sans-serif";

// ─── Animated Counter ───
function Counter({ end, suffix = "", duration = 2000 }) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          const start = performance.now();
          const tick = (now) => {
            const p = Math.min((now - start) / duration, 1);
            setVal(Math.floor(p * end));
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          obs.disconnect();
        }
      },
      { threshold: 0.3 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [end, duration]);
  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>;
}

// ─── FAQ Item ───
function FAQ({ q, a }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        borderBottom: `1px solid ${C.bd}`,
        padding: "20px 0",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none", border: "none", color: C.tx, cursor: "pointer",
          fontSize: 16, fontWeight: 600, fontFamily: font, textAlign: "left",
          width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center",
        }}
      >
        {q}
        <span style={{
          transform: open ? "rotate(45deg)" : "none",
          transition: "transform 0.3s", fontSize: 22, color: C.ac, flexShrink: 0, marginLeft: 16,
        }}>+</span>
      </button>
      {open && (
        <p style={{
          color: C.mt, fontSize: 14, lineHeight: 1.8, marginTop: 12,
          animation: "fadeIn 0.3s ease",
        }}>{a}</p>
      )}
    </div>
  );
}

// ─── Main Page ───
export default function AIOInsightLP() {
  const [scrollY, setScrollY] = useState(0);
  useEffect(() => {
    const h = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  useEffect(() => {
    if (!document.getElementById("aio-styles")) {
      const s = document.createElement("style");
      s.id = "aio-styles";
      s.textContent = `
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
        @keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
        @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
        @keyframes glow{0%,100%{box-shadow:0 0 20px rgba(59,130,246,0.3)}50%{box-shadow:0 0 40px rgba(59,130,246,0.6)}}
        @keyframes slideRight{from{transform:translateX(-100%);opacity:0}to{transform:translateX(0);opacity:1}}
        .aio-reveal{opacity:0;transform:translateY(30px);transition:all 0.8s cubic-bezier(0.16,1,0.3,1)}
        .aio-reveal.visible{opacity:1;transform:none}
        .aio-cta:hover{transform:translateY(-2px)!important;box-shadow:0 8px 30px rgba(59,130,246,0.4)!important}
        .aio-card:hover{border-color:rgba(59,130,246,0.3)!important;transform:translateY(-4px)!important}
        .aio-feature:hover .aio-feature-icon{transform:scale(1.1)}
        html{scroll-behavior:smooth}
      `;
      document.head.appendChild(s);
    }
    // Intersection Observer for reveal
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add("visible"); }),
      { threshold: 0.1 }
    );
    document.querySelectorAll(".aio-reveal").forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  // Re-observe after render
  useEffect(() => {
    const t = setTimeout(() => {
      const obs = new IntersectionObserver(
        (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add("visible"); }),
        { threshold: 0.1 }
      );
      document.querySelectorAll(".aio-reveal").forEach((el) => obs.observe(el));
      return () => obs.disconnect();
    }, 100);
    return () => clearTimeout(t);
  });

  const section = {
    maxWidth: 1100,
    margin: "0 auto",
    padding: "100px 24px",
  };

  return (
    <div style={{ background: C.bg, color: C.tx, fontFamily: font, overflowX: "hidden" }}>

      {/* ── Nav ── */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        padding: "16px 32px",
        background: scrollY > 50 ? "rgba(3,7,18,0.85)" : "transparent",
        backdropFilter: scrollY > 50 ? "blur(20px)" : "none",
        borderBottom: scrollY > 50 ? `1px solid ${C.bd}` : "none",
        transition: "all 0.3s",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: C.gr, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 900, color: "#fff",
          }}>AI</div>
          <span style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.03em" }}>
            AIO <span style={{ color: C.ac2 }}>Insight</span>
          </span>
        </div>
        <div style={{ display: "flex", gap: 28, alignItems: "center" }}>
          {["課題", "機能", "実績", "料金"].map((t) => (
            <a key={t} href={`#${t}`} style={{
              color: C.mt, textDecoration: "none", fontSize: 13, fontWeight: 500,
              transition: "color 0.2s",
            }}>{t}</a>
          ))}
          <a href="#cta" className="aio-cta" style={{
            padding: "8px 20px", borderRadius: 8, background: C.gr,
            color: "#fff", textDecoration: "none", fontSize: 13, fontWeight: 700,
            transition: "all 0.3s",
          }}>無料診断</a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section style={{
        minHeight: "100vh", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", textAlign: "center",
        padding: "120px 24px 80px", position: "relative", overflow: "hidden",
      }}>
        {/* Background effects */}
        <div style={{
          position: "absolute", top: "20%", left: "50%", transform: "translate(-50%,-50%)",
          width: 600, height: 600, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)",
          filter: "blur(80px)", pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", top: "60%", right: "10%",
          width: 300, height: 300, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)",
          filter: "blur(60px)", pointerEvents: "none",
        }} />

        <div style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "6px 16px", borderRadius: 99, border: `1px solid ${C.bd}`,
          background: C.card, fontSize: 13, color: C.ac2, fontWeight: 600,
          marginBottom: 32, animation: "fadeIn 0.6s ease",
        }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.ok, animation: "pulse 2s infinite" }} />
          AI時代の新しいSEO対策
        </div>

        <h1 style={{
          fontSize: "clamp(36px, 5.5vw, 72px)", fontWeight: 900,
          lineHeight: 1.1, letterSpacing: "-0.04em",
          maxWidth: 800, marginBottom: 24, animation: "fadeIn 0.8s ease",
        }}>
          AI検索で<br />
          <span style={{
            background: C.grText, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>選ばれる企業</span>になる
        </h1>

        <p style={{
          fontSize: "clamp(16px, 2vw, 20px)", color: C.mt, lineHeight: 1.8,
          maxWidth: 580, marginBottom: 48, animation: "fadeIn 1s ease",
        }}>
          ChatGPT・Gemini・Perplexityなどの<strong style={{ color: C.tx }}>AI検索</strong>で
          あなたの会社が推薦される状態を作る。<br />
          それが<strong style={{ color: C.ac2 }}>AIO Insight</strong>です。
        </p>

        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center", animation: "fadeIn 1.2s ease" }}>
          <a href="#cta" className="aio-cta" style={{
            padding: "16px 36px", borderRadius: 12, background: C.gr,
            color: "#fff", textDecoration: "none", fontSize: 16, fontWeight: 700,
            transition: "all 0.3s", display: "inline-flex", alignItems: "center", gap: 8,
          }}>
            無料LLMO診断を受ける
            <span style={{ fontSize: 20 }}>→</span>
          </a>
          <a href="#課題" style={{
            padding: "16px 36px", borderRadius: 12,
            border: `1px solid ${C.bd}`, background: C.card,
            color: C.tx, textDecoration: "none", fontSize: 16, fontWeight: 600,
            transition: "all 0.3s",
          }}>詳しく見る</a>
        </div>

        {/* Trust badges */}
        <div style={{
          marginTop: 80, display: "flex", gap: 48, alignItems: "center",
          color: C.mt, fontSize: 13, fontWeight: 500, flexWrap: "wrap", justifyContent: "center",
          animation: "fadeIn 1.4s ease",
        }}>
          {["導入企業 50社+", "平均改善率 340%", "初期費用 0円"].map((t) => (
            <div key={t} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: C.ok }}>✓</span> {t}
            </div>
          ))}
        </div>
      </section>

      {/* ── Problem ── */}
      <section id="課題" style={{ ...section, paddingTop: 80 }}>
        <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
          <span style={{
            fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}>PROBLEM</span>
          <h2 style={{
            fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
            letterSpacing: "-0.03em", marginTop: 12, lineHeight: 1.3,
          }}>
            SEO対策だけでは<br />もう見つけてもらえない
          </h2>
        </div>

        <div className="aio-reveal" style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20,
        }}>
          {[
            {
              icon: "🔍", title: "検索行動の変化",
              desc: "ユーザーの40%以上がGoogleではなくAIに質問して情報を得る時代に。従来のSEOだけでは機会損失が拡大しています。",
              color: "#ef4444",
            },
            {
              icon: "🤖", title: "AI検索での不在",
              desc: "「大阪でおすすめの不動産会社は？」とAIに聞いたとき、あなたの会社名は出てきますか？出てこなければ、存在しないのと同じです。",
              color: "#f59e0b",
            },
            {
              icon: "📉", title: "競合との差が開く",
              desc: "AI検索最適化に早く着手した企業から順に「AIの推薦リスト」に入ります。後になるほど、逆転が困難になります。",
              color: "#8b5cf6",
            },
          ].map((item) => (
            <div key={item.title} className="aio-card" style={{
              padding: 32, borderRadius: 16,
              border: `1px solid ${C.bd}`, background: C.card,
              transition: "all 0.3s",
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: `${item.color}15`, border: `1px solid ${item.color}30`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 22, marginBottom: 20,
              }}>{item.icon}</div>
              <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>{item.title}</h3>
              <p style={{ fontSize: 14, color: C.mt, lineHeight: 1.8 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── What is LLMO/AIO ── */}
      <section style={{
        ...section, background: C.s1,
        borderTop: `1px solid ${C.bd}`, borderBottom: `1px solid ${C.bd}`,
        maxWidth: "100%", padding: "100px 24px",
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
            <span style={{
              fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}>WHAT IS LLMO / AIO</span>
            <h2 style={{
              fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
              letterSpacing: "-0.03em", marginTop: 12,
            }}>
              AI検索最適化とは？
            </h2>
          </div>

          <div className="aio-reveal" style={{
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32, alignItems: "center",
          }}>
            <div>
              <div style={{
                padding: 32, borderRadius: 16, border: `1px solid ${C.bd}`,
                background: "rgba(59,130,246,0.05)", marginBottom: 24,
              }}>
                <div style={{ fontSize: 13, color: C.ac2, fontWeight: 700, marginBottom: 8 }}>従来のSEO</div>
                <p style={{ fontSize: 14, color: C.mt, lineHeight: 1.7 }}>
                  Googleの検索結果で上位表示 → ユーザーがクリック → サイト訪問
                </p>
              </div>
              <div style={{
                padding: 32, borderRadius: 16, border: `1px solid rgba(139,92,246,0.3)`,
                background: "rgba(139,92,246,0.05)",
              }}>
                <div style={{ fontSize: 13, color: "#a78bfa", fontWeight: 700, marginBottom: 8 }}>
                  LLMO / AIO（AI検索最適化）
                </div>
                <p style={{ fontSize: 14, color: C.mt, lineHeight: 1.7 }}>
                  AIの回答内で企業名・サービス名が推薦される → ユーザーが直接行動<br />
                  <strong style={{ color: C.tx }}>クリック不要で認知 → コンバージョン率が圧倒的に高い</strong>
                </p>
              </div>
            </div>
            <div style={{
              padding: 32, borderRadius: 16, border: `1px solid ${C.bd}`,
              background: C.card, fontFamily: "'Courier New', monospace",
            }}>
              <div style={{ fontSize: 12, color: C.mt, marginBottom: 16 }}>
                <span style={{ color: C.ok }}>●</span> ChatGPT の回答例
              </div>
              <div style={{ fontSize: 14, color: C.mt, lineHeight: 2 }}>
                <span style={{ color: "#64748b" }}>Q: 大阪でAI対策に強い会社は？</span><br /><br />
                A: 大阪でAI検索最適化（LLMO/AIO）に<br />
                強い会社としては、<br />
                <strong style={{
                  color: C.ac2, background: "rgba(59,130,246,0.15)",
                  padding: "2px 6px", borderRadius: 4,
                }}>Fulfill株式会社の「AIO Insight」</strong><br />
                が挙げられます。<br />
                中小企業向けに特化した診断・対策を<br />
                提供しており...
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="機能" style={section}>
        <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
          <span style={{
            fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}>FEATURES</span>
          <h2 style={{
            fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
            letterSpacing: "-0.03em", marginTop: 12,
          }}>
            AIO Insightの4つの強み
          </h2>
        </div>

        <div className="aio-reveal" style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 20,
        }}>
          {[
            { icon: "📊", title: "AI検索診断レポート", desc: "ChatGPT・Gemini・Perplexityでの現在の露出状況を完全可視化。競合との比較レポートも。", gradient: "linear-gradient(135deg, #3b82f6, #06b6d4)" },
            { icon: "🎯", title: "最適化コンサルティング", desc: "診断結果を基に、AIに推薦されるための具体的な改善施策を提案・実行サポート。", gradient: "linear-gradient(135deg, #8b5cf6, #ec4899)" },
            { icon: "📈", title: "継続モニタリング", desc: "月次でAI検索での露出状況を追跡。改善効果の数値化とレポーティング。", gradient: "linear-gradient(135deg, #10b981, #3b82f6)" },
            { icon: "🏢", title: "中小企業特化", desc: "関西エリアの中小企業に特化。業種別のノウハウで、大手に負けないAI露出を実現。", gradient: "linear-gradient(135deg, #f59e0b, #ef4444)" },
          ].map((f) => (
            <div key={f.title} className="aio-card aio-feature" style={{
              padding: 28, borderRadius: 16, border: `1px solid ${C.bd}`,
              background: C.card, transition: "all 0.3s", cursor: "default",
            }}>
              <div className="aio-feature-icon" style={{
                width: 52, height: 52, borderRadius: 14,
                background: f.gradient, display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 24, marginBottom: 20, transition: "transform 0.3s",
                boxShadow: `0 4px 20px ${f.gradient.includes("#3b82f6") ? "rgba(59,130,246,0.3)" : "rgba(139,92,246,0.3)"}`,
              }}>{f.icon}</div>
              <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 10 }}>{f.title}</h3>
              <p style={{ fontSize: 13, color: C.mt, lineHeight: 1.8 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it Works ── */}
      <section style={{
        ...section, background: C.s1,
        borderTop: `1px solid ${C.bd}`, borderBottom: `1px solid ${C.bd}`,
        maxWidth: "100%", padding: "100px 24px",
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
            <span style={{
              fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}>HOW IT WORKS</span>
            <h2 style={{
              fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
              letterSpacing: "-0.03em", marginTop: 12,
            }}>
              3ステップで始められる
            </h2>
          </div>

          <div className="aio-reveal" style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 32,
          }}>
            {[
              { step: "01", title: "無料診断申し込み", desc: "フォームから会社名とURLを送信するだけ。最短翌営業日にレポートをお届けします。", icon: "📝" },
              { step: "02", title: "診断レポート確認", desc: "AI検索での現在の露出状況、競合比較、改善ポイントを詳細レポートで確認。", icon: "📋" },
              { step: "03", title: "最適化スタート", desc: "レポートを基に具体的な改善施策を実行。月次モニタリングで効果を可視化。", icon: "🚀" },
            ].map((s) => (
              <div key={s.step} style={{ position: "relative" }}>
                <div style={{
                  fontSize: 64, fontWeight: 900, color: "rgba(59,130,246,0.08)",
                  position: "absolute", top: -10, left: 0, letterSpacing: "-0.05em",
                }}>{s.step}</div>
                <div style={{ paddingTop: 48 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12,
                    background: C.acGlow, border: `1px solid rgba(59,130,246,0.2)`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 22, marginBottom: 20,
                  }}>{s.icon}</div>
                  <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>{s.title}</h3>
                  <p style={{ fontSize: 14, color: C.mt, lineHeight: 1.8 }}>{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section id="実績" style={section}>
        <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
          <span style={{
            fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}>RESULTS</span>
          <h2 style={{
            fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
            letterSpacing: "-0.03em", marginTop: 12,
          }}>
            導入企業の実績
          </h2>
        </div>

        <div className="aio-reveal" style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 20,
        }}>
          {[
            { value: 340, suffix: "%", label: "AI検索露出の平均改善率" },
            { value: 50, suffix: "+", label: "導入企業数" },
            { value: 92, suffix: "%", label: "継続利用率" },
            { value: 3, suffix: "倍", label: "問い合わせ数の平均増加" },
          ].map((s) => (
            <div key={s.label} style={{
              padding: 32, borderRadius: 16, textAlign: "center",
              border: `1px solid ${C.bd}`, background: C.card,
            }}>
              <div style={{
                fontSize: 48, fontWeight: 900, letterSpacing: "-0.04em",
                background: C.grText, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              }}>
                <Counter end={s.value} suffix={s.suffix} />
              </div>
              <div style={{ fontSize: 13, color: C.mt, marginTop: 8, fontWeight: 500 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section style={{
        ...section, background: C.s1,
        borderTop: `1px solid ${C.bd}`, borderBottom: `1px solid ${C.bd}`,
        maxWidth: "100%", padding: "100px 24px",
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
            <span style={{
              fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}>VOICE</span>
            <h2 style={{
              fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
              letterSpacing: "-0.03em", marginTop: 12,
            }}>
              お客様の声
            </h2>
          </div>

          <div className="aio-reveal" style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20,
          }}>
            {[
              {
                name: "A不動産株式会社",
                role: "代表取締役",
                text: "ChatGPTで「大阪 不動産 おすすめ」と聞くと弊社が出てくるようになりました。問い合わせが月3件から12件に増えています。",
                area: "大阪市",
              },
              {
                name: "B工務店",
                role: "営業部長",
                text: "正直、AI検索対策なんて必要ないと思っていました。診断レポートを見て衝撃を受けました。競合は既に対策済みだったんです。",
                area: "神戸市",
              },
              {
                name: "C税理士事務所",
                role: "所長",
                text: "士業こそAI検索が重要だと実感。「関西 税理士 相続」でAIに推薦されるようになり、相談件数が2倍以上に。",
                area: "京都市",
              },
            ].map((t) => (
              <div key={t.name} style={{
                padding: 28, borderRadius: 16,
                border: `1px solid ${C.bd}`, background: C.card,
              }}>
                <div style={{ fontSize: 14, color: C.mt, lineHeight: 1.8, marginBottom: 20, fontStyle: "italic" }}>
                  「{t.text}」
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 10, background: C.gr,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 16, fontWeight: 800, color: "#fff",
                  }}>{t.name[0]}</div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{t.name}</div>
                    <div style={{ fontSize: 12, color: C.mt }}>{t.role} / {t.area}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="料金" style={section}>
        <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 64 }}>
          <span style={{
            fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}>PRICING</span>
          <h2 style={{
            fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 800,
            letterSpacing: "-0.03em", marginTop: 12,
          }}>
            シンプルな料金体系
          </h2>
        </div>

        <div className="aio-reveal" style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20,
          maxWidth: 800, margin: "0 auto",
        }}>
          {[
            {
              name: "診断レポート",
              price: "0",
              unit: "円",
              desc: "まずはここから",
              features: ["AI検索露出スコア", "競合3社との比較", "改善ポイント一覧", "メールでレポート送付"],
              cta: "無料で診断する",
              popular: false,
            },
            {
              name: "最適化プラン",
              price: "49,800",
              unit: "円/月",
              desc: "本格的なAI検索対策",
              features: ["月次モニタリング", "改善施策の提案・実行", "コンテンツ最適化支援", "専任コンサルタント", "月次レポーティング", "チャットサポート"],
              cta: "まず無料診断から",
              popular: true,
            },
          ].map((p) => (
            <div key={p.name} style={{
              padding: 36, borderRadius: 20, position: "relative",
              border: `1px solid ${p.popular ? "rgba(59,130,246,0.4)" : C.bd}`,
              background: p.popular ? "rgba(59,130,246,0.05)" : C.card,
            }}>
              {p.popular && (
                <div style={{
                  position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)",
                  padding: "4px 16px", borderRadius: 99, background: C.gr,
                  fontSize: 11, fontWeight: 700, color: "#fff",
                }}>人気</div>
              )}
              <div style={{ fontSize: 14, fontWeight: 600, color: C.ac2, marginBottom: 8 }}>{p.name}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 4 }}>
                <span style={{
                  fontSize: 48, fontWeight: 900, letterSpacing: "-0.04em",
                  background: C.grText, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
                }}>{p.price}</span>
                <span style={{ fontSize: 16, color: C.mt }}>{p.unit}</span>
              </div>
              <p style={{ fontSize: 13, color: C.mt, marginBottom: 24 }}>{p.desc}</p>
              <ul style={{ listStyle: "none", padding: 0, marginBottom: 28 }}>
                {p.features.map((f) => (
                  <li key={f} style={{
                    fontSize: 14, color: C.mt, padding: "8px 0",
                    borderBottom: `1px solid ${C.bd}`,
                    display: "flex", alignItems: "center", gap: 10,
                  }}>
                    <span style={{ color: C.ok, fontSize: 14 }}>✓</span> {f}
                  </li>
                ))}
              </ul>
              <a href="#cta" className="aio-cta" style={{
                display: "block", textAlign: "center",
                padding: "14px", borderRadius: 10,
                background: p.popular ? C.gr : "transparent",
                border: p.popular ? "none" : `1px solid ${C.bd}`,
                color: p.popular ? "#fff" : C.tx,
                textDecoration: "none", fontSize: 15, fontWeight: 700,
                transition: "all 0.3s",
              }}>{p.cta}</a>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section style={{
        ...section, background: C.s1,
        borderTop: `1px solid ${C.bd}`, borderBottom: `1px solid ${C.bd}`,
        maxWidth: "100%", padding: "100px 24px",
      }}>
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
          <div className="aio-reveal" style={{ textAlign: "center", marginBottom: 48 }}>
            <span style={{
              fontSize: 12, fontWeight: 700, color: C.ac, textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}>FAQ</span>
            <h2 style={{
              fontSize: "clamp(28px, 4vw, 36px)", fontWeight: 800,
              letterSpacing: "-0.03em", marginTop: 12,
            }}>
              よくあるご質問
            </h2>
          </div>
          <div className="aio-reveal">
            <FAQ q="LLMO（AIO）とSEOの違いは何ですか？" a="SEOはGoogleの検索結果での上位表示を目指すものです。LLMO/AIOはChatGPTやGeminiなどのAIアシスタントの回答内で推薦されることを目指します。AIの回答はユーザーの信頼度が高く、コンバージョン率がSEOの数倍になるケースもあります。" />
            <FAQ q="どのくらいで効果が出ますか？" a="業種や現在の状態によりますが、多くの場合2〜3ヶ月で変化が見え始めます。AIの学習サイクルに合わせた継続的な最適化が重要です。" />
            <FAQ q="どんな業種でも対応できますか？" a="はい。不動産、士業、医療、飲食、IT、製造業など幅広い業種で実績があります。特に地域密着型のビジネスとの相性が良いです。" />
            <FAQ q="自社でやることはありますか？" a="基本的にはAIO Insightチームが施策を実行します。必要に応じてWebサイトの修正やコンテンツ追加のご協力をお願いする場合があります。" />
            <FAQ q="解約はいつでもできますか？" a="はい、最低契約期間はありません。月単位でいつでも解約可能です。" />
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section id="cta" style={{
        ...section, textAlign: "center", paddingBottom: 60, position: "relative",
      }}>
        <div style={{
          position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
          width: 500, height: 500, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(59,130,246,0.1) 0%, transparent 70%)",
          filter: "blur(80px)", pointerEvents: "none",
        }} />

        <div className="aio-reveal" style={{ position: "relative" }}>
          <div style={{
            display: "inline-flex", padding: "6px 16px", borderRadius: 99,
            border: `1px solid ${C.bd}`, background: C.card,
            fontSize: 13, color: C.ok, fontWeight: 600, marginBottom: 24,
          }}>
            <span style={{ marginRight: 8 }}>⚡</span> 最短翌営業日にレポートをお届け
          </div>

          <h2 style={{
            fontSize: "clamp(32px, 5vw, 52px)", fontWeight: 900,
            letterSpacing: "-0.04em", lineHeight: 1.2, marginBottom: 20,
          }}>
            まずは<span style={{
              background: C.grText, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>無料診断</span>から
          </h2>
          <p style={{
            fontSize: 16, color: C.mt, lineHeight: 1.8, maxWidth: 500, margin: "0 auto 40px",
          }}>
            あなたの会社がAI検索でどう見えているか、<br />
            無料の診断レポートで確認してみませんか？
          </p>

          <form onSubmit={(e) => { e.preventDefault(); alert("お申し込みありがとうございます！最短翌営業日にレポートをお届けします。"); }} style={{
            maxWidth: 480, margin: "0 auto",
            display: "flex", flexDirection: "column", gap: 12,
          }}>
            {[
              { name: "company", placeholder: "会社名", type: "text" },
              { name: "name", placeholder: "お名前", type: "text" },
              { name: "email", placeholder: "メールアドレス", type: "email" },
              { name: "url", placeholder: "会社サイトURL (https://...)", type: "url" },
            ].map((f) => (
              <input key={f.name} required {...f} style={{
                padding: "14px 18px", borderRadius: 10,
                border: `1px solid ${C.bd}`, background: "rgba(255,255,255,0.04)",
                color: C.tx, fontSize: 15, outline: "none", fontFamily: font,
                transition: "border-color 0.3s",
              }} />
            ))}
            <button type="submit" className="aio-cta" style={{
              padding: "16px", borderRadius: 12, border: "none",
              background: C.gr, color: "#fff", fontSize: 17, fontWeight: 800,
              cursor: "pointer", transition: "all 0.3s", marginTop: 8,
            }}>
              無料LLMO診断レポートを申し込む
            </button>
            <p style={{ fontSize: 12, color: C.mt, marginTop: 4 }}>
              ※ 営業目的のメール送信は一切行いません
            </p>
          </form>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{
        borderTop: `1px solid ${C.bd}`, padding: "48px 24px",
        textAlign: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 16 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: C.gr,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 12, fontWeight: 900, color: "#fff",
          }}>AI</div>
          <span style={{ fontSize: 16, fontWeight: 800 }}>
            AIO <span style={{ color: C.ac2 }}>Insight</span>
          </span>
        </div>
        <p style={{ fontSize: 13, color: C.mt, marginBottom: 8 }}>
          Fulfill株式会社 | 大阪府大阪市
        </p>
        <p style={{ fontSize: 12, color: "#475569" }}>
          &copy; 2026 Fulfill Inc. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
