DETAS V3 - HAILO-8L DEPLOYMENT PAKETI

KULLANILACAK HEF
---------------
detas_v3_7class_yolov8s_hailo8l_raw_heads.hef

HEDEF DONANIM
-------------
Raspberry Pi 5 + AI HAT 13 TOPS (Hailo-8L)

SINIFLAR
--------
0 rubble
1 blocked_road
2 collapsed_building
3 damaged_vehicle
4 fire_smoke
5 open_road
6 flood_area

GIRDI
-----
- 640x640
- RGB
- uint8
- Ultralytics letterbox
- Padding: 114
- Normalizasyon HEF icindedir.

CIKTI
-----
HEF, 3 farkli olcekte 6 ham detection-head cikisi verir:
- 3 bbox DFL cikisi: 64 kanal
- 3 sinif cikisi: 7 kanal

POSTPROCESS
-----------
Raspberry Pi tarafinda:
1. DFL bbox decode
2. sigmoid class score
3. confidence filtresi
4. class-aware NMS
5. letterbox koordinatlarini asli goruntuye geri cevirme

NOT
---
Bu modelde Hailo ici NMS bulunmaz.
Mevcut detection_service.py dosyasindaki HailoBackend
sinifi bu paket icin guncellenecektir.
