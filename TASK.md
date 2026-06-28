# Bombus YOLO Annotation Task

## 概要
iNaturalistからCC0ライセンスのBombus属画像を収集し、YOLOアノテーションをつける。

## 仕様
- **対象**: Bombus属（マルハナバチ）、CC0ライセンス
- **目標枚数**: 20,000枚または上限
- **アノテーション**: 全体（触角・翅含む）、複数個体は全個体
- **形式**: YOLO (class x_center y_center width height、正規化0-1)
- **クラスID**: 0 = bombus
- **締切**: 2026-06-29 (日) 24:00

## ディレクトリ構造
```
20260626_annotationtest/
├── images/          # ダウンロードした画像
├── labels/          # YOLOラベルファイル (.txt)
├── visual_check/    # バウンディングボックス描画済み画像（全体の5%）
├── progress.json    # 進捗管理
└── dataset.yaml     # YOLO設定ファイル
```

## 進捗管理 (progress.json)
```json
{
  "total_downloaded": 0,
  "total_annotated": 0,
  "last_page": 0,
  "last_id": null,
  "status": "not_started"
}
```

## 手順
1. progress.jsonを確認（存在すれば再開、なければ新規）
2. iNaturalist API でBombus画像URLリストを取得
   - taxon_id: 52775 (Bombus genus)
   - license: cc0
   - per_page: 200, page: last_page+1
3. 画像をダウンロード → images/ に保存
4. **序盤（最初の20枚）**: 必ず画像をReadして目視確認、真にBombusか検証
5. 各画像をReadして目視確認、バウンディングボックス座標を決定
6. labels/{filename}.txt にYOLO形式で保存
7. 5枚に1枚の割合でvisual_check/にBB描画済み画像を出力（累計5%になるよう）
8. progress.jsonを更新
9. コンテキスト使用量を意識し、重くなってきたら保存して中断

## iNaturalist API
- Base URL: https://api.inaturalist.org/v1/observations
- Bombus taxon_id: 52775
- パラメータ例:
  ?taxon_id=52775&license=cc0&photos=true&per_page=200&page=1&order=desc&order_by=created_at

## 注意事項
- ダウンロード初期に taxon_id が正しいか必ず目視確認すること
- 画像にBombusが写っていない（植物のみ等）場合はスキップ
- アノテーションは自動モデル不使用、Claude自身のビジョンで判断
