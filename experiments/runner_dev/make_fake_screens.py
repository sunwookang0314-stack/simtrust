"""가짜 화면 캡처(PNG)를 만든다. 이미지 입력 확인(scripts/check_image_input.py)과 실행기 이미지 모드 개발용.

실제 서비스 화면이 아니다. snapshots/fake/{app,web}/snapshot.json의 화면 설명(text)과 같은 글자를 그리고,
설명에는 없는 글자(공고 제목, 주최, 마감일 등)도 같이 그려서 이미지에서만 얻는 정보가 있는지 볼 수 있게 했다.

실행 (리포 루트, 한글 글꼴 경로가 필요하다):
    python experiments/runner_dev/make_fake_screens.py --font /mnt/c/Windows/Fonts/malgun.ttf
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "images" / "fake"

# 화면 설명(text)에도 있는 글자. 이미지 모드와 텍스트 모드를 같은 기준으로 비교할 때 쓴다
SHARED = {
    "S1": ["공모전", "대외활동", "채용", "마감이 가까운 공고", "마이"],
    "S2": ["기획", "디자인", "IT", "마케팅", "마감순", "최신순"],
    "S3": ["저장한 공고", "알림 설정", "내 정보", "마감 3일 전 알림"],
}
# 이미지에만 있는 글자
IMAGE_ONLY = {
    "S1": ["공고 검색", "청년 아이디어 공모전", "대학생 마케팅 서포터즈", "AI 서비스 기획 대회", "D-3"],
    "S2": ["모바일 앱 디자인 공모전", "한빛재단", "11월 12일", "공공데이터 활용 대회"],
    "S3": ["마이페이지", "꺼짐"],
}

BLUE, GREY, LIGHT, DARK = (37, 99, 235), (156, 163, 175), (243, 244, 246), (17, 24, 39)


def fonts(path):
    return {size: ImageFont.truetype(path, size) for size in (18, 22, 26, 32)}


def heart(d, x, y, color=GREY):
    d.ellipse((x, y, x + 12, y + 12), fill=color)
    d.ellipse((x + 10, y, x + 22, y + 12), fill=color)
    d.polygon([(x + 1, y + 8), (x + 21, y + 8), (x + 11, y + 22)], fill=color)


def screen_s1(f, w, h):
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 24, w - 24, 80), 14, fill=LIGHT)
    d.text((44, 38), "공고 검색", font=f[22], fill=GREY)
    for i, tab in enumerate(["공모전", "대외활동", "채용"]):
        x = 24 + i * 150
        d.text((x + 10, 104), tab, font=f[26], fill=BLUE if i == 0 else DARK)
    d.line((24, 148, w - 24, 148), fill=LIGHT, width=2)
    d.text((24, 168), "마감이 가까운 공고", font=f[26], fill=DARK)
    cards = [("청년 아이디어 공모전", "D-3"), ("대학생 마케팅 서포터즈", "D-5"), ("AI 서비스 기획 대회", "D-6"),
             ("환경 사진 공모전", "D-8"), ("IT 인턴 채용", "D-9")]
    for i, (title, dday) in enumerate(cards):
        y = 220 + i * 110
        d.rounded_rectangle((24, y, w - 24, y + 92), 14, outline=LIGHT, width=3)
        d.text((44, y + 18), title, font=f[22], fill=DARK)
        d.text((44, y + 54), dday, font=f[18], fill=BLUE)
        heart(d, w - 70, y + 34)
    d.rounded_rectangle((w - 120, h - 90, w - 24, h - 34), 28, fill=BLUE)
    d.text((w - 92, h - 76), "마이", font=f[22], fill="white")
    return im


def screen_s2(f, w, h):
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    d.text((24, 28), "공모전", font=f[32], fill=DARK)
    x = 24
    for chip in ["기획", "디자인", "IT", "마케팅"]:
        tw = d.textlength(chip, font=f[22])
        d.rounded_rectangle((x, 90, x + tw + 32, 132), 20, outline=GREY, width=2)
        d.text((x + 16, 97), chip, font=f[22], fill=DARK)
        x += tw + 44
    d.text((24, 152), "마감순", font=f[22], fill=BLUE)
    d.text((110, 152), "최신순", font=f[22], fill=GREY)
    cards = [("청년 아이디어 공모전", "주최 한빛재단", "마감 11월 7일"),
             ("모바일 앱 디자인 공모전", "주최 디자인진흥원", "마감 11월 12일"),
             ("공공데이터 활용 대회", "주최 데이터진흥원", "마감 11월 20일")]
    for i, (title, host, due) in enumerate(cards):
        y = 200 + i * 150
        d.rounded_rectangle((24, y, w - 24, y + 130), 14, outline=LIGHT, width=3)
        d.text((44, y + 18), title, font=f[22], fill=DARK)
        d.text((44, y + 56), host, font=f[18], fill=GREY)
        d.text((44, y + 86), due, font=f[18], fill=BLUE)
        heart(d, w - 70, y + 52)
    return im


def screen_s3(f, w, h):
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    d.text((24, 28), "마이페이지", font=f[32], fill=DARK)
    for i, menu in enumerate(["저장한 공고", "알림 설정", "내 정보"]):
        y = 100 + i * 80
        d.text((24, y + 18), menu, font=f[26], fill=DARK)
        d.text((w - 50, y + 18), ">", font=f[26], fill=GREY)
        d.line((24, y + 72, w - 24, y + 72), fill=LIGHT, width=2)
    d.rounded_rectangle((24, 360, w - 24, 450), 14, fill=LIGHT)
    d.text((44, 388), "마감 3일 전 알림", font=f[22], fill=DARK)
    d.rounded_rectangle((w - 140, 388, w - 84, 420), 16, fill=GREY)
    d.ellipse((w - 138, 390, w - 110, 418), fill="white")
    d.text((w - 74, 390), "꺼짐", font=f[18], fill=GREY)
    return im


def main():
    ap = argparse.ArgumentParser(description="가짜 화면 캡처 만들기")
    ap.add_argument("--font", required=True, help="한글 TTF 글꼴 경로")
    args = ap.parse_args()
    f = fonts(args.font)
    # 앱은 세로(휴대폰), 웹은 가로(PC 브라우저) 비율로 그린다
    sizes = {"app": (540, 960), "web": (960, 900)}
    for platform, (w, h) in sizes.items():
        out = OUT / platform
        out.mkdir(parents=True, exist_ok=True)
        for sid, draw in (("S1", screen_s1), ("S2", screen_s2), ("S3", screen_s3)):
            draw(f, w, h).save(out / f"{sid}.png", optimize=True)
    labels = {"shared": SHARED, "image_only": IMAGE_ONLY}
    (OUT / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"만들었다: {OUT}")


if __name__ == "__main__":
    main()
