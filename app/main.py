from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, TOP, VERTICAL, Canvas, Menu, filedialog, messagebox, simpledialog, StringVar, Tk
from tkinter import ttk

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import ensure_database
from app.excel_importer import import_analysis_csv, import_workbook
from app.i18n import get_language, set_language, t
from app.paths import DB_PATH, ROOT_DIR
from app.services import CalcResult, ForgeRepository


# Canonical option-category names stored in the database (English).
CATEGORIES = [
    "Product Type",
    "Blade Direction",
    "Size Grade",
    "Crown Angle Grade",
    "Energy Grade",
    "Shift",
    "Process Name",
]
CATEGORY_LABEL_KEYS = {
    "Product Type": "cat_product_type",
    "Blade Direction": "cat_blade_direction",
    "Size Grade": "cat_size_grade",
    "Crown Angle Grade": "cat_crown_angle_grade",
    "Energy Grade": "cat_energy_grade",
    "Shift": "cat_shift",
    "Process Name": "cat_process_name",
}


def cat_label(canonical: str) -> str:
    """Localized display label for a canonical option category."""
    return t(CATEGORY_LABEL_KEYS.get(canonical, canonical))


QUALITY_CHOICES: dict[str, str] = {}
STATE_CHOICES: dict[str, str] = {}
YES_NO_CHOICES: dict[str, str] = {}
PASS_CHOICES: dict[str, str] = {}
RULE_TYPE_CHOICES: dict[str, str] = {}
CODE_TO_LABEL: dict[str, str] = {}


def _refresh_choice_labels() -> None:
    """(Re)build the label -> code choice maps for the active language."""
    QUALITY_CHOICES.clear()
    QUALITY_CHOICES.update({t("高"): "high", t("中"): "medium", t("低"): "low"})
    STATE_CHOICES.clear()
    STATE_CHOICES.update({t("良"): "good", t("可疑"): "suspect", t("异常"): "abnormal"})
    YES_NO_CHOICES.clear()
    YES_NO_CHOICES.update({t("否"): "0", t("是"): "1"})
    PASS_CHOICES.clear()
    PASS_CHOICES.update({t("合格"): "1", t("不合格"): "0"})
    RULE_TYPE_CHOICES.clear()
    RULE_TYPE_CHOICES.update(
        {
            t("产品类型横向补偿"): "product_type_x_comp",
            t("上一次叶片向横向补偿"): "prev_blade_dir_x_comp",
        }
    )
    CODE_TO_LABEL.clear()
    for _mapping in (QUALITY_CHOICES, STATE_CHOICES, RULE_TYPE_CHOICES):
        for _label, _value in _mapping.items():
            CODE_TO_LABEL[_value] = _label
    CODE_TO_LABEL["0"] = t("否")
    CODE_TO_LABEL["1"] = t("是")


_refresh_choice_labels()


class SimpleCrudFrame(ttk.Frame):
    def __init__(self, master, title, fields, load_fn, save_fn, on_saved=None, record_table=None, record_key=None):
        super().__init__(master, padding=10)
        self.fields = fields
        self.load_fn = load_fn
        self.save_fn = save_fn
        self.on_saved = on_saved
        self.record_table = record_table
        self.record_key = record_key
        self.vars: dict[str, StringVar] = {}
        self.tree: ttk.Treeview | None = None
        self._build(title)
        self.refresh()

    def _build(self, title: str) -> None:
        ttk.Label(self, text=title, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(self, text=t("尽量只填必要字段，不确定的可先留空。"), foreground="#666666").pack(anchor="w", pady=(0, 8))

        form = ttk.LabelFrame(self, text=t("新增 / 更新"))
        form.pack(fill="x", pady=(0, 10))

        for index, field in enumerate(self.fields):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(form, text=field["label"]).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            var = StringVar()
            self.vars[field["name"]] = var
            if field.get("choices"):
                widget = ttk.Combobox(
                    form,
                    textvariable=var,
                    values=list(field["choices"].keys()),
                    width=28,
                    state="readonly",
                )
                widget.set(next(iter(field["choices"].keys())))
            else:
                widget = ttk.Entry(form, textvariable=var, width=32)
            widget.grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)

        btn_row = (len(self.fields) + 1) // 2 + 1
        ttk.Button(form, text=t("保存"), command=self.save).grid(row=btn_row, column=0, padx=6, pady=8)
        ttk.Button(form, text=t("清空"), command=self.clear).grid(row=btn_row, column=1, padx=6, pady=8, sticky="w")
        ttk.Button(form, text=t("刷新列表"), command=self.refresh).grid(row=btn_row, column=2, padx=6, pady=8)

        list_frame = ttk.LabelFrame(self, text=t("当前数据"))
        list_frame.pack(fill="both", expand=True)
        columns = [field["name"] for field in self.fields] + ["_status", "_invalid_reason"]
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        for field in self.fields:
            self.tree.heading(field["name"], text=field["label"])
            self.tree.column(field["name"], width=130, anchor="center")
        self.tree.heading("_status", text=t("状态"))
        self.tree.column("_status", width=80, anchor="center")
        self.tree.heading("_invalid_reason", text=t("失效原因"))
        self.tree.column("_invalid_reason", width=180, anchor="center")
        self.tree.tag_configure("inactive", foreground="#999999", font=("Microsoft YaHei UI", 10, "overstrike"))
        vsb = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill="both", expand=True)
        vsb.pack(side=RIGHT, fill="y")

        action = ttk.Frame(self)
        action.pack(fill="x", pady=(6, 0))
        ttk.Button(action, text=t("加载选中"), command=self.load_selected).pack(side=LEFT, padx=(0, 8))
        if self.record_table and self.record_key:
            ttk.Button(action, text=t("设为失效"), command=self.invalidate_selected).pack(side=LEFT, padx=8)
            ttk.Button(action, text=t("重新启用"), command=self.activate_selected).pack(side=LEFT, padx=8)

    def _normalize_row(self, row) -> list[str]:
        values = []
        for field in self.fields:
            value = row[field["name"]] if field["name"] in row.keys() else ""
            if field.get("choices"):
                value = CODE_TO_LABEL.get(str(value), value)
            values.append("" if value is None else str(value))
        is_active = True
        if "is_active" in row.keys():
            is_active = str(row["is_active"]) == "1"
        status = t("有效") if is_active else t("失效")
        invalid_reason = row["invalid_reason"] if "invalid_reason" in row.keys() else ""
        values.extend([status, "" if invalid_reason is None else str(invalid_reason)])
        return values

    def refresh(self) -> None:
        if not self.tree:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.load_fn():
            tags = ("inactive",) if ("is_active" in row.keys() and str(row["is_active"]) == "0") else ()
            item_id = self.tree.insert("", END, values=self._normalize_row(row), tags=tags)
            if self.record_key and self.record_key in row.keys():
                self.tree.set(item_id, self.record_key, row[self.record_key])

    def clear(self) -> None:
        for field in self.fields:
            if field.get("choices"):
                self.vars[field["name"]].set(next(iter(field["choices"].keys())))
            else:
                self.vars[field["name"]].set("")

    def save(self) -> None:
        payload = {}
        for field in self.fields:
            raw_value = self.vars[field["name"]].get().strip()
            if field.get("required") and not raw_value:
                messagebox.showwarning(t("提示"), t("请填写：{label}", label=field["label"]))
                return
            payload[field["name"]] = field["choices"].get(raw_value, raw_value) if field.get("choices") else raw_value
        try:
            self.save_fn(payload)
        except Exception as exc:
            messagebox.showerror(t("保存失败"), str(exc))
            return
        self.refresh()
        self.clear()
        if self.on_saved:
            self.on_saved()
        messagebox.showinfo(t("完成"), t("保存成功。"))

    def load_selected(self) -> None:
        if not self.tree:
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(t("提示"), t("请先选中一条记录。"))
            return
        values = self.tree.item(selected[0], "values")
        for idx, field in enumerate(self.fields):
            self.vars[field["name"]].set(values[idx])

    def _get_selected_key(self):
        if not self.tree or not self.record_key:
            return None
        selected = self.tree.selection()
        if not selected:
            return None
        values = self.tree.item(selected[0], "values")
        columns = list(self.tree["columns"])
        if isinstance(self.record_key, (tuple, list)):
            result = []
            for key in self.record_key:
                if key not in columns:
                    return None
                idx = columns.index(key)
                result.append(values[idx])
            return result
        if self.record_key not in columns:
            return None
        idx = columns.index(self.record_key)
        return values[idx]

    def invalidate_selected(self) -> None:
        if not self.record_table or not self.record_key or not self.on_saved:
            return
        key = self._get_selected_key()
        if not key:
            messagebox.showwarning(t("提示"), t("请先选中一条记录。"))
            return
        reason = simpledialog.askstring(t("失效原因"), t("请输入失效原因："), parent=self)
        if reason is None:
            return
        app = self.winfo_toplevel().app
        if isinstance(self.record_key, (tuple, list)):
            app.repo.invalidate_master_record_multi(self.record_table, list(self.record_key), list(key), reason)
        else:
            app.repo.invalidate_master_record(self.record_table, self.record_key, key, reason)
        self.refresh()
        self.on_saved()
        messagebox.showinfo(t("完成"), t("已设为失效。"))

    def activate_selected(self) -> None:
        if not self.record_table or not self.record_key or not self.on_saved:
            return
        key = self._get_selected_key()
        if not key:
            messagebox.showwarning(t("提示"), t("请先选中一条记录。"))
            return
        app = self.winfo_toplevel().app
        if isinstance(self.record_key, (tuple, list)):
            app.repo.activate_master_record_multi(self.record_table, list(self.record_key), list(key))
        else:
            app.repo.activate_master_record(self.record_table, self.record_key, key)
        self.refresh()
        self.on_saved()
        messagebox.showinfo(t("完成"), t("已重新启用。"))


