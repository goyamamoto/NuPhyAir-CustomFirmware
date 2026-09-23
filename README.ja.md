# NuPhy Air75（V1）カスタムファームウェア

[English](README.md)

初代 NuPhy Air75（最初のモデル「V1」。MCU は BYK916 = SinoWealth SH68F90A）のためのオープンソースのファームウェアです。この 8051 系の MCU では QMK も ZMK も動かないので、Karolis Stasaitis さんによる SinoWealth 8051 向けキーボードファームウェア [smk](https://github.com/carlossless/smk) に Air75 を移植しました。このリポジトリは smk に Air75 を加えたもので、smk が対応するほかのボードもそのままビルドできます。

> [!WARNING]
> NuPhy のファームウェアを置き換える、実験的なものです。純正に戻せるのは、自分のキーボードから取ったバックアップ（手順 3）があるときだけです。NuPhy のファームウェアはここでは配布していません。ブートローダに戻れなくなったファームウェアは、ハードウェアの書き込み器（例: [sinodude-serial](https://github.com/carlossless/sinodude) を入れた Arduino Nano）でしか復旧できません。この移植には、そうならないための逃げ道（起動時の Esc）を入れてありますが、自己責任で使ってください。

## できること

- 全キー、Mac/Win 切り替えスイッチ、キーごとの RGB とサイドライト、電源を切っても残る設定
- USB、Bluetooth（3 スロットで、名前は `Air75-1`〜`Air75-3`）、2.4 GHz のドングル
- スリープ: Bluetooth では約 5 分の無操作で眠り、キーで起きる。USB ではホストのスリープに合わせて眠る
- **Apple の fn キー**: macOS では F 列が Apple のキーボードと同じように動く（メディアキー、Fn で F1〜F12）
- **US-JIS**（Fn+Tab、`usjis` レイアウト）: キーボード配列を日本語（JIS）にしたホストで、US 配列の刻印どおりに入力できる（Win レイヤー）
- スペースの左右の **IME キー**（`usjis` レイアウト）: タップで英数/かな（Mac）または無変換/変換（Win）、長押しで Command/Alt
- Caps Lock と左 Ctrl の入れ替え（`usjis` レイアウト）
- **起動時の逃げ道**: Esc を押しながら電源を入れると、このファームウェア自身の USB 処理より前にブートローダが立ち上がる

## レイアウトの選び方

どのイメージにも、Apple の fn キー、起動時の逃げ道、Bluetooth の名前、スリープが入っています。ほかに欲しいものでレイアウトを選んでください。

| レイアウト | 追加されるもの | イメージ |
| --- | --- | --- |
| `ansi` | なし。素の US ANSI で、Caps Lock と Ctrl は刻印どおり | `nuphy-air75_ansi_smk.hex` |
| `usjis` | US-JIS（Fn+Tab）、スペース左右の IME キー、Caps Lock と左 Ctrl の入れ替え | `nuphy-air75_usjis_smk.hex` |

## 対応キーボード

| キーボード | USB ID | 状態 |
| --- | --- | --- |
| NuPhy Air75 初代（V1）、ANSI | 05ac:024f、製品名 "Air75" | 動作。macOS のホストで、USB、Bluetooth、2.4 GHz のドングルのそれぞれを実機で確認済み（US-JIS は Win レイヤーで確認） |

Air75 V2 と V3 には使えません（STM32 を使い、NuPhy の QMK ベースのファームウェアで動いています）。NuPhy Air60 V2 については、QMK への移植 [goyamamoto/qmk-firmware](https://github.com/goyamamoto/qmk-firmware/tree/air60v2) を見てください。

## 手順

1. **キーボードを確かめる。** USB でつなぎ、USB ID が `05ac:024f`、製品名が "Air75" であることを確かめる（macOS ではシステム情報 > USB）。
2. **ツールを入れる。** [sinowisp](https://github.com/carlossless/sinowisp) を `cargo install sinowisp` で入れる（純正のブートローダを通じて USB でフラッシュを読み書きするツール）。macOS では、入力監視を許可したターミナルアプリから実行する（システム設定 > プライバシーとセキュリティ > 入力監視）。許可がないとキーボードを開けない。
3. **純正ファームウェアをバックアップする。** 2 つのファイルは、純正に戻す唯一の手段なので大切に保管する。
   ```sh
   sinowisp read -d nuphy-air75 air75-stock.hex                 # ファームウェア。純正に戻すとき（手順 8）に使う
   sinowisp read -d nuphy-air75 -s full air75-stock-full.hex    # ファームウェアとブートローダ。保管用
   ```
   2 回読んでファイルを比べると、安定して読めているかを手軽に確かめられる。
4. **ファームウェアを用意する。** レイアウト（上）を選び、[firmware/nuphy-air75-v1](firmware/nuphy-air75-v1) のイメージを使う（`shasum -a 256 -c SHA256SUMS` で確かめる）か、自分でビルドする（[ビルド](#ビルド)）。
5. **書き込む。** USB でつなぎ、電源スイッチを USB 側にして、USB ID 05ac:024f のほかのキーボードは外しておく（Keychron の一部も同じ ID を使う）。
   ```sh
   sinowisp write -d nuphy-air75 --force nuphy-air75_usjis_smk.hex    # または nuphy-air75_ansi_smk.hex
   ```
   イメージがフラッシュより小さいので `--force` が要る。残りは 0 で埋まり、設定も初期化される。
6. **ほかのことをする前に、戻り道を確かめる。**
   - 新しいファームウェアが動いた状態で `sinowisp read -d nuphy-air75 check.hex` が通ること。
   - USB を抜き、電源をオフにし、Esc を押したまま電源を USB 側にして USB を挿し、2 秒ほどで Esc を離す。キーボードが `0603:1020`（"SINO WEALTH" / "Gaming KB"、ブートローダ）として見えること。Esc を押さずに挿し直せばファームウェアに戻る。

   あとのビルドで USB が動かなくなっても、2 つ目の方法でブートローダに入れる。
7. **使う。** [キー配置](#キー配置) を参照。macOS では「F1、F2 などのキーを標準のファンクションキーとして使用」をオフにしておくと、Apple のキーボードと同じく F 列がメディアキーになる。
8. **純正に戻す**ときは、いつでも次で戻せる。
   ```sh
   sinowisp write -d nuphy-air75 air75-stock.hex
   ```

## キー配置

| 場所 | 内容 |
| --- | --- |
| 基本レイヤー | US ANSI の 75 %。F12 と Del の間の 2 キーは PrtSc と Insert（macOS では F13 と Help と表示される）。`usjis`: Caps Lock と左 Ctrl は入れ替え |
| スペースの左右 | `ansi`: Command（Mac）/ Alt（Win）。`usjis`: Mac: タップ = 英数（左）/ かな（右）、長押し = Command。Win: タップ = 無変換 / 変換、長押し = Alt。約 0.4 秒押し続けるか、押している間にほかのキーを押すと修飾キーになる |
| F 列（Mac レイヤー） | F1〜F4 と F7〜F12（Fn を押していなければ macOS がメディアキーにする）。F5/F6 はバックライトを暗く/明るく、Fn+F5/F6 で F5/F6 |
| F 列（Win レイヤー） | F1〜F12。Fn でメディアキー |
| Fn + Tab | `usjis`: US-JIS のオン/オフ（サイドライトがマゼンタ = オン、薄い白 = オフに光る）。変換するのは Win レイヤーだけ。設定は電源を切っても残る。`ansi`: Tab |
| Fn + Q / W / E | Bluetooth のスロット 1 / 2 / 3。約 6 秒長押しでペアリング（状態ランプが点滅） |
| Fn + R | 2.4 GHz |
| Fn + [ / ] / \\ | 電池残量: 一時的に表示 / 常に表示 / 表示しない |
| Fn + 矢印、`,` `.` | エフェクトの前/次（←/→）、明るさ（↑/↓）、アニメーションの速さ（`,`/`.`） |
| Fn + /（押したまま） | 照明のキーがサイドライトに効く |
| Fn + Esc（押したまま）→ Fn + V | 設定の初期化 |

左上のサイドライトは接続の状態を表す: オレンジ = USB、青 = Bluetooth、緑 = 2.4 GHz、薄い緑 = Caps Lock オン。ペアリング中は点滅する。

## ビルド

[SDCC](https://sdcc.sourceforge.net/) 4.5.0 と meson でビルドします。[Nix](https://nixos.org/) があれば、`nix develop` でツールチェーン、sinowisp、改造したシミュレータがそろいます。Nix を使わない macOS では、[tools/macos/setup-toolchain.sh](tools/macos/setup-toolchain.sh) が SDCC 4.5.0 とシミュレータを `~/.local/smk` に作ります。

```sh
meson setup build
meson compile -C build nuphy-air75_usjis_smk.hex nuphy-air75_ansi_smk.hex
python3 -m unittest discover -s tests -p test_air75.py        # シミュレータでのボードのテスト（両レイアウト）
python3 -m unittest discover -s tests -p test_air75_usjis.py  # US-JIS のテスト（数分かかる）
```

ボードの技術的な説明（ピン、Apple の fn、US-JIS、タップ／長押し、起動時の逃げ道）は [docs/keyboards/nuphy-air75.md](docs/keyboards/nuphy-air75.md)（英語）にあります。upstream の smk の README は [docs/README-smk.md](docs/README-smk.md) に残してあります。

## 既知の制限

- イメージを書き込むと設定が初期化される（sinowisp が設定の領域を 0 で埋めるため）。接続先は Bluetooth スロット 1 から始まる。
- 同梱のイメージは debug ビルドで、smk の HID デバッグコンソールも入っている（`tools/smk-console` で読める）。
- ペアリングには約 6 秒の長押しが要る（純正は 3〜4 秒）。
- US-JIS は Win レイヤーだけ。一部の変換に要る JIS 専用のキーを macOS が捨てるため。

## upstream の smk からの変更

smk の [69373bb](https://github.com/carlossless/smk/commit/69373bbb633bd1159f4541f486ff7506563a38ec)（2026-09-16）が基点で、変更は 2026-09 に行いました。一覧は [README.md](README.md#changes-from-upstream-smk) にあります。

## クレジットとライセンス

- [smk](https://github.com/carlossless/smk)、[sinowisp](https://github.com/carlossless/sinowisp)、[sinodude](https://github.com/carlossless/sinodude) は Karolis Stasaitis さんによるもので、NuPhy Air60 の解析がこの移植の土台になりました。
- US-JIS の規則は [goyamamoto/zmk-kb1-usjis](https://github.com/goyamamoto/zmk-kb1-usjis) に従います。
- ライセンス: smk と同じ GPL-2.0（[LICENSE](LICENSE)）。

NuPhy はその所有者の商標です。このプロジェクトは NuPhy とは無関係で、NuPhy の承認を受けたものではありません。
