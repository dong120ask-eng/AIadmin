"""Read-only local ecommerce pilot; no merchant adapters or model calls."""
import argparse
import base64
import binascii
import csv
import hashlib
import importlib.util
import io
import json
import re
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from xml.etree import ElementTree as ET

from .store import Problem, Store, identifier, now, text

SUITE = Path(__file__).resolve().parents[1] / "ecommerce-suite" / "示例与验收"

def load_tool(name):
    spec = importlib.util.spec_from_file_location("ecommerce_" + name, SUITE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

TOOLS = load_tool("ecom_tools")
QUALITY = load_tool("data_quality")
MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 5000
FIELDS = {
    "record_id": "记录ID", "sku": "SKU", "on_hand": "现存库存", "reserved": "已占库存",
    "safety": "安全库存", "sales_units": "区间销量", "lead_days": "采购交期天数",
    "unit_price": "当前售价", "price_floor": "售价底线", "purchase_price": "采购单价",
    "contract_price": "采购合同单价", "purchase_qty": "拟采购数量",
    "net_revenue": "净收入", "merchant_subsidy": "另计到账补贴", "goods_cost": "货品成本",
    "platform_fees": "平台费用", "ad_spend": "广告花费", "fulfillment_cost": "履约成本",
    "after_sales_net_loss": "售后净损失", "other_variable_cost": "其他变动成本",
}
REQUIRED = list(FIELDS)[:7]
NUMERIC = list(FIELDS)[2:]
INTEGERS = {"on_hand", "reserved", "safety", "sales_units", "lead_days", "purchase_qty"}
PROFIT = ["net_revenue", "merchant_subsidy", "goods_cost", "platform_fees", "ad_spend", "fulfillment_cost", "after_sales_net_loss", "other_variable_cost"]
PLATFORMS = ["京东", "天猫", "淘宝", "拼多多", "抖音", "小红书", "快手", "视频号", "O2O", "美团", "其他"]
KINDS = {"real": "真实业务数据（人工声明，未核实上游）", "demo": "演示数据", "test": "模拟测试"}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def xml(raw):
    if b"<!DOCTYPE" in raw.replace(b"\x00", b"").upper() or b"<!ENTITY" in raw.replace(b"\x00", b"").upper():
        raise Problem("Excel包含不支持的XML声明")
    return ET.fromstring(raw)


def table(filename, raw):
    """Bounded CSV / value-only OOXML import, never evaluates formulae."""
    if not raw or len(raw) > MAX_BYTES:
        raise Problem("文件为空或超过4MB")
    if filename.lower().endswith(".csv"):
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeError:
            try:
                content = raw.decode("gb18030")
            except UnicodeError:
                raise Problem("CSV编码无法识别，请另存为UTF-8 CSV")
        try:
            rows = list(csv.reader(io.StringIO(content), strict=True))
        except csv.Error:
            raise Problem("CSV格式损坏")
    elif filename.lower().endswith(".xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.infolist()
                if len(members) > 200 or sum(m.file_size for m in members) > 24 * 1024 * 1024:
                    raise Problem("Excel解压后过大或文件过多")
                if len({m.filename for m in members}) != len(members):
                    raise Problem("Excel包含重复ZIP成员")
                if any("vbaProject" in m.filename or "externalLinks/" in m.filename for m in members):
                    raise Problem("不接受宏或外部链接")
                workbook = xml(archive.read("xl/workbook.xml"))
                sheets = workbook.findall("s:sheets/s:sheet", NS)
                if len(sheets) != 1:
                    raise Problem("Excel须仅含一张数据表，请单独导出所需表")
                rels = xml(archive.read("xl/_rels/workbook.xml.rels"))
                rid = sheets[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                target = next((r.get("Target", "") for r in rels if r.get("Id") == rid), "")
                sheet_path = target.lstrip("/") if target.startswith("/") else "xl/" + target
                if not sheet_path.startswith("xl/worksheets/") or ".." in sheet_path:
                    raise Problem("Excel工作表引用无效")
                shared = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    shared = ["".join(n.itertext()) for n in xml(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
                sheet = xml(archive.read(sheet_path))
                rows = []
                for row in sheet.findall("s:sheetData/s:row", NS):
                    values = {}
                    for cell in row.findall("s:c", NS):
                        if cell.find("s:f", NS) is not None:
                            raise Problem("Excel包含公式，请复制并粘贴为数值后导入")
                        ref = cell.get("r", "")
                        letters = "".join(c for c in ref if c.isalpha())
                        index = 0
                        for char in letters:
                            index = index * 26 + ord(char.upper()) - 64
                        if not 1 <= index <= 40 or index in values:
                            raise Problem("Excel列位置无效或超过40列")
                        value = cell.findtext("s:v", "", NS)
                        kind = cell.get("t")
                        if kind == "s":
                            value = shared[int(value)]
                        elif kind == "inlineStr":
                            value = "".join(cell.find("s:is", NS).itertext())
                        elif kind in {"b", "e"}:
                            raise Problem("Excel包含布尔值或错误值")
                        values[index] = value
                    rows.append([values.get(i, "") for i in range(1, max(values, default=0) + 1)])
        except (KeyError, ValueError, IndexError, AttributeError, zipfile.BadZipFile, ET.ParseError, RuntimeError, OSError):
            raise Problem("Excel文件损坏或不支持，请另存为CSV")
    else:
        raise Problem("仅支持.csv和.xlsx，不接受旧版.xls")
    rows = [row for row in rows if any(str(x).strip() for x in row)]
    if not rows or len(rows) > MAX_ROWS + 1 or len(rows[0]) > 40:
        raise Problem("表格为空、超过5000行或40列")
    aliases = {v: k for k, v in FIELDS.items()}
    headers = [aliases.get(h.strip(), h.strip()) for h in rows[0]]
    if len(set(headers)) != len(headers) or any(h not in FIELDS for h in headers):
        raise Problem("表头重复或无法识别，请使用下载的中文模板")
    if set(REQUIRED) - set(headers):
        raise Problem("缺少必填列：" + "、".join(FIELDS[x] for x in REQUIRED if x not in headers))
    result = []
    for i, row in enumerate(rows[1:], 2):
        if len(row) > len(headers) or any(len(str(x)) > 500 for x in row):
            raise Problem(f"第{i}行列数或单元格长度异常")
        result.append(dict(zip(headers, [str(x).strip() for x in row] + [""] * (len(headers) - len(row)))))
    return result


def metadata(data):
    if not isinstance(data, dict):
        raise Problem("来源信息必须为对象")
    result = {k: text(data.get(k), label, 500) for k, label in {
        "store_id": "店铺/仓库名称", "source": "数据来源", "exported_at": "导出时间",
        "period_start": "统计开始时间", "period_end": "统计结束时间", "metric_definition": "数据口径"
    }.items()}
    if data.get("platform") not in PLATFORMS or data.get("kind") not in KINDS:
        raise Problem("请选择平台和数据类型")
    result.update(platform=data["platform"], kind=data["kind"], currency="CNY", tenant_id="internal")
    return result


def analyze(rows, meta, clock=None):
    clock = clock or datetime.now(timezone.utc)
    clean, errors, seen = [], [], set()
    for i, row in enumerate(rows, 2):
        item = dict(row)
        for field in NUMERIC:
            value = item.get(field, "")
            if value == "" and field not in REQUIRED:
                continue
            try:
                number = TOOLS.number(item, field, field in INTEGERS)
                if number > Decimal("1000000000000") or number.as_tuple().exponent < -6:
                    raise ValueError()
            except ValueError:
                errors.append(f"第{i}行：{FIELDS[field]}须为有限非负数" + ("且为整数" if field in INTEGERS else ""))
        if not item.get("sku") or item.get("sku") in seen:
            errors.append(f"第{i}行：SKU缺失或重复（每店每SKU仅一行）")
        seen.add(item.get("sku"))
        clean.append(item)
    snapshot = {"metadata": meta, "max_age_seconds": 7 * 86400, "rows": clean, "required_fields": REQUIRED, "numeric_fields": []}
    quality = QUALITY.inspect(snapshot, now=clock)
    quality_labels = {
        "stale_or_future_snapshot": "导出时间超过7天或位于未来",
        "invalid_export_time_or_freshness_limit": "导出时间格式无效，须带时区",
        "invalid_period": "统计时间区间无效，开始须早于结束，结束不得晚于当前时间",
        "no_rows": "没有数据行",
    }
    for error in quality["errors"]:
        if error.startswith("row_"):
            parts = error.split(":")
            row_number = int(parts[0][4:]) + 2
            if parts[1] == "missing":
                errors.append(f"第{row_number}行：缺少{FIELDS.get(parts[2], parts[2])}")
            else:
                errors.append(f"第{row_number}行：记录ID缺失或重复")
        else:
            errors.append(quality_labels.get(error, error))
    try:
        if QUALITY.parse(meta["period_end"]) > QUALITY.parse(meta["exported_at"]):
            errors.append("统计结束时间晚于导出时间")
    except ValueError:
        pass
    quality["errors"] = errors
    quality["status"] = "blocked" if errors else "passed_metadata_checks"
    output = {"quality": quality, "results": [], "alerts": [], "summary": {}, "mode": "offline_read_only", "platform_verified": False}
    if errors:
        return output
    days = Decimal(str((QUALITY.parse(meta["period_end"]) - QUALITY.parse(meta["period_start"])).total_seconds())) / Decimal(86400)
    revenue_total = Decimal(0)
    profit_total = Decimal(0)
    profit_rows = 0
    for row in clean:
        n = lambda key: TOOLS.number(row, key, key in INTEGERS)
        sku = row["sku"]
        # The upstream tool uses one physical SKU; call per-store row, never combine shared warehouses.
        available = TOOLS.calculate("inventory", {"source_label": meta["source"], "rows": [{**row, "requests": []}]})["results"][0]["available"]
        daily = n("sales_units") / days
        coverage = Decimal(available) / daily if daily else None
        required = int((daily * n("lead_days")).to_integral_value(rounding=ROUND_CEILING))
        suggested = max(0, required - available)
        risk = "无销量，覆盖天数不可估计" if coverage is None else ("断货风险" if coverage <= n("lead_days") else "库存可覆盖交期")
        item = {"sku": sku, "available": available, "daily_sales": str(daily.quantize(Decimal(".0001"))), "coverage_days": str(coverage.quantize(Decimal(".01"))) if coverage is not None else None, "suggested_purchase": suggested, "risk": risk, "profit": None, "ad_roas": None}
        def alert(kind, detail):
            output["alerts"].append({"sku": sku, "kind": kind, "detail": detail})
        if risk == "断货风险":
            alert("库存", f"可用库存{available}，预计覆盖{item['coverage_days']}天，采购交期{row['lead_days']}天；建议人工复核补货{suggested}件（未扣在途）")
        if n("reserved") + n("safety") > n("on_hand"):
            alert("库存口径", "已占与安全库存之和超过现存，请核对库存口径")
        if daily == 0:
            alert("经营", "统计区间销量为0，无法按历史销量预测断货时间")
        for left, right, kind in [("unit_price", "price_floor", "售价"), ("purchase_price", "contract_price", "采购价")]:
            if row.get(left, "") != "" and row.get(right, "") != "":
                bad = n(left) < n(right) if kind == "售价" else n(left) != n(right)
                if bad:
                    alert(kind, f"{FIELDS[left]}{row[left]}元，{FIELDS[right]}{row[right]}元，请人工核对")
            else:
                item[kind + "检查"] = "字段不足，未检查"
        if row.get("purchase_qty", "") and n("purchase_qty") < suggested:
            alert("采购量", f"拟采购{row['purchase_qty']}件低于按交期估算的{suggested}件，未扣在途、未计起订量")
        if all(row.get(f, "") != "" for f in PROFIT):
            profit = TOOLS.calculate("profit", {"source_label": meta["source"], "rows": [row]})
            item["profit"] = profit["total_contribution_profit"]
            item["ad_roas"] = profit["results"][0]["ad_roas"]
            profit_total += Decimal(item["profit"])
            revenue_total += n("net_revenue")
            profit_rows += 1
            if Decimal(item["profit"]) < 0:
                alert("经营", "区间贡献利润为负，请核对收入、广告和成本明细")
        output["results"].append(item)
    output["summary"] = {"sku_count": len(clean), "alert_count": len(output["alerts"]), "profit_rows": profit_rows, "profit_missing_rows": len(clean) - profit_rows, "covered_net_revenue": TOOLS.money(revenue_total) if profit_rows else None, "covered_contribution_profit": TOOLS.money(profit_total) if profit_rows else None}
    return output


class Operations:
    def __init__(self, store):
        self.store = store
        with store.connection() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS ecom_imports(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, body TEXT NOT NULL, raw BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS ecom_issues(id TEXT PRIMARY KEY, import_id TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ecom_issue_events(id INTEGER PRIMARY KEY, issue_id TEXT NOT NULL, at TEXT NOT NULL, body TEXT NOT NULL);""")

    def imports(self):
        with self.store.connection() as c:
            return [{k: v for k, v in json.loads(row[0]).items() if k not in {"rows", "analysis"}} for row in c.execute("SELECT body FROM ecom_imports ORDER BY rowid DESC LIMIT 100")]

    def get(self, key):
        identifier(key)
        with self.store.connection() as c:
            row = c.execute("SELECT body FROM ecom_imports WHERE id=?", (key,)).fetchone()
        if not row:
            raise Problem("导入记录不存在", 404)
        body = json.loads(row[0])
        body["analysis_at_import"] = body["created_at"]
        body["analysis"] = analyze(body["rows"], body["metadata"])
        body["evaluated_at"] = now()
        body["quality_status"] = body["analysis"]["quality"]["status"]
        body["issues"] = self.issues(key)
        return body

    def ingest(self, data):
        meta = metadata(data.get("metadata"))
        filename = text(data.get("filename"), "文件名", 250)
        encoded = data.get("content_base64")
        if not isinstance(encoded, str) or len(encoded) > 6 * 1024 * 1024:
            raise Problem("文件内容过大或格式无效")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise Problem("文件编码无效")
        rows = table(filename, raw)
        sha = hashlib.sha256(raw).hexdigest()
        fingerprint = hashlib.sha256((sha + json.dumps(meta, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
        analysis = analyze(rows, meta)
        body = {"id": uuid.uuid4().hex, "filename": filename, "source_sha256": sha, "metadata": meta, "created_at": now(), "rows": rows, "analysis": analysis, "quality_status": analysis["quality"]["status"]}
        with self.store.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT id FROM ecom_imports WHERE fingerprint=?", (fingerprint,)).fetchone()
            if old:
                key = old[0]
            else:
                key = body["id"]
                c.execute("INSERT INTO ecom_imports VALUES(?,?,?,?)", (key, fingerprint, json.dumps(body, ensure_ascii=False), raw))
                alerts = analysis["alerts"] if not analysis["quality"]["errors"] else [{"sku": "", "kind": "数据质量", "detail": "；".join(analysis["quality"]["errors"])[:2000]}]
                for alert in alerts:
                    issue = {**alert, "id": uuid.uuid4().hex, "import_id": key, "state": "待处理", "owner": "", "note": "", "version": 0, "updated_at": now()}
                    c.execute("INSERT INTO ecom_issues VALUES(?,?,?)", (issue["id"], key, json.dumps(issue, ensure_ascii=False)))
        return self.get(key)

    def issues(self, key):
        with self.store.connection() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT body FROM ecom_issues WHERE import_id=? ORDER BY rowid", (key,))]

    def update_issue(self, key, data):
        identifier(key)
        if data.get("state") not in {"待处理", "处理中", "已关闭"}:
            raise Problem("处理状态无效")
        owner = text(data.get("owner", ""), "负责人", 100, False)
        note = text(data.get("note", ""), "处理备注", 2000, False)
        if data["state"] == "已关闭" and not note:
            raise Problem("关闭异常前须填写核查结果")
        version = data.get("version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise Problem("任务版本无效")
        with self.store.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT body FROM ecom_issues WHERE id=?", (key,)).fetchone()
            if not row:
                raise Problem("异常任务不存在", 404)
            issue = json.loads(row[0])
            if version != issue["version"]:
                raise Problem("任务已被更新，请刷新后重试", 409)
            issue.update(state=data["state"], owner=owner, note=note, version=version + 1, updated_at=now())
            c.execute("UPDATE ecom_issues SET body=? WHERE id=?", (json.dumps(issue, ensure_ascii=False), key))
            c.execute("INSERT INTO ecom_issue_events(issue_id,at,body) VALUES(?,?,?)", (key, now(), json.dumps(issue, ensure_ascii=False)))
        return issue

    def demo(self):
        """Explicit operator action only; provenance cannot be changed by the request."""
        clock = datetime.now(timezone.utc)
        meta = {"kind": "demo", "platform": "京东", "store_id": "合成演示店 / 演示仓",
                "source": "软件合成演示，非真实店铺导出", "exported_at": clock.isoformat(),
                "period_start": (clock-timedelta(days=11)).isoformat(), "period_end": (clock-timedelta(days=1)).isoformat(),
                "metric_definition": "合成：10天销量、CNY金额、库存含已占；费用仅供演示"}
        rows = [dict(record_id="DEMO-1", sku="DEMO-001", on_hand="25", reserved="3", safety="2", sales_units="100", lead_days="3",
                     unit_price="9", price_floor="10", purchase_price="5", contract_price="4", purchase_qty="5",
                     **dict(zip(PROFIT, ["100", "0", "70", "5", "30", "10", "0", "0"]))),
                dict(record_id="DEMO-2", sku="DEMO-002", on_hand="200", reserved="0", safety="10", sales_units="20", lead_days="2",
                     **dict(zip(PROFIT, ["1000", "0", "500", "50", "100", "20", "10", "0"]))),
                dict(record_id="DEMO-3", sku="DEMO-003", on_hand="5", reserved="0", safety="0", sales_units="0", lead_days="2")]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return self.ingest({"metadata": meta, "filename": "DEMO-合成经营数据.csv", "content_base64": base64.b64encode(stream.getvalue().encode("utf-8-sig")).decode()})

    def export(self, key):
        body = self.get(key)
        meta = body["metadata"]
        analysis = body["analysis"]
        lines = ["# 电商离线经营分析", "", KINDS[meta["kind"]], "仅供人工复核；未连接店铺接口，未执行采购、投放、改价、库存调整或报名。", "", "## 数据来源", json_block(meta), "源文件SHA256：" + body["source_sha256"], "导入时间：" + body["created_at"], "报告导出时间：" + now(), "", "## 校验与结果", json_block(analysis), "", "## 方法与限制", LIMITATION, "", "## 异常处理记录", json_block(body["issues"])]
        stream = io.BytesIO()
        with self.store.connection() as c:
            events = [dict(r) for r in c.execute("SELECT e.* FROM ecom_issue_events e JOIN ecom_issues i ON i.id=e.issue_id WHERE i.import_id=? ORDER BY e.id", (key,))]
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("report.md", "\n\n".join(lines))
            archive.writestr("analysis.json", json.dumps(body, ensure_ascii=False, indent=2))
            archive.writestr("issue-history.json", json.dumps(events, ensure_ascii=False, indent=2))
            csv_file = io.StringIO(newline="")
            columns = ["sku", "available", "daily_sales", "coverage_days", "suggested_purchase", "risk", "profit", "ad_roas"]
            writer = csv.writer(csv_file)
            writer.writerow(["SKU", "可用库存", "日均销量", "覆盖天数", "建议人工复核补货量", "库存提示", "贡献利润", "广告ROAS"])
            for row in analysis["results"]:
                writer.writerow([safe_csv(row.get(k, "")) for k in columns])
            archive.writestr("results.csv", "\ufeff" + csv_file.getvalue())
        return stream.getvalue()


def json_block(value):
    # Fence cannot be closed by user-supplied Markdown or HTML.
    content = json.dumps(value, ensure_ascii=False, indent=2)
    fence = "`" * (max((len(x) for x in re.findall(r"`+", content)), default=2) + 1)
    return fence + "json\n" + content + "\n" + fence


def safe_csv(value):
    value = "" if value is None else str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value


LIMITATION = "可用库存=max(0,现存−已占−安全)；日均销量=区间销量÷区间天数；覆盖天数=可用÷日均；补货建议=max(0,向上取整(日均×采购交期)−可用)。未计在途、季节性、促销、最小起订量或跨店共享库存；不可直接下单。贡献利润复用v6口径，未填齐8项收入成本时不计算，不将空白视为0；贡献利润不等于净利润或现金流。价格比较仅按输入底线/合同值，未发现平台优惠叠加。数据有效期7天，来源真实性与业务口径需人工核实。每批仅同店同仓同区间CNY，不合计不同批次库存。"


def template():
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(FIELDS.values())
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="AI电商运营壳（本机离线只读）")
    parser.add_argument("serve", choices=["serve"])
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    from .server import make_server
    server = make_server(Store(args.data_dir / "workbench.db"), args.port, capabilities={}, homepage="ecommerce.html")
    print(f"AI电商运营壳：http://127.0.0.1:{server.server_port}（Ctrl+C停止，仅本机）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
