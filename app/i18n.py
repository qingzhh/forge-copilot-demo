"""Lightweight i18n for the ForgeCopilot demo.

Design notes
------------
* The UI was originally written in Chinese.  Translation keys are therefore
  the original Chinese strings; ``t()`` returns the English translation when
  the active language is English, and the key itself when it is Chinese.
  A small number of branded strings use symbolic keys (``app_title`` ...).
* The active language is persisted in ``app_config.json`` next to the
  database so the choice survives restarts.  Default language: English.
* Database *values* (job statuses, option lists, ...) use English canonical
  values in this demo edition; only UI chrome is translated.
"""
from __future__ import annotations

import json

from .paths import CONFIG_PATH

_current_language = "en"
_loaded = False

# Symbolic keys: key -> (english, chinese)
SYMBOLIC: dict[str, tuple[str, str]] = {
    "app_title": (
        "ForgeCopilot - Die Setup Assistant for 18,000-t Forging Press (Demo)",
        "ForgeCopilot - 1.8万吨锻压机模具安装助手（演示版）",
    ),
    "footer_line": ("ForgeCopilot Demo - v1.30", "ForgeCopilot 演示版 - v1.30"),
    "language_menu": ("Language", "语言"),
    "cat_product_type": ("Product Type", "产品类型"),
    "cat_blade_direction": ("Blade Direction", "叶片正反向"),
    "cat_size_grade": ("Size Grade", "尺寸等级"),
    "cat_crown_angle_grade": ("Crown Angle Grade", "叶冠角等级"),
    "cat_energy_grade": ("Energy Grade", "打击力等级"),
    "cat_shift": ("Shift", "班次"),
    "cat_process_name": ("Process Name", "工序名称"),
    "status_draft": ("Draft", "草稿"),
    "status_calculated": ("Calculated", "已计算"),
    "status_feedback_pending": ("Feedback Pending", "待反馈"),
    "status_completed": ("Completed", "已完成"),
    "status_imported": ("Imported History", "历史导入"),
    "home_summary": (
        "Current data:\n- Product processes: {products} entries\n- Die versions: {dies} entries\n- Die seats: {seats} entries\n- Blocks: {blocks} entries\n- History jobs: {jobs} entries",
        "当前概况：\n- 产品工序：{products} 条\n- 模具版本：{dies} 条\n- 模座：{seats} 条\n- 拼块：{blocks} 条\n- 历史任务：{jobs} 条",
    ),
    "stats_summary": (
        "All-time success rates: Template {template}% | X shim {x}% | Y shim {y}% | Samples {total}",
        "全部时间成功率：碰模板 {template}% | 横向垫板 {x}% | 纵向垫板 {y}% | 样本数 {total}",
    ),
    "import_summary_full": (
        "Master data imported: {master} rows\nHistory imported: {history} rows\nFeedback imported: {feedback} rows\nSkipped: {skipped} rows",
        "主数据导入：{master} 行\n历史记录导入：{history} 行\n反馈记录导入：{feedback} 行\n跳过：{skipped} 行",
    ),
    "import_summary_history": (
        "History imported: {history} rows\nFeedback imported: {feedback} rows\nSkipped: {skipped} rows",
        "历史记录导入：{history} 行\n反馈记录导入：{feedback} 行\n跳过：{skipped} 行",
    ),
}

