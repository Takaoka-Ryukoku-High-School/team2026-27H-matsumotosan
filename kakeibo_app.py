import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import flet as ft


DATA_FILE = Path.home() / ".kakeibo_transactions.json"
BUDGET_FILE = Path.home() / ".kakeibo_budgets.json"
PAPER = "#F4F4ED"
SURFACE = "#FFFEFA"
INK = "#202C2A"
MUTED = "#77807B"
GREEN = "#286451"
GREEN_LIGHT = "#E3EEE7"
ORANGE = "#C76D42"
ORANGE_LIGHT = "#F7E9DE"
LINE = "#E2E3D9"

EXPENSE_CATEGORIES = ["食費", "日用品", "交通費", "住居費", "光熱費", "通信費", "医療費", "娯楽", "その他"]
INCOME_CATEGORIES = ["給与", "賞与", "副収入", "臨時収入", "その他"]


def is_positive_int(value):
    return type(value) is int and value > 0


def load_transactions():
    try:
        transactions = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(transactions, list):
        return []

    valid_transactions = []
    for item in transactions:
        if not isinstance(item, dict):
            continue
        if not all(isinstance(item.get(key), str) for key in ("id", "date", "type", "category", "note")):
            continue
        if item["type"] not in ("income", "expense"):
            continue
        if not is_positive_int(item.get("amount")):
            continue
        try:
            date.fromisoformat(item["date"])
        except ValueError:
            continue
        valid_transactions.append(item)
    return valid_transactions


def save_transactions(transactions):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(transactions, ensure_ascii=False, indent=2), encoding="utf-8")


def load_budgets():
    try:
        budgets = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(budgets, dict):
        return {}
    return {
        month: amount
        for month, amount in budgets.items()
        if isinstance(month, str)
        and len(month) == 7
        and month[4] == "-"
        and is_positive_int(amount)
    }


def save_budgets(budgets):
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(budgets, ensure_ascii=False, indent=2), encoding="utf-8")


def format_yen(amount):
    return f"¥{amount:,}"


