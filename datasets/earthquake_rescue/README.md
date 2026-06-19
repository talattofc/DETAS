# DETAS Earthquake Rescue Dataset

Bu klasor DETAS icin afet sonrasi kurtarma odakli YOLO detection dataset standardidir.

## Siniflar

0. `person` - Enkaz veya acik alandaki insan
1. `rubble` - Enkaz/yikilmis beton, metal, moloz
2. `blocked_road` - Enkaz veya hasar nedeniyle kapanmis yol
3. `collapsed_building` - Yikilmis veya agir hasarli yapi
4. `damaged_vehicle` - Hasarli/arazide kalmis arac
5. `fire_smoke` - Yangin, duman veya isi riski bolgesi
6. `rescue_worker` - Kurtarma ekibi personeli
7. `safe_passage` - Gecilebilir guvenli koridor/gecis

## Ham veri ekleme

Goruntuleri ve YOLO `.txt` etiketlerini once su klasorlere koy:

```text
datasets/earthquake_rescue/raw/images/
datasets/earthquake_rescue/raw/labels/
```

Her goruntu icin ayni dosya adina sahip bir label beklenir:

```text
raw/images/frame_001.jpg
raw/labels/frame_001.txt
```

YOLO label satiri formati:

```text
class_id x_center y_center width height
```

Koordinatlar 0-1 araliginda normalize edilmis olmalidir.

## Split olusturma

```bash
python tools/prepare_earthquake_dataset.py
```

Varsayilan split:

- train: 70%
- valid: 20%
- test: 10%

Script `data.yaml` dosyasini gunceller ve `images/*`, `labels/*` klasorlerini olusturur.

## Not

`supervision` kuruluysa script dataset'i `sv.DetectionDataset.from_yolo(...)` ile yukleyerek ek dogrulama yapar. Kurulu degilse standart dosya kontrolleriyle devam eder.