# Chinese source string -> English translation
TEXTS_EN: dict[str, str] = {
    # ---- generic buttons / words ----
    "完成": "Done",
    "提示": "Notice",
    "保存": "Save",
    "清空": "Clear",
    "保存失败": "Save Failed",
    "导入完成": "Import Complete",
    "导入失败": "Import Failed",
    "导出完成": "Export Complete",
    "导出失败": "Export Failed",
    "计算失败": "Calculation Failed",
    "刷新列表": "Refresh List",
    "加载选中": "Load Selected",
    "设为失效": "Deactivate",
    "重新启用": "Reactivate",
    "新增 / 更新": "Add / Update",
    "请先选中一条记录。": "Please select a record first.",
    "请输入失效原因：": "Enter the deactivation reason:",
    "失效原因": "Deactivation Reason",
    "状态": "Status",
    "备注": "Remark",
    "是": "Yes",
    "否": "No",
    "有效": "Active",
    "失效": "Inactive",
    "启用": "Enable",
    "停用": "Disable",
    "保存成功。": "Saved successfully.",
    "已设为失效。": "Deactivated.",
    "已重新启用。": "Reactivated.",
    "高": "High",
    "中": "Medium",
    "低": "Low",
    "良": "Good",
    "可疑": "Questionable",
    "异常": "Abnormal",
    "合格": "Pass",
    "不合格": "Fail",
    "日期": "Date",
    "分类": "Category",
    "选项值": "Option Value",
    "排序号": "Sort Order",
    # ---- tabs / home ----
    "首页": "Home",
    "主数据维护": "Master Data",
    "新建安装任务": "New Setup Job",
    "历史查询": "History",
    "录入提醒": "Entry Tips",
    "1. 主数据尽量从现有 Excel 导入，不建议手工大量重复录入。": "1. Import master data from the existing Excel workbook instead of typing it in by hand.",
    "2. 新建安装任务时，先选产品工序、模具版本、模座和拼块，再填下模实际高度和目标厚度，最后填基准面。": "2. For a new setup job: pick the product process, die version, die seat and block first, then enter the lower-die actual height and target thickness, and finally the reference planes.",
    "3. 首件反馈页的“错位值”统一按“调到 0 位置还需增减多少垫板”填写。": "3. On the first-piece feedback form, enter every offset as 'how much shim must still be added or removed to reach the 0 position'.",
    "4. 如果暂时不清楚某个可选字段，可以先留空，不会影响第一版基础使用。": "4. Optional fields may be left blank if unknown; the basic workflow is unaffected.",
    "界面全部使用中文。建议先导入现有 Excel，再进行新任务录入和首件反馈。": "Tip: import the existing Excel workbook first, then create jobs and enter first-piece feedback.",
    "初始化数据库": "Initialize Database",
    "导入当前 Excel": "Import Excel Workbook",
    "导入有效历史CSV": "Import Curated History CSV",
    "刷新全部数据": "Refresh All Data",
    "数据库已初始化。": "Database initialized.",
    "当前数据": "Current Data",
    "产品工序": "Product Process",
    "模具版本": "Die Version",
    "模座": "Die Seat",
    "拼块": "Block",
    "底板": "Base Plate",
    "补偿规则": "Compensation Rules",
    # ---- master data: product process ----
    "产品名称": "Product Name",
    "产品+工序名称": "Product + Process Name",
    "产品+工序名称自动生成，无需手工输入。": "Generated automatically from product + process; no manual entry needed.",
    "默认目标厚度": "Default Target Thickness",
    "请至少填写产品名称和工序名称。": "Enter at least a product name and a process name.",
    "产品工序已保存。": "Product process saved.",
    "基础选项": "Basic Options",
    # ---- master data: die ----
    "模具": "Die",
    "版本": "Version",
    "模具编号": "Die No.",
    "模具名称": "Die Name",
    "模具规格": "Die Spec",
    "模具状态": "Die Status",
    "使用次数区间": "Use-count Bucket",
    "总打击次数": "Total Hit Count",
    "修复后打击次数": "Hits After Repair",
    "修磨后首次使用": "First Use After Regrind",
    # ---- master data: die seat ----
    "模座编号": "Die Seat No.",
    "理论闭合高度": "Theoretical Close Height",
    "导向状态": "Guide State",
    "模座状态": "Die Seat State",
    "模座导向状态": "Die Seat Guide State",
    "碰模板位置说明": "Template Position Note",
    "横向偏差基准": "Lateral Deviation Base",
    "纵向偏差基准": "Longitudinal Deviation Base",
    "理论700碰模板": "Theoretical 700 Template",
    "基础碰模板变薄量": "Base Template Thinning",
    "快速状态修改": "Quick State Edit",
    "直接修改模座导向状态或闭合高度，无需重新新增记录。": "Update a die seat's guide state or close height directly, without creating a new record.",
    "（留空则不修改）": "(leave blank to keep unchanged)",
    "保存模座状态": "Save Die Seat State",
    "请选择模座编号。": "Please select a die seat.",
    "请至少填写一项要修改的值。": "Enter at least one value to change.",
    "理论闭合高度请填写数字。": "Theoretical close height must be a number.",
    # ---- master data: block / base plate / rules ----
    "拼块编号": "Block No.",
    "拼块尺寸": "Block Size",
    "理论厚度": "Theoretical Thickness",
    "下拼横向基准": "Lower Block X Base",
    "下拼纵向基准": "Lower Block Y Base",
    "上拼横向基准": "Upper Block X Base",
    "上拼纵向基准": "Upper Block Y Base",
    "下拼底板厚度": "Lower Block Plate Thickness",
    "上拼底板厚度": "Upper Block Plate Thickness",
    "拼块底板偏差": "Block Plate Delta",
    "拼块启用/停用": "Block Enable/Disable",
    "请选择拼块编号。": "Please select a block.",
    "底板编号": "Base Plate No.",
    "底板厚度": "Base Plate Thickness",
    "规则类型": "Rule Type",
    "规则键": "Rule Key",
    "横向补偿": "Lateral (X) Compensation",
    "纵向补偿": "Longitudinal (Y) Compensation",
    "碰模板补偿": "Template Compensation",
    "产品类型横向补偿": "Product-type X compensation",
    "上一次叶片向横向补偿": "Previous blade-direction X compensation",
}