def shift_month(month_start, delta):
    month_index = month_start.year * 12 + month_start.month - 1 + delta
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def main(page: ft.Page):
    page.title = "家計簿 | Kakeibo"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PAPER
    page.padding = 24
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    transactions = load_transactions()
    budgets = load_budgets()
    shown_month = date.today().replace(day=1)
    current_filter = "all"

    month_label = ft.Text(size=19, color=INK, weight=ft.FontWeight.W_600)
    income_value = ft.Text(size=24, color=GREEN, weight=ft.FontWeight.W_600)
    expense_value = ft.Text(size=24, color=ORANGE, weight=ft.FontWeight.W_600)
    balance_value = ft.Text(size=24, color=INK, weight=ft.FontWeight.W_600)
    entry_message = ft.Text(size=12, color=ORANGE)
    budget_message = ft.Text(size=12, color=ORANGE)
    budget_status = ft.Text(size=14, color=MUTED)
    budget_progress = ft.ProgressBar(value=0, color=GREEN, bgcolor=GREEN_LIGHT, bar_height=8)
    category_list = ft.Column(spacing=12)
    transaction_list = ft.Column(spacing=0)
    transaction_count = ft.Text(size=12, color=MUTED)
    filter_buttons = {}

    type_dropdown = ft.Dropdown(
        label="種別",
        value="expense",
        options=[
            ft.DropdownOption(key="expense", text="支出"),
            ft.DropdownOption(key="income", text="収入"),
        ],
        border_radius=5,
        border_color=LINE,
        focused_border_color=GREEN,
        on_select=lambda event: update_categories(),
    )
    category_dropdown = ft.Dropdown(
        label="カテゴリ",
        value=EXPENSE_CATEGORIES[0],
        options=[ft.DropdownOption(key=value, text=value) for value in EXPENSE_CATEGORIES],
        border_radius=5,
        border_color=LINE,
        focused_border_color=GREEN,
    )
    amount_input = ft.TextField(
        label="金額",
        hint_text="例: 1200",
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=5,
        border_color=LINE,
        focused_border_color=GREEN,
    )
    date_input = ft.TextField(
        label="日付",
        value=date.today().isoformat(),
        hint_text="YYYY-MM-DD",
        border_radius=5,
        border_color=LINE,
        focused_border_color=GREEN,
    )
    note_input = ft.TextField(
        label="内容",
        hint_text="例: スーパーで買い物",
        border_radius=5,
        border_color=LINE,
        focused_border_color=GREEN,
    )
    budget_input = ft.TextField(
        label="月の支出上限",
        hint_text="例: 80000",
        value=str(budgets.get(shown_month.strftime("%Y-%m"), "")),
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=5,
        border_color=LINE,
        focused_border_color=GREEN,
    )

    def update_categories():
        choices = INCOME_CATEGORIES if type_dropdown.value == "income" else EXPENSE_CATEGORIES
        category_dropdown.options = [ft.DropdownOption(key=value, text=value) for value in choices]
        if category_dropdown.value not in choices:
            category_dropdown.value = choices[0]
        page.update()

    def set_filter(value):
        nonlocal current_filter
        current_filter = value
        render()

    def add_transaction(event):
        entry_message.color = ORANGE
        entry_message.value = ""
        try:
            transaction_date = date.fromisoformat(date_input.value.strip())
            amount = int(amount_input.value.replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except (AttributeError, ValueError):
            entry_message.value = "日付は YYYY-MM-DD、金額は1円以上で入力してください。"
            page.update()
            return

        transaction_month = transaction_date.strftime("%Y-%m")
        monthly_budget = budgets.get(transaction_month)
        if type_dropdown.value == "expense" and monthly_budget is not None:
            spent = sum(
                item["amount"]
                for item in transactions
                if item["type"] == "expense" and item["date"].startswith(transaction_month)
            )
            remaining = monthly_budget - spent
            if amount > remaining:
                entry_message.value = f"上限を超えるため登録できません。今月の残りは {format_yen(max(0, remaining))} です。"
                page.update()
                return

        note = (note_input.value or "").strip()
        transactions.append(
            {
                "id": str(uuid4()),
                "date": transaction_date.isoformat(),
                "type": type_dropdown.value,
                "category": category_dropdown.value,
                "amount": amount,
                "note": note,
            }
        )
        try:
            save_transactions(transactions)
        except OSError:
            transactions.pop()
            entry_message.value = "保存できませんでした。書き込み権限をご確認ください。"
            page.update()
            return

        amount_input.value = ""
        note_input.value = ""
        entry_message.color = GREEN
        entry_message.value = "記録しました。"
        render()

    def save_monthly_budget(event):
        month_key = shown_month.strftime("%Y-%m")
        previous_budget = budgets.get(month_key)
        raw_value = (budget_input.value or "").replace(",", "").strip()
        if raw_value:
            try:
                new_budget = int(raw_value)
                if new_budget <= 0:
                    raise ValueError
            except ValueError:
                budget_message.value = "上限は1円以上の整数で入力してください。"
                page.update()
                return
            budgets[month_key] = new_budget
        else:
            budgets.pop(month_key, None)

        try:
            save_budgets(budgets)
        except OSError:
            if previous_budget is None:
                budgets.pop(month_key, None)
            else:
                budgets[month_key] = previous_budget
            budget_message.value = "上限を保存できませんでした。"
            page.update()
            return

        budget_message.color = GREEN
        budget_message.value = "上限を保存しました。" if raw_value else "上限を解除しました。"
        render()

    def delete_transaction(transaction_id):
        removed = [item for item in transactions if item["id"] == transaction_id]
        transactions[:] = [item for item in transactions if item["id"] != transaction_id]
        try:
            save_transactions(transactions)
        except OSError:
            transactions.extend(removed)
            entry_message.color = ORANGE
            entry_message.value = "削除を保存できませんでした。"
        render()

    def change_month(delta):
        nonlocal shown_month
        shown_month = shift_month(shown_month, delta)
        budget_input.value = str(budgets.get(shown_month.strftime("%Y-%m"), ""))
        budget_message.value = ""
        render()

    def render():
        month_key = shown_month.strftime("%Y-%m")
        monthly_transactions = [item for item in transactions if item["date"].startswith(month_key)]
        monthly_income = sum(item["amount"] for item in monthly_transactions if item["type"] == "income")
        monthly_expense = sum(item["amount"] for item in monthly_transactions if item["type"] == "expense")
        monthly_budget = budgets.get(month_key)
        month_label.value = shown_month.strftime("%Y年 %m月")
        income_value.value = format_yen(monthly_income)
        expense_value.value = format_yen(monthly_expense)
        balance_value.value = format_yen(monthly_income - monthly_expense)
        balance_value.color = GREEN if monthly_income >= monthly_expense else ORANGE
        if monthly_budget is None:
            budget_status.value = "上限未設定"
            budget_status.color = MUTED
            budget_progress.value = 0
            budget_progress.color = GREEN
        else:
            remaining = monthly_budget - monthly_expense
            budget_status.value = (
                f"残り {format_yen(remaining)} / {format_yen(monthly_budget)}"
                if remaining >= 0
                else f"上限を {format_yen(abs(remaining))} 超過 / {format_yen(monthly_budget)}"
            )
            budget_status.color = GREEN if remaining > 0 else ORANGE
            budget_progress.value = min(monthly_expense / monthly_budget, 1)
            budget_progress.color = GREEN if remaining > 0 else ORANGE

        category_totals = {}
        for item in monthly_transactions:
            if item["type"] == "expense":
                category_totals[item["category"]] = category_totals.get(item["category"], 0) + item["amount"]
        categories = sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True)
        category_list.controls = []
        if categories:
            for category, amount in categories[:6]:
                share = amount / monthly_expense if monthly_expense else 0
                category_list.controls.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(category, size=13, color=INK),
                                    ft.Text(f"{format_yen(amount)}  ·  {share:.0%}", size=12, color=MUTED),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.ProgressBar(value=share, color=GREEN, bgcolor=GREEN_LIGHT, bar_height=5),
                        ],
                        spacing=6,
                    )
                )
        else:
            category_list.controls = [ft.Text("この月の支出はまだありません。", size=13, color=MUTED)]

        for key, button in filter_buttons.items():
            selected = key == current_filter
            button.style = ft.ButtonStyle(
                color=GREEN if selected else MUTED,
                bgcolor=GREEN_LIGHT if selected else "transparent",
                shape=ft.RoundedRectangleBorder(radius=4),
            )

        visible_transactions = [
            item
            for item in monthly_transactions
            if current_filter == "all" or item["type"] == current_filter
        ]
        visible_transactions.sort(key=lambda item: (item["date"], item["id"]), reverse=True)
        transaction_count.value = f"{len(visible_transactions)} 件"
        transaction_list.controls = []
        for item in visible_transactions:
            is_income = item["type"] == "income"
            title = item["note"] or item["category"]
            transaction_list.controls.extend(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.SOUTH_WEST if is_income else ft.Icons.NORTH_EAST,
                                    color=GREEN if is_income else ORANGE,
                                    size=17,
                                ),
                                width=34,
                                height=34,
                                bgcolor=GREEN_LIGHT if is_income else ORANGE_LIGHT,
                                border_radius=17,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                [
                                    ft.Text(title, size=14, color=INK, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(f"{item['date'][5:]}  ·  {item['category']}", size=11, color=MUTED),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Text(
                                f"{'+' if is_income else '−'}{format_yen(item['amount'])}",
                                size=14,
                                color=GREEN if is_income else INK,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=MUTED,
                                tooltip="この記録を削除",
                                on_click=lambda event, item_id=item["id"]: delete_transaction(item_id),
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, thickness=1, color=LINE),
                ]
            )
        if not visible_transactions:
            transaction_list.controls = [
                ft.Container(
                    content=ft.Text("この月の記録はありません。", size=13, color=MUTED),
                    padding=ft.Padding.symmetric(vertical=28),
                    alignment=ft.Alignment.CENTER,
                )
            ]
        page.update()

    def summary_tile(title, value_control, accent):
        return ft.Container(
            content=ft.Column(
                [ft.Text(title, size=12, color=accent), value_control],
                spacing=10,
            ),
            padding=18,
            bgcolor=SURFACE,
            border=ft.Border.all(1, LINE),
            border_radius=6,
        )

    def section(title, content, trailing=None):
        header_items = [ft.Text(title, size=16, color=INK, weight=ft.FontWeight.W_600)]
        if trailing is not None:
            header_items.append(trailing)
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(header_items, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    content,
                ],
                spacing=16,
            ),
            padding=20,
            bgcolor=SURFACE,
            border=ft.Border.all(1, LINE),
            border_radius=6,
        )

    filter_buttons.update(
        {
            key: ft.TextButton(label, on_click=lambda event, value=key: set_filter(value))
            for key, label in (("all", "すべて"), ("expense", "支出"), ("income", "収入"))
        }
    )

    form_fields = ft.ResponsiveRow(
        controls=[
            ft.Container(content=type_dropdown, col={"xs": 12, "sm": 6, "md": 2}),
            ft.Container(content=category_dropdown, col={"xs": 12, "sm": 6, "md": 2}),
            ft.Container(content=amount_input, col={"xs": 12, "sm": 6, "md": 2}),
            ft.Container(content=date_input, col={"xs": 12, "sm": 6, "md": 2}),
            ft.Container(content=note_input, col={"xs": 12, "sm": 8, "md": 3}),
            ft.Container(
                content=ft.Button(
                    "記録する",
                    icon=ft.Icons.ADD,
                    bgcolor=GREEN,
                    color="white",
                    height=48,
                    on_click=add_transaction,
                ),
                col={"xs": 12, "sm": 4, "md": 1},
                alignment=ft.Alignment.BOTTOM_RIGHT,
            ),
        ],
        spacing=10,
        run_spacing=8,
    )

    app_content = ft.Column(
        [
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, color="white", size=18),
                                width=36,
                                height=36,
                                bgcolor=GREEN,
                                border_radius=18,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                [
                                    ft.Text("K A K E I B O", size=10, color=GREEN, weight=ft.FontWeight.BOLD),
                                    ft.Text("家計の記録", size=16, color=INK, weight=ft.FontWeight.W_600),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Text(date.today().strftime("%Y年%m月%d日"), size=12, color=MUTED),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("お金の流れを、ひと目で。", size=28, color=INK, weight=ft.FontWeight.W_600),
                            ft.Text("毎日の収支を記録して、月ごとに振り返り。", size=13, color=MUTED),
                        ],
                        spacing=5,
                        expand=True,
                    ),
                    ft.Row(
                        [
                            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip="前の月", on_click=lambda event: change_month(-1)),
                            month_label,
                            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip="次の月", on_click=lambda event: change_month(1)),
                        ],
                        spacing=0,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(content=summary_tile("収入", income_value, GREEN), col={"xs": 12, "sm": 4}),
                    ft.Container(content=summary_tile("支出", expense_value, ORANGE), col={"xs": 12, "sm": 4}),
                    ft.Container(content=summary_tile("収支", balance_value, INK), col={"xs": 12, "sm": 4}),
                ],
                spacing=12,
                run_spacing=12,
            ),
            section(
                "収支を記録",
                ft.Column([form_fields, entry_message], spacing=4),
            ),
            section(
                "今月使える額",
                ft.Column(
                    [
                        ft.Row(
                            [
                                budget_input,
                                ft.Button(
                                    "上限を保存",
                                    icon=ft.Icons.SAVINGS_OUTLINED,
                                    bgcolor=GREEN,
                                    color="white",
                                    height=48,
                                    on_click=save_monthly_budget,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        budget_status,
                        budget_progress,
                        budget_message,
                    ],
                    spacing=8,
                ),
            ),
            section("カテゴリ別の支出", category_list),
            section(
                "今月の記録",
                transaction_list,
                trailing=ft.Row(
                    [ft.Row(list(filter_buttons.values()), spacing=0), transaction_count],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        ],
        width=1060,
        spacing=22,
    )

    app_container = ft.Container(content=app_content, width=1060, padding=ft.Padding.only(top=12, bottom=32))

    def resize_page(event):
        viewport_width = page.width or 1108
        page.padding = 12 if viewport_width < 600 else 24
        app_content.width = min(1060, max(280, viewport_width - page.padding * 2))
        app_container.width = app_content.width
        page.update()

    page.on_resize = resize_page
    page.add(app_container)
    render()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER)
