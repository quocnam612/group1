"""Generate one offline page viewer from the per-page JSON documents."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from pages import DEFAULT_PAGES, page_lock, read_page, refresh_text, regions, save_json


TEMPLATE = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kinh Thi — đối chiếu OCR theo trang</title>
<style>
:root{font-family:system-ui,sans-serif;color:#182c3b;background:#f1f4f7;color-scheme:light}
*{box-sizing:border-box}body{margin:0}button,select,input{font:inherit}button,select{border:1px solid #bdcbd6;background:white;border-radius:7px;padding:8px 12px;color:inherit}
button{cursor:pointer}button:disabled{opacity:.35;cursor:default}header{padding:14px 22px;background:#fff;border-bottom:1px solid #d7e0e7}h1{font-size:21px;margin:0 0 6px}header p{margin:0;font-size:13px;color:#536779}
.controls{display:flex;align-items:center;flex-wrap:wrap;gap:9px;padding:12px 22px;background:#f8fafc;border-bottom:1px solid #d7e0e7}.controls label{font-size:13px;display:flex;align-items:center;gap:6px}#query{padding:8px 11px;border:1px solid #bdcbd6;border-radius:7px;min-width:220px;flex:1}.controls a{font-size:13px;color:#1261a0}
main{display:grid;grid-template-columns:minmax(340px,47%) 1fr;height:calc(100vh - 163px);min-height:450px}.image-panel{overflow:auto;border-right:1px solid #cdd7df;background:#dce3e9;padding:15px}.image-wrap{position:relative;background:white;box-shadow:0 2px 12px #253d531c;min-width:100%}.image-wrap>img{display:block;width:100%;height:auto}.image-wrap svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.box{fill:transparent;stroke-width:3;cursor:pointer}.box:hover,.box.active{fill:var(--color);fill-opacity:.16;stroke-width:5}.box:focus{outline:none;stroke-width:7}
.text-panel{overflow:auto;padding:18px 22px 80px}#count{font-size:13px;color:#617485;margin:0 0 14px}.card{background:white;border:1px solid #d7e0e7;border-left:4px solid var(--color);border-radius:8px;margin-bottom:14px;padding:14px 16px;scroll-margin-top:14px}.card.active{outline:2px solid #447da3;box-shadow:0 3px 12px #24516d18}.card-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.card h2{font-size:14px;margin:0}.badge{font-size:11px;padding:3px 7px;border-radius:5px;background:#edf2f6;color:#536879}.badge.checked{background:#e3f3e9;color:#216a3d}.badge.hint{background:#fff1cf;color:#885d0b}.transcript{font-family:Georgia,"Noto Serif CJK TC",serif;font-size:21px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere;margin:10px 0 4px}.empty{padding:28px;background:#fff;border-radius:8px;color:#667b8b}.card details{font-size:13px;color:#536779;margin-top:10px}.card summary{cursor:pointer}.raw{font-family:Georgia,"Noto Serif CJK TC",serif;font-size:17px;white-space:pre-wrap;padding:10px;background:#f4f7f9;border-radius:5px;color:#253e50}.crop{max-width:100%;max-height:230px;display:block;margin:12px 0 5px;border:1px solid #e2e8ee}.raw-label{font-size:12px;font-weight:600;margin:14px 0 3px}.hint-note{font-size:12px;color:#8a610d;margin:7px 0}.source-note{font-size:12px;color:#536779;margin:5px 0}
@media(max-width:800px){main{display:block;height:auto}.image-panel{height:55vh;border-right:0;border-bottom:1px solid #cdd7df}.text-panel{height:65vh}.controls{padding:10px}header{padding:12px}#query{min-width:150px}.transcript{font-size:19px}}
</style></head><body>
<header><h1>Kinh Thi · Đối chiếu OCR</h1><p>Chọn trang và tầng nội dung. Bấm vùng trên ảnh để đối chiếu; bản đã kiểm tay và OCR thô được giữ riêng.</p></header>
<div class="controls">
<button id="prev" aria-label="Trang trước">←</button><select id="pageSelect" aria-label="Trang PDF"></select><button id="next" aria-label="Trang sau">→</button>
<select id="layerSelect" aria-label="Tầng nội dung"></select><select id="engineSelect" aria-label="Bản hiển thị"></select>
<input id="query" type="search" placeholder="Tìm chữ trong trang…" aria-label="Tìm nội dung">
<label><input type="checkbox" id="showHints" checked> Hiện gợi ý cũ</label>
<label>Ảnh <input id="zoom" type="range" min="100" max="240" value="100" aria-label="Phóng to ảnh"></label>
<a id="jsonLink">JSON trang</a>
</div>
<main><section class="image-panel" aria-label="Ảnh nguồn"><div class="image-wrap" id="imageWrap"><img id="sourceImage" alt="Trang sách nguồn"><svg id="overlay" aria-label="Các vùng nội dung"></svg></div></section>
<section class="text-panel" aria-label="Văn bản OCR"><p id="count" role="status"></p><div id="cards"></div></section></main>
<script id="page-data" type="application/json">__PAGE_DATA__</script>
<script>
"use strict";
const pages=JSON.parse(document.getElementById("page-data").textContent);
const $=id=>document.getElementById(id), labels={tieu_de:"Tiêu đề",tieu_de_han:"Tiêu đề Hán",tieu_de_viet:"Tiêu đề Việt",han:"Hán gốc",phien_am:"Phiên âm",dich_sat:"Dịch nghĩa",dich_tho:"Dịch thơ",chu_thich:"Chú giải",so_trang:"Số trang",can_kiem_tra:"Cần kiểm tra"};
const colors={tieu_de:"#bb4851",han:"#8759aa",phien_am:"#197c9d",dich_sat:"#328653",dich_tho:"#b17429",chu_thich:"#8e7b28",so_trang:"#6f7b85",can_kiem_tra:"#b25325"};
const engineName=key=>({"paddleocr:chinese_cht":"PaddleOCR · Hán","paddleocr:vi":"PaddleOCR · Việt","qwen2.5-vl":"Qwen2.5-VL","got-ocr2":"GOT-OCR2"}[key]||key);
const option=(value,text)=>{const o=document.createElement("option");o.value=value;o.textContent=text;return o};
pages.forEach((p,i)=>$("pageSelect").append(option(String(i),"Trang PDF "+p.page)));
$("layerSelect").append(option("all","Tất cả nội dung"));Object.keys(colors).forEach(k=>$("layerSelect").append(option(k,labels[k])));
$("engineSelect").append(option("display","Bản đang đối chiếu"));
const engines=[...new Set(pages.flatMap(p=>p.regions.flatMap(r=>Object.keys(r.ocr))))];engines.forEach(k=>$("engineSelect").append(option(k,"OCR thô: "+engineName(k))));
let current=0,active=null;const hash=new URLSearchParams(location.hash.slice(1));const requested=Number(hash.get("page"));const start=pages.findIndex(p=>p.page===requested);if(start>=0)current=start;
const normalize=s=>s.toLowerCase().normalize("NFD").replace(/\p{M}/gu,"").replace(/đ/g,"d");
const element=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e};
function displayed(r){const engine=$("engineSelect").value;if(engine!=="display"){const raw=r.ocr[engine];return raw?{text:raw.text,kind:"ocr",label:engineName(engine)}:null}if(r.source==="source_patch")return {text:r.text,kind:"checked",label:"Đã đối chiếu ảnh"};if(r.source==="layout_hint")return {text:r.text,kind:"hint",label:"Gợi ý cũ · chưa OCR crop"};return {text:r.text,kind:"ocr",label:engineName(r.source)+" · chưa kiểm tay"}}
function focusRegion(id,scrollText){const region=pages[current].regions.find(r=>r.id===id);if(region){const pane=document.querySelector(".image-panel"),scale=$("imageWrap").clientWidth/pages[current].size[0];pane.scrollTo({top:Math.max(0,(region.bbox[1]+region.bbox[3])/2*scale-pane.clientHeight/2),left:Math.max(0,(region.bbox[0]+region.bbox[2])/2*scale-pane.clientWidth/2),behavior:"smooth"})}active=id;document.querySelectorAll(".card,.box").forEach(e=>e.classList.toggle("active",e.dataset.id===id));if(scrollText){const card=document.querySelector('.card[data-id="'+id+'"]');if(card)card.scrollIntoView({block:"nearest",behavior:"smooth"})}location.hash="page="+pages[current].page+"&region="+id}
function render(){if(!pages.length)return;const page=pages[current];$("pageSelect").value=String(current);$("prev").disabled=current===0;$("next").disabled=current===pages.length-1;$("jsonLink").href=page.json;$("sourceImage").src=page.image;$("imageWrap").style.width=$("zoom").value+"%";$("overlay").setAttribute("viewBox","0 0 "+page.size.join(" "));$("overlay").replaceChildren();$("cards").replaceChildren();
 const query=normalize($("query").value),layer=$("layerSelect").value;let visible=0;
 for(const r of page.regions){const view=displayed(r);if(!view||layer!=="all"&&r.group!==layer||!$("showHints").checked&&view.kind==="hint"||query&&!normalize(view.text).includes(query))continue;visible++;
  const color=colors[r.group]||"#777",rect=document.createElementNS("http://www.w3.org/2000/svg","rect");rect.classList.add("box");rect.dataset.id=r.id;rect.style.setProperty("--color",color);rect.setAttribute("stroke",color);rect.setAttribute("x",r.bbox[0]);rect.setAttribute("y",r.bbox[1]);rect.setAttribute("width",r.bbox[2]-r.bbox[0]);rect.setAttribute("height",r.bbox[3]-r.bbox[1]);rect.setAttribute("tabindex","0");rect.setAttribute("role","button");rect.setAttribute("aria-label",labels[r.layer]+": "+view.text);rect.addEventListener("click",()=>focusRegion(r.id,true));rect.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();focusRegion(r.id,true)}});$("overlay").append(rect);
  const card=element("article","card");card.dataset.id=r.id;card.style.setProperty("--color",color);const head=element("div","card-head");head.append(element("h2","",labels[r.layer]||r.layer),element("span","badge "+(view.kind==="checked"?"checked":view.kind==="hint"?"hint":""),view.label));card.append(head,element("div","transcript",view.text||"Chưa có văn bản nhận diện."));
  if(view.kind==="hint")card.append(element("p","hint-note","Chưa có kết quả OCR riêng trên vùng này. Nội dung đang hiển thị là gợi ý từ bước bố cục."));
  const details=element("details"),summary=element("summary","","Xem crop và so kết quả OCR");details.append(summary);const image=element("img","crop");image.src=r.crop;image.alt="Crop "+(labels[r.layer]||r.layer);image.loading="lazy";details.append(image);
  if(r.corrected)details.append(element("p","source-note","Bản hiển thị đã đối chiếu ảnh; thay đổi lưu trong "+r.patch_file+". OCR thô bên dưới được giữ nguyên."));
  for(const [key,raw] of Object.entries(r.ocr)){details.append(element("p","raw-label",engineName(key)),element("div","raw",raw.text||"(Rỗng)"));if(raw.truncated)details.append(element("p","hint-note","Chạm giới hạn token; cần kiểm tra phần bị cắt."))}if(!Object.keys(r.ocr).length)details.append(element("p","source-note","Vùng này chưa có OCR riêng."));card.append(details);card.addEventListener("click",e=>{if(!e.target.closest("details"))focusRegion(r.id,false)});$("cards").append(card);
 }
 $("count").textContent="Trang "+page.page+" · "+visible+" vùng đang xem · "+page.regions.filter(r=>r.source==="source_patch").length+" vùng đã đối chiếu ảnh";
 if(!visible)$("cards").append(element("p","empty","Không có vùng phù hợp. Thử bỏ bộ lọc hoặc chọn bản hiển thị khác."));
 if(active)document.querySelectorAll(".card,.box").forEach(e=>e.classList.toggle("active",e.dataset.id===active));
}
function go(index){if(!pages.length)return;current=Math.max(0,Math.min(pages.length-1,index));active=null;$("query").value="";document.querySelector(".text-panel").scrollTop=0;document.querySelector(".image-panel").scrollTop=0;location.hash="page="+pages[current].page;render()}
$("prev").onclick=()=>go(current-1);$("next").onclick=()=>go(current+1);$("pageSelect").onchange=()=>go(Number($("pageSelect").value));for(const id of ["layerSelect","engineSelect","showHints"])$(id).onchange=render;$("query").oninput=render;$("zoom").oninput=()=>{$("imageWrap").style.width=$("zoom").value+"%"};
document.addEventListener("keydown",e=>{if(["INPUT","SELECT","TEXTAREA"].includes(document.activeElement.tagName))return;if(e.key==="ArrowLeft")go(current-1);if(e.key==="ArrowRight")go(current+1)});
if(!pages.length){$("count").textContent="Chưa có dữ liệu trang.";$("prev").disabled=true;$("next").disabled=true}else{render();if(hash.get("region"))focusRegion(hash.get("region"),true)}
</script></body></html>'''


def build_review(directory=DEFAULT_PAGES, output=None, refresh=True):
    directory = Path(directory)
    output = Path(output) if output else directory.parent / "viewer.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    def link(path):
        return quote(os.path.relpath(Path(path).resolve(), output.parent.resolve()).replace(os.sep, "/"), safe="/")
    documents = []
    for path in sorted(directory.glob("page-*.json")):
        with page_lock(path):
            page = read_page(path)
            if refresh:
                refresh_text(page)
                save_json(path, page)
        by_id = {r["id"]: r for r in regions(page)}
        order = page["layout"]["region_order"] if page.get("layout") else []
        items = []
        for id_ in order:
            region = by_id[id_]
            group = "tieu_de" if region["layer"].startswith("tieu_de") else region["layer"]
            items.append({"id": id_, "layer": region["layer"], "group": group,
                          "bbox": region["bbox"], "text": region["text"], "source": region["text_source"],
                          "crop": link(Path(page["layout_assets"]) / region["crop"]),
                          "corrected": region["text_source"] == "source_patch",
                          "patch_file": region.get("review", {}).get("patch_file", ""),
                          "ocr": {key: {"text": record["text"], "truncated": record.get("possibly_truncated", False)}
                                  for key, record in region.get("ocr", {}).items()}})
        documents.append({"page": page["page"], "image": link(page["source"]["image"]), "json": link(path),
                          "size": page["layout"].get("size", [1000, 1500]) if page.get("layout") else [1000, 1500], "regions": items})
    payload = json.dumps(documents, ensure_ascii=False).replace("<", "\\u003c")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                     prefix="viewer-", suffix=".tmp", delete=False) as stream:
        stream.write(TEMPLATE.replace("__PAGE_DATA__", payload))
        temporary = Path(stream.name)
    temporary.replace(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(build_review(args.pages, args.output))