TEXTS_EN.update({
    # ---- new job tab ----
    "任务编号": "Job No.",
    "任务时间": "Job Time",
    "操作员": "Operator",
    "任务输入": "Job Inputs",
    "主数据自动带出（只读）": "Filled from master data (read-only)",
    "本次模具打击次数": "Die Hit Count (this job)",
    "上模横向基准面": "Upper Die X Reference",
    "上模纵向基准面": "Upper Die Y Reference",
    "下模横向基准面": "Lower Die X Reference",
    "下模纵向基准面": "Lower Die Y Reference",
    "下模实际高度": "Lower Die Actual Height",
    "目标厚度": "Target Thickness",
    "底板1": "Base Plate 1",
    "底板2": "Base Plate 2",
    "底板3": "Base Plate 3",
    "底板4": "Base Plate 4",
    "底板5": "Base Plate 5",
    "底板厚度显示": "Base Plate Thickness",
    "底板厚度合": "Total Base Plate Thickness",
    "计算结果": "Calculation Result",
    "基础理论碰模板厚度": "Base Theoretical Template Thickness",
    "基础理论横向垫板": "Base Theoretical X Shim",
    "基础理论纵向垫板": "Base Theoretical Y Shim",
    "历史碰模板修正": "History Template Correction",
    "历史横向修正": "History X Correction",
    "历史纵向修正": "History Y Correction",
    "推荐碰模板厚度": "Recommended Template Thickness",
    "推荐横向垫板": "Recommended X Shim",
    "推荐纵向垫板": "Recommended Y Shim",
    "推荐碰模板": "Rec. Template",
    "推荐横向": "Rec. X Shim",
    "推荐纵向": "Rec. Y Shim",
    "相似案例数量": "Similar Cases",
    "推荐置信等级": "Recommendation Confidence",
    "高（样本充足）": "High (sufficient samples)",
    "中（样本偏少）": "Medium (few samples)",
    "低（样本不足）": "Low (insufficient samples)",
    "计算推荐值": "Calculate Recommendation",
    "推荐值计算完成。": "Recommendation calculated.",
    "说明：推荐值 = 基础理论值 + 历史修正值。\n如果相似案例数量少，优先以基础理论值为主。": "Note: recommendation = base theoretical value + history correction.\nWhen similar cases are few, trust the base theoretical value first.",
    "保存任务": "Save Job",
    "保存任务并首件反馈": "Save Job + First-piece Feedback",
    "清空任务": "Clear Job Form",
    "请选择模具版本。": "Please select a die version.",
    "尽量只填必要字段，不确定的可先留空。": "Fill in only the required fields; leave uncertain ones blank.",
    # ---- first-piece feedback ----
    "首件反馈（与新建任务同页填写）": "First-piece Feedback (same page as the new job)",
    "选择任务并录入首件反馈": "Select a Job and Enter First-piece Feedback",
    "当前任务参考值": "Reference Values for the Current Job",
    "实际碰模板厚度": "Actual Template Thickness",
    "实际碰模板": "Actual Template",
    "碰模板铝块厚度": "Template Aluminum Block Thickness",
    "实际厚度": "Actual Thickness",
    "实际叶根横向垫板": "Actual Root X Shim",
    "实际叶顶横向垫板": "Actual Tip X Shim",
    "实际纵向垫板": "Actual Y Shim",
    "叶根横向错位": "Root X Offset",
    "叶顶横向错位": "Tip X Offset",
    "纵向错位": "Y Offset",
    "首件厚度偏差": "First-piece Thickness Delta",
    "首件是否合格": "First Piece Passed?",
    "缺陷类型": "Defect Type",
    "反馈备注": "Feedback Remark",
    "测量可信度": "Measurement Reliability",
    "模具安装质量": "Die Installation Quality",
    "拼块安装质量": "Block Installation Quality",
    "样本等级": "Sample Grade",
    "保存首件反馈": "Save First-piece Feedback",
    "刷新任务列表": "Refresh Job List",
    "待反馈任务": "Jobs Awaiting Feedback",
    "提示：错位值统一填写“调到 0 位置还需增减多少垫板”。\n正值表示还需要增加，负值表示还需要减少。": "Tip: enter offsets as 'shim still to add/remove to reach the 0 position'.\nPositive = add more, negative = remove.",
    # ---- readjustment ----
    "本次返调记录（可选）": "Readjustment Record (optional)",
    "碰模板调整量": "Template Adjustment",
    "横向垫板调整量": "X Shim Adjustment",
    "纵向垫板调整量": "Y Shim Adjustment",
    "返调原因": "Readjustment Reason",
    "调整后结果": "Result After Adjustment",
    # ---- history / stats ----
    "产品工序筛选": "Filter by Product Process",
    "导出分析数据CSV": "Export Analysis CSV",
    "刷新成功率统计": "Refresh Success Stats",
    "计算成功率统计（偏差≤1 视为成功）": "Success-rate Statistics (success = |actual - recommended| <= 1)",
    "月份": "Month",
    "样本数": "Samples",
    "碰模板成功率": "Template Success Rate",
    "横向垫板成功率": "X Shim Success Rate",
    "纵向垫板成功率": "Y Shim Success Rate",
    "碰模板成功率%": "Template Success %",
    "横向垫板成功率%": "X Shim Success %",
    "纵向垫板成功率%": "Y Shim Success %",
    "暂无统计数据": "No statistics yet",
    "暂无按月份统计数据": "No monthly statistics yet",
    "未知月份": "Unknown month",
    # ---- dialogs / file pickers ----
    "选择导出 CSV 路径": "Choose the export CSV path",
    "选择要导入的 Excel 文件": "Select the Excel workbook to import",
    "选择要导入的有效历史 CSV": "Select the curated history CSV to import",
    "CSV 文件": "CSV Files",
    "Excel 文件": "Excel Files",
    # ---- services / importer messages ----
    "缺少必要主数据，请先维护产品工序、模座和拼块。": "Required master data is missing. Please maintain product processes, die seats and blocks first.",
    "当前没有可导出的数据。": "There is currently no data to export.",
    "关键数据缺失或存在明显异常": "Key data missing or clearly abnormal",
    "关键数据完整，质量等级良好": "Key data complete; good quality",
    "数据可用，但不满足 A 类条件": "Data usable but does not meet Grade A criteria",
    "手工失效": "Manually deactivated",
    # ---- message templates (named placeholders) ----
    "请填写：{label}": "Please fill in: {label}",
    "模座 {seat_no} 状态已更新。": "Die seat {seat_no} status updated.",
    "拼块 {block_no} 已{state_label}。": "Block {block_no} is now {state_label}.",
    "{n}号底板厚度": "Base Plate {n} Thickness",
    "分析数据已导出到：\n{output}": "Analysis data exported to:\n{output}",
    "任务已保存，编号 ID = {job_id}": "Job saved. ID = {job_id}",
    "任务与首件反馈已保存，编号 ID = {job_id}": "Job and first-piece feedback saved. ID = {job_id}",
})