class ProductProcessFrame(ttk.Frame):
    def __init__(self, master, repo: ForgeRepository, on_saved):
        super().__init__(master, padding=10)
        self.repo = repo
        self.on_saved = on_saved
        self.vars = {name: StringVar() for name in [
            "product_name", "process_name", "product_type", "blade_direction",
            "blade_size_grade", "crown_rotation_angle_grade", "energy_grade",
            "target_thickness_default"
        ]}
        self.tree: ttk.Treeview | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Label(self, text=t("产品工序"), font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(self, text=t("产品+工序名称自动生成，无需手工输入。"), foreground="#666666").pack(anchor="w", pady=(0, 8))
        form = ttk.LabelFrame(self, text=t("新增 / 更新"))
        form.pack(fill="x", pady=(0, 10))

        option_values = {
            category: [row["option_value"] for row in self.repo.list_options(category)]
            for category in ["Process Name", "Product Type", "Blade Direction", "Size Grade", "Crown Angle Grade", "Energy Grade"]
        }
        fields = [
            (t("产品名称"), "product_name", None),
            ("Process Name", "process_name", {name: name for name in option_values.get("Process Name", [])}),
            ("Product Type", "product_type", {name: name for name in option_values.get("Product Type", [])}),
            ("Blade Direction", "blade_direction", {name: name for name in option_values.get("Blade Direction", [])}),
            ("Size Grade", "blade_size_grade", {name: name for name in option_values.get("Size Grade", [])}),
            ("Crown Angle Grade", "crown_rotation_angle_grade", {name: name for name in option_values.get("Crown Angle Grade", [])}),
            ("Energy Grade", "energy_grade", {name: name for name in option_values.get("Energy Grade", [])}),
            (t("默认目标厚度"), "target_thickness_default", None),
        ]
        for idx, (label, key, choices) in enumerate(fields):
            row = idx // 2
            col = (idx % 2) * 2
            label_text = cat_label(label) if label in CATEGORY_LABEL_KEYS else t(label)
            ttk.Label(form, text=label_text).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            if choices:
                widget = ttk.Combobox(form, textvariable=self.vars[key], values=list(choices.keys()), state="readonly", width=28)
            else:
                widget = ttk.Entry(form, textvariable=self.vars[key], width=30)
            widget.grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)

        ttk.Button(form, text=t("保存"), command=self.save).grid(row=5, column=0, padx=6, pady=8)
        ttk.Button(form, text=t("清空"), command=self.clear).grid(row=5, column=1, padx=6, pady=8, sticky="w")
        ttk.Button(form, text=t("刷新列表"), command=self.refresh).grid(row=5, column=2, padx=6, pady=8)

        self.tree = ttk.Treeview(
            self,
            columns=("product_name", "process_name", "product_process_name", "product_type", "blade_direction", "blade_size_grade", "energy_grade", "is_active", "invalid_reason"),
            show="headings",
            height=12,
        )
        labels = [t("产品名称"), "Process Name", t("产品+工序名称"), "Product Type", "Blade Direction", "Size Grade", "Energy Grade", t("状态"), t("失效原因")]
        for col, label in zip(self.tree["columns"], labels):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=130, anchor="center")
        self.tree.tag_configure("inactive", foreground="#999999", font=("Microsoft YaHei UI", 10, "overstrike"))
        self.tree.pack(fill="both", expand=True)

        action = ttk.Frame(self)
        action.pack(fill="x", pady=(6, 0))
        ttk.Button(action, text=t("加载选中"), command=self.load_selected).pack(side=LEFT, padx=(0, 8))
        ttk.Button(action, text=t("设为失效"), command=self.invalidate_selected).pack(side=LEFT, padx=8)
        ttk.Button(action, text=t("重新启用"), command=self.activate_selected).pack(side=LEFT, padx=8)

    def clear(self) -> None:
        for var in self.vars.values():
            var.set("")

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.repo.list_product_processes():
            vals = (
                row["product_name"],
                row["process_name"],
                row["product_process_name"],
                row["product_type"] or "",
                row["blade_direction"] or "",
                row["blade_size_grade"] or "",
                row["energy_grade"] or "",
                t("有效") if str(row["is_active"]) == "1" else t("失效"),
                row["invalid_reason"] or "",
            )
            tags = ("inactive",) if str(row["is_active"]) == "0" else ()
            self.tree.insert("", END, values=vals, tags=tags)

    def save(self) -> None:
        if not self.vars["product_name"].get().strip() or not self.vars["process_name"].get().strip():
            messagebox.showwarning(t("提示"), t("请至少填写产品名称和工序名称。"))
            return
        try:
            self.repo.add_product_process({key: var.get().strip() for key, var in self.vars.items()})
        except Exception as exc:
            messagebox.showerror(t("保存失败"), str(exc))
            return
        self.refresh()
        self.clear()
        self.on_saved()
        messagebox.showinfo(t("完成"), t("产品工序已保存。"))

    def load_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        mapping = ["product_name", "process_name", None, "product_type", "blade_direction", "blade_size_grade", "energy_grade"]
        for idx, key in enumerate(mapping):
            if key:
                self.vars[key].set(values[idx])

    def invalidate_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        ppn = values[2]
        reason = simpledialog.askstring(t("失效原因"), t("请输入失效原因："), parent=self)
        if reason is None:
            return
        self.repo.invalidate_master_record("master_product_process", "product_process_name", ppn, reason)
        self.refresh()
        self.on_saved()

    def activate_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        ppn = values[2]
        self.repo.activate_master_record("master_product_process", "product_process_name", ppn)
        self.refresh()
        self.on_saved()


class OptionCrudFrame(SimpleCrudFrame):
    pass


class ScrollableTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = Canvas(self, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.body = ttk.Frame(self.canvas)
        self.body.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.window_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.v_scroll.pack(side=RIGHT, fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if self.winfo_ismapped():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class ForgeApp:
    def __init__(self) -> None:
        ensure_database()
        self.repo = ForgeRepository()
        self.root = Tk()
        self.root.title(t("app_title"))
        self.root.geometry("1380x860")
        self.root.minsize(1200, 760)

        self.product_map: dict[str, dict] = {}
        self.die_map: dict[str, dict] = {}
        self.seat_map: dict[str, dict] = {}
        self.block_map: dict[str, dict] = {}
        self.plate_options: list[str] = []
        self.job_map: dict[str, dict] = {}
        self.option_values: dict[str, list[str]] = {}
        self.last_calc: CalcResult | None = None

        self.root.app = self
        self._notebook: ttk.Notebook | None = None
        self._footer: ttk.Frame | None = None
        self._build_style()
        self._build_language_menu()
        self._build_ui()
        self.refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure("TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10))
        style.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Footer.TLabel", font=("Microsoft YaHei UI", 8), foreground="#666666")

    def _build_language_menu(self) -> None:
        menubar = Menu(self.root)
        lang_menu = Menu(menubar, tearoff=0)
        lang_menu.add_command(label="English", command=lambda: self._switch_language("en"))
        lang_menu.add_command(label="中文", command=lambda: self._switch_language("zh"))
        menubar.add_cascade(label=t("language_menu"), menu=lang_menu)
        self.root.config(menu=menubar)

    def _switch_language(self, language: str) -> None:
        if language == get_language():
            return
        set_language(language)
        _refresh_choice_labels()
        self.root.title(t("app_title"))
        self._build_language_menu()
        if self._notebook is not None:
            self._notebook.destroy()
        if self._footer is not None:
            self._footer.destroy()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        self._notebook = notebook

        home_tab_outer = ScrollableTab(notebook)
        master_tab_outer = ScrollableTab(notebook)
        job_tab_outer = ScrollableTab(notebook)
        history_tab_outer = ScrollableTab(notebook)
        self._job_tab_outer = job_tab_outer

        self.home_tab = home_tab_outer.body
        self.master_tab = master_tab_outer.body
        self.job_tab = job_tab_outer.body
        self.history_tab = history_tab_outer.body

        notebook.add(home_tab_outer, text=t("首页"))
        notebook.add(master_tab_outer, text=t("主数据维护"))
        notebook.add(job_tab_outer, text=t("新建安装任务"))
        notebook.add(history_tab_outer, text=t("历史查询"))

        self._build_home_tab()
        self._build_master_tab()
        self._build_job_tab()
        self._build_history_tab()
        notebook.select(self._job_tab_outer)

        footer = ttk.Frame(self.root, padding=(8, 2, 10, 6))
        footer.pack(fill="x", side="bottom")
        self._footer = footer
        ttk.Label(
            footer,
            text=t("footer_line"),
            style="Footer.TLabel",
            anchor="e",
            justify="right",
        ).pack(side=RIGHT)

    def _build_home_tab(self) -> None:
        ttk.Label(self.home_tab, text=t("app_title"), font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            self.home_tab,
            text=t("界面全部使用中文。建议先导入现有 Excel，再进行新任务录入和首件反馈。"),
            foreground="#666666",
        ).pack(anchor="w", pady=(4, 12))

        btn_frame = ttk.Frame(self.home_tab)
        btn_frame.pack(anchor="w", pady=(0, 12))
        ttk.Button(btn_frame, text=t("初始化数据库"), command=self.handle_init_db).pack(side=LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text=t("导入当前 Excel"), command=self.handle_import_excel).pack(side=LEFT, padx=8)
        ttk.Button(btn_frame, text=t("导入有效历史CSV"), command=self.handle_import_history_csv).pack(side=LEFT, padx=8)
        ttk.Button(btn_frame, text=t("刷新全部数据"), command=self.refresh_all).pack(side=LEFT, padx=8)

        self.summary_text = StringVar()
        ttk.Label(self.home_tab, textvariable=self.summary_text, justify="left").pack(anchor="w", pady=(8, 10))

        tip_frame = ttk.LabelFrame(self.home_tab, text=t("录入提醒"))
        tip_frame.pack(fill="x")
        tips = [
            t("1. 主数据尽量从现有 Excel 导入，不建议手工大量重复录入。"),
            t("2. 新建安装任务时，先选产品工序、模具版本、模座和拼块，再填下模实际高度和目标厚度，最后填基准面。"),
            t("3. 首件反馈页的“错位值”统一按“调到 0 位置还需增减多少垫板”填写。"),
            t("4. 如果暂时不清楚某个可选字段，可以先留空，不会影响第一版基础使用。"),
        ]
        for tip in tips:
            ttk.Label(tip_frame, text=tip).pack(anchor="w", padx=8, pady=2)

    def _build_master_tab(self) -> None:
        notebook = ttk.Notebook(self.master_tab)
        notebook.pack(fill="both", expand=True)
        product_frame = ProductProcessFrame(notebook, self.repo, self.refresh_all)
        notebook.add(product_frame, text=t("产品工序"))

        die_fields = [
            {"name": "die_no", "label": t("模具编号"), "required": True},
            {"name": "die_name", "label": t("模具名称")},
            {"name": "die_spec", "label": t("模具规格")},
            {"name": "die_version", "label": t("模具版本"), "required": True},
            {"name": "die_status", "label": t("模具状态")},
            {"name": "use_count_bucket", "label": t("使用次数区间")},
            {"name": "total_hit_count", "label": t("总打击次数")},
            {"name": "after_repair_hit_count", "label": t("修复后打击次数")},
            {"name": "is_after_regrind_first_use", "label": t("修磨后首次使用"), "choices": YES_NO_CHOICES},
            {"name": "remark", "label": t("备注")},
        ]
        seat_fields = [
            {"name": "die_seat_no", "label": t("模座编号"), "required": True},
            {"name": "theory_close_height", "label": t("理论闭合高度")},
            {"name": "seat_position_name", "label": t("碰模板位置说明")},
            {"name": "seat_x_offset", "label": t("横向偏差基准")},
            {"name": "seat_y_offset", "label": t("纵向偏差基准")},
            {"name": "base_template_700", "label": t("理论700碰模板")},
            {"name": "base_template_wear", "label": t("基础碰模板变薄量")},
            {"name": "guide_clearance_level", "label": t("导向状态"), "choices": STATE_CHOICES},
        ]
        block_fields = [
            {"name": "block_no", "label": t("拼块编号"), "required": True},
            {"name": "block_size", "label": t("拼块尺寸")},
            {"name": "theory_thickness", "label": t("理论厚度")},
            {"name": "lower_x_base", "label": t("下拼横向基准")},
            {"name": "lower_y_base", "label": t("下拼纵向基准")},
            {"name": "upper_x_base", "label": t("上拼横向基准")},
            {"name": "upper_y_base", "label": t("上拼纵向基准")},
            {"name": "lower_block_plate_thickness", "label": t("下拼底板厚度")},
            {"name": "upper_block_plate_thickness", "label": t("上拼底板厚度")},
            {"name": "block_plate_delta", "label": t("拼块底板偏差")},
        ]
        plate_fields = [
            {"name": "plate_no", "label": t("底板编号"), "required": True},
            {"name": "plate_thickness", "label": t("底板厚度"), "required": True},
            {"name": "plate_remark", "label": t("备注")},
        ]
        rule_fields = [
            {"name": "rule_type", "label": t("规则类型"), "required": True, "choices": RULE_TYPE_CHOICES},
            {"name": "rule_key", "label": t("规则键"), "required": True},
            {"name": "x_comp", "label": t("横向补偿")},
            {"name": "y_comp", "label": t("纵向补偿")},
            {"name": "template_comp", "label": t("碰模板补偿")},
            {"name": "remark", "label": t("备注")},
        ]

        tabs = [
            (t("模具版本"), die_fields, self.repo.list_die_versions, self.repo.add_die_version, "master_die_version", ("die_no", "die_version")),
            (t("模座"), seat_fields, self.repo.list_die_seats, self.repo.add_die_seat, "master_die_seat", "die_seat_no"),
            (t("拼块"), block_fields, self.repo.list_blocks, self.repo.add_block, "master_block", "block_no"),
            (t("底板"), plate_fields, self.repo.list_base_plates, self.repo.add_base_plate, "master_base_plate", "plate_no"),
            (t("补偿规则"), rule_fields, self.repo.list_rules, self.repo.add_rule),
        ]
        for item in tabs:
            title, fields, load_fn, save_fn, *meta = item
            record_table = meta[0] if meta else None
            record_key = meta[1] if len(meta) > 1 else None
            frame = SimpleCrudFrame(
                notebook, title, fields, load_fn, save_fn,
                on_saved=self.refresh_all, record_table=record_table, record_key=record_key
            )
            notebook.add(frame, text=title)

        option_fields = [
            {"name": "category", "label": t("分类"), "required": True, "choices": {cat_label(name): name for name in CATEGORIES}},
            {"name": "option_value", "label": t("选项值"), "required": True},
            {"name": "sort_order", "label": t("排序号")},
            {"name": "remark", "label": t("备注")},
        ]
        option_frame = SimpleCrudFrame(
            notebook,
            t("基础选项"),
            option_fields,
            lambda: self.repo._fetch_all("SELECT category, option_value, sort_order, is_active, remark AS invalid_reason FROM master_option ORDER BY category, sort_order, option_value"),
            self.repo.add_option,
            on_saved=self.refresh_all,
        )
        notebook.add(option_frame, text=t("基础选项"))

        self._build_quick_state_tab(notebook)

    def _build_quick_state_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text=t("快速状态修改"))

        ttk.Label(frame, text=t("快速状态修改"), font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text=t("直接修改模座导向状态或闭合高度，无需重新新增记录。"), foreground="#666666").pack(anchor="w", pady=(0, 10))

        seat_frame = ttk.LabelFrame(frame, text=t("模座状态"), padding=10)
        seat_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(seat_frame, text=t("模座编号")).grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self._qs_seat_var = StringVar()
        self._qs_seat_widget = ttk.Combobox(seat_frame, textvariable=self._qs_seat_var, width=24, state="readonly")
        self._qs_seat_widget.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(seat_frame, text=t("导向状态")).grid(row=0, column=2, sticky="e", padx=6, pady=4)
        self._qs_guide_var = StringVar()
        guide_cb = ttk.Combobox(seat_frame, textvariable=self._qs_guide_var, width=12, state="readonly",
                                values=list(STATE_CHOICES.keys()))
        guide_cb.grid(row=0, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(seat_frame, text=t("理论闭合高度")).grid(row=1, column=0, sticky="e", padx=6, pady=4)
        self._qs_height_var = StringVar()
        ttk.Entry(seat_frame, textvariable=self._qs_height_var, width=14).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(seat_frame, text=t("（留空则不修改）"), foreground="#888888").grid(row=1, column=2, sticky="w", padx=6)

        ttk.Button(seat_frame, text=t("保存模座状态"), command=self._handle_quick_seat_save).grid(
            row=2, column=0, columnspan=4, sticky="w", padx=6, pady=8
        )

        block_frame = ttk.LabelFrame(frame, text=t("拼块启用/停用"), padding=10)
        block_frame.pack(fill="x")

        ttk.Label(block_frame, text=t("拼块编号")).grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self._qs_block_var = StringVar()
        self._qs_block_widget = ttk.Combobox(block_frame, textvariable=self._qs_block_var, width=24, state="readonly")
        self._qs_block_widget.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        ttk.Button(block_frame, text=t("停用"), command=lambda: self._handle_quick_block_toggle(0)).grid(
            row=0, column=2, sticky="w", padx=6, pady=4
        )
        ttk.Button(block_frame, text=t("启用"), command=lambda: self._handle_quick_block_toggle(1)).grid(
            row=0, column=3, sticky="w", padx=4, pady=4
        )

    def _refresh_quick_state_options(self) -> None:
        if hasattr(self, "_qs_seat_widget"):
            self._qs_seat_widget["values"] = list(self.seat_map.keys())
        if hasattr(self, "_qs_block_widget"):
            all_blocks = [row["block_no"] for row in self.repo._fetch_all(
                "SELECT block_no FROM master_block ORDER BY block_no"
            )]
            self._qs_block_widget["values"] = all_blocks

    def _handle_quick_seat_save(self) -> None:
        seat_no = self._qs_seat_var.get().strip()
        if not seat_no:
            messagebox.showwarning(t("提示"), t("请选择模座编号。"))
            return
        guide = self._qs_guide_var.get().strip()
        if guide:
            self.repo.update_die_seat_state(seat_no, STATE_CHOICES[guide])
        height_str = self._qs_height_var.get().strip()
        if height_str:
            try:
                height = float(height_str)
            except ValueError:
                messagebox.showwarning(t("提示"), t("理论闭合高度请填写数字。"))
                return
            self.repo.update_die_seat_theory_height(seat_no, height)
        if not guide and not height_str:
            messagebox.showwarning(t("提示"), t("请至少填写一项要修改的值。"))
            return
        self.refresh_all()
        messagebox.showinfo(t("完成"), t("模座 {seat_no} 状态已更新。", seat_no=seat_no))

    def _handle_quick_block_toggle(self, is_active: int) -> None:
        block_no = self._qs_block_var.get().strip()
        if not block_no:
            messagebox.showwarning(t("提示"), t("请选择拼块编号。"))
            return
        self.repo.update_block_state(block_no, is_active)
        self.refresh_all()
        state_label = t("启用") if is_active else t("停用")
        messagebox.showinfo(t("完成"), t("拼块 {block_no} 已{state_label}。", block_no=block_no, state_label=state_label))

    def _build_job_tab(self) -> None:
        top = ttk.Frame(self.job_tab)
        top.pack(fill="both", expand=True)
        left = ttk.LabelFrame(top, text=t("任务输入"), padding=10)
        left.pack(side=LEFT, fill="both", expand=True, padx=(0, 8), pady=(0, 8))
        right = ttk.LabelFrame(top, text=t("计算结果"), padding=10)
        right.pack(side=RIGHT, fill="both", expand=True, pady=(0, 8))

        self.job_vars = {name: StringVar() for name in [
            "job_date", "shift_name", "operator_name", "product_process_name", "die_display",
            "die_seat_no", "block_no", "base_plate_no_1", "base_plate_no_2", "base_plate_no_3",
            "base_plate_no_4", "base_plate_no_5", "upper_x_ref", "upper_y_ref", "lower_x_ref", "lower_y_ref",
            "lower_die_actual_height", "target_thickness", "die_hit_count", "remark"
        ]}
        labels = [
            (t("任务时间"), "job_date"),
            ("Shift", "shift_name"),
            (t("操作员"), "operator_name"),
            (t("产品工序"), "product_process_name"),
            (t("模具编号"), "die_display"),
            (t("模座编号"), "die_seat_no"),
            (t("拼块编号"), "block_no"),
            (t("下模实际高度"), "lower_die_actual_height"),
            (t("目标厚度"), "target_thickness"),
            (t("本次模具打击次数"), "die_hit_count"),
            (t("上模横向基准面"), "upper_x_ref"),
            (t("上模纵向基准面"), "upper_y_ref"),
            (t("下模横向基准面"), "lower_x_ref"),
            (t("下模纵向基准面"), "lower_y_ref"),
            (t("底板1"), "base_plate_no_1"),
            (t("底板2"), "base_plate_no_2"),
            (t("底板3"), "base_plate_no_3"),
            (t("底板4"), "base_plate_no_4"),
            (t("底板5"), "base_plate_no_5"),
            (t("备注"), "remark"),
        ]
        combo_fields = {"shift_name", "product_process_name", "die_display", "die_seat_no", "block_no", "base_plate_no_1", "base_plate_no_2", "base_plate_no_3", "base_plate_no_4", "base_plate_no_5"}
        for idx, (label, key) in enumerate(labels):
            row = idx // 2
            col = (idx % 2) * 2
            ttk.Label(left, text=label).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            if key in combo_fields:
                state = "normal" if key in {"product_process_name", "die_display"} else "readonly"
                widget = ttk.Combobox(left, textvariable=self.job_vars[key], width=28, state=state)
                setattr(self, f"{key}_widget", widget)
            else:
                widget = ttk.Entry(left, textvariable=self.job_vars[key], width=30)
            widget.grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)
        self.product_process_name_widget.bind("<<ComboboxSelected>>", self.on_product_selected)
        self.product_process_name_widget.bind("<KeyRelease>", self.on_product_input_change)
        self.die_display_widget.bind("<KeyRelease>", self.on_die_input_change)

        self.shift_name_widget["values"] = self.option_values.get("Shift", ["Day Shift", "Swing Shift", "Night Shift", "Day 12h Shift", "Night 12h Shift"])

        info_frame = ttk.LabelFrame(left, text=t("主数据自动带出（只读）"), padding=8)
        info_frame.grid(row=(len(labels) + 1) // 2 + 1, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        self.job_info_vars = {
            "product_type": StringVar(value="--"),
            "blade_direction": StringVar(value="--"),
            "blade_size_grade": StringVar(value="--"),
            "crown_rotation_angle_grade": StringVar(value="--"),
            "energy_grade": StringVar(value="--"),
        }
        info_items = [
            ("Product Type", "product_type"),
            ("Blade Direction", "blade_direction"),
            ("Size Grade", "blade_size_grade"),
            ("Crown Angle Grade", "crown_rotation_angle_grade"),
            ("Energy Grade", "energy_grade"),
        ]
        for idx, (label, key) in enumerate(info_items):
            row = idx // 2
            col = (idx % 2) * 2
            ttk.Label(info_frame, text=label).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            ttk.Label(info_frame, textvariable=self.job_info_vars[key], foreground="#1d4e89").grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)

        plate_frame = ttk.LabelFrame(left, text=t("底板厚度显示"), padding=8)
        plate_frame.grid(row=(len(labels) + 1) // 2 + 2, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        self.plate_thickness_vars = {key: StringVar(value="--") for key in ["base_plate_no_1", "base_plate_no_2", "base_plate_no_3", "base_plate_no_4", "base_plate_no_5", "plate_total"]}
        for idx, key in enumerate(["base_plate_no_1", "base_plate_no_2", "base_plate_no_3", "base_plate_no_4", "base_plate_no_5"]):
            ttk.Label(plate_frame, text=t("{n}号底板厚度", n=idx + 1)).grid(row=idx // 2, column=(idx % 2) * 2, sticky="e", padx=6, pady=4)
            ttk.Label(plate_frame, textvariable=self.plate_thickness_vars[key], foreground="#8b5a00").grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky="w", padx=6, pady=4)
        ttk.Label(plate_frame, text=t("底板厚度合")).grid(row=3, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(plate_frame, textvariable=self.plate_thickness_vars["plate_total"], foreground="#b22222", font=("Microsoft YaHei UI", 10, "bold")).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        btn_frame = ttk.Frame(left)
        btn_frame.grid(row=(len(labels) + 1) // 2 + 3, column=0, columnspan=4, sticky="w", pady=10)
        ttk.Button(btn_frame, text=t("计算推荐值"), command=self.handle_calculate).pack(side=LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text=t("保存任务"), command=self.handle_save_job).pack(side=LEFT, padx=8)
        ttk.Button(btn_frame, text=t("保存任务并首件反馈"), command=self.handle_save_job_and_feedback).pack(side=LEFT, padx=8)
        ttk.Button(btn_frame, text=t("清空任务"), command=self.clear_job_form).pack(side=LEFT, padx=8)

        self.calc_labels = {}
        self.calc_label_widgets = {}
        result_items = [
            (t("基础理论碰模板厚度"), "theory_template_thickness_base"),
            (t("基础理论横向垫板"), "theory_lower_x_pad_base"),
            (t("基础理论纵向垫板"), "theory_lower_y_pad_base"),
            (t("历史碰模板修正"), "history_template_correction"),
            (t("历史横向修正"), "history_x_correction"),
            (t("历史纵向修正"), "history_y_correction"),
            (t("推荐碰模板厚度"), "recommend_template_thickness"),
            (t("推荐横向垫板"), "recommend_lower_x_pad"),
            (t("推荐纵向垫板"), "recommend_lower_y_pad"),
            (t("相似案例数量"), "similar_case_count"),
            (t("推荐置信等级"), "recommend_confidence"),
        ]
        CONFIDENCE_COLOR = {"high": "#1a7a1a", "medium": "#b87800", "low": "#cc2200"}
        CONFIDENCE_LABEL = {"high": t("高（样本充足）"), "medium": t("中（样本偏少）"), "low": t("低（样本不足）")}
        for idx, (label, key) in enumerate(result_items):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="e", padx=6, pady=6)
            var = StringVar(value="--")
            self.calc_labels[key] = var
            lbl = ttk.Label(right, textvariable=var, font=("Microsoft YaHei UI", 11, "bold"))
            lbl.grid(row=idx, column=1, sticky="w", padx=6, pady=6)
            self.calc_label_widgets[key] = lbl
        self._confidence_color_map = CONFIDENCE_COLOR
        self._confidence_label_map = CONFIDENCE_LABEL
        ttk.Label(
            right,
            text=t("说明：推荐值 = 基础理论值 + 历史修正值。\n如果相似案例数量少，优先以基础理论值为主。"),
            foreground="#666666",
        ).grid(row=len(result_items) + 1, column=0, columnspan=2, sticky="w", pady=(12, 0))

        feedback_frame = ttk.LabelFrame(self.job_tab, text=t("首件反馈（与新建任务同页填写）"), padding=10)
        feedback_frame.pack(fill="x", pady=(4, 0))
        self.feedback_vars = {name: StringVar() for name in [
            "actual_template_thickness", "actual_al_block_thickness", "actual_thickness",
            "actual_lower_x_pad_root", "actual_lower_x_pad_tip", "actual_lower_y_pad",
            "measured_x_offset_root", "measured_x_offset_tip", "measured_y_offset",
            "first_piece_thickness_delta", "defect_type", "feedback_remark",
            "measure_quality_level", "die_install_quality_level", "block_install_quality_level",
            "guide_clearance_level", "is_pass", "template_delta", "x_pad_delta", "y_pad_delta",
            "adjust_reason", "after_result"
        ]}
        feedback_items = [
            (t("实际碰模板厚度"), "actual_template_thickness"),
            (t("碰模板铝块厚度"), "actual_al_block_thickness"),
            (t("实际厚度"), "actual_thickness"),
            (t("实际叶根横向垫板"), "actual_lower_x_pad_root"),
            (t("实际叶顶横向垫板"), "actual_lower_x_pad_tip"),
            (t("实际纵向垫板"), "actual_lower_y_pad"),
            (t("叶根横向错位"), "measured_x_offset_root"),
            (t("叶顶横向错位"), "measured_x_offset_tip"),
            (t("纵向错位"), "measured_y_offset"),
            (t("首件厚度偏差"), "first_piece_thickness_delta"),
            (t("缺陷类型"), "defect_type"),
            (t("反馈备注"), "feedback_remark"),
        ]
        for idx, (label, key) in enumerate(feedback_items):
            row = idx // 4
            col = (idx % 4) * 2
            ttk.Label(feedback_frame, text=label).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            ttk.Entry(feedback_frame, textvariable=self.feedback_vars[key], width=20).grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)

        quality_items = [
            (t("测量可信度"), "measure_quality_level", QUALITY_CHOICES),
            (t("模具安装质量"), "die_install_quality_level", STATE_CHOICES),
            (t("拼块安装质量"), "block_install_quality_level", STATE_CHOICES),
            (t("模座导向状态"), "guide_clearance_level", STATE_CHOICES),
            (t("首件是否合格"), "is_pass", PASS_CHOICES),
        ]
        base_row = 3
        for idx, (label, key, choices) in enumerate(quality_items):
            ttk.Label(feedback_frame, text=label).grid(row=base_row + idx // 3, column=(idx % 3) * 2, sticky="e", padx=6, pady=4)
            cb = ttk.Combobox(feedback_frame, textvariable=self.feedback_vars[key], values=list(choices.keys()), state="readonly", width=18)
            cb.grid(row=base_row + idx // 3, column=(idx % 3) * 2 + 1, sticky="w", padx=6, pady=4)
            cb.set(next(iter(choices.keys())))

        adj_row = 5
        adjustment_items = [
            (t("碰模板调整量"), "template_delta"),
            (t("横向垫板调整量"), "x_pad_delta"),
            (t("纵向垫板调整量"), "y_pad_delta"),
            (t("返调原因"), "adjust_reason"),
            (t("调整后结果"), "after_result"),
        ]
        for idx, (label, key) in enumerate(adjustment_items):
            ttk.Label(feedback_frame, text=label).grid(row=adj_row + idx // 3, column=(idx % 3) * 2, sticky="e", padx=6, pady=4)
            ttk.Entry(feedback_frame, textvariable=self.feedback_vars[key], width=20).grid(row=adj_row + idx // 3, column=(idx % 3) * 2 + 1, sticky="w", padx=6, pady=4)

    def _build_feedback_tab(self) -> None:
        top = ttk.Frame(self.feedback_tab)
        top.pack(fill="x")
        left = ttk.LabelFrame(top, text=t("选择任务并录入首件反馈"), padding=10)
        left.pack(side=LEFT, fill="both", expand=True, padx=(0, 8))
        right = ttk.LabelFrame(top, text=t("当前任务参考值"), padding=10)
        right.pack(side=RIGHT, fill="both", expand=True)

        self.feedback_job_var = StringVar()
        ttk.Label(left, text=t("待反馈任务")).grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.feedback_job_widget = ttk.Combobox(left, textvariable=self.feedback_job_var, width=38, state="readonly")
        self.feedback_job_widget.grid(row=0, column=1, sticky="w", padx=6, pady=4, columnspan=3)
        self.feedback_job_widget.bind("<<ComboboxSelected>>", self.on_feedback_job_selected)

        self.feedback_vars = {name: StringVar() for name in [
            "actual_template_thickness", "actual_al_block_thickness", "actual_thickness",
            "actual_lower_x_pad_root", "actual_lower_x_pad_tip", "actual_lower_y_pad",
            "measured_x_offset_root", "measured_x_offset_tip", "measured_y_offset",
            "first_piece_thickness_delta", "defect_type", "feedback_remark",
            "measure_quality_level", "die_install_quality_level", "block_install_quality_level",
            "guide_clearance_level", "is_pass", "template_delta", "x_pad_delta", "y_pad_delta",
            "adjust_reason", "after_result"
        ]}
        feedback_items = [
            (t("实际碰模板厚度"), "actual_template_thickness"),
            (t("碰模板铝块厚度"), "actual_al_block_thickness"),
            (t("实际厚度"), "actual_thickness"),
            (t("实际叶根横向垫板"), "actual_lower_x_pad_root"),
            (t("实际叶顶横向垫板"), "actual_lower_x_pad_tip"),
            (t("实际纵向垫板"), "actual_lower_y_pad"),
            (t("叶根横向错位"), "measured_x_offset_root"),
            (t("叶顶横向错位"), "measured_x_offset_tip"),
            (t("纵向错位"), "measured_y_offset"),
            (t("首件厚度偏差"), "first_piece_thickness_delta"),
            (t("缺陷类型"), "defect_type"),
            (t("反馈备注"), "feedback_remark"),
        ]
        for idx, (label, key) in enumerate(feedback_items, start=1):
            row = idx // 2 + 1
            col = ((idx - 1) % 2) * 2
            ttk.Label(left, text=label).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            ttk.Entry(left, textvariable=self.feedback_vars[key], width=30).grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)

        quality_row = 8
        quality_items = [
            (t("测量可信度"), "measure_quality_level", QUALITY_CHOICES),
            (t("模具安装质量"), "die_install_quality_level", STATE_CHOICES),
            (t("拼块安装质量"), "block_install_quality_level", STATE_CHOICES),
            (t("模座导向状态"), "guide_clearance_level", STATE_CHOICES),
            (t("首件是否合格"), "is_pass", PASS_CHOICES),
        ]
        for idx, (label, key, choices) in enumerate(quality_items):
            row = quality_row + idx // 2
            col = (idx % 2) * 2
            ttk.Label(left, text=label).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            widget = ttk.Combobox(left, textvariable=self.feedback_vars[key], values=list(choices.keys()), state="readonly", width=28)
            widget.grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)
            widget.set(next(iter(choices.keys())))

        adjust_frame = ttk.LabelFrame(left, text=t("本次返调记录（可选）"), padding=8)
        adjust_frame.grid(row=quality_row + 3, column=0, columnspan=4, sticky="ew", pady=(10, 4))
        adjust_items = [
            (t("碰模板调整量"), "template_delta"),
            (t("横向垫板调整量"), "x_pad_delta"),
            (t("纵向垫板调整量"), "y_pad_delta"),
            (t("返调原因"), "adjust_reason"),
            (t("调整后结果"), "after_result"),
        ]
        for idx, (label, key) in enumerate(adjust_items):
            row = idx // 2
            col = (idx % 2) * 2
            ttk.Label(adjust_frame, text=label).grid(row=row, column=col, sticky="e", padx=6, pady=4)
            ttk.Entry(adjust_frame, textvariable=self.feedback_vars[key], width=30).grid(row=row, column=col + 1, sticky="w", padx=6, pady=4)

        action_frame = ttk.Frame(left)
        action_frame.grid(row=quality_row + 6, column=0, columnspan=4, sticky="w", pady=10)
        ttk.Button(action_frame, text=t("保存首件反馈"), command=self.handle_save_feedback).pack(side=LEFT, padx=(0, 8))
        ttk.Button(action_frame, text=t("刷新任务列表"), command=self.refresh_feedback_jobs).pack(side=LEFT, padx=8)

        self.feedback_summary_vars = {
            "job_no": StringVar(value="--"),
            "template": StringVar(value="--"),
            "xpad": StringVar(value="--"),
            "ypad": StringVar(value="--"),
        }
        summary_items = [
            (t("任务编号"), "job_no"),
            (t("推荐碰模板厚度"), "template"),
            (t("推荐横向垫板"), "xpad"),
            (t("推荐纵向垫板"), "ypad"),
        ]
        for idx, (label, key) in enumerate(summary_items):
            ttk.Label(right, text=label).grid(row=idx, column=0, sticky="e", padx=6, pady=6)
            ttk.Label(right, textvariable=self.feedback_summary_vars[key], font=("Microsoft YaHei UI", 11, "bold")).grid(row=idx, column=1, sticky="w", padx=6, pady=6)
        ttk.Label(
            right,
            text=t("提示：错位值统一填写“调到 0 位置还需增减多少垫板”。\n正值表示还需要增加，负值表示还需要减少。"),
            foreground="#666666",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _build_history_tab(self) -> None:
        toolbar = ttk.Frame(self.history_tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text=t("产品工序筛选")).pack(side=LEFT, padx=(0, 6))
        self.history_filter_var = StringVar()
        self.history_filter_widget = ttk.Combobox(toolbar, textvariable=self.history_filter_var, width=32, state="readonly")
        self.history_filter_widget.pack(side=LEFT, padx=(0, 8))
        ttk.Button(toolbar, text=t("刷新列表"), command=self.refresh_history).pack(side=LEFT)
        ttk.Button(toolbar, text=t("导出分析数据CSV"), command=self.handle_export_csv).pack(side=LEFT, padx=8)
        ttk.Button(toolbar, text=t("刷新成功率统计"), command=self.refresh_stats_view).pack(side=LEFT, padx=8)

        columns = [
            "job_no", "job_date", "product_process_name", "die_no", "die_version",
            "block_no", "recommend_template_thickness", "recommend_lower_x_pad",
            "recommend_lower_y_pad", "actual_template_thickness", "measured_x_offset_root",
            "measured_y_offset", "sample_grade", "job_status"
        ]
        labels = [
            t("任务编号"), t("日期"), t("产品工序"), t("模具"), t("版本"), t("拼块"), t("推荐碰模板"),
            t("推荐横向"), t("推荐纵向"), t("实际碰模板"), t("叶根横向错位"), t("纵向错位"), t("样本等级"), t("状态")
        ]
        frame = ttk.Frame(self.history_tab)
        frame.pack(fill="both", expand=True)
        self.history_tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for col, label in zip(columns, labels):
            self.history_tree.heading(col, text=label)
            self.history_tree.column(col, width=110, anchor="center")
        vsb = ttk.Scrollbar(frame, orient=VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=vsb.set)
        self.history_tree.pack(side=LEFT, fill="both", expand=True)
        vsb.pack(side=RIGHT, fill="y")

        stats_frame = ttk.LabelFrame(self.history_tab, text=t("计算成功率统计（偏差≤1 视为成功）"), padding=10)
        stats_frame.pack(fill="both", expand=False, pady=(10, 0))

        self.stats_summary_var = StringVar(value=t("暂无统计数据"))
        ttk.Label(stats_frame, textvariable=self.stats_summary_var, justify="left").pack(anchor="w")

        chart_wrap = ttk.Frame(stats_frame)
        chart_wrap.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_canvas = Canvas(chart_wrap, width=1160, height=260, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.stats_canvas.pack(side=TOP, fill=BOTH, expand=True)

        self.stats_month_tree = ttk.Treeview(
            stats_frame,
            columns=("month", "total", "template_rate", "x_rate", "y_rate"),
            show="headings",
            height=6,
        )
        for key, label, width in [
            ("month", t("月份"), 120),
            ("total", t("样本数"), 100),
            ("template_rate", t("碰模板成功率%"), 150),
            ("x_rate", t("横向垫板成功率%"), 150),
            ("y_rate", t("纵向垫板成功率%"), 150),
        ]:
            self.stats_month_tree.heading(key, text=label)
            self.stats_month_tree.column(key, width=width, anchor="center")
        self.stats_month_tree.pack(fill="x", pady=(8, 0))

    def refresh_all(self) -> None:
        self.refresh_master_maps()
        self.refresh_home_summary()
        self.refresh_job_options()
        self.refresh_history()
        self.refresh_stats_view()
        self._refresh_quick_state_options()

    def refresh_master_maps(self) -> None:
        option_categories = CATEGORIES
        self.option_values = {
            category: [row["option_value"] for row in self.repo.list_options(category)]
            for category in option_categories
        }
        self.product_map = {row["product_process_name"]: dict(row) for row in self.repo.list_product_processes() if str(row["is_active"]) == "1"}
        die_rows = [row for row in self.repo.list_die_versions() if str(row["invalid_reason"] or "") == ""]
        self.die_map = {self._die_display(row): dict(row) for row in die_rows}
        self.seat_map = {row["die_seat_no"]: dict(row) for row in self.repo.list_die_seats() if str(row["is_active"]) == "1"}
        self.block_map = {row["block_no"]: dict(row) for row in self.repo.list_blocks() if str(row["is_active"]) == "1"}
        self.plate_options = [row["plate_no"] for row in self.repo.list_base_plates() if str(row["is_active"]) == "1"]
        self._refresh_quick_state_options()

    def refresh_home_summary(self) -> None:
        self.summary_text.set(
            t(
                "home_summary",
                products=len(self.product_map),
                dies=len(self.die_map),
                seats=len(self.seat_map),
                blocks=len(self.block_map),
                jobs=len(self.repo.list_jobs(False)),
            )
        )

    def _die_display(self, row) -> str:
        die_name = row["die_name"] or ""
        return f"{row['die_no']}" if not die_name else f"{row['die_no']} | {die_name}"

    def refresh_job_options(self) -> None:
        self.product_process_name_widget["values"] = list(self.product_map.keys())
        self.die_display_widget["values"] = list(self.die_map.keys())
        self.die_seat_no_widget["values"] = list(self.seat_map.keys())
        self.block_no_widget["values"] = list(self.block_map.keys())
        for key in ("base_plate_no_1", "base_plate_no_2", "base_plate_no_3", "base_plate_no_4", "base_plate_no_5"):
            getattr(self, f"{key}_widget")["values"] = [""] + self.plate_options
            getattr(self, f"{key}_widget").bind("<<ComboboxSelected>>", self.on_plate_changed)
        self.job_vars["job_date"].set(datetime.now().strftime("%Y-%m-%d"))
        if self.option_values.get("Shift"):
            self.job_vars["shift_name"].set(self.option_values["Shift"][0])

    def refresh_history(self) -> None:
        product_name = self.history_filter_var.get().strip() or None
        self.history_filter_widget["values"] = [""] + list(self.product_map.keys())
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for row in self.repo.list_history_rows(product_name):
            self.history_tree.insert("", END, values=[row[col] if row[col] is not None else "" for col in self.history_tree["columns"]])

    def refresh_stats_view(self) -> None:
        stats = self.repo.get_success_stats()
        alltime = stats["alltime"]
        self.stats_summary_var.set(
            t(
                "stats_summary",
                template=alltime["template_rate"],
                x=alltime["x_rate"],
                y=alltime["y_rate"],
                total=alltime["total"],
            )
        )
        for item in self.stats_month_tree.get_children():
            self.stats_month_tree.delete(item)
        for row in stats["monthly"]:
            self.stats_month_tree.insert(
                "",
                END,
                values=(row["month"], row["total"], row["template_rate"], row["x_rate"], row["y_rate"]),
            )
        self.draw_stats_chart(stats["monthly"])

    def draw_stats_chart(self, monthly_rows: list[dict]) -> None:
        canvas = self.stats_canvas
        canvas.delete("all")
        width = int(canvas["width"])
        height = int(canvas["height"])
        left = 60
        top = 20
        right = width - 20
        bottom = height - 40
        canvas.create_line(left, top, left, bottom, fill="#666666")
        canvas.create_line(left, bottom, right, bottom, fill="#666666")

        for i in range(0, 101, 20):
            y = bottom - (bottom - top) * i / 100
            canvas.create_line(left, y, right, y, fill="#efefef")
            canvas.create_text(left - 20, y, text=str(i), fill="#666666")

        if not monthly_rows:
            canvas.create_text(width // 2, height // 2, text=t("暂无按月份统计数据"), fill="#666666", font=("Microsoft YaHei UI", 12))
            return

        points_count = len(monthly_rows)
        step = (right - left) / max(points_count - 1, 1)

        def to_points(key: str) -> list[tuple[float, float]]:
            result = []
            for idx, row in enumerate(monthly_rows):
                x = left + idx * step
                y = bottom - (bottom - top) * float(row[key]) / 100
                result.append((x, y))
            return result

        def draw_series(key: str, color: str, label: str, label_x: int) -> None:
            points = to_points(key)
            if len(points) >= 2:
                flat = [coord for point in points for coord in point]
                canvas.create_line(*flat, fill=color, width=2, smooth=True)
            for x, y in points:
                canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline=color)
            canvas.create_text(label_x, 10, text=label, fill=color, anchor="w", font=("Microsoft YaHei UI", 10, "bold"))

        draw_series("template_rate", "#1f77b4", t("碰模板成功率"), 80)
        draw_series("x_rate", "#2ca02c", t("横向垫板成功率"), 240)
        draw_series("y_rate", "#d62728", t("纵向垫板成功率"), 430)

        for idx, row in enumerate(monthly_rows):
            x = left + idx * step
            canvas.create_text(x, bottom + 16, text=row["month"], fill="#666666")

    def handle_export_csv(self) -> None:
        default_name = f"forge_analysis_export_{Path.cwd().name}.csv"
        file_path = filedialog.asksaveasfilename(
            title=t("选择导出 CSV 路径"),
            filetypes=[(t("CSV 文件"), "*.csv")],
            defaultextension=".csv",
            initialfile=default_name,
        )
        if not file_path:
            return
        try:
            output = self.repo.export_analysis_csv(Path(file_path))
        except Exception as exc:
            messagebox.showerror(t("导出失败"), str(exc))
            return
        messagebox.showinfo(t("导出完成"), t("分析数据已导出到：\n{output}", output=output))

    def on_product_selected(self, _event=None) -> None:
        row = self.product_map.get(self.job_vars["product_process_name"].get().strip())
        if row:
            if row.get("target_thickness_default") not in (None, ""):
                self.job_vars["target_thickness"].set(str(row["target_thickness_default"]))
            for key in self.job_info_vars:
                self.job_info_vars[key].set(row.get(key) or "--")
            die_rows = self.repo.list_dies_for_product_process(row["product_process_name"])
            self.die_display_widget["values"] = [self._die_display(r) for r in die_rows]

    def on_product_input_change(self, _event=None) -> None:
        typed = self.job_vars["product_process_name"].get().strip()
        all_values = list(self.product_map.keys())
        if not typed:
            self.product_process_name_widget["values"] = all_values
        else:
            self.product_process_name_widget["values"] = [v for v in all_values if typed.lower() in v.lower()][:50]

    def on_die_input_change(self, _event=None) -> None:
        typed = self.job_vars["die_display"].get().strip()
        current_values = list(self.die_display_widget["values"])
        if typed:
            self.die_display_widget["values"] = [v for v in current_values if typed.lower() in v.lower()][:50]

    def on_plate_changed(self, _event=None) -> None:
        plate_lookup = {row["plate_no"]: row for row in self.repo.list_base_plates()}
        total = 0.0
        for key in ("base_plate_no_1", "base_plate_no_2", "base_plate_no_3", "base_plate_no_4", "base_plate_no_5"):
            plate_no = self.job_vars[key].get().strip()
            row = plate_lookup.get(plate_no)
            thickness = row["plate_thickness"] if row else None
            self.plate_thickness_vars[key].set("--" if thickness is None else str(thickness))
            if thickness is not None:
                total += float(thickness)
        self.plate_thickness_vars["plate_total"].set(str(round(total, 3)))

    def get_selected_die(self) -> dict | None:
        return self.die_map.get(self.job_vars["die_display"].get().strip())

    def collect_job_values(self) -> dict:
        die = self.get_selected_die()
        if not die:
            raise ValueError(t("请选择模具版本。"))
        required = [
            ("shift_name", "Shift"),
            ("operator_name", t("操作员")),
            ("product_process_name", t("产品工序")),
            ("die_seat_no", t("模座编号")),
            ("block_no", t("拼块编号")),
            ("lower_die_actual_height", t("下模实际高度")),
            ("target_thickness", t("目标厚度")),
        ]
        for key, label in required:
            if not self.job_vars[key].get().strip():
                raise ValueError(t("请填写：{label}", label=label))
        row = self.product_map.get(self.job_vars["product_process_name"].get().strip(), {})
        values = {key: var.get().strip() for key, var in self.job_vars.items()}
        values.update(
            {
                "die_no": die["die_no"],
                "die_version": die["die_version"],
                "blade_direction": row.get("blade_direction") or "",
                "blade_size_grade": row.get("blade_size_grade") or "",
                "crown_rotation_angle_grade": row.get("crown_rotation_angle_grade") or "",
                "energy_grade": row.get("energy_grade") or "",
            }
        )
        return values

    def handle_calculate(self) -> None:
        try:
            values = self.collect_job_values()
            self.last_calc = self.repo.calculate_preview(values)
        except Exception as exc:
            messagebox.showerror(t("计算失败"), str(exc))
            return
        for key, var in self.calc_labels.items():
            var.set(str(getattr(self.last_calc, key)))
        # Confidence level: color + localized label
        conf = self.last_calc.recommend_confidence
        self.calc_labels["recommend_confidence"].set(
            self._confidence_label_map.get(conf, conf)
        )
        color = self._confidence_color_map.get(conf, "black")
        self.calc_label_widgets["recommend_confidence"].configure(foreground=color)
        # Recommendation rows are colored too: orange when the deviation is large
        for rec_key in ("recommend_template_thickness", "recommend_lower_x_pad", "recommend_lower_y_pad"):
            self.calc_label_widgets[rec_key].configure(foreground="#1a1a8c")
        messagebox.showinfo(t("完成"), t("推荐值计算完成。"))

    def handle_save_job(self) -> None:
        try:
            values = self.collect_job_values()
            self.last_calc = self.repo.calculate_preview(values)
            job_id = self.repo.create_job(values, self.last_calc)
        except Exception as exc:
            messagebox.showerror(t("保存失败"), str(exc))
            return
        self.clear_job_form()
        self.refresh_all()
        messagebox.showinfo(t("完成"), t("任务已保存，编号 ID = {job_id}", job_id=job_id))

    def clear_job_form(self) -> None:
        for var in self.job_vars.values():
            var.set("")
        self.last_calc = None
        for var in self.calc_labels.values():
            var.set("--")
        for var in getattr(self, "job_info_vars", {}).values():
            var.set("--")
        for var in getattr(self, "plate_thickness_vars", {}).values():
            var.set("--")
        for var in getattr(self, "feedback_vars", {}).values():
            var.set("")
        self.job_vars["job_date"].set(datetime.now().strftime("%Y-%m-%d"))
        if self.option_values.get("shift_name"):
            self.job_vars["shift_name"].set(self.option_values["shift_name"][0])

    def _collect_feedback_payload(self) -> tuple[dict, dict, dict]:
        required = [
            ("actual_template_thickness", t("实际碰模板厚度")),
            ("actual_lower_x_pad_root", t("实际叶根横向垫板")),
            ("actual_lower_y_pad", t("实际纵向垫板")),
            ("measured_x_offset_root", t("叶根横向错位")),
            ("measured_y_offset", t("纵向错位")),
        ]
        for key, label in required:
            if not self.feedback_vars[key].get().strip():
                raise ValueError(t("请填写：{label}", label=label))
        feedback = {key: var.get().strip() for key, var in self.feedback_vars.items()}
        feedback["is_pass"] = PASS_CHOICES[self.feedback_vars["is_pass"].get()]
        quality = {
            "measure_quality_level": QUALITY_CHOICES[self.feedback_vars["measure_quality_level"].get()],
            "die_install_quality_level": STATE_CHOICES[self.feedback_vars["die_install_quality_level"].get()],
            "block_install_quality_level": STATE_CHOICES[self.feedback_vars["block_install_quality_level"].get()],
            "guide_clearance_level": STATE_CHOICES[self.feedback_vars["guide_clearance_level"].get()],
        }
        adjustment = {
            "template_delta": self.feedback_vars["template_delta"].get().strip(),
            "x_pad_delta": self.feedback_vars["x_pad_delta"].get().strip(),
            "y_pad_delta": self.feedback_vars["y_pad_delta"].get().strip(),
            "adjust_reason": self.feedback_vars["adjust_reason"].get().strip(),
            "after_result": self.feedback_vars["after_result"].get().strip(),
        }
        return feedback, quality, adjustment

    def handle_save_job_and_feedback(self) -> None:
        try:
            values = self.collect_job_values()
            if not self.last_calc:
                self.last_calc = self.repo.calculate_preview(values)
            feedback, quality, adjustment = self._collect_feedback_payload()
            job_id = self.repo.save_job_and_feedback(values, self.last_calc, feedback, quality, adjustment)
        except Exception as exc:
            messagebox.showerror(t("保存失败"), str(exc))
            return
        messagebox.showinfo(t("完成"), t("任务与首件反馈已保存，编号 ID = {job_id}", job_id=job_id))
        self.clear_job_form()
        self.refresh_all()

    def handle_init_db(self) -> None:
        ensure_database()
        messagebox.showinfo(t("完成"), t("数据库已初始化。"))

    def handle_import_excel(self) -> None:
        default_path = ROOT_DIR.parent / "die_setup_workbook.xlsx"
        file_path = filedialog.askopenfilename(
            title=t("选择要导入的 Excel 文件"),
            filetypes=[(t("Excel 文件"), "*.xlsx")],
            initialdir=str(default_path.parent),
            initialfile=default_path.name,
        )
        if not file_path:
            return
        try:
            summary = import_workbook(self.repo.conn, Path(file_path))
        except Exception as exc:
            messagebox.showerror(t("导入失败"), str(exc))
            return
        self.refresh_all()
        messagebox.showinfo(
            t("导入完成"),
            t(
                "import_summary_full",
                master=summary["master_rows"],
                history=summary["history_rows"],
                feedback=summary["feedback_rows"],
                skipped=summary["skipped_rows"],
            ),
        )

    def handle_import_history_csv(self) -> None:
        file_path = filedialog.askopenfilename(
            title=t("选择要导入的有效历史 CSV"),
            filetypes=[(t("CSV 文件"), "*.csv")],
            initialdir=str(ROOT_DIR / "exports"),
        )
        if not file_path:
            return
        try:
            summary = import_analysis_csv(self.repo.conn, Path(file_path))
        except Exception as exc:
            messagebox.showerror(t("导入失败"), str(exc))
            return
        self.refresh_all()
        messagebox.showinfo(
            t("导入完成"),
            t(
                "import_summary_history",
                history=summary["history_rows"],
                feedback=summary["feedback_rows"],
                skipped=summary["skipped_rows"],
            ),
        )

    def on_close(self) -> None:
        self.repo.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_self_check() -> int:
    repo = ForgeRepository()
    try:
        products = repo.list_product_processes()
        dies = repo.list_die_versions()
        seats = repo.list_die_seats()
        blocks = repo.list_blocks()
        stats = repo.get_success_stats()
        print("Self-check passed:")
        print(f"- Database path: {DB_PATH}")
        print(f"- Database exists: {DB_PATH.exists()}")
        print(f"- Product processes: {len(products)}")
        print(f"- Die versions: {len(dies)}")
        print(f"- Die seats: {len(seats)}")
        print(f"- Blocks: {len(blocks)}")
        print(f"- All-time template success rate: {stats['alltime']['template_rate']}%")
        print(f"- All-time X shim success rate: {stats['alltime']['x_rate']}%")
        print(f"- All-time Y shim success rate: {stats['alltime']['y_rate']}%")
        print(f"- Monthly data points: {len(stats['monthly'])}")
        return 0
    finally:
        repo.close()


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-check", action="store_true")
    args, _ = parser.parse_known_args()
    ensure_database()
    if args.self_check:
        raise SystemExit(run_self_check())
    app = ForgeApp()
    app.run()


if __name__ == "__main__":
    main()
