"""본실행용 스냅샷 4묶음(서비스 2 x 플랫폼 2)을 만든다.

캡처 원본: private/snapshots/{service}/{platform}/ (정리용 이름)
결과:     {out}/snapshots/{service}/{platform}/snapshot.json
          {out}/images/{service}/{platform}/{무작위 16진수 8자리}.png
          {out}/capture_map.csv (무작위 이름과 원래 이름 대응표)

AI한테는 인턴 세트만 준다 (11/3 강선우, 폼 B v2 초안 228행, 프로토콜 v0.1 4번).
세트 구성은 private/snapshots/목록_app_20261102.md "검색어" 항목과
목록_web_20261101.md "AI한테 주는 세트" 표를 그대로 옮겼다.
캡처 파일 이름 규칙은 프로토콜 v0.1 3번 (무작위 이름, 대응표는 private/).

사용: python experiments/runner_dev/make_snapshots.py --out private/main
이미 있는 묶음은 덮어쓰지 않고 멈춘다 (무작위 이름이 바뀌면 캐시와 기록이 어긋난다).
"""
import argparse
import csv
import json
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "private" / "snapshots"

# 파일 이름 앞 번호. 순서는 목록 표 순서(기능 순서)
INTERN_SET = {
    ("linkareer", "app"): ["01-2", "02-2", "03-2", "04", "05", "06-2", "07-2"],
    ("campuspick", "app"): ["01-2", "02-2", "03-2", "04", "05", "06", "07-2"],
    ("linkareer", "web"): ["01-2", "02-2", "03-2", "04", "05", "06-3", "06-2", "07-2"],
    ("campuspick", "web"): ["01-2", "02-2", "03-2", "04", "05", "06", "07-2"],
}
SERVICE_NAME = {"linkareer": "링커리어", "campuspick": "캠퍼스픽"}  # 두 플랫폼 캡처 모두 "캠퍼스픽"으로 뜬다
VERSION = {
    ("linkareer", "app"): "linkareer-app-3.3.2-20261102-intern",
    ("campuspick", "app"): "campuspick-app-4.0.24-20261102-intern",
    ("linkareer", "web"): "linkareer-web-20261101_02-intern",
    ("campuspick", "web"): "campuspick-web-20261101_02-intern",
}


def find_file(folder: Path, prefix: str) -> Path:
    hits = [p for p in folder.glob("*.png") if p.name.split("_")[0] == prefix]
    if len(hits) != 1:
        sys.exit(f"{folder}: 앞 번호 {prefix} 파일이 {len(hits)}개다 (1개여야 함)")
    return hits[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="private/main")
    args = ap.parse_args()
    out = ROOT / args.out
    if not str(out.resolve()).startswith(str((ROOT / "private").resolve())):
        sys.exit("--out 은 private/ 아래여야 한다 (캡처는 공개 리포에 올리지 않는다)")

    rows, used = [], set()
    for (svc, plat), prefixes in INTERN_SET.items():
        snap_dir = out / "snapshots" / svc / plat
        img_dir = out / "images" / svc / plat
        if (snap_dir / "snapshot.json").exists() or (img_dir.exists() and any(img_dir.iterdir())):
            sys.exit(f"{svc}/{plat} 묶음이 이미 있다. 지우고 다시 만들려면 직접 지운다")
        img_dir.mkdir(parents=True, exist_ok=True)
        snap_dir.mkdir(parents=True, exist_ok=True)
        screens = []
        for i, pre in enumerate(prefixes, 1):
            src = find_file(SRC / svc / plat, pre)
            name = secrets.token_hex(4)
            while name in used:
                name = secrets.token_hex(4)
            used.add(name)
            shutil.copy2(src, img_dir / f"{name}.png")
            screens.append({"screen_id": f"S{i}", "image": f"{name}.png"})
            rows.append([svc, plat, f"S{i}", f"{name}.png", src.name])
        snap = {
            "_설명": "본실행용 스냅샷. 로컬 전용(private). 인턴 세트(11/3 결정). 원래 이름 대응표는 capture_map.csv",
            "service": svc,
            "service_name": SERVICE_NAME[svc],
            "platform": plat,
            "snapshot_version": VERSION[(svc, plat)],
            "missing_features": [],
            "screens": screens,
        }
        (snap_dir / "snapshot.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{svc}/{plat}: {len(screens)}장")

    with open(out / "capture_map.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["service", "platform", "screen_id", "random_name", "original"])
        w.writerows(rows)
    print(f"대응표: {out / 'capture_map.csv'}")


if __name__ == "__main__":
    main()