def _load_language() -> str:
    global _loaded
    if _loaded:
        return _current_language
    _loaded = True
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if data.get("language") in ("en", "zh"):
            return data["language"]
    except Exception:
        pass
    return "en"


def get_language() -> str:
    global _current_language
    if not _loaded:
        _current_language = _load_language()
    return _current_language


def set_language(language: str) -> None:
    global _current_language, _loaded
    if language not in ("en", "zh"):
        return
    _current_language = language
    _loaded = True
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps({"language": language}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def t(text: str, **kwargs) -> str:
    """Translate a UI string into the active language.

    Keys are the original Chinese strings (or symbolic keys).  ``kwargs``
    are interpolated with ``str.format`` so callers can pass named
    placeholders, e.g. ``t("...", seat_no="A1")``.
    """
    if text in SYMBOLIC:
        en, zh = SYMBOLIC[text]
        result = en if get_language() == "en" else zh
    elif get_language() == "en":
        result = TEXTS_EN.get(text, text)
    else:
        result = text
    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return result


# Canonical job status values stored in the database (English) and their
# symbolic i18n keys, for localized display.
STATUS_KEYS = {
    "Draft": "status_draft",
    "Calculated": "status_calculated",
    "Feedback Pending": "status_feedback_pending",
    "Completed": "status_completed",
    "Imported History": "status_imported",
    # legacy codes found in older databases
    "draft": "status_draft",
    "calculated": "status_calculated",
    "feedback_pending": "status_feedback_pending",
    "closed": "status_completed",
    "archived": "status_imported",
}


def display_status(status: str) -> str:
    key = STATUS_KEYS.get(status)
    return t(key) if key else status
