# JetPilot の追加 Docker レイヤー

対象は `Dockerfile.additional_setting` と `Dockerfile.silky_evcam`。
NVIDIA の基底イメージ・リポジトリ構成はそのまま使用する。

## アーキテクチャの選択

CLI は x86_64 を `PLATFORM=amd64`、aarch64 を `PLATFORM=arm64` に変換する。
両 Dockerfile は `runtime-${PLATFORM}` を最終ステージに選び、BuildKit が必要な枝だけをビルドする。
`uname -m` では判定せず、`dpkg --print-architecture` と `PLATFORM` の一致を検証する。
直接ビルドする場合は `--platform` と `--build-arg PLATFORM` を一致させる。
`BASE_IMAGE` には、対象アーキテクチャの必要な Isaac ROS 基底レイヤーを指定する。
ビルドコンテキストはこの `docker/` ディレクトリ。

| 追加する機能 | amd64 | arm64 / Jetson |
| --- | --- | --- |
| ROS、SLAM、位置推定、TensorRT 推論、センサー収録、Foxglove、RTP | あり | あり |
| OpenEB / SilkyEvCam（レイヤー選択時） | あり | あり |
| 地図作成用 `isaac-mapping-ros` / `visual-mapping` | あり | 追加しない |
| `/opt/env` 学習・軌道計画環境 | あり | 追加しない |
| E2V PyTorch・`/opt/event_camera_env` | SilkyEvCam レイヤーで追加 | 追加しない |
| `/opt/multi_sensor_calibration_env` オフライン校正 | あり | 追加しない |
| Cartographer RViz、rqt-tf-tree、Terminator | あり | 追加しない |
| jtop と ROS Jetson stats | 追加しない | あり |

これは追加レイヤーの方針。基底イメージや APT の必須依存に含まれる GUI・Python パッケージまで削除するものではない。
Jetson 上での地図作成・オフライン校正が必要になった場合は、対応パッケージを共通ステージへ戻すか、専用レイヤーを追加する。

## 再ビルドを軽くする配置

- ROS と共通ツールを先に置き、起動スクリプトと CycloneDDS 設定は最後に置く。
- Hokuyo の Debian パッケージ作成は `urg-builder` で行い、完成イメージには `.deb` とその実行時依存だけを導入する。作成用ツールやソースは引き継がない。
- 学習環境は独立した `training-amd64` で作り、amd64 の完成イメージへコピーする。校正・GUI の変更で学習環境を作り直さない。
- `requirements-training-gpu-amd64.txt` は重い GPU スタック、`requirements-training-amd64.txt` は周辺ツール。周辺ツールの変更で GPU スタックの導入レイヤーを無効化しない。
- OpenEB のコンパイルを E2V PyTorch の導入より前に置く。取得・ビルド・ソース削除を同じ RUN 内で行い、ビルド成果物を完成イメージに残さない。E2V のチェックポイントは amd64 の既存パスに保存する。
- APT と uv のダウンロードキャッシュは BuildKit の cache mount に保存する。Ubuntu の `docker-clean` を無効化し、APT のキャッシュ削除を防ぐ。キャッシュは完成イメージには入らない。

初回の構成変更では再ビルドが必要。その後は同じ BuildKit ビルダーを使い、通常の更新で `--no-cache` やキャッシュ削除を行わない。
キャッシュはビルドホストのディスクを使用する。別ホストへの移行時は同じダウンロードキャッシュが自動で引き継がれるわけではない。
ベースイメージ更新では、依存する後続レイヤーも再ビルドになる。

## Python は uv を標準にする

uv 0.12.0 の公式イメージから `/uv` 実行ファイルだけを使う。uvx や別の Python 配布物は追加しない。
SilkyEvCam から同じ uv が継承されている場合、additional_setting では二重コピーを避ける。
`UV_PYTHON_DOWNLOADS=never` と `--python /usr/bin/python3` で ROS と同じ Python を使い、`UV_LINK_MODE=copy` でキャッシュに依存しない環境を作る。
最終イメージの増分は主に uv 実行ファイル分であり、GB 単位の Python/CUDA 環境を uv 自体が追加する構成ではない。正確な容量差は対象機でのビルド後に測定する。

```bash
# 学習用（amd64）
source /opt/env/bin/activate
uv pip install <package>

# オフライン校正用（amd64）
uv pip install --python /opt/multi_sensor_calibration_env/bin/python <package>
```

ROS 側は NumPy 1.26.4、学習環境は NumPy 2.4.6 に分離する。
既存の pip / rosdep / colcon は削除せず、ROS 環境全体への `uv sync` は行わない。
変更対象以外の NVIDIA・センサー Dockerfile の pip 処理は今回の移行対象外。

既存の依存バージョンは維持している。requirements は親プロジェクトの uv.lock から生成し、間接依存も固定する。
`TRAJECTORY_HELPERS_REF` の既定値も従来の `master` を維持する。厳密に再現する運用ではコミット SHA を指定し、対象 Linux/GPU 環境で解決・検証したロックへ移行する。

参考: [uv 公式 Docker ガイド](https://docs.astral.sh/uv/guides/integration/docker/)

## 親プロジェクトの lock との連携

Python 依存の正本は JetPilot の `python_ws/environments/{training,calibration}/pyproject.toml` と `uv.lock`。
**uv.lock は親プロジェクトで Git 管理する。** このディレクトリの requirements は
親側の `scripts/python_env.sh export training` / `export calibration` で生成し、CLI リポジトリでもコミットする。
Docker は間接依存まで固定された生成ファイルとハッシュを検証する。requirements は手編集しない。

GUI は `INSTALL_GUI=auto|true|false` で CPU とは独立に指定できる。auto は amd64 のみ、true は Jetson にも追加する。
