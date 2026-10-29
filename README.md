# 家計簿

Python と Flet で作った、ブラウザで使えるシンプルな家計簿アプリです。収入・支出の記録、月ごとの収支確認、カテゴリ別支出の集計、記録の絞り込みと削除に対応しています。データはユーザーのホームディレクトリの `.kakeibo_transactions.json` に保存されます。

## 起動方法

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

起動するとブラウザでアプリが開きます。