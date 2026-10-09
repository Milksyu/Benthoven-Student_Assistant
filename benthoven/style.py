"""Notion-style theme for the dashboard (plain CSS, no external fonts or assets: stays offline-friendly)."""

GREEN = "#3d7a57"

CSS = """
/* ---- force a light, Notion-like look and a green accent (works in light and dark OS modes) ---- */
.gradio-container{
  --font: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --body-background-fill:#f7f7f5; --background-fill-primary:#fff; --background-fill-secondary:#fbfbfa;
  --block-background-fill:#fff; --body-text-color:#37352f; --body-text-color-subdued:#787774;
  --block-title-text-color:#787774; --block-label-text-color:#787774;
  --border-color-primary:#e9e9e7; --block-border-color:#e9e9e7; --input-border-color:#e0e0dd;
  --input-background-fill:#fff; --table-even-background-fill:#fff; --table-odd-background-fill:#fbfbfa;
  --color-accent:#3d7a57; --border-color-accent:#3d7a57; --link-text-color:#3d7a57;
  --button-primary-background-fill:#3d7a57; --button-primary-background-fill-hover:#2f6648;
  --button-primary-border-color:#3d7a57; --button-primary-text-color:#fff;
  --button-secondary-background-fill:#fff; --button-secondary-background-fill-hover:#f1f1ef;
  --button-secondary-border-color:#e0e0dd; --button-secondary-text-color:#37352f;
  --checkbox-background-color-selected:#3d7a57; --checkbox-border-color-selected:#3d7a57;
  --slider-color:#3d7a57; --block-radius:6px; --button-large-radius:6px; --input-radius:6px;
  --shadow-drop:none; --block-shadow:none;
  color-scheme: light; max-width:1280px !important; font-family:var(--font); color:#37352f;
}
body, .gradio-container{background:#f7f7f5 !important}
footer{opacity:.5}

/* ---- the "page" ---- */
.bv-page{background:#fff !important;border:1px solid #ececea !important;border-radius:8px !important;
  box-shadow:0 1px 10px rgba(15,15,15,.07) !important;padding:0 56px 40px !important;overflow:hidden;gap:14px !important}
.bv-cover{position:relative;height:200px;margin:0 -56px;
  background:
    repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 1px,transparent 1px 3px),
    repeating-linear-gradient(90deg,rgba(255,255,255,.02) 0 1px,transparent 1px 3px),
    linear-gradient(135deg,#2b2b29,#1f1f1e)}
.bv-seal{position:absolute;right:60px;top:56px;width:34px;height:34px;border-radius:50%;
  border:3px solid rgba(214,69,65,.85);box-shadow:inset 0 0 0 4px rgba(214,69,65,.25)}
.bv-cover::before{content:"";position:absolute;right:120px;top:0;width:96px;height:16px;border-radius:0 0 8px 8px;
  background:rgba(231,111,81,.9)}
.bv-icon{width:40px;height:40px;margin:-30px 0 0;position:relative;display:grid;grid-template-columns:1fr 1fr;gap:3px}
.bv-icon i{background:#3d7a57;border-radius:2px}
.bv-title{font-size:32px;font-weight:700;letter-spacing:-.3px;margin-top:14px;line-height:1.2}
.bv-sub{font-size:13px;color:#787774;margin-top:4px}
.bv-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.bv-chip{background:#f1f1ef;color:#5f5e5b;padding:2px 9px;border-radius:4px;font-size:12px;white-space:nowrap}
.bv-chip b{color:inherit}
.bv-chip.good{background:#dbeddb;color:#1c3829}.bv-chip.warn{background:#fdecc8;color:#402c1b}
.bv-chip.bad{background:#ffe2dd;color:#5d1715}
.bv-hr{border:0;border-top:1px solid #e9e9e7;margin:16px 0 4px}

/* ---- cards (chart + table) with the green dot ---- */
.bv-chartcol,.bv-tablecard{position:relative;border:1px solid #e9e9e7 !important;border-radius:6px !important;
  background:#fff !important;padding:10px 12px !important}
.bv-chartcol::before,.bv-tablecard::before{content:"";position:absolute;left:12px;top:14px;width:12px;height:12px;
  border-radius:50%;background:#3d7a57;z-index:2}
.bv-chart-head{margin:0 0 0 28px;padding:4px 0 8px;font-size:12px;color:#5f5e5b;border-bottom:1px solid #ededeb}
.bv-chart-body{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:310px;gap:16px}
.bv-donut{position:relative;width:120px;height:120px}
.bv-donut-svg{width:100%;height:100%;display:block}
.bv-donut-num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.bv-donut-num b{font-size:30px;font-weight:600;line-height:1}.bv-donut-num span{font-size:10px;color:#787774;margin-top:2px}
.bv-legend-list{list-style:none;margin:0;padding:0;font-size:10.5px;color:#787774;display:flex;flex-direction:column;gap:3px}
.bv-legend-list i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}
.bv-chart-foot{font-size:11px;color:#787774;text-align:center;line-height:1.6}.bv-chart-foot b{color:#37352f}
.bv-chart-foot .bad{color:#c4554d}

/* tabs inside the table card */
.bv-tablecard [role="tablist"]{margin-left:22px;border-bottom:1px solid #ededeb !important;gap:2px}
.bv-tablecard button[role="tab"]{background:transparent !important;border:0 !important;border-bottom:2px solid transparent !important;
  border-radius:0 !important;color:#787774 !important;font-size:12px !important;padding:4px 8px 8px !important;box-shadow:none !important}
.bv-tablecard button[role="tab"][aria-selected="true"],.bv-tablecard button[role="tab"].selected{
  color:#37352f !important;border-bottom-color:#37352f !important}
.bv-tablecard .tabitem,.bv-tablecard [role="tabpanel"]{padding:0 !important;border:0 !important;background:transparent !important}

/* the notion-like table */
.bv-tbl-wrap{overflow-x:auto;min-height:220px}
.bv-tbl{width:100%;border-collapse:collapse;font-size:12.5px;table-layout:auto}
.bv-tbl th,.bv-tbl td{border:0 !important;border-bottom:1px solid #ededeb !important;text-align:left;padding:7px 10px;white-space:nowrap}
.bv-tbl th{font-weight:400;font-size:12px;color:#787774;background:transparent}
.bv-tbl td.name{color:#3d7a57;font-weight:500;text-decoration:underline;text-decoration-color:rgba(61,122,87,.35);text-underline-offset:2px}
.bv-tbl td.due{color:#3d7a57}.bv-tbl td.due.late{color:#c4554d}
.bv-tbl .bv-empty{white-space:normal;color:#787774;padding:18px 10px}
.bv-pill,.bv-status{display:inline-block;max-width:135px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle;
  padding:1px 8px;border-radius:4px;font-size:12px;line-height:20px;background:#e3e2e0;color:#32302c}
.bv-pill.red{background:#ffe2dd;color:#5d1715}.bv-pill.blue{background:#d3e5ef;color:#183347}
.bv-pill.yellow{background:#fdecc8;color:#402c1b}.bv-pill.green{background:#dbeddb;color:#1c3829}
.bv-pill.purple{background:#e8deee;color:#412454}.bv-pill.orange{background:#fadec9;color:#49290e}
.bv-pill.pink{background:#f5e0e9;color:#4c2337}.bv-pill.brown{background:#eee0da;color:#32302c}
.bv-status{border-radius:999px;padding:1px 9px 1px 7px}.bv-status i{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:6px;vertical-align:middle;background:#9b9a97}
.bv-status.progress{background:#d3e5ef;color:#183347}.bv-status.progress i{background:#2f80c9}
.bv-status.done{background:#dbeddb;color:#1c3829}.bv-status.done i{background:#4d8f6a}
.bv-status.archived{background:#eee0da;color:#32302c}.bv-status.archived i{background:#977d6c}
.bv-tbl td.prog{min-width:130px;color:#787774;font-size:11.5px}
.bv-tbl td.prog .bv-bar{display:inline-block;vertical-align:middle;width:56px;margin-right:8px}
.bv-bar{height:6px;border-radius:99px;background:#ededeb;overflow:hidden}.bv-bar div{height:100%;background:#5fbf8f}

/* ---- tab bar for the workspace ---- */
.bv-tabs{gap:2px !important;border-bottom:1px solid #ededeb;align-items:center;flex-wrap:wrap !important}
.bv-tabs button{background:transparent !important;border:0 !important;border-bottom:2px solid transparent !important;
  border-radius:0 !important;box-shadow:none !important;color:#787774 !important;font-size:13px !important;
  min-width:0 !important;padding:6px 10px !important;flex:0 0 auto !important}
.bv-tabs button:hover{background:#f1f1ef !important;color:#37352f !important}
.bv-tabs button.primary{color:#37352f !important;border-bottom-color:#37352f !important;font-weight:600}
.bv-tabs button.bv-quick{border:1px solid #e0e0dd !important;border-radius:6px !important;margin-bottom:3px}
.bv-tabs button.bv-quick:first-of-type{margin-left:auto}

/* ---- workspace + side cards ---- */
.bv-main{border:1px solid #e9e9e7 !important;border-radius:6px !important;padding:16px !important;min-height:560px;background:#fff !important}
.bv-card{border:1px solid #e9e9e7;border-radius:6px;padding:12px 14px;background:#fff;color:#37352f}
.bv-card-title{font-weight:600;margin-bottom:8px;font-size:12px;color:#787774}
.bv-cal{width:100%;border-collapse:collapse;text-align:center;table-layout:fixed}
.bv-cal,.bv-cal th,.bv-cal td{border:none !important}
.bv-cal th{font-size:11px;color:#787774;font-weight:400;padding:3px 0}
.bv-cal td{height:38px;font-size:12.5px;vertical-align:top;padding-top:3px;border-radius:6px}
.bv-cal td.other{opacity:.35}.bv-cal td.today span{background:#3d7a57;color:#fff;border-radius:99px;padding:1px 6px}
.bv-cal td div{display:flex;justify-content:center;gap:3px;margin-top:2px;min-height:7px}
.bv-cal i,.bv-legend i{display:inline-block;width:7px;height:7px;border-radius:99px}
i.due{background:#e5484d}i.study{background:#2f9be9}.bv-legend{font-size:11.5px;color:#787774;margin-top:6px}
.bv-next{padding:10px;border-radius:6px;background:#f1f6f3;margin-bottom:8px}
.bv-next-time{font-size:12px;color:#787774}.bv-next-task{font-weight:600;font-size:15px;margin:2px 0}
.bv-next-task small{font-weight:400;color:#787774}.bv-next-goal{font-size:12.5px;color:#5f5e5b}
.bv-mini{font-size:12.5px;padding:4px 0}.bv-sep{margin:10px 0 4px;font-size:11px;color:#787774}
.bv-dot{display:inline-block;width:8px;height:8px;border-radius:99px;background:#5fbf8f;margin-right:6px}
.bv-dot.warn{background:#f5a524}.bv-dot.bad{background:#e5484d}.bv-muted{color:#787774}.bv-empty{font-size:13px;color:#787774;padding:6px 0}
.bv-calnav{flex-wrap:nowrap !important;gap:6px}.bv-calnav button{min-width:0 !important}

@media (max-width:760px){
  .bv-page{padding:0 16px 28px !important}.bv-cover{margin:0 -16px;height:140px}.bv-title{font-size:26px}
}
"""
